"""C.001 semantic wrapper for D.002 WireGuard peer technical probes."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import Iterable

from .bound_probe_policy import (
    BoundProbeIntent,
    build_bound_probe_policy_desired_state,
)
from .network_policy_layout import (
    NetworkPolicyLayout,
    NetworkPolicyPlatformSpace,
    WireGuardPeerProbeOwner,
)
from .probe_policy import (
    AvailabilityProbeMechanism,
    ProbeLocalPlatform,
    ProbeNetworkPolicyDesiredState,
)
from .route_priority_inventory import RoutePriorityPathRoute


class WireGuardPeerProbePolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WireGuardPeerProbeIntent:
    owner: WireGuardPeerProbeOwner
    target: IPv4Address
    path_route: RoutePriorityPathRoute
    mechanism: AvailabilityProbeMechanism = AvailabilityProbeMechanism.ICMP

    def __post_init__(self) -> None:
        if not isinstance(self.owner, WireGuardPeerProbeOwner):
            raise WireGuardPeerProbePolicyError(
                "owner must be WireGuardPeerProbeOwner"
            )
        if not isinstance(self.target, IPv4Address):
            raise WireGuardPeerProbePolicyError(
                "target must be IPv4Address"
            )
        if not isinstance(self.path_route, RoutePriorityPathRoute):
            raise WireGuardPeerProbePolicyError(
                "path_route must be RoutePriorityPathRoute"
            )
        if self.path_route.path_id.device_id != self.owner.device_id:
            raise WireGuardPeerProbePolicyError(
                "peer probe owner Device differs from current path Device"
            )
        if self.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise WireGuardPeerProbePolicyError(
                "Release 1 WireGuard peer probes must use ICMP"
            )


def build_wireguard_peer_probe_policy_desired_state(
    intents: Iterable[WireGuardPeerProbeIntent],
    layout: NetworkPolicyLayout,
    network_platform: NetworkPolicyPlatformSpace,
    local_platform: ProbeLocalPlatform,
) -> ProbeNetworkPolicyDesiredState:
    raw = tuple(intents)
    if any(not isinstance(item, WireGuardPeerProbeIntent) for item in raw):
        raise WireGuardPeerProbePolicyError(
            "intents must contain WireGuardPeerProbeIntent"
        )
    return build_bound_probe_policy_desired_state(
        tuple(
            BoundProbeIntent(
                item.owner,
                item.target,
                item.path_route,
                item.mechanism,
            )
            for item in raw
        ),
        layout,
        network_platform,
        local_platform,
    )
