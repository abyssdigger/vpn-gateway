"""Lifecycle contract for optional ordinary-host routing contributions."""

from __future__ import annotations

from typing import Protocol


class HostRoutingContribution(Protocol):
    def converge(self) -> None:
        """Converge the complete host-routing contribution or raise."""

    def cleanup(self) -> None:
        """Remove the contribution completely or raise."""
