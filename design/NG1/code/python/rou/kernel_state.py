from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .device_engine import DeviceBindingSnapshot
from .domain import ActiveConfig
from .environment import EnvironmentSnapshot, KernelRoute, KernelRule, RouteNexthop
from .kernel_allocation import KernelAllocation
from .metrics import BLACKHOLE_METRIC
from .route_intent import compile_profile_route_intents
from .traffic_state import TrafficProjection


ROUTE_PROTOCOL = 202
BLACKHOLE_PROTOCOL = 201
HOST_INTERFACE = "host0"


@dataclass(frozen=True)
class KernelRouteSpec:
    table: int
    destination: IPv4Network
    route_type: str
    protocol: int
    metric: int
    ifname: str | None = None
    nexthops: tuple[RouteNexthop, ...] = ()


@dataclass(frozen=True)
class KernelRuleSpec:
    priority: int
    iif: str
    destination: IPv4Network | None
    table: int | None
    action: str


@dataclass(frozen=True)
class KernelDesiredState:
    routes: tuple[KernelRouteSpec, ...]
    rules: tuple[KernelRuleSpec, ...]
    owned_tables: tuple[int, ...]


@dataclass(frozen=True)
class KernelVerification:
    ok: bool
    errors: tuple[str, ...]


def compile_kernel_desired_state(
    config: ActiveConfig,
    bindings: DeviceBindingSnapshot,
    metrics: TrafficProjection,
    allocation: KernelAllocation,
) -> KernelDesiredState:
    """Compile complete owned Profile route/RPDB desired state."""

    table_by_profile = allocation.table_by_profile
    route_intents = compile_profile_route_intents(config, bindings, metrics)
    routes: list[KernelRouteSpec] = []

    for profile_intent in route_intents:
        table = table_by_profile.get(profile_intent.profile_name)
        if table is None:
            raise ValueError(
                f"Profile {profile_intent.profile_name!r} has no routing-table allocation"
            )

        for item in profile_intent.normal_routes:
            routes.append(
                KernelRouteSpec(
                    table=table,
                    destination=item.destination,
                    route_type="unicast",
                    protocol=ROUTE_PROTOCOL,
                    metric=item.metric,
                    ifname=item.identity.ifname,
                )
            )

        for item in profile_intent.fallback_routes:
            if len(item.members) == 1:
                routes.append(
                    KernelRouteSpec(
                        table=table,
                        destination=item.destination,
                        route_type="unicast",
                        protocol=ROUTE_PROTOCOL,
                        metric=item.metric,
                        ifname=item.members[0].ifname,
                    )
                )
            elif len(item.members) > 1:
                routes.append(
                    KernelRouteSpec(
                        table=table,
                        destination=item.destination,
                        route_type="unicast",
                        protocol=ROUTE_PROTOCOL,
                        metric=item.metric,
                        nexthops=tuple(
                            RouteNexthop(member.ifname, 1)
                            for member in item.members
                        ),
                    )
                )

        routes.append(
            KernelRouteSpec(
                table=table,
                destination=IPv4Network("0.0.0.0/0"),
                route_type="blackhole",
                protocol=BLACKHOLE_PROTOCOL,
                metric=profile_intent.terminal_blackhole_metric,
            )
        )

    rules = [
        KernelRuleSpec(
            priority=item.priority,
            iif=HOST_INTERFACE,
            destination=item.destination,
            table=item.table_id,
            action="to_tbl",
        )
        for item in allocation.dispatch_rules
    ]
    rules.append(
        KernelRuleSpec(
            priority=allocation.terminal_host0_priority,
            iif=HOST_INTERFACE,
            destination=None,
            table=None,
            action="unreachable",
        )
    )

    routes.sort(
        key=lambda item: (
            item.table,
            -item.destination.prefixlen,
            int(item.destination.network_address),
            item.metric,
            item.route_type,
            item.ifname or "",
            tuple((n.ifname, n.weight) for n in item.nexthops),
        )
    )

    return KernelDesiredState(
        routes=tuple(routes),
        rules=tuple(rules),
        owned_tables=tuple(item.table_id for item in allocation.profile_tables),
    )


def _route_key(route: KernelRoute | KernelRouteSpec):
    return (
        route.table,
        route.destination,
        route.route_type,
        route.protocol,
        route.metric,
        route.ifname,
        tuple((item.ifname, item.weight) for item in route.nexthops),
    )


def _rule_key(rule: KernelRule | KernelRuleSpec):
    return (
        rule.priority,
        rule.iif,
        rule.destination,
        rule.table,
        rule.action,
    )


def verify_kernel_desired_state(
    desired: KernelDesiredState,
    observed: EnvironmentSnapshot,
) -> KernelVerification:
    """Verify complete owned routing state from a fresh EnvironmentSnapshot.

    Profile tables are exclusive ROU-owned tables: every observed route in one of them must
    be desired and every desired route must be present. RPDB priorities from 1 through the
    terminal host0 priority are likewise treated as the owned priority window.
    """

    errors: list[str] = []

    expected_routes = {_route_key(item) for item in desired.routes}
    observed_owned_routes = {
        _route_key(item)
        for item in observed.routes
        if item.table in desired.owned_tables
    }

    missing_routes = expected_routes - observed_owned_routes
    extra_routes = observed_owned_routes - expected_routes
    if missing_routes:
        errors.append(f"missing owned routes: {sorted(map(str, missing_routes))}")
    if extra_routes:
        errors.append(f"unexpected routes in owned tables: {sorted(map(str, extra_routes))}")

    expected_rules = {_rule_key(item) for item in desired.rules}
    max_priority = max((item.priority for item in desired.rules), default=0)
    observed_owned_rules = {
        _rule_key(item)
        for item in observed.rules
        if 1 <= item.priority <= max_priority
    }

    missing_rules = expected_rules - observed_owned_rules
    extra_rules = observed_owned_rules - expected_rules
    if missing_rules:
        errors.append(f"missing owned rules: {sorted(map(str, missing_rules))}")
    if extra_rules:
        errors.append(f"unexpected rules in owned priority window: {sorted(map(str, extra_rules))}")

    return KernelVerification(ok=not errors, errors=tuple(errors))
