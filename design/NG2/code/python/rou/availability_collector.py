from __future__ import annotations

from dataclasses import dataclass

from .interface_identity import InterfaceIdentity


@dataclass(frozen=True)
class AvailabilityHysteresisPolicy:
    """Payload-priority hysteresis; intentionally independent of probe cadence."""

    failure_ticks: int
    recovery_good_news: int

    def __post_init__(self) -> None:
        if type(self.failure_ticks) is not int or self.failure_ticks <= 0:
            raise ValueError("failure_ticks must be a positive integer")
        if (
            type(self.recovery_good_news) is not int
            or self.recovery_good_news <= 0
        ):
            raise ValueError("recovery_good_news must be a positive integer")


@dataclass(frozen=True)
class AvailabilityPriorityChannel:
    """Probe-independent channel description consumed by payload priority."""

    channel_id: str
    path: InterfaceIdentity
    enabled: bool
    policy: AvailabilityHysteresisPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.channel_id, str) or not self.channel_id:
            raise ValueError("availability channel_id must be non-empty")
        if not isinstance(self.path, InterfaceIdentity):
            raise ValueError("availability channel path must be InterfaceIdentity")
        if type(self.enabled) is not bool:
            raise ValueError("availability channel enabled must be boolean")
        if not isinstance(self.policy, AvailabilityHysteresisPolicy):
            raise ValueError(
                "availability channel policy must be AvailabilityHysteresisPolicy"
            )


@dataclass(frozen=True)
class ProfileAvailabilityAssignment:
    profile_name: str
    channel_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profile_name, str) or not self.profile_name:
            raise ValueError(
                "availability assignment requires non-empty profile_name"
            )
        if any(
            not isinstance(item, str) or not item
            for item in self.channel_ids
        ):
            raise ValueError(
                "availability assignment requires non-empty channel_id values"
            )
        if len(set(self.channel_ids)) != len(self.channel_ids):
            raise ValueError(
                "availability assignment contains duplicate channel_id"
            )


@dataclass(frozen=True)
class AvailabilityPriorityConfig:
    channels: tuple[AvailabilityPriorityChannel, ...]
    assignments: tuple[ProfileAvailabilityAssignment, ...]

    def __post_init__(self) -> None:
        ids = [item.channel_id for item in self.channels]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate availability channel_id")

        profile_names = [item.profile_name for item in self.assignments]
        if len(set(profile_names)) != len(profile_names):
            raise ValueError("duplicate Profile availability assignment")

        known = set(ids)
        for assignment in self.assignments:
            missing = set(assignment.channel_ids) - known
            if missing:
                raise ValueError(
                    f"Profile {assignment.profile_name!r} references "
                    "unknown availability channel_id: "
                    + ", ".join(sorted(missing))
                )


@dataclass(frozen=True)
class AvailabilityGoodNews:
    channel_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.channel_id, str) or not self.channel_id:
            raise ValueError("good news requires non-empty channel_id")


@dataclass(frozen=True)
class AvailabilityTick:
    channel_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.channel_id, str) or not self.channel_id:
            raise ValueError("tick requires non-empty channel_id")


@dataclass
class AvailabilityPendingInput:
    """Bounded colorless input accumulated while the collector is unavailable."""

    pending_good_news: int = 0
    tick_pending: bool = False

    def note_good_news(self, policy: AvailabilityHysteresisPolicy) -> None:
        if not isinstance(policy, AvailabilityHysteresisPolicy):
            raise ValueError(
                "policy must be AvailabilityHysteresisPolicy"
            )
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
    """Current optional negative priority modifier for one channel."""

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
        self.failure_misses = 0
        self.recovery_progress = 0
        self.good_news_since_tick = False

    def disable(self) -> bool:
        changed = self.availability_problems
        self.availability_problems = False
        self.reset_policy_progress()
        return changed

    def process(
        self,
        policy: AvailabilityHysteresisPolicy,
        *,
        pending_good_news: int,
        tick_pending: bool,
    ) -> bool:
        if not isinstance(policy, AvailabilityHysteresisPolicy):
            raise ValueError(
                "policy must be AvailabilityHysteresisPolicy"
            )
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
            self.good_news_since_tick = False

        return self.availability_problems != previous


def calculate_availability_path_order(
    configured_order: tuple[InterfaceIdentity, ...],
    current_order: tuple[InterfaceIdentity, ...],
    availability_problems: frozenset[InterfaceIdentity],
) -> tuple[InterfaceIdentity, ...]:
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
        path for path in configured_order if path in no_problem
    )
    remainder = tuple(
        path for path in current_order if path in availability_problems
    )
    return preferred_prefix + remainder
