from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class ProbeObservationGeneration:
    """Physical ProbeRules/readiness generation for stale-worker rejection."""

    sequence: int

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence <= 0:
            raise ValueError(
                "probe observation generation sequence must be a positive integer"
            )
