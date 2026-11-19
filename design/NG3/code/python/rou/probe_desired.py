"""Pure assembly from Release-1 availability config to probe network desired state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .availability_description import resolve_availability_probe_intents
from .network_policy_layout import (
    NetworkPolicyLayout,
    NetworkPolicyPlatformSpace,
    ProbeRoutingDemand,
    allocate_network_policy_layout,
)
from .payload_profile import PayloadProfileRequest
from .probe_policy import (
    ProbeLocalPlatform,
    ProbeNetworkPolicyDesiredState,
    build_probe_network_policy_desired_state,
)
from .release1_config import Release1Config
from .route_priority_inventory import RoutePriorityPathRoute


class ProbeDesiredAssemblyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProbeDesiredAssembly:
    layout: NetworkPolicyLayout
    probe: ProbeNetworkPolicyDesiredState


def build_probe_desired_assembly(
    config: Release1Config,
    payload_profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
    network_platform: NetworkPolicyPlatformSpace,
    local_platform: ProbeLocalPlatform,
) -> ProbeDesiredAssembly:
    """Resolve current availability intent and allocate one shared lower layout."""
    profiles = tuple(payload_profiles)
    routes = tuple(path_routes)

    if any(not isinstance(item, PayloadProfileRequest) for item in profiles):
        raise ProbeDesiredAssemblyError(
            "payload_profiles must contain PayloadProfileRequest"
        )
    if any(not isinstance(item, RoutePriorityPathRoute) for item in routes):
        raise ProbeDesiredAssemblyError(
            "path_routes must contain RoutePriorityPathRoute"
        )
    path_ids = tuple(route.path_id for route in routes)
    if len(set(path_ids)) != len(path_ids):
        raise ProbeDesiredAssemblyError(
            "path_routes contains duplicate logical path realization"
        )

    profile_paths = frozenset(
        path
        for profile in profiles
        for path in profile.ordered_paths
    )
    route_paths = frozenset(path_ids)
    if profile_paths != route_paths:
        raise ProbeDesiredAssemblyError(
            "payload Profile current path membership does not match path_routes"
        )

    intents = resolve_availability_probe_intents(config, path_ids)
    demands = tuple(
        ProbeRoutingDemand(intent.owner)
        for intent in intents
    )
    layout = allocate_network_policy_layout(
        profiles,
        demands,
        network_platform,
    )
    probe = build_probe_network_policy_desired_state(
        intents,
        layout,
        routes,
        network_platform,
        local_platform,
    )
    return ProbeDesiredAssembly(layout, probe)
