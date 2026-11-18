"""Bounded optional host-boundary lifecycle contribution for controller startup/stop."""

from __future__ import annotations

from typing import Protocol


class ControllerBoundaryContribution(Protocol):
    def converge(self) -> None:
        """Converge the complete boundary contribution or raise."""

    def cleanup(self) -> None:
        """Remove the contribution completely or raise."""
