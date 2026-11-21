"""Bounded NG3 controller stop / owned-domain cleanup orchestration.

Architecture: structured Annex A A.001 ProductLifecycleControl. Cleanup composes
HostRoutingContribution plus C.009 OrdinarySidePortalLifecycle,
B.001 ManagedL3BoundaryLifecycle, and C.007 ManagedNetworkEnvironmentLifecycle.
Requirement traceability: VPNG0005-R5.R4/R5, VPNG0004-R4.R6, VPNG0007-R7.R3/R7.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .host_routing_contribution import HostRoutingContribution
from .instance_lock import ControllerInstanceLock

if TYPE_CHECKING:
    from .controller_startup import ControllerStartupSession
from .forwarding_gate import (
    ForwardingGateEnforcementResult,
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .linux_forwarding_gate import LinuxForwardingGateDriver
from .managed_network_domain import (
    ManagedNetworkDomainRunner,
    ManagedNetworkDomainSpec,
    cleanup_ordinary_side_portal,
    destroy_managed_l3_boundary,
    destroy_managed_network_environment,
)


class ControllerStopStatus(str, Enum):
    STOPPED = "stopped"
    CLEANUP_FAILED_CONTAINED = "cleanup_failed_contained"
    CLEANUP_FAILED_UNCONTAINED = "cleanup_failed_uncontained"
    LOCK_RELEASE_FAILED = "lock_release_failed"


@dataclass(frozen=True, slots=True)
class ControllerStopResult:
    status: ControllerStopStatus
    containment: ForwardingGateEnforcementResult
    cleanup_error: str | None = None
    cleanup_diagnostic: str | None = None
    lock_error: str | None = None

    @property
    def stopped(self) -> bool:
        return self.status is ControllerStopStatus.STOPPED


def cleanup_controller_owned_domain_once(
    lock: ControllerInstanceLock,
    domain_spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
    host_routing_contribution: HostRoutingContribution | None = None,
) -> ControllerStopResult:
    """Run one bounded owned-domain cleanup attempt under a retained lifetime lock."""
    if not lock.acquired:
        raise ValueError(
            "controller cleanup requires a still-acquired lifetime lock"
        )

    containment = converge_forwarding_gate_once(
        LinuxForwardingGateDriver(runner, domain_spec.namespace),
        ForwardingGateState.DISABLED,
    )

    cleanup_errors: list[str] = []

    if host_routing_contribution is not None:
        try:
            host_routing_contribution.cleanup()
        except Exception as exc:
            cleanup_errors.append(
                "host-routing contribution cleanup failed: "
                f"{type(exc).__name__}: {exc}"
            )

    contained_cleanup_diagnostics: list[str] = []

    try:
        cleanup_ordinary_side_portal(domain_spec, runner)
    except Exception as exc:
        contained_cleanup_diagnostics.append(
            "ordinary-side portal cleanup failed: "
            f"{type(exc).__name__}: {exc}"
        )

    try:
        destroy_managed_l3_boundary(domain_spec, runner)
    except Exception as exc:
        contained_cleanup_diagnostics.append(
            "ordinary-side transition destroy failed: "
            f"{type(exc).__name__}: {exc}"
        )

    environment_removed = False
    try:
        destroy_managed_network_environment(domain_spec, runner)
        environment_removed = True
    except Exception as exc:
        cleanup_errors.append(
            "managed-network environment destroy failed: "
            f"{type(exc).__name__}: {exc}"
        )

    if not environment_removed:
        # Without the stronger environment-absence postcondition, earlier
        # contained-artifact failures remain material cleanup failures.
        cleanup_errors.extend(contained_cleanup_diagnostics)

    cleanup_error = "; ".join(cleanup_errors) if cleanup_errors else None
    cleanup_diagnostic = (
        "; ".join(contained_cleanup_diagnostics)
        if contained_cleanup_diagnostics
        else None
    )

    if cleanup_error is not None:
        return ControllerStopResult(
            status=(
                ControllerStopStatus.CLEANUP_FAILED_CONTAINED
                if containment.confirmed
                else ControllerStopStatus.CLEANUP_FAILED_UNCONTAINED
            ),
            containment=containment,
            cleanup_error=cleanup_error,
            cleanup_diagnostic=cleanup_diagnostic,
        )

    try:
        lock.release()
    except Exception as exc:
        return ControllerStopResult(
            status=ControllerStopStatus.LOCK_RELEASE_FAILED,
            containment=containment,
            cleanup_diagnostic=cleanup_diagnostic,
            lock_error=f"{type(exc).__name__}: {exc}",
        )

    return ControllerStopResult(
        status=ControllerStopStatus.STOPPED,
        containment=containment,
        cleanup_diagnostic=cleanup_diagnostic,
    )


def stop_controller_once(
    session: "ControllerStartupSession",
    domain_spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ControllerStopResult:
    """Run one bounded stop attempt for a retained READY startup session."""
    if not session.lock.acquired:
        raise ValueError(
            "controller stop requires the still-acquired startup lifetime lock"
        )

    return cleanup_controller_owned_domain_once(
        session.lock,
        domain_spec,
        runner,
        session.host_routing_contribution,
    )
