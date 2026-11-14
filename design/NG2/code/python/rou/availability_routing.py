from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .interface_identity import InterfaceIdentity


@dataclass(frozen=True)
class AvailabilityWindowPolicy:
    """Minimal normalized active-probe timing policy.

    interval_seconds defines the observation window. failure_intervals is the
    number of consecutive windows without good news required to stop treating a
    path as confirmed live. A positive reply never needs a recovery threshold.
    """

    interval_seconds: float
    failure_intervals: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.interval_seconds, bool)
            or not isinstance(self.interval_seconds, (int, float))
            or not isfinite(float(self.interval_seconds))
            or float(self.interval_seconds) <= 0
        ):
            raise ValueError(
                "interval_seconds must be a positive finite number"
            )
        if (
            type(self.failure_intervals) is not int
            or self.failure_intervals <= 0
        ):
            raise ValueError(
                "failure_intervals must be a positive integer"
            )
@dataclass
class AvailabilityWindowState:
    """Routing-relevant evidence for one configured probe.

    No attempt identity is retained. Any valid reply is good news immediately.
    Negative evidence is only the integral count of closed windows without good
    news.
    """

    confirmed_live: bool = False
    missed_intervals: int = 0
    good_news_since_boundary: bool = False

    def note_good_news(self) -> None:
        self.good_news_since_boundary = True
        self.missed_intervals = 0
        self.confirmed_live = True

    def close_interval(self, policy: AvailabilityWindowPolicy) -> bool:
        """Close one observation window and return whether live state changed."""

        if not isinstance(policy, AvailabilityWindowPolicy):
            raise ValueError(
                "policy must be an AvailabilityWindowPolicy"
            )

        previous = self.confirmed_live

        if self.good_news_since_boundary:
            self.good_news_since_boundary = False
            self.missed_intervals = 0
            self.confirmed_live = True
            return self.confirmed_live != previous

        self.missed_intervals += 1
        if self.missed_intervals >= policy.failure_intervals:
            self.confirmed_live = False

        return self.confirmed_live != previous


def calculate_effective_path_order(
    configured_order: tuple[InterfaceIdentity, ...],
    current_order: tuple[InterfaceIdentity, ...],
    confirmed_live: frozenset[InterfaceIdentity],
) -> tuple[InterfaceIdentity, ...]:
    """Bubble confirmed-live paths above paths without positive evidence.

    Confirmed-live paths use configured priority. All remaining paths preserve
    their current relative order. With no confirmed-live path, probing makes no
    routing change.
    """

    if len(set(configured_order)) != len(configured_order):
        raise ValueError("configured_order contains duplicate paths")
    if len(set(current_order)) != len(current_order):
        raise ValueError("current_order contains duplicate paths")
    if set(configured_order) != set(current_order):
        raise ValueError(
            "configured_order and current_order must contain the same paths"
        )
    if not confirmed_live <= set(configured_order):
        raise ValueError("confirmed_live contains an unknown path")

    if not confirmed_live:
        return current_order

    live_prefix = tuple(
        path
        for path in configured_order
        if path in confirmed_live
    )
    remainder = tuple(
        path
        for path in current_order
        if path not in confirmed_live
    )
    return live_prefix + remainder
