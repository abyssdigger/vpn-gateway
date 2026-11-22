"""Bounded protective payload-gate convergence.

Architecture: C.010 ProtectivePayloadGate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ProtectivePayloadGateState(str, Enum):
    DISABLED = "disabled"
    ENABLED = "enabled"


@dataclass(frozen=True, slots=True)
class ProtectivePayloadGateDesired:
    state: ProtectivePayloadGateState
    boundary_interface: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, ProtectivePayloadGateState):
            raise ValueError("state must be ProtectivePayloadGateState")
        if self.state is ProtectivePayloadGateState.ENABLED:
            if (
                not isinstance(self.boundary_interface, str)
                or not self.boundary_interface
            ):
                raise ValueError(
                    "enabled protective gate requires boundary_interface"
                )
        elif self.boundary_interface is not None:
            raise ValueError(
                "disabled protective gate must not carry boundary_interface"
            )


class ProtectivePayloadGateObservationStatus(str, Enum):
    ABSENT = "absent"
    EXACT = "exact"
    OWNED_DRIFT = "owned_drift"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class ProtectivePayloadGateObservation:
    status: ProtectivePayloadGateObservationStatus
    conflict_reason: str | None = None

    @property
    def owned(self) -> bool:
        return self.status in {
            ProtectivePayloadGateObservationStatus.EXACT,
            ProtectivePayloadGateObservationStatus.OWNED_DRIFT,
        }

    def matches(self, desired: ProtectivePayloadGateDesired) -> bool:
        if desired.state is ProtectivePayloadGateState.ENABLED:
            return self.status is ProtectivePayloadGateObservationStatus.EXACT
        return self.status is ProtectivePayloadGateObservationStatus.ABSENT


class ProtectivePayloadGateDriver(Protocol):
    def observe_protective_payload_gate(
        self,
        desired: ProtectivePayloadGateDesired,
    ) -> ProtectivePayloadGateObservation:
        """Return one fresh observation relative to desired state."""

    def apply_protective_payload_gate(
        self,
        desired: ProtectivePayloadGateDesired,
        initial: ProtectivePayloadGateObservation,
    ) -> None:
        """Perform one bounded owned mutation attempt; confirmation is separate."""


class ProtectivePayloadGateEnforcementStatus(str, Enum):
    SUCCESS = "success"
    OBSERVATION_FAILED = "observation_failed"
    CONFLICT = "conflict"
    APPLY_FAILED = "apply_failed"
    POSTCONDITION_FAILED = "postcondition_failed"


@dataclass(frozen=True, slots=True)
class ProtectivePayloadGateEnforcementResult:
    status: ProtectivePayloadGateEnforcementStatus
    desired: ProtectivePayloadGateDesired
    initial: ProtectivePayloadGateObservation | None
    final: ProtectivePayloadGateObservation | None
    mutation_attempted: bool
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status is ProtectivePayloadGateEnforcementStatus.SUCCESS
            and self.final is not None
            and self.final.matches(self.desired)
        )


def converge_protective_payload_gate_once(
    driver: ProtectivePayloadGateDriver,
    desired: ProtectivePayloadGateDesired,
) -> ProtectivePayloadGateEnforcementResult:
    """One fresh observe -> optional owned mutation -> fresh observe attempt."""
    if not isinstance(desired, ProtectivePayloadGateDesired):
        raise ValueError("desired must be ProtectivePayloadGateDesired")

    try:
        initial = driver.observe_protective_payload_gate(desired)
    except Exception as exc:
        return ProtectivePayloadGateEnforcementResult(
            ProtectivePayloadGateEnforcementStatus.OBSERVATION_FAILED,
            desired,
            None,
            None,
            False,
            f"initial observation failed: {type(exc).__name__}: {exc}",
        )

    if initial.status is ProtectivePayloadGateObservationStatus.CONFLICT:
        return ProtectivePayloadGateEnforcementResult(
            ProtectivePayloadGateEnforcementStatus.CONFLICT,
            desired,
            initial,
            initial,
            False,
            initial.conflict_reason or "protective gate ownership conflict",
        )

    mutation_attempted = not initial.matches(desired)
    apply_error: Exception | None = None
    if mutation_attempted:
        try:
            driver.apply_protective_payload_gate(desired, initial)
        except Exception as exc:
            apply_error = exc

    try:
        final = driver.observe_protective_payload_gate(desired)
    except Exception as exc:
        prefix = ""
        if apply_error is not None:
            prefix = f"apply failed: {type(apply_error).__name__}: {apply_error}; "
        return ProtectivePayloadGateEnforcementResult(
            (
                ProtectivePayloadGateEnforcementStatus.APPLY_FAILED
                if apply_error is not None
                else ProtectivePayloadGateEnforcementStatus.OBSERVATION_FAILED
            ),
            desired,
            initial,
            None,
            mutation_attempted,
            prefix + f"final observation failed: {type(exc).__name__}: {exc}",
        )

    if final.matches(desired):
        diagnostic = None
        if apply_error is not None:
            diagnostic = (
                f"apply raised {type(apply_error).__name__}: {apply_error}; "
                "desired postcondition independently confirmed"
            )
        return ProtectivePayloadGateEnforcementResult(
            ProtectivePayloadGateEnforcementStatus.SUCCESS,
            desired,
            initial,
            final,
            mutation_attempted,
            diagnostic,
        )

    if final.status is ProtectivePayloadGateObservationStatus.CONFLICT:
        return ProtectivePayloadGateEnforcementResult(
            ProtectivePayloadGateEnforcementStatus.CONFLICT,
            desired,
            initial,
            final,
            mutation_attempted,
            final.conflict_reason or "fresh final state conflicts with ownership",
        )

    if apply_error is not None:
        return ProtectivePayloadGateEnforcementResult(
            ProtectivePayloadGateEnforcementStatus.APPLY_FAILED,
            desired,
            initial,
            final,
            mutation_attempted,
            (
                f"apply failed: {type(apply_error).__name__}: {apply_error}; "
                "fresh final state does not match desired"
            ),
        )

    return ProtectivePayloadGateEnforcementResult(
        ProtectivePayloadGateEnforcementStatus.POSTCONDITION_FAILED,
        desired,
        initial,
        final,
        mutation_attempted,
        "fresh final protective payload-gate state does not match desired",
    )
