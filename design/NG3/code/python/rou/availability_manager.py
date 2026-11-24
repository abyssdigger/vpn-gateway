"""Bounded availability Manager state from fresh probe evidence to effective path order."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .availability_confirmation import (
    AvailabilityConfirmationState,
    apply_availability_evidence,
)
from .availability_routing_state import (
    AvailabilityRoutingState,
    project_availability_routing,
)
from .network_policy_layout import ProbePolicyOwner
from .payload_profile import PayloadProfileRequest
from .probe_runtime import ProbeEvidence, ProbeObservationContext
from .release1_config import Release1Config

LOG_TAG = "AVAIL"


class AvailabilityManagerError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AvailabilityManagerPolicy:
    degradation_threshold: int
    recovery_threshold: int

    def __post_init__(self) -> None:
        for name, value in (
            ("degradation_threshold", self.degradation_threshold),
            ("recovery_threshold", self.recovery_threshold),
        ):
            if type(value) is not int or value <= 0:
                raise AvailabilityManagerError(
                    f"{name} must be a positive integer"
                )


@dataclass(frozen=True, slots=True)
class AvailabilitySubjectState:
    context: ProbeObservationContext
    confirmation: AvailabilityConfirmationState


@dataclass(frozen=True, slots=True)
class AvailabilityManagerProjection:
    effective_profiles: tuple[PayloadProfileRequest, ...]
    problem_owners: frozenset[ProbePolicyOwner]


@dataclass(slots=True)
class AvailabilityManager:
    """Own current availability confirmation and effective path-order state."""

    policy: AvailabilityManagerPolicy
    _subjects: dict[ProbePolicyOwner, AvailabilitySubjectState] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _routing: dict[str, AvailabilityRoutingState] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.policy, AvailabilityManagerPolicy):
            raise AvailabilityManagerError(
                "policy must be AvailabilityManagerPolicy"
            )

    def synchronize(
        self,
        contexts: Iterable[ProbeObservationContext],
        profiles: Iterable[PayloadProfileRequest],
        config: Release1Config,
    ) -> AvailabilityManagerProjection:
        current_contexts = tuple(contexts)
        current_profiles = tuple(profiles)
        self._validate_inputs(current_contexts, current_profiles, config)

        context_by_owner = {
            context.intent.owner: context
            for context in current_contexts
        }
        next_subjects: dict[ProbePolicyOwner, AvailabilitySubjectState] = {}
        for owner, context in context_by_owner.items():
            previous = self._subjects.get(owner)
            if previous is not None and previous.context == context:
                next_subjects[owner] = previous
            else:
                next_subjects[owner] = AvailabilitySubjectState(
                    context,
                    AvailabilityConfirmationState(),
                )
        self._subjects = next_subjects
        return self._project(current_profiles, config)

    def apply_evidence(
        self,
        evidence: ProbeEvidence,
        profiles: Iterable[PayloadProfileRequest],
        config: Release1Config,
    ) -> AvailabilityManagerProjection:
        if not isinstance(evidence, ProbeEvidence):
            raise AvailabilityManagerError(
                "evidence must be ProbeEvidence"
            )
        current_profiles = tuple(profiles)
        self._validate_profiles(current_profiles, config)

        owner = evidence.context.intent.owner
        current = self._subjects.get(owner)
        if current is None or current.context != evidence.context:
            raise AvailabilityManagerError(
                "evidence does not belong to the current synchronized context"
            )

        self._subjects[owner] = AvailabilitySubjectState(
            current.context,
            apply_availability_evidence(
                current.confirmation,
                evidence.outcome,
                degradation_threshold=self.policy.degradation_threshold,
                recovery_threshold=self.policy.recovery_threshold,
            ),
        )
        return self._project(current_profiles, config)

    def _project(
        self,
        profiles: tuple[PayloadProfileRequest, ...],
        config: Release1Config,
    ) -> AvailabilityManagerProjection:
        problem_owners = frozenset(
            owner
            for owner, state in self._subjects.items()
            if state.confirmation.availability_problem
        )
        out: list[PayloadProfileRequest] = []
        next_routing: dict[str, AvailabilityRoutingState] = {}

        for profile in sorted(profiles, key=lambda item: item.profile_id):
            semantic = config.profiles[profile.profile_id]
            problem_paths = tuple(
                path
                for path in profile.ordered_paths
                if ProbePolicyOwner(profile.profile_id, path) in problem_owners
            )
            previous = self._routing.get(
                profile.profile_id,
                AvailabilityRoutingState(),
            )
            projected = project_availability_routing(
                profile.ordered_paths,
                problem_paths,
                previous,
                reserve_device_ids=semantic.reserve_device_ids,
            )
            next_routing[profile.profile_id] = projected.next_state
            out.append(
                PayloadProfileRequest(
                    profile_id=profile.profile_id,
                    direction=profile.direction,
                    destinations=profile.destinations,
                    ordered_paths=projected.effective_order,
                )
            )

        self._routing = next_routing
        return AvailabilityManagerProjection(
            effective_profiles=tuple(out),
            problem_owners=problem_owners,
        )

    def _validate_inputs(
        self,
        contexts: tuple[ProbeObservationContext, ...],
        profiles: tuple[PayloadProfileRequest, ...],
        config: Release1Config,
    ) -> None:
        self._validate_profiles(profiles, config)
        owners = tuple(context.intent.owner for context in contexts)
        if len(set(owners)) != len(owners):
            raise AvailabilityManagerError(
                "contexts contain duplicate availability owner"
            )

        profile_by_id = {profile.profile_id: profile for profile in profiles}
        for context in contexts:
            owner = context.intent.owner
            profile = profile_by_id.get(owner.profile_id)
            if profile is None or owner.path_id not in profile.ordered_paths:
                raise AvailabilityManagerError(
                    "probe context is outside current Profile/path membership"
                )

    @staticmethod
    def _validate_profiles(
        profiles: tuple[PayloadProfileRequest, ...],
        config: Release1Config,
    ) -> None:
        if not isinstance(config, Release1Config):
            raise AvailabilityManagerError(
                "config must be Release1Config"
            )
        if any(
            not isinstance(profile, PayloadProfileRequest)
            for profile in profiles
        ):
            raise AvailabilityManagerError(
                "profiles must contain PayloadProfileRequest"
            )
        profile_ids = tuple(profile.profile_id for profile in profiles)
        if len(set(profile_ids)) != len(profile_ids):
            raise AvailabilityManagerError(
                "profiles contain duplicate Profile"
            )
        enabled_ids = {
            profile_id
            for profile_id, structural in config.structural.profiles.items()
            if structural.enabled
        }
        if set(profile_ids) != enabled_ids:
            raise AvailabilityManagerError(
                "profiles do not match enabled configuration Profiles"
            )
