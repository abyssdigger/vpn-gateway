from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol

from .binding import LogicalPathId
from .route_priority import RoutePriorityMove
from .route_priority_convergence import (
    RoutePriorityConvergenceStep,
    RoutePriorityDeleteDuplicate,
    plan_route_priority_convergence,
)


@dataclass(frozen=True, slots=True)
class RoutePrioritySnapshot:
    """One authoritative normalized observation of owned priority routes."""

    routes: Mapping[LogicalPathId, frozenset[int]]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "routes",
            MappingProxyType(
                {
                    path_id: frozenset(metrics)
                    for path_id, metrics in self.routes.items()
                }
            ),
        )

    @classmethod
    def build(
        cls,
        routes: Mapping[LogicalPathId, Iterable[int]],
    ) -> "RoutePrioritySnapshot":
        return cls(
            {
                path_id: frozenset(metrics)
                for path_id, metrics in routes.items()
            }
        )


class RoutePriorityBackend(Protocol):
    """Physical boundary used by one priority-only convergence attempt."""

    def observe_route_priority(self) -> RoutePrioritySnapshot:
        """Return a fresh authoritative owned-route snapshot."""

    def delete_duplicate_route(
        self,
        step: RoutePriorityDeleteDuplicate,
    ) -> None:
        """Delete exactly one already-observed redundant route copy."""

    def move_route_priority(
        self,
        move: RoutePriorityMove,
    ) -> None:
        """Execute add-new -> verify -> delete-old for one semantic move."""


class RoutePriorityEnforcementStatus(str, Enum):
    SUCCESS = "success"
    APPLY_FAILED = "apply_failed"
    POSTCONDITION_FAILED = "postcondition_failed"


@dataclass(frozen=True, slots=True)
class RoutePriorityEnforcementResult:
    status: RoutePriorityEnforcementStatus
    initial: RoutePrioritySnapshot
    final: RoutePrioritySnapshot
    planned_steps: tuple[RoutePriorityConvergenceStep, ...]
    completed_steps: tuple[RoutePriorityConvergenceStep, ...]
    failed_step: RoutePriorityConvergenceStep | None = None
    error: str | None = None

    @property
    def confirmed(self) -> bool:
        return self.status is RoutePriorityEnforcementStatus.SUCCESS


def converge_route_priority_once(
    backend: RoutePriorityBackend,
    desired: Mapping[LogicalPathId, int],
    working_metrics: Iterable[int],
) -> RoutePriorityEnforcementResult:
    """Enforce one desired route-priority assignment with fresh verification.

    No retry loop is hidden here. If a physical step fails, the remaining plan
    is discarded, a fresh observation is obtained immediately, and the caller
    receives APPLY_FAILED. A later invocation starts from that re-observed
    state and computes a new plan.

    Successful command issue is not confirmation: SUCCESS is returned only
    after a fresh final observation exactly matches the desired assignment.
    """
    initial = backend.observe_route_priority()
    planned = plan_route_priority_convergence(
        initial.routes,
        desired,
        working_metrics,
    )

    completed: list[RoutePriorityConvergenceStep] = []

    for step in planned:
        try:
            if isinstance(step, RoutePriorityDeleteDuplicate):
                backend.delete_duplicate_route(step)
            else:
                backend.move_route_priority(step)
        except Exception as exc:
            # The old tail is now stale. Re-observe before exposing control to
            # any future attempt; do not execute another mutation in this call.
            after_failure = backend.observe_route_priority()
            return RoutePriorityEnforcementResult(
                status=RoutePriorityEnforcementStatus.APPLY_FAILED,
                initial=initial,
                final=after_failure,
                planned_steps=planned,
                completed_steps=tuple(completed),
                failed_step=step,
                error=f"{type(exc).__name__}: {exc}",
            )
        completed.append(step)

    final = backend.observe_route_priority()
    if not _matches_desired(final, desired):
        return RoutePriorityEnforcementResult(
            status=RoutePriorityEnforcementStatus.POSTCONDITION_FAILED,
            initial=initial,
            final=final,
            planned_steps=planned,
            completed_steps=tuple(completed),
            error="fresh final observation does not match desired route-priority assignment",
        )

    return RoutePriorityEnforcementResult(
        status=RoutePriorityEnforcementStatus.SUCCESS,
        initial=initial,
        final=final,
        planned_steps=planned,
        completed_steps=tuple(completed),
    )


def _matches_desired(
    snapshot: RoutePrioritySnapshot,
    desired: Mapping[LogicalPathId, int],
) -> bool:
    if set(snapshot.routes) != set(desired):
        return False
    return all(
        snapshot.routes[path_id] == frozenset((metric,))
        for path_id, metric in desired.items()
    )
