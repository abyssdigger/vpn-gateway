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
        if self.degradation_progress < 0 or self.recovery_progress < 0:
            raise ValueError("availability confirmation progress must be non-negative")
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

    if outcome is AvailabilityOutcome.NO_EVIDENCE:
        return state

    if not state.availability_problem:
        if outcome is AvailabilityOutcome.POSITIVE:
            return AvailabilityConfirmationState()
        progress = min(degradation_threshold, state.degradation_progress + 1)
        if progress >= degradation_threshold:
            return AvailabilityConfirmationState(availability_problem=True)
        return AvailabilityConfirmationState(degradation_progress=progress)

    if outcome is AvailabilityOutcome.NEGATIVE:
        return AvailabilityConfirmationState(availability_problem=True)
    progress = min(recovery_threshold, state.recovery_progress + 1)
    if progress >= recovery_threshold:
        return AvailabilityConfirmationState()
    return AvailabilityConfirmationState(
        availability_problem=True,
        recovery_progress=progress,
    )


def _validate_threshold(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
