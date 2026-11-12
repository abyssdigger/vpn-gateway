from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .device_engine import InterfaceIdentity
from .domain import Availability


class ProbeOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class AvailabilityPolicy:
    """Protocol-neutral hysteresis thresholds.

    Values are deliberately mandatory. Production DeviceManager configuration has not yet
    selected user-facing defaults for cadence, probe target or thresholds.
    """

    failure_threshold: int
    recovery_threshold: int

    def __post_init__(self) -> None:
        if self.failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if self.recovery_threshold <= 0:
            raise ValueError("recovery_threshold must be positive")


@dataclass(frozen=True)
class InterfaceAvailabilityState:
    availability: Availability = Availability.UNKNOWN
    success_streak: int = 0
    failure_streak: int = 0

    def __post_init__(self) -> None:
        if self.success_streak < 0:
            raise ValueError("success_streak must be non-negative")
        if self.failure_streak < 0:
            raise ValueError("failure_streak must be non-negative")
        if self.success_streak and self.failure_streak:
            raise ValueError(
                "success_streak and failure_streak cannot both be non-zero"
            )


@dataclass(frozen=True)
class AvailabilityTrackerState:
    by_interface: Mapping[InterfaceIdentity, InterfaceAvailabilityState]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "by_interface",
            MappingProxyType(dict(self.by_interface)),
        )

    @classmethod
    def empty(cls) -> "AvailabilityTrackerState":
        return cls({})


@dataclass(frozen=True)
class AvailabilityUpdate:
    next_state: AvailabilityTrackerState
    availability: Mapping[InterfaceIdentity, Availability]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "availability",
            MappingProxyType(dict(self.availability)),
        )


def _advance_one(
    previous: InterfaceAvailabilityState,
    outcome: ProbeOutcome,
    policy: AvailabilityPolicy,
) -> InterfaceAvailabilityState:
    if outcome is ProbeOutcome.INDETERMINATE:
        return previous

    if outcome is ProbeOutcome.SUCCESS:
        success_streak = min(
            previous.success_streak + 1,
            policy.recovery_threshold,
        )
        availability = previous.availability
        if success_streak >= policy.recovery_threshold:
            availability = Availability.AVAILABLE
        return InterfaceAvailabilityState(
            availability=availability,
            success_streak=success_streak,
            failure_streak=0,
        )

    failure_streak = min(
        previous.failure_streak + 1,
        policy.failure_threshold,
    )
    availability = previous.availability
    if failure_streak >= policy.failure_threshold:
        availability = Availability.UNAVAILABLE
    return InterfaceAvailabilityState(
        availability=availability,
        success_streak=0,
        failure_streak=failure_streak,
    )


def reconcile_availability(
    previous: AvailabilityTrackerState,
    observed_interfaces: tuple[InterfaceIdentity, ...],
    evidence: Mapping[InterfaceIdentity, ProbeOutcome],
    policy: AvailabilityPolicy,
) -> AvailabilityUpdate:
    """Advance availability for one fresh interface generation snapshot.

    State is keyed by concrete (ifname, ifindex). Disappearing generations are forgotten;
    same-name/new-ifindex starts UNKNOWN. Missing evidence is equivalent to INDETERMINATE
    and never creates positive AVAILABLE/UNAVAILABLE evidence.

    INDETERMINATE freezes the previous hysteresis state; it represents "no decisive path
    evidence in this sample", not a failed/stalled detector. A future DeviceManager must
    supervise detector freshness separately and must not feed an indefinitely silent
    detector through this API as harmless INDETERMINATE evidence.

    This is pure normalized state logic. It does not choose how a Device is probed, how
    often probes run, what target is used, or how detector-staleness is supervised.
    """

    observed = tuple(observed_interfaces)
    if len(set(observed)) != len(observed):
        raise ValueError("observed_interfaces contains duplicate identity")

    observed_set = set(observed)
    unexpected = set(evidence) - observed_set
    if unexpected:
        raise ValueError(
            "probe evidence contains unobserved interface generation(s): "
            + repr(sorted(unexpected))
        )

    next_map: dict[InterfaceIdentity, InterfaceAvailabilityState] = {}
    availability: dict[InterfaceIdentity, Availability] = {}

    for identity in observed:
        old = previous.by_interface.get(
            identity,
            InterfaceAvailabilityState(),
        )
        outcome = evidence.get(
            identity,
            ProbeOutcome.INDETERMINATE,
        )
        current = _advance_one(old, outcome, policy)
        next_map[identity] = current
        availability[identity] = current.availability

    return AvailabilityUpdate(
        next_state=AvailabilityTrackerState(next_map),
        availability=availability,
    )
