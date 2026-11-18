from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .availability_priority import calculate_effective_path_order
from .binding import LogicalPathId


@dataclass(frozen=True, slots=True)
class AvailabilityRoutingState:
    """Manager-owned bounded routing state for one Profile."""

    active_path: LogicalPathId | None = None


@dataclass(frozen=True, slots=True)
class AvailabilityRoutingProjection:
    """Pure result: next Manager state plus current effective order."""

    next_state: AvailabilityRoutingState
    effective_order: tuple[LogicalPathId, ...]


def project_availability_routing(
    configured_paths: Iterable[LogicalPathId],
    problem_paths: Iterable[LogicalPathId],
    previous: AvailabilityRoutingState,
    *,
    reserve_device_ids: Iterable[str] = (),
) -> AvailabilityRoutingProjection:
    """Project one Profile's sticky/reserve availability routing state.

    A previous active path that disappeared from current structural membership is
    treated as no longer active rather than as malformed caller input. Problem
    paths are still required to belong to current membership by the priority
    calculator.
    """
    configured = tuple(configured_paths)
    problems = tuple(problem_paths)
    configured_set = set(configured)

    current_active = (
        previous.active_path
        if previous.active_path in configured_set
        else None
    )
    effective_order = calculate_effective_path_order(
        configured,
        problems,
        active_path=current_active,
        reserve_device_ids=reserve_device_ids,
    )

    problem_set = frozenset(problems)
    next_active = next(
        (
            path_id
            for path_id in effective_order
            if path_id not in problem_set
        ),
        None,
    )
    return AvailabilityRoutingProjection(
        next_state=AvailabilityRoutingState(next_active),
        effective_order=effective_order,
    )
