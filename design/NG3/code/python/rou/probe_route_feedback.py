"""Pure bridge from per-path probe confirmation to Profile effective routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .availability_routing_state import (
    AvailabilityRoutingProjection,
    AvailabilityRoutingState,
    project_availability_routing,
)
from .binding import LogicalPathId
from .network_policy_layout import ProbePolicyOwner
from .payload_profile import PayloadProfileRequest
from .probe_attempt_runtime import ProbeSubjectRuntimeState


class ProbeRouteFeedbackError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProbeRouteFeedbackProjection:
    problem_paths: tuple[LogicalPathId, ...]
    routing: AvailabilityRoutingProjection


def project_probe_route_feedback(
    profile: PayloadProfileRequest,
    subject_states: Mapping[
        ProbePolicyOwner,
        ProbeSubjectRuntimeState,
    ],
    previous_routing: AvailabilityRoutingState,
    *,
    reserve_device_ids: frozenset[str] = frozenset(),
) -> ProbeRouteFeedbackProjection:
    """Feed only confirmed current-path problems into sticky/reserve routing.

    Missing subject state means that no confirmed problem exists yet (the
    operator-facing state is "unknown"). States for owners that are no longer
    part of current Profile membership are ignored and therefore cannot keep a
    replacement/current path degraded.
    """
    if not isinstance(profile, PayloadProfileRequest):
        raise ProbeRouteFeedbackError(
            "profile must be PayloadProfileRequest"
        )
    if not isinstance(previous_routing, AvailabilityRoutingState):
        raise ProbeRouteFeedbackError(
            "previous_routing must be AvailabilityRoutingState"
        )
    if not isinstance(reserve_device_ids, frozenset) or not all(
        isinstance(item, str) and item
        for item in reserve_device_ids
    ):
        raise ProbeRouteFeedbackError(
            "reserve_device_ids must be a frozenset of non-empty strings"
        )

    current_owners = tuple(
        ProbePolicyOwner(profile.profile_id, path_id)
        for path_id in profile.ordered_paths
    )
    for owner, state in subject_states.items():
        if not isinstance(owner, ProbePolicyOwner):
            raise ProbeRouteFeedbackError(
                "subject_states keys must be ProbePolicyOwner"
            )
        if not isinstance(state, ProbeSubjectRuntimeState):
            raise ProbeRouteFeedbackError(
                "subject_states values must be ProbeSubjectRuntimeState"
            )
        if (
            state.context is not None
            and state.context.intent.owner != owner
        ):
            raise ProbeRouteFeedbackError(
                "subject state context owner does not match mapping key"
            )

    problem_paths = tuple(
        owner.path_id
        for owner in current_owners
        if (
            owner in subject_states
            and subject_states[
                owner
            ].confirmation.availability_problem
        )
    )

    routing = project_availability_routing(
        profile.ordered_paths,
        problem_paths,
        previous_routing,
        reserve_device_ids=reserve_device_ids,
    )
    return ProbeRouteFeedbackProjection(
        problem_paths=problem_paths,
        routing=routing,
    )
