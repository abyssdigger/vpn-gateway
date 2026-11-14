from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .probe_attempt import ProbeAttemptResult


class AvailabilityProbeState(str, Enum):
    UNKNOWN = "unknown"
    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True, order=True)
class ProbeObservationGeneration:
    """Manager-local rules-readiness epoch for authoritative probe evidence."""

    sequence: int

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence <= 0:
            raise ValueError(
                "probe observation generation sequence must be a positive integer"
            )


@dataclass(frozen=True)
class AvailabilityProbeStateInfo:
    probe_id: str
    state: AvailabilityProbeState
    reason: str | None = None
    observation_generation: ProbeObservationGeneration | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.probe_id, str) or not self.probe_id:
            raise ValueError("probe state info requires non-empty probe_id")
        if not isinstance(self.state, AvailabilityProbeState):
            raise ValueError("probe state info requires AvailabilityProbeState")
        if (
            self.observation_generation is not None
            and not isinstance(
                self.observation_generation,
                ProbeObservationGeneration,
            )
        ):
            raise ValueError(
                "probe state info observation_generation must be "
                "ProbeObservationGeneration or None"
            )

        if self.state is AvailabilityProbeState.UNKNOWN:
            if self.observation_generation is not None:
                raise ValueError(
                    "UNKNOWN probe state must not claim authoritative evidence generation"
                )
            return

        if self.observation_generation is None:
            raise ValueError(
                "reachable/unreachable probe state requires observation generation"
            )


@dataclass(frozen=True)
class ProbeAttemptObservation:
    """Raw attempt observation accepted inside one rules-readiness epoch."""

    probe_id: str
    observation_generation: ProbeObservationGeneration
    result: ProbeAttemptResult

    def __post_init__(self) -> None:
        if not isinstance(self.probe_id, str) or not self.probe_id:
            raise ValueError("probe attempt observation requires non-empty probe_id")
        if not isinstance(
            self.observation_generation,
            ProbeObservationGeneration,
        ):
            raise ValueError(
                "probe attempt observation requires ProbeObservationGeneration"
            )
        if not isinstance(self.result, ProbeAttemptResult):
            raise ValueError(
                "probe attempt observation requires ProbeAttemptResult"
            )
