from __future__ import annotations

from typing import Iterable

from .binding import LogicalPathId


class AvailabilityPriorityError(ValueError):
    pass


def calculate_effective_path_order(
    configured_paths: Iterable[LogicalPathId],
    problem_paths: Iterable[LogicalPathId],
    *,
    active_path: LogicalPathId | None = None,
    reserve_paths: Iterable[LogicalPathId] = (),
) -> tuple[LogicalPathId, ...]:
    """Calculate sticky availability order without per-flow state.

    The caller owns the current Profile-level active path. Ordinary active paths
    stay first while usable. A reserve active path yields to any usable path
    with higher configured baseline preference.
    """
    configured = tuple(configured_paths)
    problems_input = tuple(problem_paths)
    reserve_input = tuple(reserve_paths)

    if len(set(configured)) != len(configured):
        raise AvailabilityPriorityError(
            "configured path order contains duplicate logical path IDs"
        )
    if len(set(problems_input)) != len(problems_input):
        raise AvailabilityPriorityError(
            "problem path set contains duplicate logical path IDs"
        )
    if len(set(reserve_input)) != len(reserve_input):
        raise AvailabilityPriorityError(
            "reserve path set contains duplicate logical path IDs"
        )

    configured_set = set(configured)
    problems = frozenset(problems_input)
    reserves = frozenset(reserve_input)

    unknown_problems = problems - configured_set
    if unknown_problems:
        raise AvailabilityPriorityError(
            "problem paths are outside configured membership: "
            f"{sorted(unknown_problems)!r}"
        )

    unknown_reserves = reserves - configured_set
    if unknown_reserves:
        raise AvailabilityPriorityError(
            "reserve paths are outside configured membership: "
            f"{sorted(unknown_reserves)!r}"
        )

    if active_path is not None and active_path not in configured_set:
        raise AvailabilityPriorityError(
            f"active path is outside configured membership: {active_path!r}"
        )

    usable = tuple(path_id for path_id in configured if path_id not in problems)
    problem_tail = tuple(path_id for path_id in configured if path_id in problems)

    if active_path is None or active_path in problems:
        usable_order = usable
    elif active_path not in reserves:
        usable_order = (active_path,) + tuple(
            path_id for path_id in usable if path_id != active_path
        )
    else:
        active_index = configured.index(active_path)
        higher_usable_exists = any(
            index < active_index and path_id not in problems
            for index, path_id in enumerate(configured)
        )
        if higher_usable_exists:
            usable_order = usable
        else:
            usable_order = (active_path,) + tuple(
                path_id for path_id in usable if path_id != active_path
            )

    return usable_order + problem_tail
