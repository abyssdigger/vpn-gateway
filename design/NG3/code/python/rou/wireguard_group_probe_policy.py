"""C.001 semantic wrapper for D.002 WireGuard recoverable-group probes."""

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
    WireGuardGroupProbeOwner,
)
from .probe_policy import (
    AvailabilityProbeMechanism,
    ProbeLocalPlatform,
    ProbeNetworkPolicyDesiredState,
)
from .route_priority_inventory import RoutePriorityPathRoute


class WireGuardGroupProbePolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WireGuardGroupProbeIntent:
    owner: WireGuardGroupProbeOwner
    target: IPv4Address
    path_route: RoutePriorityPathRoute
    mechanism: AvailabilityProbeMechanism = AvailabilityProbeMechanism.ICMP

    def __post_init__(self) -> None:
        if not isinstance(self.owner, WireGuardGroupProbeOwner):
            raise WireGuardGroupProbePolicyError(
                "owner must be WireGuardGroupProbeOwner"
            )
        if not isinstance(self.target, IPv4Address):
            raise WireGuardGroupProbePolicyError(
                "target must be IPv4Address"
            )
        if not isinstance(self.path_route, RoutePriorityPathRoute):
            raise WireGuardGroupProbePolicyError(
                "path_route must be RoutePriorityPathRoute"
            )
        if self.path_route.path_id.device_id != self.owner.device_id:
            raise WireGuardGroupProbePolicyError(
                "group probe owner Device differs from current path Device"
            )
        if self.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise WireGuardGroupProbePolicyError(
                "Release 1 WireGuard group probes must use ICMP"
            )


def build_wireguard_group_probe_policy_desired_state(
    intents: Iterable[WireGuardGroupProbeIntent],
    layout: NetworkPolicyLayout,
    network_platform: NetworkPolicyPlatformSpace,
    local_platform: ProbeLocalPlatform,
) -> ProbeNetworkPolicyDesiredState:
    raw = tuple(intents)
    if any(not isinstance(item, WireGuardGroupProbeIntent) for item in raw):
        raise WireGuardGroupProbePolicyError(
            "intents must contain WireGuardGroupProbeIntent"
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
