"""Bounded composite aggressive host-routing Enforcer.

Architecture: E.004 AggressiveHostRoutingEnforcer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address

from .host_managed_routing import HostManagedRoutingPlan
from .linux_aggressive_escape_guard import (
    AggressiveEscapeGuardDesired,
    AggressiveEscapeGuardState,
    LinuxAggressiveEscapeGuardDriver,
    converge_aggressive_escape_guard_once,
)
from .linux_aggressive_routing_authority import (
    AggressiveRoutingAuthorityObservation,
    observe_aggressive_routing_authority,
)
from .linux_host_managed_routing import (
    HostManagedRoutingLinuxAllocation,
    HostManagedRoutingLinuxDesired,
    build_linux_host_managed_routing_desired,
)
from .linux_host_managed_routing_backend import (
    LinuxHostManagedRoutingDriver,
    cleanup_host_managed_routing_once,
    converge_host_managed_routing_once,
)


@dataclass(frozen=True, slots=True)
class AggressiveHostRoutingDesired:
    routing: HostManagedRoutingLinuxDesired
    guard: AggressiveEscapeGuardDesired

    def __post_init__(self) -> None:
        if not isinstance(self.routing, HostManagedRoutingLinuxDesired):
            raise ValueError("routing must be HostManagedRoutingLinuxDesired")
        if self.routing.dispatch is None or self.routing.bypass is None:
            raise ValueError("aggressive desired state requires routing capture")
        if self.guard.state is not AggressiveEscapeGuardState.ENABLED:
            raise ValueError("aggressive desired state requires enabled guard")
        if self.guard.boundary_interface != self.routing.bypass.interface:
            raise ValueError("routing and guard boundary interfaces must match")


class AggressiveHostRoutingEnforcementStatus(str, Enum):
    ACTIVE_CONFIRMED = "active_confirmed"
    INACTIVE_CONFIRMED = "inactive_confirmed"
    GUARD_FAILED = "guard_failed"
    ROUTING_FAILED = "routing_failed"
    AUTHORITY_FAILED = "authority_failed"
    CLEANUP_FAILED = "cleanup_failed"
    GUARD_RELEASE_FAILED = "guard_release_failed"


@dataclass(frozen=True, slots=True)
class AggressiveHostRoutingEnforcementResult:
    status: AggressiveHostRoutingEnforcementStatus
    local_containment_confirmed: bool
    authority: AggressiveRoutingAuthorityObservation | None = None
    diagnostic: str | None = None

    @property
    def confirmed_active(self) -> bool:
        return self.status is AggressiveHostRoutingEnforcementStatus.ACTIVE_CONFIRMED

    @property
    def confirmed_inactive(self) -> bool:
        return self.status is AggressiveHostRoutingEnforcementStatus.INACTIVE_CONFIRMED


@dataclass(slots=True)
class AggressiveHostRoutingEnforcer:
    """E.004 component facade hiding its lower Linux Drivers from E.003."""

    routing_driver: LinuxHostManagedRoutingDriver
    guard_driver: LinuxAggressiveEscapeGuardDriver

    def __post_init__(self) -> None:
        if not isinstance(self.routing_driver, LinuxHostManagedRoutingDriver):
            raise ValueError(
                "routing_driver must be LinuxHostManagedRoutingDriver"
            )
        if not isinstance(
            self.guard_driver,
            LinuxAggressiveEscapeGuardDriver,
        ):
            raise ValueError(
                "guard_driver must be LinuxAggressiveEscapeGuardDriver"
            )

    def converge_active(
        self,
        desired: AggressiveHostRoutingDesired,
    ) -> AggressiveHostRoutingEnforcementResult:
        return converge_aggressive_host_routing_active_once(
            self.routing_driver,
            self.guard_driver,
            desired,
        )

    def converge_inactive(
        self,
        desired: AggressiveHostRoutingDesired,
    ) -> AggressiveHostRoutingEnforcementResult:
        return converge_aggressive_host_routing_inactive_once(
            self.routing_driver,
            self.guard_driver,
            desired,
        )


def build_aggressive_host_routing_desired(
    plan: HostManagedRoutingPlan,
    *,
    host_interface: str,
    allocation: HostManagedRoutingLinuxAllocation,
    stack_service_address: IPv4Address | None = None,
) -> AggressiveHostRoutingDesired:
    routing = build_linux_host_managed_routing_desired(
        plan,
        host_interface=host_interface,
        allocation=allocation,
        stack_service_address=stack_service_address,
    )
    if not routing.routes:
        raise ValueError("aggressive host routing requires at least one managed destination")
    return AggressiveHostRoutingDesired(
        routing=routing,
        guard=AggressiveEscapeGuardDesired(
            AggressiveEscapeGuardState.ENABLED,
            host_interface,
            tuple(route.destination for route in routing.routes),
        ),
    )


def converge_aggressive_host_routing_active_once(
    routing_driver: LinuxHostManagedRoutingDriver,
    guard_driver: LinuxAggressiveEscapeGuardDriver,
    desired: AggressiveHostRoutingDesired,
) -> AggressiveHostRoutingEnforcementResult:
    try:
        converge_aggressive_escape_guard_once(guard_driver, desired.guard)
    except Exception as exc:
        return AggressiveHostRoutingEnforcementResult(
            AggressiveHostRoutingEnforcementStatus.GUARD_FAILED,
            False,
            diagnostic=f"escape guard convergence failed: {type(exc).__name__}: {exc}",
        )

    try:
        converge_host_managed_routing_once(routing_driver, desired.routing)
    except Exception as exc:
        return AggressiveHostRoutingEnforcementResult(
            AggressiveHostRoutingEnforcementStatus.ROUTING_FAILED,
            True,
            diagnostic=f"routing convergence failed: {type(exc).__name__}: {exc}",
        )

    try:
        authority = observe_aggressive_routing_authority(
            routing_driver,
            desired.routing,
        )
        guard = guard_driver.observe(desired.guard)
    except Exception as exc:
        return AggressiveHostRoutingEnforcementResult(
            AggressiveHostRoutingEnforcementStatus.AUTHORITY_FAILED,
            True,
            diagnostic=f"fresh authority observation failed: {type(exc).__name__}: {exc}",
        )

    guard_exact = guard.matches(desired.guard)
    if authority.confirmed and guard_exact:
        return AggressiveHostRoutingEnforcementResult(
            AggressiveHostRoutingEnforcementStatus.ACTIVE_CONFIRMED,
            True,
            authority=authority,
        )

    return AggressiveHostRoutingEnforcementResult(
        AggressiveHostRoutingEnforcementStatus.AUTHORITY_FAILED,
        guard_exact,
        authority=authority,
        diagnostic=(
            "; ".join(authority.conflicts)
            if authority.conflicts
            else "fresh escape guard postcondition is not exact"
        ),
    )


def converge_aggressive_host_routing_inactive_once(
    routing_driver: LinuxHostManagedRoutingDriver,
    guard_driver: LinuxAggressiveEscapeGuardDriver,
    desired: AggressiveHostRoutingDesired,
) -> AggressiveHostRoutingEnforcementResult:
    # Deactivation must restore/reconfirm the local guard before touching routing.
    try:
        converge_aggressive_escape_guard_once(guard_driver, desired.guard)
    except Exception as exc:
        return AggressiveHostRoutingEnforcementResult(
            AggressiveHostRoutingEnforcementStatus.GUARD_FAILED,
            False,
            diagnostic=f"cannot establish guard before cleanup: {type(exc).__name__}: {exc}",
        )

    try:
        cleanup_host_managed_routing_once(routing_driver, desired.routing)
    except Exception as exc:
        return AggressiveHostRoutingEnforcementResult(
            AggressiveHostRoutingEnforcementStatus.CLEANUP_FAILED,
            True,
            diagnostic=f"routing cleanup failed: {type(exc).__name__}: {exc}",
        )

    disabled = AggressiveEscapeGuardDesired(AggressiveEscapeGuardState.DISABLED)
    try:
        converge_aggressive_escape_guard_once(guard_driver, disabled)
    except Exception as exc:
        return AggressiveHostRoutingEnforcementResult(
            AggressiveHostRoutingEnforcementStatus.GUARD_RELEASE_FAILED,
            True,
            diagnostic=f"guard release failed: {type(exc).__name__}: {exc}",
        )
    return AggressiveHostRoutingEnforcementResult(
        AggressiveHostRoutingEnforcementStatus.INACTIVE_CONFIRMED,
        False,
    )
