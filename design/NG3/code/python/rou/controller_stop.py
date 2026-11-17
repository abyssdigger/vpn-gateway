"""Bounded NG3 controller stop / owned-domain cleanup orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .controller_startup import ControllerStartupSession
from .forwarding_gate import (
    ForwardingGateExecutionResult,
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .linux_forwarding_gate import LinuxForwardingGateBackend
from .managed_network_domain import (
    ManagedNetworkDomainRunner,
    ManagedNetworkDomainSpec,
    destroy_managed_network_domain,
)


class ControllerStopStatus(str, Enum):
    STOPPED = "stopped"
    CLEANUP_FAILED_CONTAINED = "cleanup_failed_contained"
    CLEANUP_FAILED_UNCONTAINED = "cleanup_failed_uncontained"
    LOCK_RELEASE_FAILED = "lock_release_failed"


@dataclass(frozen=True, slots=True)
class ControllerStopResult:
    status: ControllerStopStatus
    containment: ForwardingGateExecutionResult
    cleanup_error: str | None = None
    lock_error: str | None = None

    @property
    def stopped(self) -> bool:
        return self.status is ControllerStopStatus.STOPPED


def stop_controller_once(
    session: ControllerStartupSession,
    domain_spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ControllerStopResult:
    """Run one bounded stop attempt for a retained READY startup session.

    The lifetime lock must still belong to the caller. Forwarding containment is
    attempted first, but a failed containment observation never suppresses the
    independent stronger cleanup attempt of removing the owned managed domain.
    The lock is released only after managed-domain absence has been confirmed by
    destroy_managed_network_domain().
    """
    if not session.lock.acquired:
        raise ValueError(
            "controller stop requires the still-acquired startup lifetime lock"
        )

    containment = converge_forwarding_gate_once(
        LinuxForwardingGateBackend(runner, domain_spec.namespace),
        ForwardingGateState.DISABLED,
    )

    cleanup_error: str | None = None
    try:
        destroy_managed_network_domain(domain_spec, runner)
    except Exception as exc:
        cleanup_error = f"{type(exc).__name__}: {exc}"

    if cleanup_error is not None:
        return ControllerStopResult(
            status=(
                ControllerStopStatus.CLEANUP_FAILED_CONTAINED
                if containment.confirmed
                else ControllerStopStatus.CLEANUP_FAILED_UNCONTAINED
            ),
            containment=containment,
            cleanup_error=cleanup_error,
        )

    try:
        session.lock.release()
    except Exception as exc:
        return ControllerStopResult(
            status=ControllerStopStatus.LOCK_RELEASE_FAILED,
            containment=containment,
            lock_error=f"{type(exc).__name__}: {exc}",
        )

    return ControllerStopResult(
        status=ControllerStopStatus.STOPPED,
        containment=containment,
    )
