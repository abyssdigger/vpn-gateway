from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network
from typing import Iterable

from .binding import LogicalPathId
from .device_policy import DeviceNatPolicyIntent, NatIntent
from .domain import Direction
from .interface_identity import InterfaceIdentity
from .payload_profile import PayloadProfileRequest
from .profile_prefix_partition import (
    ProfilePrefixPartitionError,
    build_inbound_profile_partition,
)
from .route_priority_inventory import RoutePriorityPathRoute


class PayloadNatProjectionError(ValueError):
    pass


@dataclass(frozen=True, order=True, slots=True)
class PayloadMasqueradeSpec:
    """Device-owned ordinary->VPN source NAT on one current path."""

    path_id: LogicalPathId
    ingress: InterfaceIdentity
    egress: InterfaceIdentity


@dataclass(frozen=True, order=True, slots=True)
class ProfileGatewayMasqueradeSpec:
    """Profile-owned VPN->ordinary gateway NAT inside STACK.

    The remote-source fragment is already disjoint under most-specific Profile
    classification. Exact host-local destinations are negative matches so this
    behavior applies only to payload that the ordinary host will forward onward.
    """

    profile_id: str
    path_id: LogicalPathId
    ingress: InterfaceIdentity
    egress: InterfaceIdentity
    remote_source: IPv4Network

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise PayloadNatProjectionError(
                "gateway NAT profile_id must be non-empty text"
            )
        if not isinstance(self.path_id, LogicalPathId):
            raise PayloadNatProjectionError(
                "gateway NAT path_id must be LogicalPathId"
            )
        if not isinstance(self.ingress, InterfaceIdentity):
            raise PayloadNatProjectionError(
                "gateway NAT ingress must be InterfaceIdentity"
            )
        if not isinstance(self.egress, InterfaceIdentity):
            raise PayloadNatProjectionError(
                "gateway NAT egress must be InterfaceIdentity"
            )
        if not isinstance(self.remote_source, IPv4Network):
            raise PayloadNatProjectionError(
                "gateway NAT remote_source must be IPv4Network"
            )


PayloadNatRuleSpec = PayloadMasqueradeSpec | ProfileGatewayMasqueradeSpec


@dataclass(frozen=True, slots=True)
class PayloadNatDesiredState:
    masquerade_rules: tuple[PayloadNatRuleSpec, ...]


