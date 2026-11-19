"""Bounded fail-closed convergence for probe-owned route/RPDB state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .interface_identity import InterfaceIdentity
from .payload_routing_desired import ManagedRouteSpec
from .probe_policy import ProbeNetworkPolicyDesiredState, ProbeRuleSpec
from .probe_routing_compare import (
    ProbeRoutingComparison,
    compare_probe_routing,
)
from .probe_routing_plan import (
    ProbeRoutingMutationStep,
    ProbeRoutingPlanError,
    ProbeRoutingStepKind,
    probe_routing_rank,
    select_probe_routing_step,
)
from .network_policy_layout import NetworkPolicyPlatformSpace
from .structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
    StructuralRoutingObservation,
)


@dataclass(frozen=True, slots=True)
class ProbeRoutingPhysicalSnapshot:
    interfaces: tuple[InterfaceIdentity, ...]
    routing: StructuralRoutingObservation


class ProbeRoutingConvergenceBackend(Protocol):
    def observe_probe_routing_snapshot(
        self,
    ) -> ProbeRoutingPhysicalSnapshot: ...

    def add_route(self, spec: ManagedRouteSpec) -> None: ...
    def delete_route(self, route: ObservedManagedRoute) -> None: ...
    def add_rule(self, spec: ProbeRuleSpec) -> None: ...
    def delete_rule(self, rule: ObservedManagedRule) -> None: ...


class ProbeRoutingConvergenceStatus(str, Enum):
    CONFIRMED = "confirmed"
    STEP_APPLIED = "step_applied"
    OBSERVATION_FAILED = "observation_failed"
    CONFLICT = "conflict"
    APPLY_FAILED = "apply_failed"
    POSTCONDITION_FAILED = "postcondition_failed"


@dataclass(frozen=True, slots=True)
class ProbeRoutingConvergenceResult:
    status: ProbeRoutingConvergenceStatus
    initial: ProbeRoutingComparison | None
    final: ProbeRoutingComparison | None
    mutation_attempted: bool
    step: ProbeRoutingMutationStep | None = None
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status is ProbeRoutingConvergenceStatus.CONFIRMED
            and self.final is not None
            and self.final.confirmed
        )


def converge_probe_routing_step_once(
    backend: ProbeRoutingConvergenceBackend,
    desired: ProbeNetworkPolicyDesiredState,
    platform: NetworkPolicyPlatformSpace,
) -> ProbeRoutingConvergenceResult:
    """Perform at most one fail-closed probe route/RPDB write."""
    if not isinstance(desired, ProbeNetworkPolicyDesiredState):
        raise ValueError(
            "desired must be ProbeNetworkPolicyDesiredState"
        )
    if not isinstance(platform, NetworkPolicyPlatformSpace):
        raise ValueError(
            "platform must be NetworkPolicyPlatformSpace"
        )

    def result(
        status: ProbeRoutingConvergenceStatus,
        initial: ProbeRoutingComparison | None = None,
        final: ProbeRoutingComparison | None = None,
        *,
        attempted: bool = False,
        step: ProbeRoutingMutationStep | None = None,
        diagnostic: str | None = None,
    ) -> ProbeRoutingConvergenceResult:
        return ProbeRoutingConvergenceResult(
            status=status,
            initial=initial,
            final=final,
            mutation_attempted=attempted,
            step=step,
            diagnostic=diagnostic,
        )

    try:
        before = backend.observe_probe_routing_snapshot()
        initial = compare_probe_routing(
            desired,
            before.routing,
            platform,
        )
    except Exception as exc:
        return result(
            ProbeRoutingConvergenceStatus.OBSERVATION_FAILED,
            diagnostic=(
                "initial probe routing observation failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if initial.conflicts:
        return result(
            ProbeRoutingConvergenceStatus.CONFLICT,
            initial,
            diagnostic=initial.conflicts[0].reason,
        )

    if initial.confirmed:
        return result(
            ProbeRoutingConvergenceStatus.CONFIRMED,
            initial,
            initial,
        )

    try:
        step = select_probe_routing_step(initial)
    except ProbeRoutingPlanError as exc:
        return result(
            ProbeRoutingConvergenceStatus.CONFLICT,
            initial,
            diagnostic=str(exc),
        )
    if step is None:
        return result(
            ProbeRoutingConvergenceStatus.CONFLICT,
            initial,
            diagnostic=(
                "probe routing is not exact but planner returned no step"
            ),
        )

    apply_error: Exception | None = None
    try:
        _apply_step(backend, step)
    except Exception as exc:
        apply_error = exc

    try:
        after = backend.observe_probe_routing_snapshot()
        final = compare_probe_routing(
            desired,
            after.routing,
            platform,
        )
    except Exception as exc:
        return result(
            (
                ProbeRoutingConvergenceStatus.APPLY_FAILED
                if apply_error is not None
                else ProbeRoutingConvergenceStatus.POSTCONDITION_FAILED
            ),
            initial,
            attempted=True,
            step=step,
            diagnostic=(
                "fresh probe routing postcondition observation failed: "
                f"{type(exc).__name__}: {exc}"
                + (
                    f"; apply error: {type(apply_error).__name__}: "
                    f"{apply_error}"
                    if apply_error is not None
                    else ""
                )
            ),
        )

    if final.conflicts:
        return result(
            (
                ProbeRoutingConvergenceStatus.APPLY_FAILED
                if apply_error is not None
                else ProbeRoutingConvergenceStatus.CONFLICT
            ),
            initial,
            final,
            attempted=True,
            step=step,
            diagnostic=(
                final.conflicts[0].reason
                + (
                    f"; apply error: {type(apply_error).__name__}: "
                    f"{apply_error}"
                    if apply_error is not None
                    else ""
                )
            ),
        )

    if (
        before.interfaces != after.interfaces
        or not (
            probe_routing_rank(final)
            < probe_routing_rank(initial)
        )
    ):
        return result(
            (
                ProbeRoutingConvergenceStatus.APPLY_FAILED
                if apply_error is not None
                else ProbeRoutingConvergenceStatus.POSTCONDITION_FAILED
            ),
            initial,
            final,
            attempted=True,
            step=step,
            diagnostic=(
                "fresh probe routing postcondition did not make "
                "strict fail-closed rank progress"
                + (
                    f"; apply error: {type(apply_error).__name__}: "
                    f"{apply_error}"
                    if apply_error is not None
                    else ""
                )
            ),
        )

    diagnostic = (
        f"apply raised {type(apply_error).__name__}: {apply_error}; "
        "fresh probe routing state independently made strict progress"
        if apply_error is not None
        else None
    )

    if final.confirmed:
        return result(
            ProbeRoutingConvergenceStatus.CONFIRMED,
            initial,
            final,
            attempted=True,
            step=step,
            diagnostic=diagnostic,
        )

    return result(
        ProbeRoutingConvergenceStatus.STEP_APPLIED,
        initial,
        final,
        attempted=True,
        step=step,
        diagnostic=diagnostic,
    )


def _apply_step(
    backend: ProbeRoutingConvergenceBackend,
    step: ProbeRoutingMutationStep,
) -> None:
    if step.kind in {
        ProbeRoutingStepKind.ADD_GUARD_ROUTE,
        ProbeRoutingStepKind.ADD_PATH_ROUTE,
    }:
        assert step.desired_route is not None
        backend.add_route(step.desired_route)
    elif step.kind in {
        ProbeRoutingStepKind.DELETE_PATH_ROUTE,
        ProbeRoutingStepKind.DELETE_GUARD_ROUTE,
    }:
        assert step.observed_route is not None
        backend.delete_route(step.observed_route)
    elif step.kind is ProbeRoutingStepKind.WITHDRAW_RULE:
        assert step.observed_rule is not None
        backend.delete_rule(step.observed_rule)
    elif step.kind is ProbeRoutingStepKind.ADD_RULE:
        assert step.desired_rule is not None
        backend.add_rule(step.desired_rule)
    else:
        raise ValueError(
            f"unsupported probe routing step {step.kind!r}"
        )


class ProbeRoutingTransactionStatus(str, Enum):
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REGRESSED = "regressed"


@dataclass(frozen=True, slots=True)
class ProbeRoutingTransactionResult:
    status: ProbeRoutingTransactionStatus
    attempts: tuple[ProbeRoutingConvergenceResult, ...]
    initial_rank: tuple[int, int, int, int] | None
    final_rank: tuple[int, int, int, int] | None
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status is ProbeRoutingTransactionStatus.CONFIRMED
            and bool(self.attempts)
            and self.attempts[-1].confirmed
        )


def converge_probe_routing(
    backend: ProbeRoutingConvergenceBackend,
    desired: ProbeNetworkPolicyDesiredState,
    platform: NetworkPolicyPlatformSpace,
) -> ProbeRoutingTransactionResult:
    """Drive bounded fresh one-step convergence until exact or terminal failure.

    There is no retry-on-error budget. Every successful write must expose a
    strictly lower lexicographic safety rank. Between attempts, a fresh rank
    increase terminates the transaction as regression.
    """
    attempts: list[ProbeRoutingConvergenceResult] = []
    initial_rank: tuple[int, int, int, int] | None = None
    previous_final_rank: tuple[int, int, int, int] | None = None

    while True:
        attempt = converge_probe_routing_step_once(
            backend,
            desired,
            platform,
        )
        attempts.append(attempt)

        attempt_initial_rank = (
            probe_routing_rank(attempt.initial)
            if attempt.initial is not None
            else None
        )
        attempt_final_rank = (
            probe_routing_rank(attempt.final)
            if attempt.final is not None
            else None
        )

        if initial_rank is None and attempt_initial_rank is not None:
            initial_rank = attempt_initial_rank

        if attempt.status is ProbeRoutingConvergenceStatus.CONFIRMED:
            return ProbeRoutingTransactionResult(
                ProbeRoutingTransactionStatus.CONFIRMED,
                tuple(attempts),
                initial_rank,
                attempt_final_rank,
                attempt.diagnostic,
            )

        if (
            previous_final_rank is not None
            and attempt_initial_rank is not None
            and attempt_initial_rank > previous_final_rank
        ):
            return ProbeRoutingTransactionResult(
                ProbeRoutingTransactionStatus.REGRESSED,
                tuple(attempts),
                initial_rank,
                attempt_initial_rank,
                (
                    "fresh probe routing state regressed between "
                    f"transaction attempts: previous={previous_final_rank}, "
                    f"current={attempt_initial_rank}"
                ),
            )

        if attempt.status is not ProbeRoutingConvergenceStatus.STEP_APPLIED:
            return ProbeRoutingTransactionResult(
                ProbeRoutingTransactionStatus.FAILED,
                tuple(attempts),
                initial_rank,
                attempt_final_rank,
                (
                    "probe routing transaction stopped at "
                    f"{attempt.status.value}"
                    + (
                        f": {attempt.diagnostic}"
                        if attempt.diagnostic
                        else ""
                    )
                ),
            )

        if (
            attempt_initial_rank is None
            or attempt_final_rank is None
            or not (attempt_final_rank < attempt_initial_rank)
        ):
            return ProbeRoutingTransactionResult(
                ProbeRoutingTransactionStatus.REGRESSED,
                tuple(attempts),
                initial_rank,
                attempt_final_rank,
                (
                    "STEP_APPLIED did not expose strict probe routing "
                    "rank decrease"
                ),
            )

        previous_final_rank = attempt_final_rank
