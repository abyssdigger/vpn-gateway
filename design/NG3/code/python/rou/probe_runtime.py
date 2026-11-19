"""Bounded Release-1 availability probe observation-context Agent semantics.

This module owns only the current normalized observation context and rejection of late
technical results. It does not derive targets, schedule probes, choose timeouts, execute
ICMP, own confirmation hysteresis or mutate routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .availability_confirmation import AvailabilityOutcome
from .interface_identity import InterfaceIdentity
from .probe_policy import (
    AvailabilityProbeIntent,
    AvailabilityProbeMechanism,
)


class ProbeRuntimeError(ValueError):
    pass


class ProbeTechnicalOutcome(str, Enum):
    REPLY = "reply"
    NO_REPLY = "no_reply"
    LOCAL_ERROR = "local_error"


@dataclass(frozen=True, slots=True)
class ProbeTechnicalObservation:
    outcome: ProbeTechnicalOutcome
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ProbeTechnicalOutcome):
            raise ProbeRuntimeError(
                "outcome must be ProbeTechnicalOutcome"
            )
        if self.outcome is ProbeTechnicalOutcome.LOCAL_ERROR:
            if not isinstance(self.diagnostic, str) or not self.diagnostic:
                raise ProbeRuntimeError(
                    "LOCAL_ERROR requires non-empty diagnostic"
                )
        elif self.diagnostic is not None:
            raise ProbeRuntimeError(
                "reply/no-reply technical observation must not carry diagnostic"
            )


@dataclass(frozen=True, slots=True)
class ProbeObservationContext:
    intent: AvailabilityProbeIntent
    endpoint: InterfaceIdentity
    generation: int

    def __post_init__(self) -> None:
        if not isinstance(self.intent, AvailabilityProbeIntent):
            raise ProbeRuntimeError(
                "intent must be AvailabilityProbeIntent"
            )
        if self.intent.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise ProbeRuntimeError(
                "Release 1 observation context must use ICMP"
            )
        if not isinstance(self.endpoint, InterfaceIdentity):
            raise ProbeRuntimeError(
                "endpoint must be InterfaceIdentity"
            )
        if type(self.generation) is not int or self.generation <= 0:
            raise ProbeRuntimeError(
                "generation must be a positive integer"
            )


@dataclass(frozen=True, slots=True)
class ProbeEvidence:
    context: ProbeObservationContext
    outcome: AvailabilityOutcome
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProbeObservationContext):
            raise ProbeRuntimeError(
                "context must be ProbeObservationContext"
            )
        if not isinstance(self.outcome, AvailabilityOutcome):
            raise ProbeRuntimeError(
                "outcome must be AvailabilityOutcome"
            )
        if self.outcome is AvailabilityOutcome.NO_EVIDENCE:
            if not isinstance(self.diagnostic, str) or not self.diagnostic:
                raise ProbeRuntimeError(
                    "NO_EVIDENCE probe result requires diagnostic"
                )
        elif self.diagnostic is not None:
            raise ProbeRuntimeError(
                "positive/negative probe evidence must not carry diagnostic"
            )


@dataclass(slots=True)
class AvailabilityProbeAgent:
    """Own exactly one current observation context and its generation token."""

    _current: ProbeObservationContext | None = None
    _last_generation: int = 0

    @property
    def current_context(self) -> ProbeObservationContext | None:
        return self._current

    def configure(
        self,
        intent: AvailabilityProbeIntent,
        endpoint: InterfaceIdentity,
    ) -> ProbeObservationContext:
        if not isinstance(intent, AvailabilityProbeIntent):
            raise ProbeRuntimeError(
                "intent must be AvailabilityProbeIntent"
            )
        if not isinstance(endpoint, InterfaceIdentity):
            raise ProbeRuntimeError(
                "endpoint must be InterfaceIdentity"
            )

        current = self._current
        if (
            current is not None
            and current.intent == intent
            and current.endpoint == endpoint
        ):
            return current

        self._last_generation += 1
        self._current = ProbeObservationContext(
            intent=intent,
            endpoint=endpoint,
            generation=self._last_generation,
        )
        return self._current

    def disable(self) -> None:
        # Do not advance here: re-enable necessarily configures from None and obtains
        # the next generation. Keeping the counter bounded to context transitions also
        # avoids meaningless generation churn on repeated disable calls.
        self._current = None

    def begin_attempt(self) -> ProbeObservationContext:
        if self._current is None:
            raise ProbeRuntimeError(
                "probe observation context is not configured"
            )
        return self._current

    def accept_result(
        self,
        attempted_context: ProbeObservationContext,
        observation: ProbeTechnicalObservation,
    ) -> ProbeEvidence | None:
        if not isinstance(attempted_context, ProbeObservationContext):
            raise ProbeRuntimeError(
                "attempted_context must be ProbeObservationContext"
            )
        if not isinstance(observation, ProbeTechnicalObservation):
            raise ProbeRuntimeError(
                "observation must be ProbeTechnicalObservation"
            )

        # Exact immutable-context equality includes subject, logical path, concrete
        # target, mechanism, concrete endpoint generation and Agent generation token.
        if self._current != attempted_context:
            return None

        if observation.outcome is ProbeTechnicalOutcome.REPLY:
            return ProbeEvidence(
                attempted_context,
                AvailabilityOutcome.POSITIVE,
            )
        if observation.outcome is ProbeTechnicalOutcome.NO_REPLY:
            return ProbeEvidence(
                attempted_context,
                AvailabilityOutcome.NEGATIVE,
            )
        return ProbeEvidence(
            attempted_context,
            AvailabilityOutcome.NO_EVIDENCE,
            observation.diagnostic,
        )
