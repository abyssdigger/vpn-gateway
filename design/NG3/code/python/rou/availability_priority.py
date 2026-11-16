from __future__ import annotations

from typing import Iterable

from .binding import LogicalPathId


class AvailabilityPriorityError(ValueError):
    pass


def calculate_effective_path_order(
    configured_paths: Iterable[LogicalPathId],
    problem_paths: Iterable[LogicalPathId],
) -> tuple[LogicalPathId, ...]:
    """Apply established availability problems as a stable negative priority modifier."""
    configured = tuple(configured_paths)
    problems_input = tuple(problem_paths)

    if len(set(configured)) != len(configured):
        raise AvailabilityPriorityError(
            "configured path order contains duplicate logical path IDs"
        )
    if len(set(problems_input)) != len(problems_input):
        raise AvailabilityPriorityError(
            "problem path set contains duplicate logical path IDs"
        )

    configured_set = set(configured)
    problems = frozenset(problems_input)
    unknown = problems - configured_set
    if unknown:
        raise AvailabilityPriorityError(
            f"problem paths are outside configured membership: {sorted(unknown)!r}"
        )

    return tuple(
        path_id for path_id in configured if path_id not in problems
    ) + tuple(
        path_id for path_id in configured if path_id in problems
    )
