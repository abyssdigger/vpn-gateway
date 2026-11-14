from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class RouteSlotMove:
    """Move one path through the implicit empty metric slot.

    Materialization is make-before-break: add the path at target_slot first,
    then delete its old route at source_slot. The source slot consequently
    becomes the next empty slot.
    """

    path: T
    source_slot: int
    target_slot: int


def route_slots(
    ordered_paths: tuple[T, ...],
    confirmed_live_count: int,
) -> tuple[T | None, ...]:
    """Return N+1 working slots for one route-priority projection.

    None is not a configured object or a route. It denotes the one unused
    metric position immediately before the first non-confirmed path. If all
    paths are confirmed live, the unused working position is trailing and is
    outside the steady route projection.
    """

    if type(confirmed_live_count) is not int:
        raise ValueError("confirmed_live_count must be an integer")
    if not 0 <= confirmed_live_count <= len(ordered_paths):
        raise ValueError("confirmed_live_count is out of range")
    if len(set(ordered_paths)) != len(ordered_paths):
        raise ValueError("ordered_paths contains duplicates")

    return (
        ordered_paths[:confirmed_live_count]
        + (None,)
        + ordered_paths[confirmed_live_count:]
    )


def plan_route_slot_moves(
    current_slots: tuple[T | None, ...],
    desired_slots: tuple[T | None, ...],
) -> tuple[RouteSlotMove, ...]:
    """Plan a permutation using only the implicit empty metric slot.

    Each returned move preserves the complete path set: the moving path is
    first duplicated into the current empty slot and only then removed from
    its old slot. At most one path is duplicated at a time.

    A permutation cycle that does not initially touch the empty slot is opened
    by temporarily copying one misplaced path into the empty slot; normal
    empty-slot chasing then completes that cycle.
    """

    if len(current_slots) != len(desired_slots):
        raise ValueError("current and desired slot counts differ")
    if current_slots.count(None) != 1 or desired_slots.count(None) != 1:
        raise ValueError(
            "current and desired layouts require exactly one empty slot"
        )

    current_paths = tuple(item for item in current_slots if item is not None)
    desired_paths = tuple(item for item in desired_slots if item is not None)
    if len(set(current_paths)) != len(current_paths):
        raise ValueError("current layout contains duplicate paths")
    if len(set(desired_paths)) != len(desired_paths):
        raise ValueError("desired layout contains duplicate paths")
    if set(current_paths) != set(desired_paths):
        raise ValueError("current and desired layouts contain different paths")

    work = list(current_slots)
    target = list(desired_slots)
    moves: list[RouteSlotMove] = []

    while work != target:
        empty = work.index(None)
        wanted = target[empty]

        if wanted is None:
            source = next(
                index
                for index, (actual, expected) in enumerate(zip(work, target))
                if actual is not None and actual != expected
            )
            path = work[source]
            assert path is not None
        else:
            path = wanted
            source = work.index(path)

        moves.append(
            RouteSlotMove(
                path=path,
                source_slot=source,
                target_slot=empty,
            )
        )
        work[empty] = path
        work[source] = None

    return tuple(moves)
