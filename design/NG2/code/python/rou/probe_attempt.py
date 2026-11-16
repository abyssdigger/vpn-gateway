"""Standalone single-shot diagnostic probe contract.

This module is retained as executable evidence for the already-proven Linux probe process
mechanics. Production NG2 availability routing is not attempt-oriented and
AvailabilityProbeManager does not depend on this contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
class ProbeAttemptOutcome(str, Enum):
    REPLY = "reply"
    NO_REPLY = "no-reply"
    ERROR = "error"


@dataclass(frozen=True)
class ProbeAttemptResult:
    outcome: ProbeAttemptOutcome
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ProbeAttemptOutcome):
            raise ValueError(
                "probe attempt outcome must be ProbeAttemptOutcome"
            )
        if self.outcome is ProbeAttemptOutcome.ERROR:
            if not self.diagnostic:
                raise ValueError(
                    "probe execution error requires diagnostic"
                )
        elif self.diagnostic is not None:
            raise ValueError(
                "non-error probe result must not carry diagnostic"
            )


