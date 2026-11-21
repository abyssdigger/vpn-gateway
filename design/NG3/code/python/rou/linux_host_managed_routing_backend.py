"""Strict Linux Driver for ordinary-host managed-destination routing."""

from __future__ import annotations

from dataclasses import dataclass
import json
from ipaddress import IPv4Address, IPv4Network, ip_network

from .iproute_priority_backend import CommandRunner
from .linux_host_managed_routing import (
    HostManagedBypassRuleSpec,
    HostManagedDispatchRuleSpec,
    HostManagedPreserveMainRuleSpec,
    HostManagedRouteSpec,
    HostManagedRoutingLinuxAllocation,
    HostManagedRoutingLinuxDesired,
    HostManagedScopeExitRuleSpec,
)


class HostManagedRoutingConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HostManagedRoutingObservation:
    routes: tuple[HostManagedRouteSpec, ...]
    rule_priorities: tuple[int, ...]
    missing_routes: tuple[HostManagedRouteSpec, ...]
    stale_routes: tuple[HostManagedRouteSpec, ...]
    missing_rule_priorities: tuple[int, ...]
    stale_rule_priorities: tuple[int, ...]
    conflicts: tuple[str, ...]

    @property
    def exact(self) -> bool:
        return not (
            self.missing_routes
            or self.stale_routes
            or self.missing_rule_priorities
            or self.stale_rule_priorities
            or self.conflicts
        )


@dataclass(slots=True)
class LinuxHostManagedRoutingDriver:
    runner: CommandRunner
    allocation: HostManagedRoutingLinuxAllocation
    network_namespace: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allocation, HostManagedRoutingLinuxAllocation):
            raise ValueError("allocation must be HostManagedRoutingLinuxAllocation")
        if self.network_namespace is not None and (
            not isinstance(self.network_namespace, str) or not self.network_namespace
        ):
            raise ValueError("network_namespace must be non-empty text or None")

    def observe(
        self,
        desired: HostManagedRoutingLinuxDesired,
    ) -> HostManagedRoutingObservation:
        if not isinstance(desired, HostManagedRoutingLinuxDesired):
            raise ValueError("desired must be HostManagedRoutingLinuxDesired")
        route_rows = _json_array(
            self.runner.run(self._cmd("ip", "-j", "-4", "route", "show", "table", "all")),
            "host managed route snapshot",
        )
        rule_rows = _json_array(
            self.runner.run(self._cmd("ip", "-j", "-4", "rule", "show")),
            "host managed rule snapshot",
        )
        observed_routes, route_conflicts = _observe_routes(
            route_rows, self.allocation
        )
        owned_rules, matching_rules, rule_conflicts = _observe_rules(
            rule_rows, self.allocation, desired
        )

        desired_routes = set(desired.routes)
        observed_route_set = set(observed_routes)
        desired_priorities = _desired_rule_priorities(desired)
        owned_priorities = set(owned_rules)
        matching_priorities = set(matching_rules)
        return HostManagedRoutingObservation(
            routes=tuple(sorted(observed_routes, key=_route_key)),
            rule_priorities=tuple(sorted(owned_priorities)),
            missing_routes=tuple(
                sorted(desired_routes - observed_route_set, key=_route_key)
            ),
            stale_routes=tuple(
                sorted(observed_route_set - desired_routes, key=_route_key)
            ),
            missing_rule_priorities=tuple(
                sorted(desired_priorities - matching_priorities)
            ),
            stale_rule_priorities=tuple(
                sorted(owned_priorities - matching_priorities)
            ),
            conflicts=tuple(route_conflicts + rule_conflicts),
        )

    def add_route(self, route: HostManagedRouteSpec) -> None:
        destination = (
            "default"
            if route.destination.prefixlen == 0
            else route.destination.with_prefixlen
        )
        args = [
            "ip", "-4", "route", "add", "table", str(route.table),
            destination,
        ]
        if route.gateway is not None:
            args.extend(("via", str(route.gateway)))
        args.extend(("dev", route.interface))
        if route.onlink:
            args.append("onlink")
        args.extend(("proto", str(route.protocol)))
        self.runner.run(self._cmd(*args))

    def delete_route(self, route: HostManagedRouteSpec) -> None:
        destination = (
            "default"
            if route.destination.prefixlen == 0
            else route.destination.with_prefixlen
        )
        args = [
            "ip", "-4", "route", "del", "table", str(route.table),
            destination,
        ]
        if route.gateway is not None:
            args.extend(("via", str(route.gateway)))
        args.extend(("dev", route.interface, "proto", str(route.protocol)))
        self.runner.run(self._cmd(*args))

    def add_bypass_rule(self, rule: HostManagedBypassRuleSpec) -> None:
        args = [
            "ip", "-4", "rule", "add", "priority", str(rule.priority),
            "protocol", str(rule.protocol), "iif", rule.interface,
        ]
        if rule.goto_priority is None:
            args.extend(("lookup", "main"))
        else:
            args.extend(("goto", str(rule.goto_priority)))
        self.runner.run(self._cmd(*args))

    def add_preserve_main_rule(
        self,
        rule: HostManagedPreserveMainRuleSpec,
    ) -> None:
        args = [
            "ip", "-4", "rule", "add", "priority", str(rule.priority),
            "protocol", str(rule.protocol),
        ]
        if rule.invert_incoming_interface:
            args.append("not")
        if rule.incoming_interface is not None:
            args.extend(("iif", rule.incoming_interface))
        args.extend(
            (
                "lookup", "main",
                "suppress_prefixlength", str(rule.suppress_prefixlength),
            )
        )
        self.runner.run(self._cmd(*args))

    def add_dispatch_rule(self, rule: HostManagedDispatchRuleSpec) -> None:
        args = [
            "ip", "-4", "rule", "add", "priority", str(rule.priority),
            "protocol", str(rule.protocol),
        ]
        if rule.invert_incoming_interface:
            args.append("not")
        if rule.incoming_interface is not None:
            args.extend(("iif", rule.incoming_interface))
        args.extend(("lookup", str(rule.table)))
        self.runner.run(self._cmd(*args))

    def add_scope_exit_rule(self, rule: HostManagedScopeExitRuleSpec) -> None:
        self.runner.run(
            self._cmd(
                "ip", "-4", "rule", "add", "priority", str(rule.priority),
                "protocol", str(rule.protocol), "type", "nop",
            )
        )

    def delete_rule_priority(self, priority: int) -> None:
        self.runner.run(
            self._cmd(
                "ip", "-4", "rule", "del", "priority", str(priority),
                "protocol", str(self.allocation.rule_protocol),
            )
        )

    def _cmd(self, *args: str) -> tuple[str, ...]:
        if self.network_namespace is None:
            return tuple(args)
        return ("ip", "netns", "exec", self.network_namespace, *args)


