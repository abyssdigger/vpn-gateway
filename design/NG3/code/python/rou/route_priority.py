from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .binding import LogicalPathId


class RoutePriorityPlanError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RoutePriorityMove:
    path_id: LogicalPathId
    from_metric: int
    to_metric: int


def plan_route_priority_moves(
    current: Mapping[LogicalPathId, int],
    desired: Mapping[LogicalPathId, int],
    working_metrics: Iterable[int],
) -> tuple[RoutePriorityMove, ...]:
    """Plan make-before-break moves for one pure-priority assignment change."""
    now = dict(current)
    target = dict(desired)
    metrics = _validate_inputs(now, target, working_metrics)
    moves: list[RoutePriorityMove] = []

    while now != target:
        occupied = {metric: path_id for path_id, metric in now.items()}
        free = sorted(metrics - set(occupied))

        direct = sorted(
            (target_metric, path_id)
            for path_id, target_metric in target.items()
            if now[path_id] != target_metric and target_metric in free
        )
        if direct:
            to_metric, path_id = direct[0]
            _move(now, path_id, to_metric, moves)
            continue

        if not free:
            raise RoutePriorityPlanError(
                "priority permutation requires a currently free owned metric"
            )

        scratch = free[0]
        mismatched_targets = sorted(
            (target_metric, path_id)
            for path_id, target_metric in target.items()
            if now[path_id] != target_metric
        )
        if not mismatched_targets:
            break
        blocked_metric, _desired_path = mismatched_targets[0]
        occupant = occupied.get(blocked_metric)
        if occupant is None:
            raise RoutePriorityPlanError(
                "planner invariant failed: desired free metric was not selected"
            )
        _move(now, occupant, scratch, moves)

    if now != target:
        raise RoutePriorityPlanError("planner failed to reach desired assignment")
    return tuple(moves)


def _move(
    state: dict[LogicalPathId, int],
    path_id: LogicalPathId,
    to_metric: int,
    moves: list[RoutePriorityMove],
) -> None:
    occupied = set(state.values())
    if to_metric in occupied:
        raise RoutePriorityPlanError(
            f"move destination metric {to_metric} is not free"
        )
    from_metric = state[path_id]
    moves.append(RoutePriorityMove(path_id, from_metric, to_metric))
    state[path_id] = to_metric


def _validate_inputs(
    current: dict[LogicalPathId, int],
    desired: dict[LogicalPathId, int],
    working_metrics: Iterable[int],
) -> set[int]:
    if set(current) != set(desired):
        raise RoutePriorityPlanError(
            "pure-priority plan requires identical current and desired path membership"
        )

    metrics = set(working_metrics)
    if any(type(metric) is not int or metric < 0 for metric in metrics):
        raise RoutePriorityPlanError("working metrics must be non-negative integers")

    for name, assignment in (("current", current), ("desired", desired)):
        values = tuple(assignment.values())
        if any(type(metric) is not int or metric < 0 for metric in values):
            raise RoutePriorityPlanError(
                f"{name} metrics must be non-negative integers"
            )
        if len(set(values)) != len(values):
            raise RoutePriorityPlanError(
                f"{name} assignment contains duplicate metrics"
            )
        outside = sorted(set(values) - metrics)
        if outside:
            raise RoutePriorityPlanError(
                f"{name} assignment uses metric outside owned working set: {outside}"
            )

    return metrics
