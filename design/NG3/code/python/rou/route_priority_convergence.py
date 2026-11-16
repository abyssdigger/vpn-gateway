from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .binding import LogicalPathId


class RoutePriorityConvergenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RoutePriorityAdd:
    path_id: LogicalPathId
    metric: int


@dataclass(frozen=True, slots=True)
class RoutePriorityDelete:
    path_id: LogicalPathId
    metric: int


RoutePriorityMutation = RoutePriorityAdd | RoutePriorityDelete


def plan_route_priority_convergence(
    observed: Mapping[LogicalPathId, Iterable[int]],
    desired: Mapping[LogicalPathId, int],
    working_metrics: Iterable[int],
) -> tuple[RoutePriorityMutation, ...]:
    """Plan safe convergence from one fresh owned-route observation.

    The priority-only contract requires identical logical-path membership.
    A path may be observed at more than one owned metric after a partially
    completed make-before-break move. The returned mutations never delete
    the last observed route copy for an eligible path.

    The caller must execute the plan transactionally at its own boundary and
    re-observe authoritative state after any partial failure before asking for
    another plan. A returned plan is not postcondition evidence.
    """
    state = _normalize_observed(observed)
    target = dict(desired)
    metrics = _validate_inputs(state, target, working_metrics)
    mutations: list[RoutePriorityMutation] = []

    while not _is_desired(state, target):
        # If a path already owns its desired metric, every other copy is stale
        # for this pure-priority target and may be removed without breaking
        # path continuity.
        cleanup = sorted(
            (metric, path_id)
            for path_id, path_metrics in state.items()
            if target[path_id] in path_metrics and len(path_metrics) > 1
            for metric in path_metrics
            if metric != target[path_id]
        )
        if cleanup:
            metric, path_id = cleanup[0]
            _delete_copy(state, path_id, metric, mutations)
            continue

        occupied = _occupied_metrics(state)

        # A failed prior transaction may have left a duplicate copy occupying
        # another path's desired metric. If the occupant has another copy,
        # deleting this stale copy is already make-before-break safe and is
        # preferable to creating yet another scratch copy.
        unblock = sorted(
            (target[path_id], path_id, occupied[target[path_id]])
            for path_id in state
            if target[path_id] not in state[path_id]
            and target[path_id] in occupied
            and len(state[occupied[target[path_id]]]) > 1
        )
        if unblock:
            metric, _waiting_path, occupant = unblock[0]
            _delete_copy(state, occupant, metric, mutations)
            continue

        occupied = _occupied_metrics(state)
        free = sorted(metrics - set(occupied))

        # Prefer a desired metric that is already free.
        direct = sorted(
            (target[path_id], path_id)
            for path_id in state
            if target[path_id] not in state[path_id]
            and target[path_id] in free
        )
        if direct:
            metric, path_id = direct[0]
            _add_copy(state, path_id, metric, mutations)
            continue

        if not free:
            raise RoutePriorityConvergenceError(
                "priority convergence requires a free owned metric or a safely removable duplicate"
            )

        # Remaining mismatch is a cycle. Make one scratch copy of the path
        # occupying the lowest blocked desired metric. The next iteration can
        # safely remove the old copy and continue from the newly freed metric.
        blocked = sorted(
            (target[path_id], path_id, occupied[target[path_id]])
            for path_id in state
            if target[path_id] not in state[path_id]
            and target[path_id] in occupied
        )
        if not blocked:
            raise RoutePriorityConvergenceError(
                "convergence invariant failed: no progress candidate"
            )

        _blocked_metric, _waiting_path, occupant = blocked[0]
        _add_copy(state, occupant, free[0], mutations)

    return tuple(mutations)


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

    desired_outside = sorted(set(desired_values) - metrics)
    if desired_outside:
        raise RoutePriorityConvergenceError(
            f"desired assignment uses metric outside owned working set: {desired_outside}"
        )

    for path_id, path_metrics in state.items():
        if not path_metrics:
            raise RoutePriorityConvergenceError(
                f"observed path {path_id!r} has no route; priority-only continuity is not provable"
            )
        outside = sorted(path_metrics - metrics)
        if outside:
            raise RoutePriorityConvergenceError(
                f"observed path {path_id!r} uses metric outside owned working set: {outside}"
            )

    _occupied_metrics(state)
    return metrics


def _occupied_metrics(
    state: Mapping[LogicalPathId, set[int]],
) -> dict[int, LogicalPathId]:
    occupied: dict[int, LogicalPathId] = {}
    for path_id in sorted(state):
        for metric in sorted(state[path_id]):
            owner = occupied.get(metric)
            if owner is not None and owner != path_id:
                raise RoutePriorityConvergenceError(
                    f"owned metric {metric} is observed for multiple logical paths"
                )
            occupied[metric] = path_id
    return occupied


def _is_desired(
    state: Mapping[LogicalPathId, set[int]],
    desired: Mapping[LogicalPathId, int],
) -> bool:
    return all(state[path_id] == {desired[path_id]} for path_id in state)


def _add_copy(
    state: dict[LogicalPathId, set[int]],
    path_id: LogicalPathId,
    metric: int,
    mutations: list[RoutePriorityMutation],
) -> None:
    occupied = _occupied_metrics(state)
    if metric in occupied:
        raise RoutePriorityConvergenceError(
            f"add destination metric {metric} is not free"
        )
    state[path_id].add(metric)
    mutations.append(RoutePriorityAdd(path_id=path_id, metric=metric))


def _delete_copy(
    state: dict[LogicalPathId, set[int]],
    path_id: LogicalPathId,
    metric: int,
    mutations: list[RoutePriorityMutation],
) -> None:
    if metric not in state[path_id]:
        raise RoutePriorityConvergenceError(
            f"delete source metric {metric} is not observed for {path_id!r}"
        )
    if len(state[path_id]) <= 1:
        raise RoutePriorityConvergenceError(
            f"refusing to delete the last observed route for {path_id!r}"
        )
    state[path_id].remove(metric)
    mutations.append(RoutePriorityDelete(path_id=path_id, metric=metric))