def converge_host_managed_routing_once(
    backend: LinuxHostManagedRoutingDriver,
    desired: HostManagedRoutingLinuxDesired,
) -> HostManagedRoutingObservation:
    if not isinstance(backend, LinuxHostManagedRoutingDriver):
        raise ValueError("backend must be LinuxHostManagedRoutingDriver")

    initial = backend.observe(desired)
    if initial.conflicts:
        raise HostManagedRoutingConflict("; ".join(initial.conflicts))
    if initial.exact:
        return initial

    # Disable stale capture before changing the table.
    for priority in sorted(initial.stale_rule_priorities, reverse=True):
        backend.delete_rule_priority(priority)

    after_rules = backend.observe(desired)
    if after_rules.conflicts:
        raise HostManagedRoutingConflict("; ".join(after_rules.conflicts))
    for route in after_rules.stale_routes:
        backend.delete_route(route)

    after_cleanup = backend.observe(desired)
    if after_cleanup.conflicts:
        raise HostManagedRoutingConflict("; ".join(after_cleanup.conflicts))
    for route in after_cleanup.missing_routes:
        backend.add_route(route)

    observed = backend.observe(desired)
    if observed.conflicts:
        raise HostManagedRoutingConflict("; ".join(observed.conflicts))
    if (
        desired.scope_exit is not None
        and desired.scope_exit.priority in observed.missing_rule_priorities
    ):
        backend.add_scope_exit_rule(desired.scope_exit)

    observed = backend.observe(desired)
    if observed.conflicts:
        raise HostManagedRoutingConflict("; ".join(observed.conflicts))
    if (
        desired.bypass is not None
        and desired.bypass.priority in observed.missing_rule_priorities
    ):
        backend.add_bypass_rule(desired.bypass)

    for preserve in desired.preserve_main_rules:
        observed = backend.observe(desired)
        if observed.conflicts:
            raise HostManagedRoutingConflict("; ".join(observed.conflicts))
        if preserve.priority in observed.missing_rule_priorities:
            backend.add_preserve_main_rule(preserve)

    for dispatch in desired.dispatch_rules:
        observed = backend.observe(desired)
        if observed.conflicts:
            raise HostManagedRoutingConflict("; ".join(observed.conflicts))
        if dispatch.priority in observed.missing_rule_priorities:
            backend.add_dispatch_rule(dispatch)

    final = backend.observe(desired)
    if final.conflicts:
        raise HostManagedRoutingConflict("; ".join(final.conflicts))
    if not final.exact:
        raise RuntimeError("host managed-routing fresh postcondition is not exact")
    return final


