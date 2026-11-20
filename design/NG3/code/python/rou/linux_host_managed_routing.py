"""Linux lowering for the ordinary-host managed-destination routing owner."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

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
    preserve_priority: int | None = None
    scope_exit_priority: int | None = None

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
        if self.preserve_priority is not None:
            if type(self.preserve_priority) is not int or not 1 <= self.preserve_priority <= 0xFFFFFFFF:
                raise ValueError("preserve_priority must be in [1, 2^32-1] or None")
            if not self.owned_rule_priorities.contains(self.preserve_priority):
                raise ValueError("preserve priority must be inside owned rule priority pool")
            if not self.bypass_priority < self.preserve_priority < self.dispatch_priority:
                raise ValueError("preserve rule must execute between bypass and managed dispatch")
        if self.scope_exit_priority is not None:
            if type(self.scope_exit_priority) is not int or not 1 <= self.scope_exit_priority <= 0xFFFFFFFF:
                raise ValueError("scope_exit_priority must be in [1, 2^32-1] or None")
            if not self.owned_rule_priorities.contains(self.scope_exit_priority):
                raise ValueError("scope exit priority must be inside owned rule priority pool")
            if self.scope_exit_priority <= self.dispatch_priority:
                raise ValueError("scope exit must execute after managed dispatch")
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
    gateway: IPv4Address | None = None
    onlink: bool = False


@dataclass(frozen=True, slots=True)
class HostManagedDispatchSelector:
    incoming_interface: str | None = None
    invert_incoming_interface: bool = False

    def __post_init__(self) -> None:
        if self.incoming_interface is not None and (
            not isinstance(self.incoming_interface, str) or not self.incoming_interface
        ):
            raise ValueError("incoming_interface must be non-empty text or None")
        if self.invert_incoming_interface and self.incoming_interface is None:
            raise ValueError("inverted dispatch requires incoming_interface")


@dataclass(frozen=True, slots=True)
class HostManagedBypassRuleSpec:
    priority: int
    interface: str
    protocol: int
    goto_priority: int | None = None


@dataclass(frozen=True, slots=True)
class HostManagedDispatchRuleSpec:
    priority: int
    table: int
    protocol: int
    incoming_interface: str | None = None
    invert_incoming_interface: bool = False


@dataclass(frozen=True, slots=True)
class HostManagedPreserveMainRuleSpec:
    priority: int
    protocol: int
    suppress_prefixlength: int = 0


@dataclass(frozen=True, slots=True)
class HostManagedScopeExitRuleSpec:
    priority: int
    protocol: int


@dataclass(frozen=True, slots=True)
class HostManagedRoutingLinuxDesired:
    routes: tuple[HostManagedRouteSpec, ...]
    bypass: HostManagedBypassRuleSpec | None
    dispatch: HostManagedDispatchRuleSpec | None
    preserve_main: HostManagedPreserveMainRuleSpec | None = None
    additional_dispatches: tuple[HostManagedDispatchRuleSpec, ...] = ()
    scope_exit: HostManagedScopeExitRuleSpec | None = None

    @property
    def dispatch_rules(self) -> tuple[HostManagedDispatchRuleSpec, ...]:
        if self.dispatch is None:
            return self.additional_dispatches
        return (self.dispatch, *self.additional_dispatches)


def build_linux_host_managed_routing_desired(
    plan: HostManagedRoutingPlan,
    *,
    host_interface: str,
    allocation: HostManagedRoutingLinuxAllocation,
    stack_service_address: IPv4Address | None = None,
) -> HostManagedRoutingLinuxDesired:
    if not isinstance(plan, HostManagedRoutingPlan):
        raise ValueError("plan must be HostManagedRoutingPlan")
    if not isinstance(host_interface, str) or not host_interface:
        raise ValueError("host_interface must be non-empty text")
    if not isinstance(allocation, HostManagedRoutingLinuxAllocation):
        raise ValueError("allocation must be HostManagedRoutingLinuxAllocation")
    if stack_service_address is not None and not isinstance(stack_service_address, IPv4Address):
        raise ValueError("stack_service_address must be IPv4Address or None")
    if not plan.routes:
        return HostManagedRoutingLinuxDesired((), None, None)
    if any(item.via_stack_service for item in plan.routes) and stack_service_address is None:
        raise ValueError("SNAT identity host route requires current stack_service_address")

    routes = tuple(
        HostManagedRouteSpec(
            destination=item.destination,
            interface=host_interface,
            table=allocation.table,
            protocol=allocation.route_protocol,
            gateway=stack_service_address if item.via_stack_service else None,
            onlink=item.via_stack_service,
        )
        for item in plan.routes
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


def build_linux_peaceful_host_routing_desired(
    plan: HostManagedRoutingPlan,
    *,
    host_interface: str,
    allocation: HostManagedRoutingLinuxAllocation,
    dispatch_selectors: tuple[HostManagedDispatchSelector, ...],
    stack_service_address: IPv4Address | None = None,
) -> HostManagedRoutingLinuxDesired:
    """Lower scoped Release-1 lifecycle assistance without authoritative precedence."""
    if allocation.preserve_priority is None:
        raise ValueError("peaceful helper allocation requires preserve_priority")
    if allocation.scope_exit_priority is None:
        raise ValueError("peaceful helper allocation requires scope_exit_priority")
    if not isinstance(dispatch_selectors, tuple) or any(
        not isinstance(item, HostManagedDispatchSelector) for item in dispatch_selectors
    ):
        raise ValueError("dispatch_selectors must be a tuple of HostManagedDispatchSelector")
    if not dispatch_selectors:
        return HostManagedRoutingLinuxDesired((), None, None, None)

    base = build_linux_host_managed_routing_desired(
        plan,
        host_interface=host_interface,
        allocation=allocation,
        stack_service_address=stack_service_address,
    )
    if not base.routes:
        return HostManagedRoutingLinuxDesired((), None, None, None)

    dispatches = []
    for offset, selector in enumerate(dispatch_selectors):
        priority = allocation.dispatch_priority + offset
        if priority >= allocation.scope_exit_priority or not allocation.owned_rule_priorities.contains(priority):
            raise ValueError("peaceful helper selector count exceeds reserved RPDB priority space")
        dispatches.append(
            HostManagedDispatchRuleSpec(
                priority=priority,
                table=allocation.table,
                protocol=allocation.rule_protocol,
                incoming_interface=selector.incoming_interface,
                invert_incoming_interface=selector.invert_incoming_interface,
            )
        )

    return HostManagedRoutingLinuxDesired(
        routes=base.routes,
        bypass=HostManagedBypassRuleSpec(
            priority=allocation.bypass_priority,
            interface=host_interface,
            protocol=allocation.rule_protocol,
            goto_priority=allocation.scope_exit_priority,
        ),
        dispatch=dispatches[0],
        preserve_main=HostManagedPreserveMainRuleSpec(
            priority=allocation.preserve_priority,
            protocol=allocation.rule_protocol,
            suppress_prefixlength=0,
        ),
        additional_dispatches=tuple(dispatches[1:]),
        scope_exit=HostManagedScopeExitRuleSpec(
            priority=allocation.scope_exit_priority,
            protocol=allocation.rule_protocol,
        ),
    )
