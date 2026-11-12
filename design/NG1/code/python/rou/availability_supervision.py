from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from .availability import (
    AvailabilityPolicy,
    AvailabilityTrackerState,
    AvailabilityUpdate,
    ProbeOutcome,
    reconcile_availability,
)
from .device_engine import InterfaceIdentity
from .domain import Availability


class DetectorSupervisionError(RuntimeError):
    pass


class DetectorEvidenceMissing(DetectorSupervisionError):
    pass


class DetectorEvidenceStale(DetectorSupervisionError):
    pass


class DetectorEvidenceRegression(DetectorSupervisionError):
    pass


@dataclass(frozen=True)
class DetectorFreshnessPolicy:
    """Maximum accepted age of one detector sample.

    No default is provided because cadence/freshness are future DeviceManager product
    policy. The pure supervision layer only validates an explicitly supplied contract.
    """

    max_age_seconds: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_age_seconds, bool)
            or not isinstance(self.max_age_seconds, (int, float))
            or not math.isfinite(self.max_age_seconds)
            or self.max_age_seconds <= 0
        ):
            raise ValueError(
                "max_age_seconds must be a finite positive number"
            )


@dataclass(frozen=True)
class TimedProbeSample:
    outcome: ProbeOutcome
    monotonic_time: float
    sample_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ProbeOutcome):
            raise ValueError("outcome must be ProbeOutcome")
        if (
            isinstance(self.monotonic_time, bool)
            or not isinstance(self.monotonic_time, (int, float))
            or not math.isfinite(self.monotonic_time)
            or self.monotonic_time < 0
        ):
            raise ValueError(
                "monotonic_time must be a finite non-negative number"
            )
        if (
            isinstance(self.sample_id, bool)
            or type(self.sample_id) is not int
            or self.sample_id < 0
        ):
            raise ValueError("sample_id must be a non-negative integer")


@dataclass(frozen=True)
class FreshEvidence:
    outcomes: Mapping[InterfaceIdentity, ProbeOutcome]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "outcomes",
            MappingProxyType(dict(self.outcomes)),
        )


@dataclass(frozen=True)
class SupervisedAvailabilityState:
    tracker: AvailabilityTrackerState
    last_samples: Mapping[InterfaceIdentity, TimedProbeSample]

    def __post_init__(self) -> None:
        samples = dict(self.last_samples)
        if set(samples) != set(self.tracker.by_interface):
            raise ValueError(
                "last_samples and tracker must contain identical interface generations"
            )
        object.__setattr__(
            self,
            "last_samples",
            MappingProxyType(samples),
        )

    @classmethod
    def empty(cls) -> "SupervisedAvailabilityState":
        return cls(AvailabilityTrackerState.empty(), {})


@dataclass(frozen=True)
class SupervisedAvailabilityUpdate:
    next_state: SupervisedAvailabilityState
    availability: Mapping[InterfaceIdentity, Availability]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "availability",
            MappingProxyType(dict(self.availability)),
        )


