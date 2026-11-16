from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class AvailabilityProbePolicy:
    """Normalized per-logical-probe cadence and hysteresis policy.

    User-facing configuration parsing belongs above this type.  A request with policy=None
    remains manually driven through evaluate_once(); run_due() ignores it.
    """

    interval_seconds: float
    retry_interval_seconds: float
    timeout_seconds: int
    failure_threshold: int = 1
    recovery_threshold: int = 1

    def __post_init__(self) -> None:
        for name, value in (
            ("interval_seconds", self.interval_seconds),
            ("retry_interval_seconds", self.retry_interval_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a positive finite number")
            if not isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"{name} must be a positive finite number")

        if type(self.timeout_seconds) is not int or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive integer")

        for name, value in (
            ("failure_threshold", self.failure_threshold),
            ("recovery_threshold", self.recovery_threshold),
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
