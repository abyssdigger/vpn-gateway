"""Pure managed-stack Profile flow-association and return-affinity projection.

The owned conntrack mark represents the selected Profile for the whole flow:

- VPN-originated NEW is classified by ingress path + remote source;
- ordinary-originated NEW for a bidirectional Profile is classified by the
  canonical outbound destination partition;
- established host-boundary replies restore the Profile mark to the packet so
  RPDB selects the original Profile routing table.

Forwarding permission remains a separate payload_forward responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network
from typing import Iterable

from .binding import LogicalPathId
from .domain import Direction
from .interface_identity import InterfaceIdentity
from .network_policy_layout import NetworkPolicyLayout, NumericResourcePool
from .payload_profile import PayloadProfileRequest
from .profile_prefix_partition import (
    ProfilePrefixPartitionError,
    build_inbound_profile_partition,
    build_outbound_profile_partition,
)
from .route_priority_inventory import RoutePriorityPathRoute


class StackReturnAffinityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StackReturnAffinityAllocation:
    profile_id: str
    mark: int
    rule_priority: int

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise StackReturnAffinityError("profile_id must be non-empty text")
        for label, value in (("mark", self.mark), ("rule_priority", self.rule_priority)):
            if type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
                raise StackReturnAffinityError(
                    f"{label} must be an integer in [1, 2^32-1]"
                )


@dataclass(frozen=True, slots=True)
class StackReturnAffinityPlatformSpace:
    marks: NumericResourcePool
    rule_priorities: NumericResourcePool

    def __post_init__(self) -> None:
        if self.marks.first == 0:
            raise StackReturnAffinityError("affinity mark pool must not include mark 0")
        if self.rule_priorities.first == 0:
            raise StackReturnAffinityError(
                "affinity RPDB priority pool must not include Linux local priority 0"
            )


def allocate_stack_return_affinity(
    profiles: Iterable[PayloadProfileRequest],
    layout: NetworkPolicyLayout,
    platform: StackReturnAffinityPlatformSpace,
) -> tuple[StackReturnAffinityAllocation, ...]:
    if not isinstance(layout, NetworkPolicyLayout):
        raise StackReturnAffinityError("layout must be NetworkPolicyLayout")
    if not isinstance(platform, StackReturnAffinityPlatformSpace):
        raise StackReturnAffinityError(
            "platform must be StackReturnAffinityPlatformSpace"
        )

    current_profiles = tuple(profiles)
    if any(not isinstance(profile, PayloadProfileRequest) for profile in current_profiles):
        raise StackReturnAffinityError(
            "profiles must contain PayloadProfileRequest"
        )

    active = tuple(
        sorted(
            (
                profile
                for profile in current_profiles
                if profile.direction in {Direction.INBOUND, Direction.BIDIRECTIONAL}
                and profile.ordered_paths
            ),
            key=lambda item: item.profile_id,
        )
    )
    if len(active) != len({profile.profile_id for profile in active}):
        raise StackReturnAffinityError("duplicate inbound Profile identity")

    layout_ids = {item.profile_id for item in layout.payload}
    profile_ids = {profile.profile_id for profile in current_profiles}
    if layout_ids != profile_ids:
        raise StackReturnAffinityError(
            "layout payload Profile set must exactly match semantic Profiles"
        )

    marks = platform.marks.take(len(active))
    priorities = platform.rule_priorities.take(len(active))
    if layout.dispatch_rules and priorities:
        first_dispatch = min(item.priority for item in layout.dispatch_rules)
        if max(priorities) >= first_dispatch:
            raise StackReturnAffinityError(
                "affinity RPDB rules must execute before ordinary payload dispatch"
            )

    return tuple(
        StackReturnAffinityAllocation(
            profile_id=profile.profile_id,
            mark=marks[index],
            rule_priority=priorities[index],
        )
        for index, profile in enumerate(active)
    )


@dataclass(frozen=True, slots=True)
class StackReturnClassifierSpec:
    """VPN-originated NEW classifier: ingress path + remote source."""

    profile_id: str
    ingress: InterfaceIdentity
    remote_prefix: IPv4Network
    mark: int


@dataclass(frozen=True, slots=True)
class StackOutboundAssociationSpec:
    """Ordinary-originated NEW classifier for a bidirectional Profile."""

    profile_id: str
    ingress: InterfaceIdentity
    remote_prefix: IPv4Network
    mark: int


@dataclass(frozen=True, slots=True)
class StackReturnRuleSpec:
    profile_id: str
    mark: int
    table: int
    priority: int


@dataclass(frozen=True, slots=True)
class StackReturnAffinityDesired:
    host_boundary: InterfaceIdentity
    classifiers: tuple[StackReturnClassifierSpec, ...]
    outbound_classifiers: tuple[StackOutboundAssociationSpec, ...]
    rules: tuple[StackReturnRuleSpec, ...]


def build_stack_return_affinity_desired(
    profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
    host_boundary: InterfaceIdentity,
    layout: NetworkPolicyLayout,
    allocations: Iterable[StackReturnAffinityAllocation],
) -> StackReturnAffinityDesired:
    if not isinstance(host_boundary, InterfaceIdentity):
        raise StackReturnAffinityError("host_boundary must be InterfaceIdentity")
    if not isinstance(layout, NetworkPolicyLayout):
        raise StackReturnAffinityError("layout must be NetworkPolicyLayout")

    current_profiles = tuple(profiles)
    profile_by_id: dict[str, PayloadProfileRequest] = {}
    for profile in current_profiles:
        if not isinstance(profile, PayloadProfileRequest):
            raise StackReturnAffinityError(
                "profiles must contain PayloadProfileRequest"
            )
        if profile.profile_id in profile_by_id:
            raise StackReturnAffinityError(
                f"duplicate Profile {profile.profile_id!r}"
            )
        profile_by_id[profile.profile_id] = profile
        if (
            profile.direction in {Direction.INBOUND, Direction.BIDIRECTIONAL}
            and len(profile.ordered_paths) > 1
        ):
            raise StackReturnAffinityError(
                f"Release-1 inbound Profile {profile.profile_id!r} has more than one current path"
            )

    route_by_path: dict[LogicalPathId, RoutePriorityPathRoute] = {}
    for route in path_routes:
        if not isinstance(route, RoutePriorityPathRoute):
            raise StackReturnAffinityError(
                "path_routes must contain RoutePriorityPathRoute"
            )
        if route.path_id in route_by_path:
            raise StackReturnAffinityError(
                f"duplicate path realization {route.path_id!r}"
            )
        if route.endpoint == host_boundary:
            raise StackReturnAffinityError(
                "host boundary cannot be a VPN path endpoint"
            )
        route_by_path[route.path_id] = route

    required_paths = {
        path_id
        for profile in current_profiles
        for path_id in profile.ordered_paths
    }
    if set(route_by_path) != required_paths:
        raise StackReturnAffinityError(
            "physical path set must exactly match semantic Profile paths"
        )

    table_by_profile = {
        item.profile_id: item.table
        for item in layout.payload
    }
    if set(table_by_profile) != set(profile_by_id):
        raise StackReturnAffinityError(
            "layout payload Profile set must exactly match semantic Profiles"
        )

    allocation_by_profile: dict[str, StackReturnAffinityAllocation] = {}
    seen_marks: set[int] = set()
    seen_priorities: set[int] = set()
    for allocation in allocations:
        if not isinstance(allocation, StackReturnAffinityAllocation):
            raise StackReturnAffinityError(
                "allocations must contain StackReturnAffinityAllocation"
            )
        if allocation.profile_id in allocation_by_profile:
            raise StackReturnAffinityError(
                f"duplicate affinity allocation for {allocation.profile_id!r}"
            )
        if allocation.mark in seen_marks:
            raise StackReturnAffinityError("affinity marks must be unique")
        if allocation.rule_priority in seen_priorities:
            raise StackReturnAffinityError(
                "affinity rule priorities must be unique"
            )
        allocation_by_profile[allocation.profile_id] = allocation
        seen_marks.add(allocation.mark)
        seen_priorities.add(allocation.rule_priority)

    association_profile_ids = {
        profile.profile_id
        for profile in current_profiles
        if profile.direction in {Direction.INBOUND, Direction.BIDIRECTIONAL}
        and profile.ordered_paths
    }
    if set(allocation_by_profile) != association_profile_ids:
        raise StackReturnAffinityError(
            "affinity allocations must exactly cover current inbound-capable Profiles with paths"
        )

    inbound_classifiers: list[StackReturnClassifierSpec] = []
    for path_id in sorted(required_paths):
        try:
            fragments = build_inbound_profile_partition(
                current_profiles,
                path_id,
            )
        except ProfilePrefixPartitionError as exc:
            raise StackReturnAffinityError(str(exc)) from exc

        endpoint = route_by_path[path_id].endpoint
        for fragment in fragments:
            allocation = allocation_by_profile.get(fragment.profile_id)
            if allocation is None:
                raise StackReturnAffinityError(
                    f"inbound fragment for {fragment.profile_id!r} has no affinity allocation"
                )
            inbound_classifiers.append(
                StackReturnClassifierSpec(
                    profile_id=fragment.profile_id,
                    ingress=endpoint,
                    remote_prefix=fragment.remote_prefix,
                    mark=allocation.mark,
                )
            )

    try:
        outbound_fragments = build_outbound_profile_partition(current_profiles)
    except ProfilePrefixPartitionError as exc:
        raise StackReturnAffinityError(str(exc)) from exc

    outbound_classifiers: list[StackOutboundAssociationSpec] = []
    for fragment in outbound_fragments:
        allocation = allocation_by_profile.get(fragment.profile_id)
        if allocation is None:
            # The selected Profile is outbound-only and therefore cannot use
            # Profile +snat or require inbound return affinity.
            continue
        outbound_classifiers.append(
            StackOutboundAssociationSpec(
                profile_id=fragment.profile_id,
                ingress=host_boundary,
                remote_prefix=fragment.remote_prefix,
                mark=allocation.mark,
            )
        )

    rules = tuple(
        StackReturnRuleSpec(
            profile_id=profile_id,
            mark=allocation_by_profile[profile_id].mark,
            table=table_by_profile[profile_id],
            priority=allocation_by_profile[profile_id].rule_priority,
        )
        for profile_id in sorted(allocation_by_profile)
    )
    return StackReturnAffinityDesired(
        host_boundary=host_boundary,
        classifiers=tuple(
            sorted(
                inbound_classifiers,
                key=lambda item: (
                    item.ingress.ifindex,
                    -item.remote_prefix.prefixlen,
                    int(item.remote_prefix.network_address),
                    item.profile_id,
                ),
            )
        ),
        outbound_classifiers=tuple(
            sorted(
                outbound_classifiers,
                key=lambda item: (
                    -item.remote_prefix.prefixlen,
                    int(item.remote_prefix.network_address),
                    item.profile_id,
                ),
            )
        ),
        rules=rules,
    )
