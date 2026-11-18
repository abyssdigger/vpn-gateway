"""Selected Linux host-bootstrap lowering backed by EXP-056/059."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

from .host_boundary_policy import HostBoundaryPolicyPlan
from .network_policy_layout import NumericResourcePool


@dataclass(frozen=True, slots=True)
class HostBootstrapLinuxAllocation:
    table: int
    bypass_priority: int
    pair_priorities: NumericResourcePool
    rule_protocol: int
    route_protocol: int

    def __post_init__(self) -> None:
        if type(self.table) is not int or not 1 <= self.table <= 0xFFFFFFFF:
            raise ValueError("table must be in [1, 2^32-1]")
        if type(self.bypass_priority) is not int or not 1 <= self.bypass_priority <= 0xFFFFFFFF:
            raise ValueError("bypass_priority must be in [1, 2^32-1]")
        if not isinstance(self.pair_priorities, NumericResourcePool):
            raise ValueError("pair_priorities must be NumericResourcePool")
        for label,value in (
            ("rule_protocol", self.rule_protocol),
            ("route_protocol", self.route_protocol),
        ):
            if type(value) is not int or not 1 <= value <= 255:
                raise ValueError(f"{label} must be in [1, 255]")
        if self.pair_priorities.contains(self.bypass_priority):
            raise ValueError("bypass priority must be outside pair priority pool")


@dataclass(frozen=True, slots=True)
class HostBootstrapRouteSpec:
    destination: IPv4Network
    via: IPv4Address
    interface: str
    table: int
    protocol: int


@dataclass(frozen=True, slots=True)
class HostBootstrapBypassRuleSpec:
    priority: int
    interface: str
    protocol: int


@dataclass(frozen=True, slots=True)
class HostBootstrapPreserveRuleSpec:
    priority: int
    destination: IPv4Network
    suppress_prefixlen: int
    protocol: int


@dataclass(frozen=True, slots=True)
class HostBootstrapDispatchRuleSpec:
    priority: int
    destination: IPv4Network
    table: int
    protocol: int


@dataclass(frozen=True, slots=True)
class HostBootstrapRulePair:
    preserve: HostBootstrapPreserveRuleSpec
    dispatch: HostBootstrapDispatchRuleSpec


@dataclass(frozen=True, slots=True)
class HostBootstrapLinuxDesired:
    routes: tuple[HostBootstrapRouteSpec, ...]
    bypass: HostBootstrapBypassRuleSpec | None
    pairs: tuple[HostBootstrapRulePair, ...]


def build_linux_host_bootstrap_desired(
    plan: HostBoundaryPolicyPlan,
    *,
    host_interface: str,
    inner_gateway: IPv4Address,
    allocation: HostBootstrapLinuxAllocation,
) -> HostBootstrapLinuxDesired:
    if not isinstance(plan, HostBoundaryPolicyPlan):
        raise ValueError("plan must be HostBoundaryPolicyPlan")
    if not isinstance(host_interface, str) or not host_interface:
        raise ValueError("host_interface must be non-empty text")
    if not isinstance(inner_gateway, IPv4Address):
        raise ValueError("inner_gateway must be IPv4Address")
    if not isinstance(allocation, HostBootstrapLinuxAllocation):
        raise ValueError("allocation must be HostBootstrapLinuxAllocation")

    destinations = tuple(
        sorted(
            {item.destination for item in plan.bootstrap_routes},
            key=lambda network: (-network.prefixlen, int(network.network_address)),
        )
    )
    if not destinations:
        return HostBootstrapLinuxDesired(routes=(), bypass=None, pairs=())

    priority_values = allocation.pair_priorities.allocate(len(destinations) * 2)
    pairs = tuple(
        HostBootstrapRulePair(
            preserve=HostBootstrapPreserveRuleSpec(
                priority=priority_values[index * 2],
                destination=destination,
                suppress_prefixlen=destination.prefixlen,
                protocol=allocation.rule_protocol,
            ),
            dispatch=HostBootstrapDispatchRuleSpec(
                priority=priority_values[index * 2 + 1],
                destination=destination,
                table=allocation.table,
                protocol=allocation.rule_protocol,
            ),
        )
        for index,destination in enumerate(destinations)
    )
    routes = tuple(
        HostBootstrapRouteSpec(
            destination=destination,
            via=inner_gateway,
            interface=host_interface,
            table=allocation.table,
            protocol=allocation.route_protocol,
        )
        for destination in destinations
    )
    return HostBootstrapLinuxDesired(
        routes=routes,
        bypass=HostBootstrapBypassRuleSpec(
            priority=allocation.bypass_priority,
            interface=host_interface,
            protocol=allocation.rule_protocol,
        ),
        pairs=pairs,
    )
