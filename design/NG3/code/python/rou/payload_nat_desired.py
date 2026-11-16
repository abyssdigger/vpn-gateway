from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .binding import LogicalPathId
from .device_policy import DeviceNatPolicyIntent, NatIntent
from .interface_identity import InterfaceIdentity
from .payload_profile import PayloadProfileRequest
from .route_priority_inventory import RoutePriorityPathRoute


class PayloadNatProjectionError(ValueError):
    pass


@dataclass(frozen=True, order=True, slots=True)
class PayloadMasqueradeSpec:
    path_id: LogicalPathId
    ingress: InterfaceIdentity
    egress: InterfaceIdentity


@dataclass(frozen=True, slots=True)
class PayloadNatDesiredState:
    masquerade_rules: tuple[PayloadMasqueradeSpec, ...]


def build_payload_nat_desired_state(
    profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
    device_policies: Iterable[DeviceNatPolicyIntent],
    host_boundary: InterfaceIdentity,
) -> PayloadNatDesiredState:
    """Project explicit Device NAT intent onto current payload paths.

    This consumes normalized semantics only; it does not parse external NAT
    configuration spelling and it does not inspect availability state.
    """
    if not isinstance(host_boundary, InterfaceIdentity):
        raise PayloadNatProjectionError(
            "host_boundary must be InterfaceIdentity"
        )

    semantic_paths: set[LogicalPathId] = set()
    profile_ids: set[str] = set()
    for profile in profiles:
        if not isinstance(profile, PayloadProfileRequest):
            raise PayloadNatProjectionError(
                "profiles must contain PayloadProfileRequest"
            )
        if profile.profile_id in profile_ids:
            raise PayloadNatProjectionError(
                f"duplicate payload Profile {profile.profile_id!r}"
            )
        profile_ids.add(profile.profile_id)
        if len(set(profile.ordered_paths)) != len(profile.ordered_paths):
            raise PayloadNatProjectionError(
                f"Profile {profile.profile_id!r} repeats a logical path"
            )
        semantic_paths.update(profile.ordered_paths)

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

    rules: list[PayloadMasqueradeSpec] = []
    for path_id in sorted(semantic_paths):
        policy = policy_by_device.get(path_id.device_id)
        if policy is None:
            raise PayloadNatProjectionError(
                f"current payload path {path_id!r} has no explicit normalized NAT intent"
            )
        if policy.nat_intent is NatIntent.NONE:
            continue
        route = route_by_path[path_id]
        rules.append(
            PayloadMasqueradeSpec(
                path_id=path_id,
                ingress=host_boundary,
                egress=route.endpoint,
            )
        )

    return PayloadNatDesiredState(
        masquerade_rules=tuple(rules),
    )
