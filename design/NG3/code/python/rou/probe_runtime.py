"""Bounded Release-1 availability probe observation-context Agent semantics.

This module owns only the current normalized observation context and rejection of late
technical results. It does not derive targets, schedule probes, choose timeouts, execute
ICMP, own confirmation hysteresis or mutate routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from .availability_confirmation import AvailabilityOutcome
from .interface_identity import InterfaceIdentity
from .network_policy_layout import ProbePolicyOwner
from .route_priority_inventory import RoutePriorityPathRoute
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

    _current: ProbeObservationContext | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _last_generation: int = field(
        default=0,
        init=False,
        repr=False,
    )

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


@dataclass(slots=True)
class AvailabilityProbeRuntime:
    """Bounded multi-channel implementation of the AvailabilityProbeAgent role.

    One child AvailabilityProbeAgent is retained per owner seen under the accepted
    configuration so disable/re-enable cannot reuse an old generation token.
    """

    _agents: dict[ProbePolicyOwner, AvailabilityProbeAgent] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _active: frozenset[ProbePolicyOwner] = field(
        default_factory=frozenset,
        init=False,
        repr=False,
    )

    @property
    def current_contexts(self) -> tuple[ProbeObservationContext, ...]:
        contexts = [
            self._agents[owner].current_context
            for owner in sorted(self._active)
        ]
        if any(context is None for context in contexts):
            raise ProbeRuntimeError(
                "active probe owner has no current observation context"
            )
        return tuple(context for context in contexts if context is not None)

    def configure(
        self,
        intents: Iterable[AvailabilityProbeIntent],
        path_routes: Iterable[RoutePriorityPathRoute],
    ) -> tuple[ProbeObservationContext, ...]:
        raw_intents = tuple(intents)
        raw_routes = tuple(path_routes)
        if any(
            not isinstance(intent, AvailabilityProbeIntent)
            for intent in raw_intents
        ):
            raise ProbeRuntimeError(
                "intents must contain AvailabilityProbeIntent"
            )
        if any(
            not isinstance(route, RoutePriorityPathRoute)
            for route in raw_routes
        ):
            raise ProbeRuntimeError(
                "path_routes must contain RoutePriorityPathRoute"
            )

        intent_by_owner: dict[ProbePolicyOwner, AvailabilityProbeIntent] = {}
        for intent in raw_intents:
            if intent.owner in intent_by_owner:
                raise ProbeRuntimeError(
                    f"duplicate availability probe owner {intent.owner!r}"
                )
            intent_by_owner[intent.owner] = intent

        route_by_path = {}
        for route in raw_routes:
            if route.path_id in route_by_path:
                raise ProbeRuntimeError(
                    f"duplicate current path realization {route.path_id!r}"
                )
            route_by_path[route.path_id] = route

        for owner, intent in intent_by_owner.items():
            route = route_by_path.get(owner.path_id)
            if route is None:
                raise ProbeRuntimeError(
                    f"probe owner has no current path realization: {owner!r}"
                )
            agent = self._agents.get(owner)
            if agent is None:
                agent = AvailabilityProbeAgent()
                self._agents[owner] = agent
            agent.configure(intent, route.endpoint)

        next_active = frozenset(intent_by_owner)
        for owner in self._active - next_active:
            self._agents[owner].disable()
        self._active = next_active
        return self.current_contexts

    def begin_attempt(
        self,
        owner: ProbePolicyOwner,
    ) -> ProbeObservationContext:
        if not isinstance(owner, ProbePolicyOwner):
            raise ProbeRuntimeError(
                "owner must be ProbePolicyOwner"
            )
        if owner not in self._active:
            raise ProbeRuntimeError(
                "probe owner is not currently active"
            )
        return self._agents[owner].begin_attempt()

    def accept_result(
        self,
        owner: ProbePolicyOwner,
        attempted_context: ProbeObservationContext,
        observation: ProbeTechnicalObservation,
    ) -> ProbeEvidence | None:
        if not isinstance(owner, ProbePolicyOwner):
            raise ProbeRuntimeError(
                "owner must be ProbePolicyOwner"
            )
        agent = self._agents.get(owner)
        if agent is None or owner not in self._active:
            return None
        return agent.accept_result(attempted_context, observation)
