from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from .availability import ProbeOutcome
from .device_engine import InterfaceIdentity


class DetectorSupervisionError(RuntimeError):
    pass


class DetectorEvidenceMissing(DetectorSupervisionError):
    pass


class DetectorEvidenceStale(DetectorSupervisionError):
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


@dataclass(frozen=True)
class FreshEvidence:
    outcomes: Mapping[InterfaceIdentity, ProbeOutcome]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "outcomes",
            MappingProxyType(dict(self.outcomes)),
        )


def require_fresh_evidence(
    observed_interfaces: tuple[InterfaceIdentity, ...],
    samples: Mapping[InterfaceIdentity, TimedProbeSample],
    *,
    now_monotonic: float,
    policy: DetectorFreshnessPolicy,
) -> FreshEvidence:
    """Validate detector freshness for every currently observed interface generation.

    This function deliberately does not translate missing/stale detector evidence into an
    Availability value. It surfaces supervision failure explicitly so a future
    DeviceManager/runtime policy can decide the containment behavior.

    Samples for no-longer-observed generations are ignored: concrete interface identity
    ownership remains with DeviceEngine, and stale historical samples must never transfer
    to a fresh same-name/new-ifindex generation.

    Sample timestamps are process-local monotonic-clock values. They are ephemeral
    supervision state and must never be persisted/reused across process restart or reboot.
    A restarted detector must establish fresh samples for current interface generations.
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

    observed = tuple(observed_interfaces)
    if len(set(observed)) != len(observed):
        raise ValueError("observed_interfaces contains duplicate identity")

    outcomes: dict[InterfaceIdentity, ProbeOutcome] = {}
    for identity in observed:
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
