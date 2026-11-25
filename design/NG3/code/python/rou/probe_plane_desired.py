"""Combined C.001 desired-state assembly for the shared physical probe plane.

Architecture: A.007 AvailabilityProbeAgent, C.001 NetworkPolicyAdapter,
D.002 WireGuardPeerManager.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .bound_probe_policy import (
    BoundProbeIntent,
    build_bound_probe_policy_desired_state,
)
from .network_policy_layout import (
    NetworkPolicyLayout,
    NetworkPolicyPlatformSpace,
    ProbeRoutingDemand,
    WireGuardGroupProbeOwner,
    WireGuardPeerProbeOwner,
    allocate_network_policy_layout,
    probe_owner_sort_key,
)
from .payload_profile import PayloadProfileRequest
from .probe_policy import (
    AvailabilityProbeIntent,
    ProbeLocalPlatform,
    ProbeNetworkPolicyDesiredState,
)
from .release1_config import CurrentConfig
from .route_priority_inventory import RoutePriorityPathRoute
from .wireguard_group_probe_policy import WireGuardGroupProbeIntent
from .wireguard_peer_probe_policy import WireGuardPeerProbeIntent


class ProbePlaneDesiredAssemblyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProbePlaneDesiredAssembly:
    """One accepted full-union desired state plus its typed semantic inputs."""

    layout: NetworkPolicyLayout
    probe: ProbeNetworkPolicyDesiredState
    availability_intents: tuple[AvailabilityProbeIntent, ...]
    peer_intents: tuple[WireGuardPeerProbeIntent, ...]
    group_intents: tuple[WireGuardGroupProbeIntent, ...]


def project_current_wireguard_probe_intents(
    current_config: CurrentConfig,
    payload_profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
) -> tuple[
    tuple[WireGuardPeerProbeIntent, ...],
    tuple[WireGuardGroupProbeIntent, ...],
]:
    """Project normalized managed-WireGuard current demand onto current paths only."""

    if not isinstance(current_config, CurrentConfig):
        raise ProbePlaneDesiredAssemblyError(
            "current_config must be CurrentConfig"
        )
    profiles = tuple(payload_profiles)
    routes = tuple(path_routes)
    if any(not isinstance(item, PayloadProfileRequest) for item in profiles):
        raise ProbePlaneDesiredAssemblyError(
            "payload_profiles must contain PayloadProfileRequest"
        )
    if any(not isinstance(item, RoutePriorityPathRoute) for item in routes):
        raise ProbePlaneDesiredAssemblyError(
            "path_routes must contain RoutePriorityPathRoute"
        )

    profile_by_id = {item.profile_id: item for item in profiles}
    if len(profile_by_id) != len(profiles):
        raise ProbePlaneDesiredAssemblyError(
            "payload_profiles contains duplicate Profile"
        )
    route_by_path = {item.path_id: item for item in routes}
    if len(route_by_path) != len(routes):
        raise ProbePlaneDesiredAssemblyError(
            "path_routes contains duplicate logical path realization"
        )

    peer_by_owner: dict[
        WireGuardPeerProbeOwner,
        WireGuardPeerProbeIntent,
    ] = {}
    groups: list[WireGuardGroupProbeIntent] = []

    for group_key in sorted(current_config.wireguard_groups):
        group = current_config.wireguard_groups[group_key]
        profile = profile_by_id.get(group.profile_id)
        if profile is None:
            raise ProbePlaneDesiredAssemblyError(
                f"WireGuard group {group_key!r} has no current payload Profile"
            )

        current_paths = tuple(
            path
            for path in profile.ordered_paths
            if path.device_id == group.device_id
        )
        if not current_paths:
            # The managed Device has no accepted current path realization.
            continue
        if len(current_paths) != 1:
            raise ProbePlaneDesiredAssemblyError(
                f"managed WireGuard Device {group.device_id!r} has ambiguous "
                "current logical paths"
            )
        route = route_by_path.get(current_paths[0])
        if route is None:
            raise ProbePlaneDesiredAssemblyError(
                "WireGuard group current path has no accepted route realization"
            )

        managed = current_config.managed_vpns.get(group.device_id)
        if managed is None:
            raise ProbePlaneDesiredAssemblyError(
                f"WireGuard group {group_key!r} has no managed Device config"
            )
        peer_by_id = {item.peer_id: item for item in managed.peers}
        if len(peer_by_id) != len(managed.peers):
            raise ProbePlaneDesiredAssemblyError(
                f"managed WireGuard Device {group.device_id!r} repeats peer ID"
            )

        for membership in group.peer_memberships:
            peer = peer_by_id.get(membership.peer_id)
            if peer is None:
                raise ProbePlaneDesiredAssemblyError(
                    f"WireGuard group {group_key!r} references unknown peer "
                    f"{membership.peer_id!r}"
                )
            owner = WireGuardPeerProbeOwner(
                group.device_id,
                membership.peer_id,
            )
            intent = WireGuardPeerProbeIntent(
                owner,
                peer.probe_target,
                route,
            )
            previous = peer_by_owner.get(owner)
            if previous is not None and previous != intent:
                raise ProbePlaneDesiredAssemblyError(
                    f"WireGuard peer {owner!r} has conflicting current probe binding"
                )
            peer_by_owner[owner] = intent

        check = group.availability_check
        if check is not None:
            if check.mechanism != "icmp" or check.target is None:
                raise ProbePlaneDesiredAssemblyError(
                    f"WireGuard group {group_key!r} has unsupported availability check"
                )
            groups.append(
                WireGuardGroupProbeIntent(
                    WireGuardGroupProbeOwner(
                        group.profile_id,
                        group.device_id,
                    ),
                    check.target,
                    route,
                )
            )

    peers = tuple(
        sorted(
            peer_by_owner.values(),
            key=lambda item: probe_owner_sort_key(item.owner),
        )
    )
    ordered_groups = tuple(
        sorted(
            groups,
            key=lambda item: probe_owner_sort_key(item.owner),
        )
    )
    return peers, ordered_groups


def build_probe_plane_desired_assembly(
    payload_profiles: Iterable[PayloadProfileRequest],
    availability_intents: Iterable[AvailabilityProbeIntent],
    peer_intents: Iterable[WireGuardPeerProbeIntent],
    group_intents: Iterable[WireGuardGroupProbeIntent],
    path_routes: Iterable[RoutePriorityPathRoute],
    network_platform: NetworkPolicyPlatformSpace,
    local_platform: ProbeLocalPlatform,
) -> ProbePlaneDesiredAssembly:
    """Compose A.007 and D.002 semantic owners into one C.001 physical union."""

    profiles = tuple(payload_profiles)
    availability = _typed_sorted(
        availability_intents,
        AvailabilityProbeIntent,
        "availability_intents",
    )
    peers = _typed_sorted(
        peer_intents,
        WireGuardPeerProbeIntent,
        "peer_intents",
    )
    groups = _typed_sorted(
        group_intents,
        WireGuardGroupProbeIntent,
        "group_intents",
    )
    routes = tuple(path_routes)

    if any(not isinstance(item, PayloadProfileRequest) for item in profiles):
        raise ProbePlaneDesiredAssemblyError(
            "payload_profiles must contain PayloadProfileRequest"
        )
    if any(not isinstance(item, RoutePriorityPathRoute) for item in routes):
        raise ProbePlaneDesiredAssemblyError(
            "path_routes must contain RoutePriorityPathRoute"
        )

    route_by_path: dict[object, RoutePriorityPathRoute] = {}
    endpoint_owner: dict[object, object] = {}
    for route in routes:
        if route.path_id in route_by_path:
            raise ProbePlaneDesiredAssemblyError(
                "path_routes contains duplicate logical path realization"
            )
        previous = endpoint_owner.get(route.endpoint)
        if previous is not None and previous != route.path_id:
            raise ProbePlaneDesiredAssemblyError(
                "one endpoint is realized for multiple logical paths"
            )
        route_by_path[route.path_id] = route
        endpoint_owner[route.endpoint] = route.path_id

    profile_by_id: dict[str, PayloadProfileRequest] = {}
    for profile in profiles:
        if profile.profile_id in profile_by_id:
            raise ProbePlaneDesiredAssemblyError(
                f"payload_profiles contains duplicate Profile {profile.profile_id!r}"
            )
        profile_by_id[profile.profile_id] = profile

    profile_paths = frozenset(
        path
        for profile in profiles
        for path in profile.ordered_paths
    )
    if profile_paths != frozenset(route_by_path):
        raise ProbePlaneDesiredAssemblyError(
            "payload Profile current path membership does not match path_routes"
        )

    bound: list[BoundProbeIntent] = []
    for intent in availability:
        profile = profile_by_id.get(intent.owner.profile_id)
        if profile is None or intent.owner.path_id not in profile.ordered_paths:
            raise ProbePlaneDesiredAssemblyError(
                "availability owner is outside current Profile/path membership"
            )
        path_route = route_by_path.get(intent.owner.path_id)
        if path_route is None:
            raise ProbePlaneDesiredAssemblyError(
                f"availability owner has no current path realization: {intent.owner!r}"
            )
        bound.append(
            BoundProbeIntent(
                intent.owner,
                intent.target,
                path_route,
                intent.mechanism,
            )
        )

    for intent in peers:
        current = route_by_path.get(intent.path_route.path_id)
        if current != intent.path_route:
            raise ProbePlaneDesiredAssemblyError(
                f"D.002 probe intent is not bound to the accepted current path: "
                f"{intent.owner!r}"
            )
        bound.append(
            BoundProbeIntent(
                intent.owner,
                intent.target,
                intent.path_route,
                intent.mechanism,
            )
        )

    for intent in groups:
        profile = profile_by_id.get(intent.owner.profile_id)
        if (
            profile is None
            or intent.path_route.path_id not in profile.ordered_paths
        ):
            raise ProbePlaneDesiredAssemblyError(
                "group probe owner is outside current Profile/path membership"
            )
        current = route_by_path.get(intent.path_route.path_id)
        if current != intent.path_route:
            raise ProbePlaneDesiredAssemblyError(
                f"D.002 probe intent is not bound to the accepted current path: "
                f"{intent.owner!r}"
            )
        bound.append(
            BoundProbeIntent(
                intent.owner,
                intent.target,
                intent.path_route,
                intent.mechanism,
            )
        )

    owners = tuple(item.owner for item in bound)
    if len(set(owners)) != len(owners):
        raise ProbePlaneDesiredAssemblyError(
            "combined probe plane contains duplicate semantic owner"
        )

    layout = allocate_network_policy_layout(
        profiles,
        tuple(ProbeRoutingDemand(owner) for owner in owners),
        network_platform,
    )
    probe = build_bound_probe_policy_desired_state(
        bound,
        layout,
        network_platform,
        local_platform,
    )
    return ProbePlaneDesiredAssembly(
        layout=layout,
        probe=probe,
        availability_intents=availability,
        peer_intents=peers,
        group_intents=groups,
    )


def _typed_sorted(
    values: Iterable[object],
    expected_type: type,
    label: str,
):
    raw = tuple(values)
    if any(not isinstance(item, expected_type) for item in raw):
        raise ProbePlaneDesiredAssemblyError(
            f"{label} contains an unsupported value"
        )
    return tuple(
        sorted(
            raw,
            key=lambda item: probe_owner_sort_key(item.owner),
        )
    )
