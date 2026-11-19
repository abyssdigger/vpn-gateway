"""Linux lowering for the ordinary-host managed-destination routing owner."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .host_managed_routing import HostManagedRoutingPlan
from .network_policy_layout import NumericResourcePool


@dataclass(frozen=True, slots=True)
class HostManagedRoutingLinuxAllocation:
    table: int
    bypass_priority: int
    dispatch_priority: int
    owned_rule_priorities: NumericResourcePool
    rule_protocol: int
    route_protocol: int

    def __post_init__(self) -> None:
        for label, value in (
            ("table", self.table),
            ("bypass_priority", self.bypass_priority),
            ("dispatch_priority", self.dispatch_priority),
        ):
            if type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
                raise ValueError(f"{label} must be in [1, 2^32-1]")
        if not isinstance(self.owned_rule_priorities, NumericResourcePool):
            raise ValueError("owned_rule_priorities must be NumericResourcePool")
        if self.bypass_priority == self.dispatch_priority:
            raise ValueError("bypass and dispatch priorities must be distinct")
        if not self.owned_rule_priorities.contains(self.dispatch_priority):
            raise ValueError("dispatch priority must be inside owned rule priority pool")
        if self.owned_rule_priorities.contains(self.bypass_priority):
            raise ValueError("bypass priority must be outside owned rule priority pool")
        if self.bypass_priority > self.dispatch_priority:
            raise ValueError("bypass rule must execute before managed dispatch")
        for label, value in (
            ("rule_protocol", self.rule_protocol),
            ("route_protocol", self.route_protocol),
        ):
            if type(value) is not int or not 1 <= value <= 255:
                raise ValueError(f"{label} must be in [1, 255]")


@dataclass(frozen=True, slots=True)
class HostManagedRouteSpec:
    destination: IPv4Network
    interface: str
    table: int
    protocol: int


@dataclass(frozen=True, slots=True)
class HostManagedBypassRuleSpec:
    priority: int
    interface: str
    protocol: int


@dataclass(frozen=True, slots=True)
class HostManagedDispatchRuleSpec:
    priority: int
    table: int
    protocol: int


@dataclass(frozen=True, slots=True)
class HostManagedRoutingLinuxDesired:
    routes: tuple[HostManagedRouteSpec, ...]
    bypass: HostManagedBypassRuleSpec | None
    dispatch: HostManagedDispatchRuleSpec | None


def build_linux_host_managed_routing_desired(
    plan: HostManagedRoutingPlan,
    *,
    host_interface: str,
    allocation: HostManagedRoutingLinuxAllocation,
) -> HostManagedRoutingLinuxDesired:
    if not isinstance(plan, HostManagedRoutingPlan):
        raise ValueError("plan must be HostManagedRoutingPlan")
    if not isinstance(host_interface, str) or not host_interface:
        raise ValueError("host_interface must be non-empty text")
    if not isinstance(allocation, HostManagedRoutingLinuxAllocation):
        raise ValueError("allocation must be HostManagedRoutingLinuxAllocation")

    destinations = tuple(item.destination for item in plan.routes)
    if not destinations:
        return HostManagedRoutingLinuxDesired((), None, None)

    routes = tuple(
        HostManagedRouteSpec(
            destination=destination,
            interface=host_interface,
            table=allocation.table,
            protocol=allocation.route_protocol,
        )
        for destination in destinations
    )
    return HostManagedRoutingLinuxDesired(
        routes=routes,
        bypass=HostManagedBypassRuleSpec(
            priority=allocation.bypass_priority,
            interface=host_interface,
            protocol=allocation.rule_protocol,
        ),
        dispatch=HostManagedDispatchRuleSpec(
            priority=allocation.dispatch_priority,
            table=allocation.table,
            protocol=allocation.rule_protocol,
        ),
    )
