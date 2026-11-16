from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .binding import LogicalPathId
from .route_priority import (
    RoutePriorityMove,
    RoutePriorityPlanError,
    plan_route_priority_moves,
)


class RoutePriorityConvergenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RoutePriorityDeleteDuplicate:
    """Delete one already-observed redundant copy of an eligible path."""

    path_id: LogicalPathId
    metric: int


RoutePriorityConvergenceStep = RoutePriorityDeleteDuplicate | RoutePriorityMove


def plan_route_priority_convergence(
    observed: Mapping[LogicalPathId, Iterable[int]],
    desired: Mapping[LogicalPathId, int],
    working_metrics: Iterable[int],
) -> tuple[RoutePriorityConvergenceStep, ...]:
    """Plan recovery/convergence from one fresh owned-route observation.

    The priority-only contract requires identical logical-path membership.
    A path may be observed at multiple owned metrics after a partially
    completed make-before-break move.

    Duplicate cleanup is safe because it deletes only a copy of a path that
    remains represented by another already-observed copy. Once one metric per
    path remains, the existing RoutePriorityMove primitive is used. A Move is
    intentionally semantic: its Executor realization is add-new -> verify ->
    delete-old, not two independently replayable raw commands.

    After a partial execution failure the caller must discard the remaining
    steps, re-observe authoritative lower state and request a new plan.
    Returning a plan is never postcondition evidence.
    """
    state = _normalize_observed(observed)
    target = dict(desired)
    metrics = _validate_inputs(state, target, working_metrics)
    steps: list[RoutePriorityConvergenceStep] = []

    desired_owner = {
        metric: path_id
        for path_id, metric in target.items()
    }

    # Normalize a re-observed partial make-before-break state to exactly one
    # already-confirmed copy per path without ever deleting the last copy.
    while any(len(path_metrics) > 1 for path_metrics in state.values()):
        candidates: list[tuple[int, int, LogicalPathId, int]] = []

        for path_id in sorted(state):
            path_metrics = state[path_id]
            if len(path_metrics) <= 1:
                continue

            own_target = target[path_id]
            for metric in sorted(path_metrics):
                # If this path already owns its desired metric, never select
                # that desired copy as redundant.
                if metric == own_target:
                    continue

                owner = desired_owner.get(metric)
                blocks_other_target = owner is not None and owner != path_id

                # First free metrics desired by another path. Otherwise remove
                # the highest stale metric so the currently better copy is
                # retained while recovery continues.
                if blocks_other_target:
                    candidates.append((0, metric, path_id, metric))
                else:
                    candidates.append((1, -metric, path_id, metric))

        if not candidates:
            raise RoutePriorityConvergenceError(
                "duplicate normalization found no safely removable route copy"
            )

        _priority, _metric_key, path_id, metric = min(candidates)
        if len(state[path_id]) <= 1:
            raise RoutePriorityConvergenceError(
                f"refusing to delete the last observed route for {path_id!r}"
            )
        state[path_id].remove(metric)
        steps.append(RoutePriorityDeleteDuplicate(path_id=path_id, metric=metric))

    current = {
        path_id: next(iter(path_metrics))
        for path_id, path_metrics in state.items()
    }

    try:
        moves = plan_route_priority_moves(current, target, metrics)
    except RoutePriorityPlanError as exc:
        raise RoutePriorityConvergenceError(str(exc)) from exc

    steps.extend(moves)
    return tuple(steps)


def _normalize_observed(
    observed: Mapping[LogicalPathId, Iterable[int]],
) -> dict[LogicalPathId, set[int]]:
    state: dict[LogicalPathId, set[int]] = {}
    for path_id, raw_metrics in observed.items():
        values = tuple(raw_metrics)
        if any(type(metric) is not int or metric < 0 for metric in values):
            raise RoutePriorityConvergenceError(
                "observed route metrics must be non-negative integers"
            )
        if len(set(values)) != len(values):
            raise RoutePriorityConvergenceError(
                f"observed path {path_id!r} contains duplicate route metrics"
            )
        state[path_id] = set(values)
    return state


def _validate_inputs(
    state: dict[LogicalPathId, set[int]],
    desired: dict[LogicalPathId, int],
    working_metrics: Iterable[int],
) -> set[int]:
    if set(state) != set(desired):
        raise RoutePriorityConvergenceError(
            "pure-priority convergence requires identical observed and desired path membership"
        )

    metrics = set(working_metrics)
    if any(type(metric) is not int or metric < 0 for metric in metrics):
        raise RoutePriorityConvergenceError(
            "working metrics must be non-negative integers"
        )

    desired_values = tuple(desired.values())
    if any(type(metric) is not int or metric < 0 for metric in desired_values):
        raise RoutePriorityConvergenceError(
            "desired metrics must be non-negative integers"
        )
    if len(set(desired_values)) != len(desired_values):
        raise RoutePriorityConvergenceError(
            "desired assignment contains duplicate metrics"
        )

    outside_desired = sorted(set(desired_values) - metrics)
    if outside_desired:
        raise RoutePriorityConvergenceError(
            f"desired assignment uses metric outside owned working set: {outside_desired}"
        )

    occupied: dict[int, LogicalPathId] = {}
    for path_id in sorted(state):
        path_metrics = state[path_id]
        if not path_metrics:
            raise RoutePriorityConvergenceError(
                f"observed path {path_id!r} has no route; priority-only continuity is not provable"
            )

        outside = sorted(path_metrics - metrics)
        if outside:
            raise RoutePriorityConvergenceError(
                f"observed path {path_id!r} uses metric outside owned working set: {outside}"
            )

        for metric in sorted(path_metrics):
            other = occupied.get(metric)
            if other is not None and other != path_id:
                raise RoutePriorityConvergenceError(
                    f"owned metric {metric} is observed for multiple logical paths"
                )
            occupied[metric] = path_id

    return metrics