def cleanup_host_managed_routing_once(
    backend: LinuxHostManagedRoutingDriver,
    desired: HostManagedRoutingLinuxDesired,
    *,
    tolerate_foreign_replacements: bool = False,
) -> HostManagedRoutingObservation:
    if not isinstance(backend, LinuxHostManagedRoutingDriver):
        raise ValueError("backend must be LinuxHostManagedRoutingDriver")

    current = backend.observe(desired)
    if current.conflicts and not tolerate_foreign_replacements:
        raise HostManagedRoutingConflict("; ".join(current.conflicts))

    # Capture goes away before routes; remove selector dispatches before bypass/exit.
    for dispatch in reversed(desired.dispatch_rules):
        if dispatch.priority in current.rule_priorities:
            backend.delete_rule_priority(dispatch.priority)
            current = backend.observe(desired)
    for preserve in reversed(desired.preserve_main_rules):
        if preserve.priority in current.rule_priorities:
            backend.delete_rule_priority(preserve.priority)
            current = backend.observe(desired)
    current = backend.observe(desired)
    if (
        desired.bypass is not None
        and desired.bypass.priority in current.rule_priorities
    ):
        backend.delete_rule_priority(desired.bypass.priority)
    current = backend.observe(desired)
    if (
        desired.scope_exit is not None
        and desired.scope_exit.priority in current.rule_priorities
    ):
        backend.delete_rule_priority(desired.scope_exit.priority)

    # Also remove any stale rules from the superseded paired-RPDB owner.
    current = backend.observe(desired)
    for priority in sorted(current.stale_rule_priorities, reverse=True):
        backend.delete_rule_priority(priority)

    current = backend.observe(desired)
    for route in tuple(current.routes):
        backend.delete_route(route)

    empty = HostManagedRoutingLinuxDesired((), None, None)
    final = backend.observe(empty)
    if final.conflicts and not tolerate_foreign_replacements:
        raise HostManagedRoutingConflict("; ".join(final.conflicts))
    if final.routes or final.rule_priorities:
        raise RuntimeError("host managed-routing cleanup postcondition failed")
    return final


def _observe_routes(rows, allocation):
    observed = []
    conflicts = []
    for row in rows:
        if _decimal(row.get("table")) != allocation.table:
            continue
        if _decimal(row.get("protocol")) != allocation.route_protocol:
            conflicts.append("foreign route exists in reserved managed-routing table")
            continue
        if row.get("type", "unicast") != "unicast":
            conflicts.append("unsupported owner route type in managed-routing table")
            continue
        destination = _route_network(row.get("dst", "default"))
        interface = row.get("dev")
        if destination is None or not isinstance(interface, str):
            conflicts.append("unrepresentable owner route in managed-routing table")
            continue
        gateway_raw = row.get("gateway")
        if gateway_raw is None:
            gateway = None
        else:
            try:
                gateway = IPv4Address(gateway_raw)
            except (TypeError, ValueError):
                conflicts.append("managed-routing route has invalid IPv4 gateway")
                continue
        flags = row.get("flags", ())
        if flags is None:
            flags = ()
        if not isinstance(flags, (list, tuple)):
            conflicts.append("managed-routing route flags are not representable")
            continue
        unsupported_flags = set(flags) - {"onlink"}
        if unsupported_flags:
            conflicts.append(
                "managed-routing route has unsupported flags: "
                + ",".join(sorted(unsupported_flags))
            )
            continue
        observed.append(
            HostManagedRouteSpec(
                destination=destination,
                interface=interface,
                table=allocation.table,
                protocol=allocation.route_protocol,
                gateway=gateway,
                onlink="onlink" in flags,
            )
        )
    return observed, conflicts


