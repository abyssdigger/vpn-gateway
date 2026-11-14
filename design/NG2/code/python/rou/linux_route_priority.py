from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class RouteSlotMove:
    """One make-before-break move through the current free metric."""

    path: T
    source_slot: int
    target_slot: int


def route_slots(
    ordered_paths: tuple[T, ...],
    confirmed_live_count: int,
) -> tuple[T | None, ...]:
    """Build the N+1 working slot view for one availability state.

    None is only an operational representation of an unused metric position.

    If all paths are confirmed live, the unused working position is trailing and
    is not a steady-state "gap". Otherwise it is immediately before the first
    non-confirmed path. If no path is confirmed live, slot zero is unused and all
    paths start at the second metric position.
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
    """Plan a permutation by moving the free metric through the slot vector.

    Every elementary move is materialized as:

        add path at current free metric
        delete the path's old route

    Therefore the full eligible path set remains present at all times. Between
    the add and delete exactly one path is duplicated; after the delete the old
    source metric becomes the new free position.
    """

    if len(current_slots) != len(desired_slots):
        raise ValueError("current and desired slot counts differ")
    if current_slots.count(None) != 1 or desired_slots.count(None) != 1:
        raise ValueError(
            "current and desired working layouts require exactly one free slot"
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
        free = work.index(None)
        wanted = target[free]

        if wanted is None:
            # The free slot is already at its final position but another
            # permutation cycle remains. Open that cycle deterministically.
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
                target_slot=free,
            )
        )
        work[free] = path
        work[source] = None

    return tuple(moves)
