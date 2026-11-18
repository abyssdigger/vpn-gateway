"""Guarded convergence for the managed-stack return-affinity owner."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .forwarding_gate import ForwardingGateBackend, ForwardingGateState
from .stack_return_affinity import StackReturnAffinityDesired


class StackReturnAffinityOwnerStatus(str, Enum):
    ABSENT = "absent"
    EXACT = "exact"
    STALE = "stale"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class StackReturnAffinityObservation:
    status: StackReturnAffinityOwnerStatus
    desired: StackReturnAffinityDesired | None = None
    diagnostic: str | None = None


class StackReturnAffinityBackend(Protocol):
    def observe(self, desired: StackReturnAffinityDesired) -> StackReturnAffinityObservation:
        """Observe/classify the reserved owner against one exact desired state."""

    def replace_owned(
        self,
        desired: StackReturnAffinityDesired,
        observed: StackReturnAffinityObservation,
    ) -> None:
        """Replace only an already classified ABSENT/STALE owned state."""

    def cleanup_owned(self) -> None:
        """Remove only the reserved owner state or raise on conflict/unknown state."""


class StackReturnAffinityConvergenceStatus(str, Enum):
    EXACT = "exact"
    APPLIED = "applied"
    BARRIER_LOST = "barrier_lost"
    OBSERVATION_FAILED = "observation_failed"
    CONFLICT = "conflict"
    APPLY_FAILED = "apply_failed"
    POSTCONDITION_FAILED = "postcondition_failed"


@dataclass(frozen=True, slots=True)
class StackReturnAffinityConvergenceResult:
    status: StackReturnAffinityConvergenceStatus
    initial: StackReturnAffinityObservation | None
    final: StackReturnAffinityObservation | None
    mutation_attempted: bool
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status
            in {
                StackReturnAffinityConvergenceStatus.EXACT,
                StackReturnAffinityConvergenceStatus.APPLIED,
            }
            and self.final is not None
            and self.final.status is StackReturnAffinityOwnerStatus.EXACT
        )


def converge_stack_return_affinity_once(
    gate_backend: ForwardingGateBackend,
    backend: StackReturnAffinityBackend,
    desired: StackReturnAffinityDesired,
) -> StackReturnAffinityConvergenceResult:
    """Converge the owner only while forwarding is freshly confirmed disabled."""
    try:
        initial = backend.observe(desired)
    except Exception as exc:
        return StackReturnAffinityConvergenceResult(
            StackReturnAffinityConvergenceStatus.OBSERVATION_FAILED,
            None,
            None,
            False,
            f"initial affinity observation failed: {type(exc).__name__}: {exc}",
        )

    if initial.status is StackReturnAffinityOwnerStatus.CONFLICT:
        return StackReturnAffinityConvergenceResult(
            StackReturnAffinityConvergenceStatus.CONFLICT,
            initial,
            initial,
            False,
            initial.diagnostic or "reserved affinity owner conflicts with observed state",
        )

    if initial.status is StackReturnAffinityOwnerStatus.EXACT:
        return StackReturnAffinityConvergenceResult(
            StackReturnAffinityConvergenceStatus.EXACT,
            initial,
            initial,
            False,
        )

    try:
        gate = gate_backend.observe_forwarding_gate()
    except Exception as exc:
        return StackReturnAffinityConvergenceResult(
            StackReturnAffinityConvergenceStatus.BARRIER_LOST,
            initial,
            None,
            False,
            f"forwarding barrier re-observation failed: {type(exc).__name__}: {exc}",
        )
    if gate is not ForwardingGateState.DISABLED:
        return StackReturnAffinityConvergenceResult(
            StackReturnAffinityConvergenceStatus.BARRIER_LOST,
            initial,
            None,
            False,
            "forwarding barrier is not disabled immediately before affinity mutation",
        )

    apply_error: Exception | None = None
    try:
        backend.replace_owned(desired, initial)
    except Exception as exc:
        apply_error = exc

    try:
        final = backend.observe(desired)
    except Exception as exc:
        return StackReturnAffinityConvergenceResult(
            (
                StackReturnAffinityConvergenceStatus.APPLY_FAILED
                if apply_error is not None
                else StackReturnAffinityConvergenceStatus.OBSERVATION_FAILED
            ),
            initial,
            None,
            True,
            (
                (
                    f"affinity apply failed: {type(apply_error).__name__}: {apply_error}; "
                    if apply_error is not None
                    else ""
                )
                + f"final affinity observation failed: {type(exc).__name__}: {exc}"
            ),
        )

    try:
        final_gate = gate_backend.observe_forwarding_gate()
    except Exception as exc:
        return StackReturnAffinityConvergenceResult(
            StackReturnAffinityConvergenceStatus.BARRIER_LOST,
            initial,
            final,
            True,
            f"forwarding barrier final observation failed: {type(exc).__name__}: {exc}",
        )
    if final_gate is not ForwardingGateState.DISABLED:
        return StackReturnAffinityConvergenceResult(
            StackReturnAffinityConvergenceStatus.BARRIER_LOST,
            initial,
            final,
            True,
            "forwarding barrier was lost during affinity convergence",
        )

    if final.status is StackReturnAffinityOwnerStatus.EXACT:
        return StackReturnAffinityConvergenceResult(
            StackReturnAffinityConvergenceStatus.APPLIED,
            initial,
            final,
            True,
            (
                None
                if apply_error is None
                else (
                    f"affinity apply raised {type(apply_error).__name__}: {apply_error}; "
                    "exact postcondition independently confirmed"
                )
            ),
        )

    if final.status is StackReturnAffinityOwnerStatus.CONFLICT:
        status = StackReturnAffinityConvergenceStatus.CONFLICT
    elif apply_error is not None:
        status = StackReturnAffinityConvergenceStatus.APPLY_FAILED
    else:
        status = StackReturnAffinityConvergenceStatus.POSTCONDITION_FAILED
    return StackReturnAffinityConvergenceResult(
        status,
        initial,
        final,
        True,
        (
            final.diagnostic
            or (
                f"affinity apply failed: {type(apply_error).__name__}: {apply_error}"
                if apply_error is not None
                else "exact affinity postcondition is not confirmed"
            )
        ),
    )
