from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import Iterable

from .binding import LogicalPathId
from .device_policy import DeviceNatPolicyIntent, NatIntent
from .domain import Direction
from .interface_identity import InterfaceIdentity
from .payload_profile import PayloadProfileRequest
from .route_priority_inventory import RoutePriorityPathRoute
from .stack_return_affinity import StackReturnAffinityAllocation


class PayloadNatProjectionError(ValueError):
    pass


@dataclass(frozen=True, order=True, slots=True)
class PayloadMasqueradeSpec:
    path_id: LogicalPathId
    ingress: InterfaceIdentity
    egress: InterfaceIdentity


@dataclass(frozen=True, slots=True)
class ProfileSnatPolicyIntent:
    profile_id: str
    source_address: IPv4Address


@dataclass(frozen=True, slots=True)
class PayloadProfileSnatSpec:
    profile_id: str
    mark: int
    egress: InterfaceIdentity
    source_address: IPv4Address


PayloadNatRuleSpec = PayloadMasqueradeSpec | PayloadProfileSnatSpec


@dataclass(frozen=True, slots=True)
class PayloadNatDesiredState:
    masquerade_rules: tuple[PayloadMasqueradeSpec, ...]
    profile_snat_rules: tuple[PayloadProfileSnatSpec, ...] = ()

    @property
    def rules(self) -> tuple[PayloadNatRuleSpec, ...]:
        return (*self.masquerade_rules, *self.profile_snat_rules)


def build_payload_nat_desired_state(
    profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
    device_policies: Iterable[DeviceNatPolicyIntent],
    host_boundary: InterfaceIdentity,
    profile_snat_policies: Iterable[ProfileSnatPolicyIntent] = (),
    profile_allocations: Iterable[StackReturnAffinityAllocation] = (),
) -> PayloadNatDesiredState:
    if not isinstance(host_boundary, InterfaceIdentity):
        raise PayloadNatProjectionError("host_boundary must be InterfaceIdentity")

    current_profiles = tuple(profiles)
    semantic_paths: set[LogicalPathId] = set()
    profile_by_id: dict[str, PayloadProfileRequest] = {}
    for profile in current_profiles:
        if not isinstance(profile, PayloadProfileRequest):
            raise PayloadNatProjectionError("profiles must contain PayloadProfileRequest")
        if profile.profile_id in profile_by_id:
            raise PayloadNatProjectionError(f"duplicate payload Profile {profile.profile_id!r}")
        profile_by_id[profile.profile_id] = profile
        if len(set(profile.ordered_paths)) != len(profile.ordered_paths):
            raise PayloadNatProjectionError(f"Profile {profile.profile_id!r} repeats a logical path")
        semantic_paths.update(profile.ordered_paths)

    route_by_path: dict[LogicalPathId, RoutePriorityPathRoute] = {}
    endpoint_owner: dict[InterfaceIdentity, LogicalPathId] = {}
    for route in path_routes:
        if not isinstance(route, RoutePriorityPathRoute):
            raise PayloadNatProjectionError("path_routes must contain RoutePriorityPathRoute")
        if route.path_id in route_by_path:
            raise PayloadNatProjectionError(f"duplicate current route realization for {route.path_id!r}")
        if route.endpoint == host_boundary:
            raise PayloadNatProjectionError("host boundary cannot also be a payload VPN path endpoint")
        previous = endpoint_owner.get(route.endpoint)
        if previous is not None and previous != route.path_id:
            raise PayloadNatProjectionError("one current endpoint cannot realize multiple logical paths")
        route_by_path[route.path_id] = route
        endpoint_owner[route.endpoint] = route.path_id
    if set(route_by_path) != semantic_paths:
        raise PayloadNatProjectionError("physical path-route set does not exactly match current semantic payload paths")

    policy_by_device: dict[str, DeviceNatPolicyIntent] = {}
    for policy in device_policies:
        if not isinstance(policy, DeviceNatPolicyIntent):
            raise PayloadNatProjectionError("device_policies must contain DeviceNatPolicyIntent")
        if policy.device_id in policy_by_device:
            raise PayloadNatProjectionError(f"duplicate Device NAT policy for {policy.device_id!r}")
        policy_by_device[policy.device_id] = policy

    masquerade_rules: list[PayloadMasqueradeSpec] = []
    for path_id in sorted(semantic_paths):
        policy = policy_by_device.get(path_id.device_id)
        if policy is None:
            raise PayloadNatProjectionError(f"current payload path {path_id!r} has no explicit normalized NAT intent")
        if policy.nat_intent is NatIntent.NONE:
            continue
        masquerade_rules.append(PayloadMasqueradeSpec(path_id, host_boundary, route_by_path[path_id].endpoint))

    snat_by_profile: dict[str, ProfileSnatPolicyIntent] = {}
    for policy in profile_snat_policies:
        if not isinstance(policy, ProfileSnatPolicyIntent):
            raise PayloadNatProjectionError("profile_snat_policies must contain ProfileSnatPolicyIntent")
        if policy.profile_id in snat_by_profile:
            raise PayloadNatProjectionError(f"duplicate Profile SNAT policy for {policy.profile_id!r}")
        profile = profile_by_id.get(policy.profile_id)
        if profile is None:
            raise PayloadNatProjectionError(f"Profile SNAT policy references unknown Profile {policy.profile_id!r}")
        if profile.direction not in {Direction.INBOUND, Direction.BIDIRECTIONAL}:
            raise PayloadNatProjectionError(f"Profile SNAT policy {policy.profile_id!r} is not inbound-capable")
        snat_by_profile[policy.profile_id] = policy

    allocation_by_profile = {}
    for allocation in profile_allocations:
        if not isinstance(allocation, StackReturnAffinityAllocation):
            raise PayloadNatProjectionError("profile_allocations must contain StackReturnAffinityAllocation")
        if allocation.profile_id in allocation_by_profile:
            raise PayloadNatProjectionError(f"duplicate Profile association allocation {allocation.profile_id!r}")
        allocation_by_profile[allocation.profile_id] = allocation

    profile_snat_rules = []
    for profile_id in sorted(snat_by_profile):
        profile = profile_by_id[profile_id]
        if not profile.ordered_paths:
            continue
        allocation = allocation_by_profile.get(profile_id)
        if allocation is None:
            raise PayloadNatProjectionError(f"active +snat Profile {profile_id!r} has no flow-association allocation")
        policy = snat_by_profile[profile_id]
        profile_snat_rules.append(PayloadProfileSnatSpec(
            profile_id, allocation.mark, host_boundary, policy.source_address
        ))

    return PayloadNatDesiredState(tuple(masquerade_rules), tuple(profile_snat_rules))
