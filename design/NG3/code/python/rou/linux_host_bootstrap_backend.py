"""Strict Linux owner/backend for selected paired-RPDB host bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
import json
from ipaddress import IPv4Network, ip_network

from .iproute_priority_backend import CommandRunner
from .linux_host_bootstrap import (
    HostBootstrapBypassRuleSpec,
    HostBootstrapDispatchRuleSpec,
    HostBootstrapLinuxAllocation,
    HostBootstrapLinuxDesired,
    HostBootstrapPreserveRuleSpec,
    HostBootstrapRouteSpec,
)


class HostBootstrapConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HostBootstrapObservation:
    routes: tuple[HostBootstrapRouteSpec, ...]
    rule_priorities: tuple[int, ...]
    missing_routes: tuple[HostBootstrapRouteSpec, ...]
    stale_routes: tuple[HostBootstrapRouteSpec, ...]
    missing_rule_priorities: tuple[int, ...]
    stale_rule_priorities: tuple[int, ...]
    conflicts: tuple[str, ...]

    @property
    def exact(self) -> bool:
        return (
            not self.missing_routes
            and not self.stale_routes
            and not self.missing_rule_priorities
            and not self.stale_rule_priorities
            and not self.conflicts
        )


@dataclass(slots=True)
class LinuxHostBootstrapBackend:
    runner: CommandRunner
    allocation: HostBootstrapLinuxAllocation
    network_namespace: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allocation, HostBootstrapLinuxAllocation):
            raise ValueError("allocation must be HostBootstrapLinuxAllocation")
        if self.network_namespace is not None and (
            not isinstance(self.network_namespace, str) or not self.network_namespace
        ):
            raise ValueError("network_namespace must be non-empty text or None")

    def observe(self, desired: HostBootstrapLinuxDesired) -> HostBootstrapObservation:
        if not isinstance(desired, HostBootstrapLinuxDesired):
            raise ValueError("desired must be HostBootstrapLinuxDesired")
        route_rows = _json_array(
            self.runner.run(self._cmd("ip","-j","-4","route","show","table","all")),
            "host bootstrap route snapshot",
        )
        rule_rows = _json_array(
            self.runner.run(self._cmd("ip","-j","-4","rule","show")),
            "host bootstrap rule snapshot",
        )
        observed_routes,route_conflicts=_observe_routes(
            route_rows,self.allocation,desired
        )
        owned_rules,matching_rules,rule_conflicts=_observe_rules(
            rule_rows,self.allocation,desired
        )

        desired_routes=set(desired.routes)
        observed_route_set=set(observed_routes)
        desired_rule_priorities=_desired_rule_priorities(desired)
        owned_rule_priorities=set(owned_rules)
        matching_rule_priorities=set(matching_rules)

        return HostBootstrapObservation(
            routes=tuple(sorted(observed_routes,key=_route_key)),
            rule_priorities=tuple(sorted(owned_rule_priorities)),
            missing_routes=tuple(sorted(desired_routes-observed_route_set,key=_route_key)),
            stale_routes=tuple(sorted(observed_route_set-desired_routes,key=_route_key)),
            missing_rule_priorities=tuple(sorted(desired_rule_priorities-matching_rule_priorities)),
            stale_rule_priorities=tuple(sorted(owned_rule_priorities-matching_rule_priorities)),
            conflicts=tuple(route_conflicts+rule_conflicts),
        )

    def add_route(self, route: HostBootstrapRouteSpec) -> None:
        destination="default" if route.destination.prefixlen==0 else route.destination.with_prefixlen
        self.runner.run(self._cmd(
            "ip","-4","route","add","table",str(route.table),destination,
            "via",str(route.via),"dev",route.interface,"proto",str(route.protocol),
        ))

    def delete_route(self, route: HostBootstrapRouteSpec) -> None:
        destination="default" if route.destination.prefixlen==0 else route.destination.with_prefixlen
        self.runner.run(self._cmd(
            "ip","-4","route","del","table",str(route.table),destination,
            "via",str(route.via),"dev",route.interface,"proto",str(route.protocol),
        ))

    def add_bypass_rule(self, rule: HostBootstrapBypassRuleSpec) -> None:
        self.runner.run(self._cmd(
            "ip","-4","rule","add","priority",str(rule.priority),
            "protocol",str(rule.protocol),"iif",rule.interface,"lookup","main",
        ))

    def add_preserve_rule(self, rule: HostBootstrapPreserveRuleSpec) -> None:
        self.runner.run(self._cmd(
            "ip","-4","rule","add","priority",str(rule.priority),
            "protocol",str(rule.protocol),"to",rule.destination.with_prefixlen,
            "lookup","main","suppress_prefixlength",str(rule.suppress_prefixlen),
        ))

    def add_dispatch_rule(self, rule: HostBootstrapDispatchRuleSpec) -> None:
        self.runner.run(self._cmd(
            "ip","-4","rule","add","priority",str(rule.priority),
            "protocol",str(rule.protocol),"to",rule.destination.with_prefixlen,
            "lookup",str(rule.table),
        ))

    def delete_rule_priority(self, priority: int) -> None:
        self.runner.run(self._cmd(
            "ip","-4","rule","del","priority",str(priority),
            "protocol",str(self.allocation.rule_protocol),
        ))

    def _cmd(self,*args: str) -> tuple[str,...]:
        if self.network_namespace is None:
            return tuple(args)
        return ("ip","netns","exec",self.network_namespace,*args)


def converge_host_bootstrap_once(
    backend: LinuxHostBootstrapBackend,
    desired: HostBootstrapLinuxDesired,
) -> HostBootstrapObservation:
    """Converge under an already-contained managed domain.

    Caller must keep managed forwarding closed until this function confirms exact state.
    """
    if not isinstance(backend,LinuxHostBootstrapBackend):
        raise ValueError("backend must be LinuxHostBootstrapBackend")
    initial=backend.observe(desired)
    if initial.conflicts:
        raise HostBootstrapConflict("; ".join(initial.conflicts))
    if initial.exact:
        return initial

    # Remove active stale owner rules first. With the managed domain externally contained,
    # this can only stop stale capture; it cannot create an unintended VPN path.
    for priority in sorted(initial.stale_rule_priorities,reverse=True):
        backend.delete_rule_priority(priority)

    # Stale owner routes live only in the dedicated table. No bootstrap rule should refer to
    # them after stale rules are removed.
    for route in initial.stale_routes:
        backend.delete_route(route)

    # Prepare every table route before exposing any new dispatch rule.
    after_cleanup=backend.observe(desired)
    if after_cleanup.conflicts:
        raise HostBootstrapConflict("; ".join(after_cleanup.conflicts))
    for route in after_cleanup.missing_routes:
        backend.add_route(route)

    # Bypass must exist before any destination dispatch can capture stack-origin packets.
    observed=backend.observe(desired)
    if observed.conflicts:
        raise HostBootstrapConflict("; ".join(observed.conflicts))
    if desired.bypass is not None and desired.bypass.priority in observed.missing_rule_priorities:
        backend.add_bypass_rule(desired.bypass)

    # For each destination, expose main-preservation before dispatch.
    observed=backend.observe(desired)
    for pair in desired.pairs:
        if pair.preserve.priority in observed.missing_rule_priorities:
            backend.add_preserve_rule(pair.preserve)
        observed=backend.observe(desired)
        if observed.conflicts:
            raise HostBootstrapConflict("; ".join(observed.conflicts))
        if pair.dispatch.priority in observed.missing_rule_priorities:
            backend.add_dispatch_rule(pair.dispatch)
        observed=backend.observe(desired)
        if observed.conflicts:
            raise HostBootstrapConflict("; ".join(observed.conflicts))

    final=backend.observe(desired)
    if final.conflicts:
        raise HostBootstrapConflict("; ".join(final.conflicts))
    if not final.exact:
        raise RuntimeError("host bootstrap fresh postcondition does not match desired state")
    return final


def cleanup_host_bootstrap_once(
    backend: LinuxHostBootstrapBackend,
    desired: HostBootstrapLinuxDesired,
) -> HostBootstrapObservation:
    """Remove dispatch first, then preservation/bypass, then dedicated-table routes."""
    if not isinstance(backend,LinuxHostBootstrapBackend):
        raise ValueError("backend must be LinuxHostBootstrapBackend")
    current=backend.observe(desired)
    if current.conflicts:
        raise HostBootstrapConflict("; ".join(current.conflicts))

    desired_priorities=_desired_rule_priorities(desired)
    # Dispatch first, longest-prefix pairs in reverse administrative order is irrelevant once
    # each dispatch disappears before its preserve rule.
    for pair in reversed(desired.pairs):
        if pair.dispatch.priority in current.rule_priorities:
            backend.delete_rule_priority(pair.dispatch.priority)
        current=backend.observe(desired)
        if pair.preserve.priority in current.rule_priorities:
            backend.delete_rule_priority(pair.preserve.priority)
        current=backend.observe(desired)

    if desired.bypass is not None and desired.bypass.priority in current.rule_priorities:
        backend.delete_rule_priority(desired.bypass.priority)

    current=backend.observe(desired)
    # Delete only owner routes still exactly matching desired/stale owner representation.
    for route in tuple(current.routes):
        backend.delete_route(route)

    empty=HostBootstrapLinuxDesired(routes=(),bypass=None,pairs=())
    final=backend.observe(empty)
    if final.conflicts:
        raise HostBootstrapConflict("; ".join(final.conflicts))
    if final.routes or final.rule_priorities:
        raise RuntimeError("host bootstrap owner cleanup postcondition failed")
    return final


def _observe_routes(rows,allocation,desired):
    desired_by_key={(r.destination,r.table):r for r in desired.routes}
    observed=[]
    conflicts=[]
    for row in rows:
        if _decimal(row.get("table"))!=allocation.table:
            continue
        proto=_decimal(row.get("protocol"))
        if proto!=allocation.route_protocol:
            conflicts.append("foreign route exists in reserved host bootstrap table")
            continue
        if row.get("type","unicast")!="unicast":
            conflicts.append("unsupported owner route type in host bootstrap table")
            continue
        destination=_route_network(row.get("dst","default"))
        gateway=row.get("gateway"); dev=row.get("dev")
        if destination is None or not isinstance(gateway,str) or not isinstance(dev,str):
            conflicts.append("unrepresentable owner route in host bootstrap table")
            continue
        try:
            via=IPv4Address(gateway)
        except ValueError:
            conflicts.append("non-IPv4 gateway in host bootstrap table")
            continue
        observed.append(HostBootstrapRouteSpec(
            destination=destination,via=via,interface=dev,
            table=allocation.table,protocol=allocation.route_protocol,
        ))
    return observed,conflicts


def _observe_rules(rows,allocation,desired):
    reserved_priorities={allocation.bypass_priority}
    reserved_priorities.update(range(allocation.pair_priorities.first,allocation.pair_priorities.stop))
    expected=_expected_rule_signatures(desired)
    owned=[]
    matching=[]
    conflicts=[]
    for row in rows:
        priority=_decimal(row.get("priority"))
        if priority not in reserved_priorities:
            continue
        if _decimal(row.get("protocol"))!=allocation.rule_protocol:
            conflicts.append(f"foreign rule occupies reserved host bootstrap priority {priority}")
            continue
        owned.append(priority)
        expected_signature=expected.get(priority)
        if expected_signature is not None and _rule_signature(row)==expected_signature:
            matching.append(priority)
    return owned,matching,conflicts


def _expected_rule_signatures(desired):
    result={}
    if desired.bypass is not None:
        result[desired.bypass.priority]=(
            "bypass",desired.bypass.interface,"main",None,None
        )
    for pair in desired.pairs:
        result[pair.preserve.priority]=(
            "preserve",None,"main",pair.preserve.destination,pair.preserve.suppress_prefixlen
        )
        result[pair.dispatch.priority]=(
            "dispatch",None,str(pair.dispatch.table),pair.dispatch.destination,None
        )
    return result


def _rule_signature(row):
    priority=_decimal(row.get("priority"))
    iif=row.get("iif")
    table=row.get("table")
    table_text=str(table) if table not in (254,"main") else "main"
    destination=_route_network(row.get("dst","0.0.0.0/0"))
    suppress=_decimal(row.get("suppress_prefixlen"))
    if isinstance(iif,str):
        return ("bypass",iif,table_text,None,None)
    if suppress is not None:
        return ("preserve",None,table_text,destination,suppress)
    return ("dispatch",None,table_text,destination,None)


def _desired_rule_priorities(desired):
    result=set()
    if desired.bypass is not None:
        result.add(desired.bypass.priority)
    for pair in desired.pairs:
        result.add(pair.preserve.priority)
        result.add(pair.dispatch.priority)
    return result


def _route_network(value):
    if value=="default":
        return IPv4Network("0.0.0.0/0")
    if not isinstance(value,str):
        return None
    try:
        network=ip_network(value,strict=False)
    except ValueError:
        return None
    return network if isinstance(network,IPv4Network) else None


def _decimal(value):
    if type(value) is int:
        return value
    if isinstance(value,str) and value.isdigit():
        return int(value)
    return None


def _json_array(raw,label):
    try:
        value=json.loads(raw)
    except (TypeError,json.JSONDecodeError):
        raise RuntimeError(f"invalid {label} JSON") from None
    if not isinstance(value,list) or any(not isinstance(x,dict) for x in value):
        raise RuntimeError(f"{label} must be an array of objects")
    return value


def _route_key(route):
    return (int(route.destination.network_address),route.destination.prefixlen,route.table,route.interface,int(route.via))
