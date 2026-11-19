"""Bounded one-attempt availability runtime composition.

This module composes already existing contracts:
- lower probe policy must already be exact;
- AvailabilityProbeAgent owns current observation-context freshness;
- ActiveProbeDriver emits one technical result;
- availability_confirmation owns hysteresis state.

It does not schedule attempts, derive targets, mutate Linux policy or choose route order.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .availability_confirmation import (
    AvailabilityConfirmationState,
    AvailabilityOutcome,
    apply_availability_evidence,
)
from .interface_identity import InterfaceIdentity
from .probe_policy import AvailabilityProbeIntent
from .probe_runtime import (
    AvailabilityProbeAgent,
    ProbeEvidence,
    ProbeObservationContext,
    ProbeTechnicalObservation,
)


class ActiveProbeDriver(Protocol):
    def check(
        self,
        context: ProbeObservationContext,
    ) -> ProbeTechnicalObservation: ...


@dataclass(frozen=True, slots=True)
class ProbeAttemptPreconditions:
    routing_confirmed: bool
    local_policy_confirmed: bool

    def __post_init__(self) -> None:
        if type(self.routing_confirmed) is not bool:
            raise ValueError("routing_confirmed must be boolean")
        if type(self.local_policy_confirmed) is not bool:
            raise ValueError(
                "local_policy_confirmed must be boolean"
            )

    @property
    def confirmed(self) -> bool:
        return (
            self.routing_confirmed
            and self.local_policy_confirmed
        )


@dataclass(frozen=True, slots=True)
class ProbeSubjectRuntimeState:
    confirmation: AvailabilityConfirmationState = (
        AvailabilityConfirmationState()
    )
    context: ProbeObservationContext | None = None
    availability_known: bool = False

    def __post_init__(self) -> None:
        if not isinstance(
            self.confirmation,
            AvailabilityConfirmationState,
        ):
            raise ValueError(
                "confirmation must be AvailabilityConfirmationState"
            )
        if (
            self.context is not None
            and not isinstance(self.context, ProbeObservationContext)
        ):
            raise ValueError(
                "context must be ProbeObservationContext or None"
            )
        if type(self.availability_known) is not bool:
            raise ValueError(
                "availability_known must be boolean"
            )
        if (
            self.context is None
            and (
                self.availability_known
                or self.confirmation != AvailabilityConfirmationState()
            )
        ):
            raise ValueError(
                "non-empty confirmation state requires observation context"
            )
        if self.confirmation.availability_problem and not self.availability_known:
            raise ValueError(
                "confirmed availability problem requires known state"
            )

    @property
    def availability_label(self) -> str:
        if not self.availability_known:
            return "unknown"
        return (
            "not available"
            if self.confirmation.availability_problem
            else "available"
        )


class ProbeAttemptStatus(str, Enum):
    PRECONDITION_FAILED = "precondition_failed"
    EVIDENCE_APPLIED = "evidence_applied"
    STALE_RESULT_DISCARDED = "stale_result_discarded"


@dataclass(frozen=True, slots=True)
class ProbeAttemptResult:
    status: ProbeAttemptStatus
    previous_state: ProbeSubjectRuntimeState
    next_state: ProbeSubjectRuntimeState
    context: ProbeObservationContext | None
    evidence: ProbeEvidence | None
    diagnostic: str | None = None

    @property
    def availability_problem(self) -> bool:
        return self.next_state.confirmation.availability_problem


def run_probe_attempt_once(
    agent: AvailabilityProbeAgent,
    driver: ActiveProbeDriver,
    intent: AvailabilityProbeIntent,
    endpoint: InterfaceIdentity,
    state: ProbeSubjectRuntimeState,
    preconditions: ProbeAttemptPreconditions,
    *,
    degradation_threshold: int,
    recovery_threshold: int,
) -> ProbeAttemptResult:
    """Run at most one technical attempt and one confirmation transition."""
    if not isinstance(agent, AvailabilityProbeAgent):
        raise ValueError("agent must be AvailabilityProbeAgent")
    if not isinstance(intent, AvailabilityProbeIntent):
        raise ValueError("intent must be AvailabilityProbeIntent")
    if not isinstance(endpoint, InterfaceIdentity):
        raise ValueError("endpoint must be InterfaceIdentity")
    if not isinstance(state, ProbeSubjectRuntimeState):
        raise ValueError("state must be ProbeSubjectRuntimeState")
    if not isinstance(preconditions, ProbeAttemptPreconditions):
        raise ValueError(
            "preconditions must be ProbeAttemptPreconditions"
        )

    if not preconditions.confirmed:
        missing = []
        if not preconditions.routing_confirmed:
            missing.append("probe route/RPDB")
        if not preconditions.local_policy_confirmed:
            missing.append("probe-local nft")
        return ProbeAttemptResult(
            status=ProbeAttemptStatus.PRECONDITION_FAILED,
            previous_state=state,
            next_state=state,
            context=None,
            evidence=None,
            diagnostic=(
                "probe lower precondition is not confirmed: "
                + ", ".join(missing)
            ),
        )

    agent.configure(intent, endpoint)
    attempted_context = agent.begin_attempt()

    # Confirmation evidence belongs to one exact observation context. A target,
    # subject or concrete endpoint generation change starts at unknown rather
    # than inheriting the old context's available/problem state.
    base_state = (
        state
        if state.context == attempted_context
        else ProbeSubjectRuntimeState(context=attempted_context)
    )

    technical = driver.check(attempted_context)
    evidence = agent.accept_result(
        attempted_context,
        technical,
    )

    if evidence is None:
        current_context = agent.current_context
        return ProbeAttemptResult(
            status=ProbeAttemptStatus.STALE_RESULT_DISCARDED,
            previous_state=state,
            next_state=ProbeSubjectRuntimeState(
                context=current_context,
            ),
            context=attempted_context,
            evidence=None,
            diagnostic=(
                "probe result belongs to a superseded "
                "observation context"
            ),
        )

    next_confirmation = apply_availability_evidence(
        base_state.confirmation,
        evidence.outcome,
        degradation_threshold=degradation_threshold,
        recovery_threshold=recovery_threshold,
    )
    availability_known = _next_availability_known(
        base_state,
        evidence.outcome,
        next_confirmation,
    )
    next_state = ProbeSubjectRuntimeState(
        confirmation=next_confirmation,
        context=attempted_context,
        availability_known=availability_known,
    )
    return ProbeAttemptResult(
        status=ProbeAttemptStatus.EVIDENCE_APPLIED,
        previous_state=state,
        next_state=next_state,
        context=attempted_context,
        evidence=evidence,
        diagnostic=evidence.diagnostic,
    )



def _next_availability_known(
    previous: ProbeSubjectRuntimeState,
    outcome: AvailabilityOutcome,
    next_confirmation: AvailabilityConfirmationState,
) -> bool:
    if outcome is AvailabilityOutcome.NO_EVIDENCE:
        return previous.availability_known
    if next_confirmation.availability_problem:
        return True
    if outcome is AvailabilityOutcome.POSITIVE:
        return True
    # A negative sample below the degradation threshold is not yet a confirmed
    # not-available state. If this context was previously confirmed available,
    # it remains known-available until the problem threshold is crossed;
    # otherwise the operator-facing state remains unknown.
    return previous.availability_known
