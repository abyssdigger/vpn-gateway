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

    def __post_init__(self) -> None:
        if not isinstance(
            self.confirmation,
            AvailabilityConfirmationState,
        ):
            raise ValueError(
                "confirmation must be AvailabilityConfirmationState"
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
    technical = driver.check(attempted_context)
    evidence = agent.accept_result(
        attempted_context,
        technical,
    )

    if evidence is None:
        return ProbeAttemptResult(
            status=ProbeAttemptStatus.STALE_RESULT_DISCARDED,
            previous_state=state,
            next_state=state,
            context=attempted_context,
            evidence=None,
            diagnostic=(
                "probe result belongs to a superseded "
                "observation context"
            ),
        )

    next_confirmation = apply_availability_evidence(
        state.confirmation,
        evidence.outcome,
        degradation_threshold=degradation_threshold,
        recovery_threshold=recovery_threshold,
    )
    next_state = ProbeSubjectRuntimeState(
        confirmation=next_confirmation,
    )
    return ProbeAttemptResult(
        status=ProbeAttemptStatus.EVIDENCE_APPLIED,
        previous_state=state,
        next_state=next_state,
        context=attempted_context,
        evidence=evidence,
        diagnostic=evidence.diagnostic,
    )
