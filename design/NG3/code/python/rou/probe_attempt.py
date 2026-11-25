"""One-shot physical probe execution behind an exact readiness gate."""

from __future__ import annotations

from typing import Protocol

from .network_policy_layout import ProbePolicyOwner
from .probe_precondition import (
    ProbeExecutionContextKey,
    ProbeExecutionPrecondition,
    require_probe_execution_context,
)
from .probe_runtime import (
    AvailabilityProbeRuntime,
    ProbeEvidence,
    ProbeObservationContext,
    ProbeTechnicalObservation,
)


class ProbeAttemptError(RuntimeError):
    pass


class ProbeAttemptDriver(Protocol):
    def check(
        self,
        context: ProbeObservationContext,
    ) -> ProbeTechnicalObservation:
        """Execute one bounded physical check for the supplied immutable context."""


def execute_probe_attempt_once(
    runtime: AvailabilityProbeRuntime,
    owner: ProbePolicyOwner,
    precondition: ProbeExecutionPrecondition,
    driver: ProbeAttemptDriver,
) -> ProbeEvidence | None:
    """Run one current attempt or reject before I/O if readiness is not exact."""
    if not isinstance(runtime, AvailabilityProbeRuntime):
        raise TypeError("runtime must be AvailabilityProbeRuntime")
    if not isinstance(owner, ProbePolicyOwner):
        raise TypeError("owner must be ProbePolicyOwner")
    if not isinstance(precondition, ProbeExecutionPrecondition):
        raise TypeError(
            "precondition must be ProbeExecutionPrecondition"
        )
    if not precondition.confirmed:
        raise ProbeAttemptError(
            "probe execution precondition is not confirmed"
        )
    if owner not in precondition.owners:
        raise ProbeAttemptError(
            "probe owner is absent from confirmed execution precondition"
        )

    context = runtime.begin_attempt(owner)
    context_key = ProbeExecutionContextKey(
        owner=context.intent.owner,
        mechanism=context.intent.mechanism,
        target=context.intent.target,
        endpoint=context.endpoint,
    )
    try:
        require_probe_execution_context(precondition, context_key)
    except RuntimeError as exc:
        raise ProbeAttemptError(str(exc)) from exc

    observation = driver.check(context)
    return runtime.accept_result(
        owner,
        context,
        observation,
    )
