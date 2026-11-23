from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ForwardingGateState(str, Enum):
    DISABLED = "disabled"
    ENABLED = "enabled"


class ForwardingGateDriver(Protocol):
    """Lower Driver contract for fresh observation and unconfirmed gate mutation."""

    def observe_forwarding_gate(self) -> ForwardingGateState:
        """Return one fresh authoritative managed-netns forwarding state."""

    def set_forwarding_gate(self, desired: ForwardingGateState) -> None:
        """Issue one lower mutation attempt. Confirmation is not implied."""


class ForwardingGateEnforcementStatus(str, Enum):
    SUCCESS = "success"
    OBSERVATION_FAILED = "observation_failed"
    APPLY_FAILED = "apply_failed"
    POSTCONDITION_FAILED = "postcondition_failed"


@dataclass(frozen=True, slots=True)
class ForwardingGateEnforcementResult:
    status: ForwardingGateEnforcementStatus
    desired: ForwardingGateState
    initial: ForwardingGateState | None
    final: ForwardingGateState | None
    mutation_attempted: bool
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status is ForwardingGateEnforcementStatus.SUCCESS
            and self.final is self.desired
        )


def converge_forwarding_gate_once(
    backend: ForwardingGateDriver,
    desired: ForwardingGateState,
) -> ForwardingGateEnforcementResult:
    """One observe -> optional write -> fresh observe attempt.

    The lower write command is never treated as confirmation. A failed write
    may still end SUCCESS if a subsequent independent observation proves the
    exact desired state, because the safety property is the effective kernel
    state rather than subprocess success.

    No retry loop is hidden here.
    """
    if not isinstance(desired, ForwardingGateState):
        raise ValueError("desired must be ForwardingGateState")

    try:
        initial = backend.observe_forwarding_gate()
    except Exception as exc:
        return ForwardingGateEnforcementResult(
            status=ForwardingGateEnforcementStatus.OBSERVATION_FAILED,
            desired=desired,
            initial=None,
            final=None,
            mutation_attempted=False,
            diagnostic=f"initial observation failed: {type(exc).__name__}: {exc}",
        )

    mutation_attempted = initial is not desired
    apply_error: Exception | None = None

    if mutation_attempted:
        try:
            backend.set_forwarding_gate(desired)
        except Exception as exc:
            apply_error = exc

    try:
        final = backend.observe_forwarding_gate()
    except Exception as exc:
        prefix = ""
        if apply_error is not None:
            prefix = (
                f"apply failed: {type(apply_error).__name__}: {apply_error}; "
            )
        return ForwardingGateEnforcementResult(
            status=(
                ForwardingGateEnforcementStatus.APPLY_FAILED
                if apply_error is not None
                else ForwardingGateEnforcementStatus.OBSERVATION_FAILED
            ),
            desired=desired,
            initial=initial,
            final=None,
            mutation_attempted=mutation_attempted,
            diagnostic=(
                prefix
                + f"final observation failed: {type(exc).__name__}: {exc}"
            ),
        )

    if final is desired:
        diagnostic = None
        if apply_error is not None:
            diagnostic = (
                f"apply raised {type(apply_error).__name__}: {apply_error}; "
                "desired postcondition independently confirmed"
            )
        return ForwardingGateEnforcementResult(
            status=ForwardingGateEnforcementStatus.SUCCESS,
            desired=desired,
            initial=initial,
            final=final,
            mutation_attempted=mutation_attempted,
            diagnostic=diagnostic,
        )

    if apply_error is not None:
        return ForwardingGateEnforcementResult(
            status=ForwardingGateEnforcementStatus.APPLY_FAILED,
            desired=desired,
            initial=initial,
            final=final,
            mutation_attempted=mutation_attempted,
            diagnostic=(
                f"apply failed: {type(apply_error).__name__}: {apply_error}; "
                "fresh final state does not match desired"
            ),
        )

    return ForwardingGateEnforcementResult(
        status=ForwardingGateEnforcementStatus.POSTCONDITION_FAILED,
        desired=desired,
        initial=initial,
        final=final,
        mutation_attempted=mutation_attempted,
        diagnostic="fresh final forwarding-gate state does not match desired",
    )


def forwarding_gate_is_lost(driver: ForwardingGateDriver) -> bool:
    """Return True unless a fresh observation proves the gate is DISABLED.

    Observation failure is deliberately treated as lost containment.
    """
    try:
        return (
            driver.observe_forwarding_gate()
            is not ForwardingGateState.DISABLED
        )
    except Exception:
        return True


# Transitional aliases for code/evidence written before the component-model rename.
ForwardingGateBackend = ForwardingGateDriver
ForwardingGateExecutionStatus = ForwardingGateEnforcementStatus
ForwardingGateExecutionResult = ForwardingGateEnforcementResult
