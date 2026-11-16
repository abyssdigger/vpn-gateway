from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .interface_identity import InterfaceIdentity


@dataclass(frozen=True)
class AvailabilityChannelPolicy:
    """Routing-priority availability policy for one logical probe channel."""

    interval_seconds: float
    failure_ticks: int
    recovery_good_news: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.interval_seconds, bool)
            or not isinstance(self.interval_seconds, (int, float))
            or not isfinite(float(self.interval_seconds))
            or float(self.interval_seconds) <= 0
        ):
            raise ValueError("interval_seconds must be a positive finite number")
        if type(self.failure_ticks) is not int or self.failure_ticks <= 0:
            raise ValueError("failure_ticks must be a positive integer")
        if (
            type(self.recovery_good_news) is not int
            or self.recovery_good_news <= 0
        ):
            raise ValueError("recovery_good_news must be a positive integer")


@dataclass
class AvailabilityPendingInput:
    """Bounded colorless input accumulated while the collector is unavailable."""

    pending_good_news: int = 0
    tick_pending: bool = False

    def note_good_news(self, policy: AvailabilityChannelPolicy) -> None:
        if not isinstance(policy, AvailabilityChannelPolicy):
            raise ValueError("policy must be AvailabilityChannelPolicy")
        self.pending_good_news = min(
            self.pending_good_news + 1,
            policy.recovery_good_news,
        )

    def note_tick(self) -> None:
        self.tick_pending = True

    def take(self) -> tuple[int, bool]:
        result = (self.pending_good_news, self.tick_pending)
        self.pending_good_news = 0
        self.tick_pending = False
        return result

    def clear(self) -> None:
        self.pending_good_news = 0
        self.tick_pending = False


@dataclass
class AvailabilityChannelState:
    """Current routing-relevant availability state for one logical channel.

    availability_problems=False is both the initial state and the state of disabled
    probing. Availability is therefore only an optional negative priority modifier.
    """

    availability_problems: bool = False
    failure_misses: int = 0
    recovery_progress: int = 0
    good_news_since_tick: bool = False

    def __post_init__(self) -> None:
        if type(self.availability_problems) is not bool:
            raise ValueError("availability_problems must be boolean")
        if type(self.failure_misses) is not int or self.failure_misses < 0:
            raise ValueError("failure_misses must be a non-negative integer")
        if type(self.recovery_progress) is not int or self.recovery_progress < 0:
            raise ValueError("recovery_progress must be a non-negative integer")
        if type(self.good_news_since_tick) is not bool:
            raise ValueError("good_news_since_tick must be boolean")

    def reset_policy_progress(self) -> None:
        """Keep the routing flag but forget progress measured under an old policy."""

        self.failure_misses = 0
        self.recovery_progress = 0
        self.good_news_since_tick = False

    def disable(self) -> bool:
        """Disabled probing has no availability problems by definition."""

        changed = self.availability_problems
        self.availability_problems = False
        self.reset_policy_progress()
        return changed

    def process(
        self,
        policy: AvailabilityChannelPolicy,
        *,
        pending_good_news: int,
        tick_pending: bool,
    ) -> bool:
        """Apply one collector snapshot and report a routing-flag transition.

        Good-news multiplicity and a pending tick are deliberately unordered within
        this pass. Transition rules are selected from the state at entry so a
        simultaneous opposite-kind input cannot immediately reverse a transition.
        """

        if not isinstance(policy, AvailabilityChannelPolicy):
            raise ValueError("policy must be AvailabilityChannelPolicy")
        if type(pending_good_news) is not int or pending_good_news < 0:
            raise ValueError("pending_good_news must be a non-negative integer")
        if type(tick_pending) is not bool:
            raise ValueError("tick_pending must be boolean")

        pending_good_news = min(
            pending_good_news,
            policy.recovery_good_news,
        )
        previous = self.availability_problems

        if not previous:
            if pending_good_news:
                self.good_news_since_tick = True

            if tick_pending:
                if self.good_news_since_tick:
                    self.failure_misses = 0
                else:
                    self.failure_misses += 1
                    if self.failure_misses >= policy.failure_ticks:
                        self.availability_problems = True
                        self.recovery_progress = 0
                self.good_news_since_tick = False

            return self.availability_problems != previous

        # Problem state: every reply contributes independently to recovery.
        if pending_good_news:
            self.good_news_since_tick = True
            self.recovery_progress = min(
                self.recovery_progress + pending_good_news,
                policy.recovery_good_news,
            )
            if self.recovery_progress >= policy.recovery_good_news:
                self.availability_problems = False
                self.failure_misses = 0
                self.recovery_progress = 0

        if tick_pending:
            if not self.good_news_since_tick and self.availability_problems:
                self.recovery_progress = 0
            # A simultaneous tick never degrades a state just recovered by good news.
            self.good_news_since_tick = False

        return self.availability_problems != previous


def calculate_availability_path_order(
    configured_order: tuple[InterfaceIdentity, ...],
    current_order: tuple[InterfaceIdentity, ...],
    availability_problems: frozenset[InterfaceIdentity],
) -> tuple[InterfaceIdentity, ...]:
    """Promote paths without availability problems above paths with problems.

    Configured priority is authoritative within the no-problem prefix. Problem paths
    preserve their current relative order. If every path currently has problems there
    is no better path to promote, so relative order is unchanged.
    """

    if len(set(configured_order)) != len(configured_order):
        raise ValueError("configured_order contains duplicate paths")
    if len(set(current_order)) != len(current_order):
        raise ValueError("current_order contains duplicate paths")
    if set(configured_order) != set(current_order):
        raise ValueError(
            "configured_order and current_order must contain the same paths"
        )
    if not availability_problems <= set(configured_order):
        raise ValueError("availability_problems contains an unknown path")

    no_problem = set(configured_order) - set(availability_problems)
    if not no_problem:
        return current_order

    preferred_prefix = tuple(
        path
        for path in configured_order
        if path in no_problem
    )
    remainder = tuple(
        path
        for path in current_order
        if path in availability_problems
    )
    return preferred_prefix + remainder
