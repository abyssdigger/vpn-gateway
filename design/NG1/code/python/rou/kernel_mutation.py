from __future__ import annotations

from dataclasses import dataclass

from .environment import EnvironmentSnapshot
from .kernel_allocation import (
    MAX_OWNED_RULE_PRIORITY,
    RT_TABLE_COMPAT,
    RT_TABLE_DEFAULT,
    RT_TABLE_LOCAL,
    RT_TABLE_MAIN,
    RT_TABLE_UNSPEC,
)
from .kernel_state import (
    BLACKHOLE_PROTOCOL,
    ROUTE_PROTOCOL,
    KernelDesiredState,
    KernelRouteSpec,
    KernelRuleSpec,
)


class KernelMutationPlanError(RuntimeError):
    pass


@dataclass(frozen=True)
class KernelMutation:
    argv: tuple[str, ...]
    phase: str


@dataclass(frozen=True)
class KernelMutationPlan:
    commands: tuple[KernelMutation, ...]


_RESERVED_TABLES = frozenset(
    {
        RT_TABLE_UNSPEC,
        RT_TABLE_COMPAT,
        RT_TABLE_DEFAULT,
        RT_TABLE_MAIN,
        RT_TABLE_LOCAL,
    }
)


def _route_argv(route: KernelRouteSpec) -> tuple[str, ...]:
    dst = route.destination.with_prefixlen
    base = ["ip", "route", "add", "table", str(route.table)]

    if route.route_type == "blackhole":
        if route.ifname is not None or route.nexthops:
            raise KernelMutationPlanError("blackhole route must not have interface nexthops")
        return tuple(
            base
            + [
                "blackhole",
                dst,
                "proto",
                str(route.protocol),
                "metric",
                str(route.metric),
            ]
        )

    if route.route_type != "unicast":
        raise KernelMutationPlanError(
            f"unsupported route type {route.route_type!r}"
        )

    if route.ifname is not None and route.nexthops:
        raise KernelMutationPlanError(
            "unicast route cannot have both direct interface and multipath nexthops"
        )

    if route.ifname is not None:
        return tuple(
            base
            + [
                dst,
                "dev",
                route.ifname,
                "proto",
                str(route.protocol),
                "metric",
                str(route.metric),
            ]
        )

    if route.nexthops:
        out = base + [
            dst,
            "proto",
            str(route.protocol),
            "metric",
            str(route.metric),
        ]
        for nexthop in route.nexthops:
            out.extend(
                [
                    "nexthop",
                    "dev",
                    nexthop.ifname,
                    "weight",
                    str(nexthop.weight),
                ]
            )
        return tuple(out)

    raise KernelMutationPlanError("unicast route has no output interface")


def _rule_argv(rule: KernelRuleSpec) -> tuple[str, ...]:
    out = [
        "ip",
        "rule",
        "add",
        "priority",
        str(rule.priority),
        "iif",
        rule.iif,
    ]

    if rule.destination is not None:
        out.extend(["to", rule.destination.with_prefixlen])

    if rule.action == "to_tbl":
        if rule.table is None:
            raise KernelMutationPlanError("to_tbl rule requires table")
        out.extend(["lookup", str(rule.table)])
        return tuple(out)

    if rule.table is not None:
        raise KernelMutationPlanError(
            f"terminal rule action {rule.action!r} must not carry table"
        )
    if rule.action not in {"unreachable", "blackhole", "prohibit"}:
        raise KernelMutationPlanError(
            f"unsupported terminal RPDB action {rule.action!r}"
        )
    out.extend(["type", rule.action])
    return tuple(out)



def compile_lifecycle_route_rebuild_plan(
    desired: KernelDesiredState,
    observed: EnvironmentSnapshot,
) -> KernelMutationPlan:
    """Compile an incremental Profile-table rebuild for proven binding lifecycle.

    RPDB rules and IPv4 forwarding are intentionally untouched. The caller may use this
    only after proving that owned RPDB state is exactly desired and that observed routes
    are limited to the previous/new verified generations.

    During a table flush/rebuild the still-installed Profile dispatch rule cannot fall
    through to main because the subsequent terminal host0 RPDB action remains in place.
    The transient effect is therefore Profile-local fail-closed, not fail-open.
    """

    commands: list[KernelMutation] = []
    desired_tables = set(desired.owned_tables)

    observed_tables = {
        route.table
        for route in observed.routes
        if route.table in desired_tables
    }
    for table in sorted(observed_tables):
        commands.append(
            KernelMutation(
                ("ip", "route", "flush", "table", str(table)),
                "lifecycle-route-clear",
            )
        )

    for route in desired.routes:
        commands.append(
            KernelMutation(
                _route_argv(route),
                "lifecycle-route-install",
            )
        )

    return KernelMutationPlan(tuple(commands))


def compile_kernel_mutation_plan(
    desired: KernelDesiredState,
    observed: EnvironmentSnapshot,
) -> KernelMutationPlan:
    """Compile a full fail-closed routing/RPDB rebuild.

    The plan always starts by disabling IPv4 forwarding. It never enables forwarding;
    that is reserved for the caller after a fresh post-apply observation verifies the
    complete desired state.

    The ROU namespace owns every non-default RPDB priority before main (1..32765), so all
    currently observed rules in that range are removed before desired rules are rebuilt.
    """

    commands: list[KernelMutation] = [
        KernelMutation(
            ("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"),
            "barrier-close",
        )
    ]

    desired_tables = set(desired.owned_tables)
    stale_tagged_tables: set[int] = set()

    for route in observed.routes:
        if route.protocol in {ROUTE_PROTOCOL, BLACKHOLE_PROTOCOL}:
            if route.table in _RESERVED_TABLES:
                raise KernelMutationPlanError(
                    f"ROU-tagged route unexpectedly exists in reserved table {route.table}"
                )
            if route.table not in desired_tables:
                stale_tagged_tables.add(route.table)

    observed_tables = {route.table for route in observed.routes}
    for table in sorted(
        (desired_tables & observed_tables) | stale_tagged_tables
    ):
        commands.append(
            KernelMutation(
                ("ip", "route", "flush", "table", str(table)),
                "route-clear",
            )
        )

    owned_rules = sorted(
        (
            rule
            for rule in observed.rules
            if 1 <= rule.priority <= MAX_OWNED_RULE_PRIORITY
        ),
        key=lambda rule: rule.priority,
    )
    for rule in owned_rules:
        commands.append(
            KernelMutation(
                ("ip", "rule", "del", "priority", str(rule.priority)),
                "rule-clear",
            )
        )

    for route in desired.routes:
        commands.append(KernelMutation(_route_argv(route), "route-install"))

    for rule in desired.rules:
        commands.append(KernelMutation(_rule_argv(rule), "rule-install"))

    return KernelMutationPlan(tuple(commands))