def _observe_rules(rows, allocation, desired):
    expected = _expected_rule_signatures(desired)
    reserved = {allocation.bypass_priority}
    if allocation.preserve_priority is not None:
        reserved.add(allocation.preserve_priority)
    reserved.update(
        range(
            allocation.owned_rule_priorities.first,
            allocation.owned_rule_priorities.stop,
        )
    )
    owned = []
    matching = []
    conflicts = []
    for row in rows:
        priority = _decimal(row.get("priority"))
        if priority not in reserved:
            continue
        protocol = _decimal(row.get("protocol"))
        expected_signature = expected.get(priority)
        if protocol == allocation.rule_protocol:
            owned.append(priority)
            if (
                expected_signature is not None
                and _rule_signature(row) == expected_signature
            ):
                matching.append(priority)
            continue
        if expected_signature is not None:
            conflicts.append(
                f"foreign rule occupies desired managed-routing priority {priority}"
            )
    return owned, matching, conflicts


def _expected_rule_signatures(desired):
    result = {}
    if desired.bypass is not None:
        result[desired.bypass.priority] = (
            ("bypass", desired.bypass.interface, "main")
            if desired.bypass.goto_priority is None
            else ("goto", desired.bypass.interface, desired.bypass.goto_priority)
        )
    for preserve in desired.preserve_main_rules:
        result[preserve.priority] = (
            "preserve_main",
            preserve.incoming_interface,
            preserve.invert_incoming_interface,
            "main",
            preserve.suppress_prefixlength,
        )
    for dispatch in desired.dispatch_rules:
        result[dispatch.priority] = (
            "dispatch",
            dispatch.incoming_interface,
            dispatch.invert_incoming_interface,
            str(dispatch.table),
        )
    if desired.scope_exit is not None:
        result[desired.scope_exit.priority] = ("nop",)
    return result


def _rule_signature(row):
    if "nop" in row:
        return ("nop",)
    if "goto" in row:
        return ("goto", row.get("iif"), _decimal(row.get("goto")))

    table = row.get("table")
    if table is None:
        table = row.get("lookup")
    numeric_table = _decimal(table)
    table_value = (
        "main"
        if table == "main" or numeric_table == 254
        else (str(table) if table is not None else None)
    )
    suppress = row.get("suppress_prefixlen")
    if suppress is None:
        suppress = row.get("suppress_prefixlength")
    if suppress is not None:
        return (
            "preserve_main",
            row.get("iif"),
            "not" in row,
            table_value,
            _decimal(suppress),
        )
    selectors = (
        "dst", "dstlen", "fwmark", "fwmask",
        "uidrange", "sport", "dport", "ipproto", "oif",
    )
    if any(key in row for key in selectors):
        return ("other", None, table_value)
    interface = row.get("iif")
    inverted = "not" in row
    if interface is not None and table_value == "main" and not inverted:
        return ("bypass", interface, table_value)
    return ("dispatch", interface, inverted, table_value)


def _desired_rule_priorities(desired):
    result = set()
    if desired.bypass is not None:
        result.add(desired.bypass.priority)
    result.update(item.priority for item in desired.preserve_main_rules)
    result.update(item.priority for item in desired.dispatch_rules)
    if desired.scope_exit is not None:
        result.add(desired.scope_exit.priority)
    return result

def _route_network(value):
    if value in (None, "default"):
        return IPv4Network("0.0.0.0/0")
    if not isinstance(value, str):
        return None
    try:
        parsed = ip_network(value, strict=True)
    except ValueError:
        return None
    return parsed if isinstance(parsed, IPv4Network) else None


def _route_key(route):
    return (-route.destination.prefixlen, int(route.destination.network_address))


def _decimal(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _json_array(raw, label):
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise RuntimeError(f"invalid {label} JSON") from None
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise RuntimeError(f"{label} must be an array of objects")
    return value


# Historical executable-evidence compatibility alias.
LinuxHostManagedRoutingBackend = LinuxHostManagedRoutingDriver