def require_fresh_evidence(
    tracked_interfaces: tuple[InterfaceIdentity, ...],
    samples: Mapping[InterfaceIdentity, TimedProbeSample],
    *,
    now_monotonic: float,
    policy: DetectorFreshnessPolicy,
) -> FreshEvidence:
    """Validate detector freshness for every currently tracked interface generation.

    This function deliberately does not translate missing/stale detector evidence into an
    Availability value. It surfaces supervision failure explicitly so a future
    DeviceManager/runtime policy can decide the containment behavior.

    Samples for no-longer-tracked generations are ignored: concrete interface identity
    ownership remains with DeviceEngine, and stale historical samples must never transfer
    to a fresh same-name/new-ifindex generation.

    Sample timestamps and sample IDs are process-local ephemeral supervision state. They
    must never be persisted/reused across process restart or reboot. A restarted detector
    must establish fresh samples for current interface generations.
    """

    if (
        isinstance(now_monotonic, bool)
        or not isinstance(now_monotonic, (int, float))
        or not math.isfinite(now_monotonic)
        or now_monotonic < 0
    ):
        raise ValueError(
            "now_monotonic must be a finite non-negative number"
        )

    tracked = tuple(tracked_interfaces)
    if len(set(tracked)) != len(tracked):
        raise ValueError("tracked_interfaces contains duplicate identity")

    outcomes: dict[InterfaceIdentity, ProbeOutcome] = {}
    for identity in tracked:
        sample = samples.get(identity)
        if sample is None:
            raise DetectorEvidenceMissing(
                f"no detector sample for interface generation {identity!r}"
            )

        age = now_monotonic - sample.monotonic_time
        if age < 0:
            raise DetectorSupervisionError(
                "detector sample timestamp is in the future for "
                f"{identity!r}"
            )
        if age > policy.max_age_seconds:
            raise DetectorEvidenceStale(
                "detector sample is stale for "
                f"{identity!r}: age={age:.6f}s "
                f"max={policy.max_age_seconds:.6f}s"
            )

        outcomes[identity] = sample.outcome

    return FreshEvidence(outcomes)


def reconcile_supervised_availability(
    previous: SupervisedAvailabilityState,
    tracked_interfaces: tuple[InterfaceIdentity, ...],
    samples: Mapping[InterfaceIdentity, TimedProbeSample],
    *,
    now_monotonic: float,
    freshness_policy: DetectorFreshnessPolicy,
    availability_policy: AvailabilityPolicy,
) -> SupervisedAvailabilityUpdate:
    """Compose freshness proof with exactly-once probe evidence consumption.

    Freshness is checked first. Each interface's sample_id is then compared with the last
    consumed id for that concrete interface generation:

    - larger id: consume one new evidence outcome;
    - equal id: accept only an identical sample and do not advance hysteresis;
    - smaller id: explicit detector evidence regression error.

    A new id may not carry an older monotonic timestamp. This prevents a detector from
    refreshing stale evidence by mutating/reissuing an old sample identity.

    The caller still owns the policy consequence of DetectorSupervisionError. This helper
    deliberately does not stop forwarding, demote a path, retry a detector or persist
    detector supervision state.
    """

    fresh = require_fresh_evidence(
        tracked_interfaces,
        samples,
        now_monotonic=now_monotonic,
        policy=freshness_policy,
    )

    evidence_to_consume: dict[InterfaceIdentity, ProbeOutcome] = {}
    next_samples: dict[InterfaceIdentity, TimedProbeSample] = {}

    for identity in tracked_interfaces:
        sample = samples[identity]
        previous_sample = previous.last_samples.get(identity)
        if previous_sample is not None:
            if sample.sample_id < previous_sample.sample_id:
                raise DetectorEvidenceRegression(
                    "detector sample id regressed for "
                    f"{identity!r}: previous={previous_sample.sample_id} "
                    f"current={sample.sample_id}"
                )
            if sample.sample_id == previous_sample.sample_id:
                if sample != previous_sample:
                    raise DetectorEvidenceRegression(
                        "detector reused sample id with different content for "
                        f"{identity!r}: sample_id={sample.sample_id}"
                    )
                evidence_to_consume[identity] = ProbeOutcome.INDETERMINATE
                next_samples[identity] = previous_sample
                continue
            if sample.monotonic_time < previous_sample.monotonic_time:
                raise DetectorEvidenceRegression(
                    "detector sample time regressed for "
                    f"{identity!r}: previous={previous_sample.monotonic_time:.6f} "
                    f"current={sample.monotonic_time:.6f}"
                )

        evidence_to_consume[identity] = fresh.outcomes[identity]
        next_samples[identity] = sample

    update: AvailabilityUpdate = reconcile_availability(
        previous.tracker,
        tracked_interfaces,
        evidence_to_consume,
        availability_policy,
    )
    return SupervisedAvailabilityUpdate(
        next_state=SupervisedAvailabilityState(
            tracker=update.next_state,
            last_samples=next_samples,
        ),
        availability=update.availability,
    )