def build_payload_nat_desired_state(
    profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
    device_policies: Iterable[DeviceNatPolicyIntent],
    host_boundary: InterfaceIdentity,
    *,
    gateway_nat_profile_ids: Iterable[str] = (),
) -> PayloadNatDesiredState:
    """Project both accepted source-NAT semantics inside the managed domain.

    Device NAT:
        ordinary -> current VPN path, exact boundary/path pair.

    Profile gateway NAT:
        current VPN path -> ordinary boundary, disjoint remote-source fragment,

    Both run after managed payload filtering in postrouting.  No Profile
    identity or NAT class crosses into the ordinary host namespace.
    """
    if not isinstance(host_boundary, InterfaceIdentity):
        raise PayloadNatProjectionError(
            "host_boundary must be InterfaceIdentity"
        )

    current_profiles = tuple(profiles)
    semantic_paths: set[LogicalPathId] = set()
    profile_ids: set[str] = set()
    profile_by_id: dict[str, PayloadProfileRequest] = {}
    for profile in current_profiles:
        if not isinstance(profile, PayloadProfileRequest):
            raise PayloadNatProjectionError(
                "profiles must contain PayloadProfileRequest"
            )
        if profile.profile_id in profile_ids:
            raise PayloadNatProjectionError(
                f"duplicate payload Profile {profile.profile_id!r}"
            )
        profile_ids.add(profile.profile_id)
        profile_by_id[profile.profile_id] = profile
        if len(set(profile.ordered_paths)) != len(profile.ordered_paths):
            raise PayloadNatProjectionError(
                f"Profile {profile.profile_id!r} repeats a logical path"
            )
        semantic_paths.update(profile.ordered_paths)

    gateway_ids_raw = tuple(gateway_nat_profile_ids)
    if any(not isinstance(item, str) or not item for item in gateway_ids_raw):
        raise PayloadNatProjectionError(
            "gateway_nat_profile_ids must contain non-empty Profile IDs"
        )
    if len(set(gateway_ids_raw)) != len(gateway_ids_raw):
        raise PayloadNatProjectionError(
            "gateway_nat_profile_ids must not contain duplicates"
        )
    gateway_ids = frozenset(gateway_ids_raw)
    unknown_gateway_ids = gateway_ids - profile_ids
    if unknown_gateway_ids:
        raise PayloadNatProjectionError(
            "gateway NAT references unknown current Profile(s): "
            + ", ".join(sorted(unknown_gateway_ids))
        )
    for profile_id in gateway_ids:
        if profile_by_id[profile_id].direction not in {
            Direction.INBOUND,
            Direction.BIDIRECTIONAL,
        }:
            raise PayloadNatProjectionError(
                f"Profile {profile_id!r} requests gateway NAT without VPN-to-ordinary direction"
            )


    route_by_path: dict[LogicalPathId, RoutePriorityPathRoute] = {}
    endpoint_owner: dict[InterfaceIdentity, LogicalPathId] = {}
    for route in path_routes:
        if not isinstance(route, RoutePriorityPathRoute):
            raise PayloadNatProjectionError(
                "path_routes must contain RoutePriorityPathRoute"
            )
        if route.path_id in route_by_path:
            raise PayloadNatProjectionError(
                f"duplicate current route realization for {route.path_id!r}"
            )
        if route.endpoint == host_boundary:
            raise PayloadNatProjectionError(
                "host boundary cannot also be a payload VPN path endpoint"
            )
        previous = endpoint_owner.get(route.endpoint)
        if previous is not None and previous != route.path_id:
            raise PayloadNatProjectionError(
                "one current endpoint cannot realize multiple logical paths"
            )
        route_by_path[route.path_id] = route
        endpoint_owner[route.endpoint] = route.path_id

    if set(route_by_path) != semantic_paths:
        raise PayloadNatProjectionError(
            "physical path-route set does not exactly match current semantic payload paths"
        )

    policy_by_device: dict[str, DeviceNatPolicyIntent] = {}
    for policy in device_policies:
        if not isinstance(policy, DeviceNatPolicyIntent):
            raise PayloadNatProjectionError(
                "device_policies must contain DeviceNatPolicyIntent"
            )
        if policy.device_id in policy_by_device:
            raise PayloadNatProjectionError(
                f"duplicate Device NAT policy for {policy.device_id!r}"
            )
        policy_by_device[policy.device_id] = policy

    rules: list[PayloadNatRuleSpec] = []

    # Device/path NAT remains one physical rule per currently used path.
    for path_id in sorted(semantic_paths):
        policy = policy_by_device.get(path_id.device_id)
        if policy is None:
            raise PayloadNatProjectionError(
                f"current payload path {path_id!r} has no explicit normalized NAT intent"
            )
        if policy.nat_intent is NatIntent.MASQUERADE:
            route = route_by_path[path_id]
            rules.append(
                PayloadMasqueradeSpec(
                    path_id=path_id,
                    ingress=host_boundary,
                    egress=route.endpoint,
                )
            )

    # Gateway NAT uses the same inbound most-specific Profile partition as
    # forwarding permission, so a nested no-SNAT Profile can never fall through
    # into a broader +snat Profile rule.
    for path_id in sorted(semantic_paths):
        try:
            fragments = build_inbound_profile_partition(
                current_profiles,
                path_id,
            )
        except ProfilePrefixPartitionError as exc:
            raise PayloadNatProjectionError(str(exc)) from exc
        ingress = route_by_path[path_id].endpoint
        for fragment in fragments:
            if fragment.profile_id not in gateway_ids:
                continue
            rules.append(
                ProfileGatewayMasqueradeSpec(
                    profile_id=fragment.profile_id,
                    path_id=path_id,
                    ingress=ingress,
                    egress=host_boundary,
                    remote_source=fragment.remote_prefix,
                )
            )

    return PayloadNatDesiredState(
        masquerade_rules=tuple(rules),
    )
