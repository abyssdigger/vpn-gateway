"""Alpha adapter from Profile availability config to explicit probe subjects.

This adapter intentionally supports only already explicit Release-1 targets. Bare
`availability_check = "icmp"` remains behind integration-specific target-derivation
evidence and is rejected instead of guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .network_policy_layout import (
    NetworkPolicyLayout,
    NetworkPolicyPlatformSpace,
    ProbePolicyOwner,
    ProbeRoutingDemand,
    allocate_network_policy_layout,
)
from .payload_profile import PayloadProfileRequest
from .probe_policy import (
    AvailabilityProbeIntent,
    ProbeLocalPlatform,
    ProbeNetworkPolicyDesiredState,
    build_probe_network_policy_desired_state,
)
from .route_priority_inventory import RoutePriorityPathRoute
from .release1_config import ProfileRelease1Config


class AlphaProbeProjectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AlphaProbeProjection:
    intents: tuple[AvailabilityProbeIntent, ...]
    routing_demands: tuple[ProbeRoutingDemand, ...]

    def __post_init__(self) -> None:
        if len(self.intents) != len(self.routing_demands):
            raise AlphaProbeProjectionError(
                "probe intents/demands cardinality mismatch"
            )
        if tuple(
            intent.owner for intent in self.intents
        ) != tuple(
            demand.owner for demand in self.routing_demands
        ):
            raise AlphaProbeProjectionError(
                "probe intents/demands owner order mismatch"
            )


def build_alpha_explicit_probe_projection(
    profiles: tuple[PayloadProfileRequest, ...],
    profile_config: Mapping[str, ProfileRelease1Config],
) -> AlphaProbeProjection:
    if not isinstance(profiles, tuple) or not all(
        isinstance(item, PayloadProfileRequest)
        for item in profiles
    ):
        raise AlphaProbeProjectionError(
            "profiles must be a tuple of PayloadProfileRequest"
        )

    seen_profiles: set[str] = set()
    intents: list[AvailabilityProbeIntent] = []
    demands: list[ProbeRoutingDemand] = []

    for profile in sorted(
        profiles,
        key=lambda value: value.profile_id,
    ):
        if profile.profile_id in seen_profiles:
            raise AlphaProbeProjectionError(
                f"duplicate Profile {profile.profile_id!r}"
            )
        seen_profiles.add(profile.profile_id)

        config = profile_config.get(profile.profile_id)
        if not isinstance(config, ProfileRelease1Config):
            raise AlphaProbeProjectionError(
                f"missing Release-1 config for Profile {profile.profile_id!r}"
            )

        check = config.availability_check
        if check is None:
            continue
        if check.mechanism != "icmp":
            raise AlphaProbeProjectionError(
                f"Profile {profile.profile_id!r} uses unsupported "
                f"availability mechanism {check.mechanism!r}"
            )
        if check.target is None:
            raise AlphaProbeProjectionError(
                f"Profile {profile.profile_id!r} uses bare "
                'availability_check="icmp"; target derivation requires '
                "integration-specific evidence"
            )

        for path_id in profile.ordered_paths:
            owner = ProbePolicyOwner(
                profile.profile_id,
                path_id,
            )
            intents.append(
                AvailabilityProbeIntent(
                    owner=owner,
                    target=check.target,
                )
            )
            demands.append(ProbeRoutingDemand(owner))

    return AlphaProbeProjection(
        intents=tuple(intents),
        routing_demands=tuple(demands),
    )



@dataclass(frozen=True, slots=True)
class AlphaProbeDesiredProjection:
    semantic: AlphaProbeProjection
    layout: NetworkPolicyLayout
    desired: ProbeNetworkPolicyDesiredState


def build_alpha_explicit_probe_desired(
    profiles: tuple[PayloadProfileRequest, ...],
    profile_config: Mapping[str, ProfileRelease1Config],
    path_routes: tuple[RoutePriorityPathRoute, ...],
    platform: NetworkPolicyPlatformSpace,
    local_platform: ProbeLocalPlatform,
) -> AlphaProbeDesiredProjection:
    """Allocate payload+probe resources once and project explicit probe state.

    The returned layout is the shared layout that the caller must also pass to
    payload desired-state projection. This prevents alpha assembly from
    constructing independent payload/probe resource allocations.
    """
    if not isinstance(path_routes, tuple) or not all(
        isinstance(item, RoutePriorityPathRoute)
        for item in path_routes
    ):
        raise AlphaProbeProjectionError(
            "path_routes must be a tuple of RoutePriorityPathRoute"
        )
    if not isinstance(platform, NetworkPolicyPlatformSpace):
        raise AlphaProbeProjectionError(
            "platform must be NetworkPolicyPlatformSpace"
        )
    if not isinstance(local_platform, ProbeLocalPlatform):
        raise AlphaProbeProjectionError(
            "local_platform must be ProbeLocalPlatform"
        )

    semantic = build_alpha_explicit_probe_projection(
        profiles,
        profile_config,
    )
    layout = allocate_network_policy_layout(
        profiles,
        semantic.routing_demands,
        platform,
    )
    desired = build_probe_network_policy_desired_state(
        semantic.intents,
        layout,
        path_routes,
        platform,
        local_platform,
    )
    return AlphaProbeDesiredProjection(
        semantic=semantic,
        layout=layout,
        desired=desired,
    )
