from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AvailabilityOutcome(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NO_EVIDENCE = "no_evidence"


@dataclass(frozen=True, slots=True)
class AvailabilityConfirmationState:
    availability_problem: bool = False
    degradation_progress: int = 0
    recovery_progress: int = 0

    def __post_init__(self) -> None:
        if type(self.availability_problem) is not bool:
            raise ValueError("availability_problem must be boolean")
        for name, value in (
            ("degradation_progress", self.degradation_progress),
            ("recovery_progress", self.recovery_progress),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.availability_problem and self.degradation_progress != 0:
            raise ValueError("degradation progress must be zero while problem is established")
        if not self.availability_problem and self.recovery_progress != 0:
            raise ValueError("recovery progress must be zero while no problem is established")


def apply_availability_evidence(
    state: AvailabilityConfirmationState,
    outcome: AvailabilityOutcome,
    *,
    degradation_threshold: int,
    recovery_threshold: int,
) -> AvailabilityConfirmationState:
    _validate_threshold(degradation_threshold, "degradation_threshold")
    _validate_threshold(recovery_threshold, "recovery_threshold")
    if not isinstance(outcome, AvailabilityOutcome):
        raise ValueError("outcome must be an AvailabilityOutcome")
    _validate_progress_bounds(
        state,
        degradation_threshold=degradation_threshold,
        recovery_threshold=recovery_threshold,
    )

    if outcome is AvailabilityOutcome.NO_EVIDENCE:
        return state

    if not state.availability_problem:
        if outcome is AvailabilityOutcome.POSITIVE:
            return AvailabilityConfirmationState()
        progress = state.degradation_progress + 1
        if progress >= degradation_threshold:
            return AvailabilityConfirmationState(availability_problem=True)
        return AvailabilityConfirmationState(degradation_progress=progress)

    if outcome is AvailabilityOutcome.NEGATIVE:
        return AvailabilityConfirmationState(availability_problem=True)
    progress = state.recovery_progress + 1
    if progress >= recovery_threshold:
        return AvailabilityConfirmationState()
    return AvailabilityConfirmationState(
        availability_problem=True,
        recovery_progress=progress,
    )


def _validate_threshold(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _validate_progress_bounds(
    state: AvailabilityConfirmationState,
    *,
    degradation_threshold: int,
    recovery_threshold: int,
) -> None:
    if state.degradation_progress > degradation_threshold:
        raise ValueError(
            "degradation_progress exceeds degradation_threshold"
        )
    if state.recovery_progress > recovery_threshold:
        raise ValueError(
            "recovery_progress exceeds recovery_threshold"
        )
