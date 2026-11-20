from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Network
from typing import Iterable

from .binding import LogicalPathId
from .interface_identity import InterfaceIdentity
from .network_policy_layout import (
    NetworkPolicyLayout,
    PayloadDispatchRule,
    PayloadPolicyAllocation,
)
from .payload_profile import PayloadProfileRequest
from .route_priority_domain_builder import (
    RoutePriorityDomainBuildError,
    build_route_priority_domain_realizations,
)
from .route_priority_inventory import RoutePriorityPathRoute


class PayloadRoutingProjectionError(ValueError):
    pass


class ManagedRouteType(str, Enum):
    UNICAST = "unicast"
    BLACKHOLE = "blackhole"


class ManagedRouteRole(str, Enum):
    GUARD = "guard"
    VPN_PATH = "vpn_path"
    LEGACY_HOST_BOUNDARY_LANE = "host_boundary_lane"


@dataclass(frozen=True, slots=True)
class ManagedRouteSpec:
    table: int
    destination: IPv4Network
    route_type: ManagedRouteType
    protocol: int
    metric: int
    path_id: LogicalPathId | None = None
    endpoint: InterfaceIdentity | None = None
    gateway: IPv4Address | None = None
    onlink: bool = False
    role: ManagedRouteRole | None = None

    def __post_init__(self) -> None:
        if type(self.table) is not int or not 1 <= self.table <= 0xFFFFFFFF:
            raise PayloadRoutingProjectionError(
                "route table must be an integer in [1, 2^32-1]"
            )
        if not isinstance(self.destination, IPv4Network):
            raise PayloadRoutingProjectionError(
                "route destination must be IPv4Network"
            )
        if not isinstance(self.route_type, ManagedRouteType):
            raise PayloadRoutingProjectionError(
                "route_type must be ManagedRouteType"
            )
        if type(self.protocol) is not int or not 1 <= self.protocol <= 255:
            raise PayloadRoutingProjectionError(
                "route protocol must be an integer in [1, 255]"
            )
        if (
            type(self.metric) is not int
            or not 0 <= self.metric <= 0xFFFFFFFF
        ):
            raise PayloadRoutingProjectionError(
                "route metric must be an integer in [0, 2^32-1]"
            )
        if type(self.onlink) is not bool:
            raise PayloadRoutingProjectionError("onlink must be bool")

        role = self.role
        if role is None:
            role = (
                ManagedRouteRole.GUARD
                if self.route_type is ManagedRouteType.BLACKHOLE
                else ManagedRouteRole.VPN_PATH
            )
            object.__setattr__(self, "role", role)
        if not isinstance(role, ManagedRouteRole):
            raise PayloadRoutingProjectionError(
                "route role must be ManagedRouteRole"
            )

        if role is ManagedRouteRole.GUARD:
            if self.route_type is not ManagedRouteType.BLACKHOLE:
                raise PayloadRoutingProjectionError(
                    "guard route must be blackhole"
                )
            if any(
                value is not None
                for value in (
                    self.path_id,
                    self.endpoint,
                    self.gateway,
                )
            ) or self.onlink:
                raise PayloadRoutingProjectionError(
                    "blackhole route cannot carry path/endpoint/gateway/onlink"
                )
            return

        if self.route_type is not ManagedRouteType.UNICAST:
            raise PayloadRoutingProjectionError(
                "non-guard managed route must be unicast"
            )
        if not isinstance(self.endpoint, InterfaceIdentity):
            raise PayloadRoutingProjectionError(
                "unicast route requires InterfaceIdentity"
            )
        if self.gateway is not None and not isinstance(
            self.gateway,
            IPv4Address,
        ):
            raise PayloadRoutingProjectionError(
                "unicast gateway must be IPv4Address or None"
            )

        if role is ManagedRouteRole.VPN_PATH:
            if not isinstance(self.path_id, LogicalPathId):
                raise PayloadRoutingProjectionError(
                    "VPN path route requires LogicalPathId"
                )
            return

        if role is ManagedRouteRole.LEGACY_HOST_BOUNDARY_LANE:
            raise PayloadRoutingProjectionError(
                "legacy host-boundary lane route is observation-only and cannot be desired"
            )

        raise PayloadRoutingProjectionError("unsupported managed route role")


@dataclass(frozen=True, slots=True)
class ManagedRuleSpec:
    priority: int
    ingress: InterfaceIdentity
    destination: IPv4Network
    table: int

    def __post_init__(self) -> None:
        if (
            type(self.priority) is not int
            or not 1 <= self.priority < 0x1_0000_0000
        ):
            raise PayloadRoutingProjectionError(
                "rule priority must be an integer in [1, 2^32-1]"
            )
        if not isinstance(self.ingress, InterfaceIdentity):
            raise PayloadRoutingProjectionError(
                "rule ingress must be InterfaceIdentity"
            )
        if not isinstance(self.destination, IPv4Network):
            raise PayloadRoutingProjectionError(
                "rule destination must be IPv4Network"
            )
        if type(self.table) is not int or not 1 <= self.table <= 0xFFFFFFFF:
            raise PayloadRoutingProjectionError(
                "rule table must be an integer in [1, 2^32-1]"
            )


@dataclass(frozen=True, slots=True)
class PayloadRoutingDesiredState:
    host_boundary: InterfaceIdentity
    routes: tuple[ManagedRouteSpec, ...]
    rules: tuple[ManagedRuleSpec, ...]


def build_payload_routing_desired_state(
    profiles: Iterable[PayloadProfileRequest],
    layout: NetworkPolicyLayout,
    path_routes: Iterable[RoutePriorityPathRoute],
    host_boundary: InterfaceIdentity,
) -> PayloadRoutingDesiredState:
    """Build complete route/RPDB desired data without mutating Linux."""
    if not isinstance(layout, NetworkPolicyLayout):
        raise PayloadRoutingProjectionError(
            "layout must be NetworkPolicyLayout"
        )
    if not isinstance(host_boundary, InterfaceIdentity):
        raise PayloadRoutingProjectionError(
            "host_boundary must be InterfaceIdentity"
        )

    current_profiles = tuple(
        sorted(profiles, key=lambda value: value.profile_id)
    )
    profile_by_id: dict[str, PayloadProfileRequest] = {}
    for profile in current_profiles:
        if not isinstance(profile, PayloadProfileRequest):
            raise PayloadRoutingProjectionError(
                "profiles must contain PayloadProfileRequest"
            )
        if profile.profile_id in profile_by_id:
            raise PayloadRoutingProjectionError(
                f"duplicate Profile {profile.profile_id!r}"
            )
        profile_by_id[profile.profile_id] = profile

    allocation_by_id: dict[str, PayloadPolicyAllocation] = {}
    for allocation in layout.payload:
        if not isinstance(allocation, PayloadPolicyAllocation):
            raise PayloadRoutingProjectionError(
                "layout payload must contain PayloadPolicyAllocation"
            )
        if allocation.profile_id in allocation_by_id:
            raise PayloadRoutingProjectionError(
                f"duplicate payload allocation {allocation.profile_id!r}"
            )
        allocation_by_id[allocation.profile_id] = allocation

    if set(allocation_by_id) != set(profile_by_id):
        raise PayloadRoutingProjectionError(
            "payload allocation Profile set does not match semantic Profile set"
        )

    route_by_path: dict[LogicalPathId, RoutePriorityPathRoute] = {}
    endpoint_owner: dict[InterfaceIdentity, LogicalPathId] = {}
    for route in path_routes:
        if not isinstance(route, RoutePriorityPathRoute):
            raise PayloadRoutingProjectionError(
                "path_routes must contain RoutePriorityPathRoute"
            )
        if route.path_id in route_by_path:
            raise PayloadRoutingProjectionError(
                f"duplicate path route realization for {route.path_id!r}"
            )
        previous = endpoint_owner.get(route.endpoint)
        if previous is not None and previous != route.path_id:
            raise PayloadRoutingProjectionError(
                f"one endpoint is realized for multiple logical paths: "
                f"{previous!r}, {route.path_id!r}"
            )
        route_by_path[route.path_id] = route
        endpoint_owner[route.endpoint] = route.path_id

    required_path_ids = {
        path_id
        for profile in current_profiles
        for path_id in profile.ordered_paths
    }
    if set(route_by_path) != required_path_ids:
        raise PayloadRoutingProjectionError(
            "physical path-route set does not exactly match current semantic payload paths"
        )

    _validate_dispatch_rules(
        current_profiles,
        layout.dispatch_rules,
        allocation_by_id,
    )

    desired_routes: list[ManagedRouteSpec] = []

    for profile in current_profiles:
        allocation = allocation_by_id[profile.profile_id]

        desired_routes.append(
            ManagedRouteSpec(
                table=allocation.table,
                destination=IPv4Network("0.0.0.0/0"),
                route_type=ManagedRouteType.BLACKHOLE,
                protocol=allocation.guard_route_protocol,
                metric=allocation.terminal_guard_metric,
                role=ManagedRouteRole.GUARD,
            )
        )

        required_route_realizations: list[RoutePriorityPathRoute] = []
        for path_id in profile.ordered_paths:
            route = route_by_path.get(path_id)
            if route is None:
                raise PayloadRoutingProjectionError(
                    f"Profile {profile.profile_id!r} has no physical route realization "
                    f"for {path_id!r}"
                )
            required_route_realizations.append(route)

        try:
            domains = build_route_priority_domain_realizations(
                profile,
                allocation,
                required_route_realizations,
            )
        except RoutePriorityDomainBuildError as exc:
            raise PayloadRoutingProjectionError(str(exc)) from exc

        for domain in domains:
            ordered_paths = tuple(
                spec.path_id
                for spec in domain.path_routes
            )
            metrics = domain.desired_metrics(ordered_paths)
            for path_route in domain.path_routes:
                desired_routes.append(
                    ManagedRouteSpec(
                        table=domain.table,
                        destination=domain.domain_id.destination,
                        route_type=ManagedRouteType.UNICAST,
                        protocol=domain.owner_protocol,
                        metric=metrics[path_route.path_id],
                        path_id=path_route.path_id,
                        endpoint=path_route.endpoint,
                        gateway=path_route.gateway,
                        onlink=path_route.onlink,
                        role=ManagedRouteRole.VPN_PATH,
                    )
                )


    desired_rules = tuple(
        ManagedRuleSpec(
            priority=rule.priority,
            ingress=host_boundary,
            destination=rule.destination,
            table=rule.table,
        )
        for rule in layout.dispatch_rules
    )

    return PayloadRoutingDesiredState(
        host_boundary=host_boundary,
        routes=tuple(sorted(desired_routes, key=_route_sort_key)),
        rules=desired_rules,
    )


def _validate_dispatch_rules(
    profiles: tuple[PayloadProfileRequest, ...],
    rules: tuple[PayloadDispatchRule, ...],
    allocations: dict[str, PayloadPolicyAllocation],
) -> None:
    canonical = sorted(
        (
            profile.profile_id,
            destination,
        )
        for profile in profiles
        for destination in profile.destinations
    )
    canonical.sort(
        key=lambda item: (
            -item[1].prefixlen,
            int(item[1].network_address),
            item[0],
        )
    )
    expected = set(canonical)
    observed: set[tuple[str, IPv4Network]] = set()
    priorities: list[int] = []
    observed_order: list[tuple[str, IPv4Network]] = []

    for rule in rules:
        if not isinstance(rule, PayloadDispatchRule):
            raise PayloadRoutingProjectionError(
                "layout dispatch rules must contain PayloadDispatchRule"
            )
        key = (rule.profile_id, rule.destination)
        if key in observed:
            raise PayloadRoutingProjectionError(
                f"duplicate payload dispatch rule for {key!r}"
            )
        observed.add(key)
        observed_order.append(key)
        if (
            type(rule.priority) is not int
            or not 1 <= rule.priority < 0x1_0000_0000
        ):
            raise PayloadRoutingProjectionError(
                "dispatch rule priority must be an integer in [1, 2^32-1]"
            )
        priorities.append(rule.priority)

        allocation = allocations.get(rule.profile_id)
        if allocation is None or allocation.table != rule.table:
            raise PayloadRoutingProjectionError(
                "dispatch rule table does not match current Profile allocation"
            )

    if observed != expected:
        raise PayloadRoutingProjectionError(
            "dispatch-rule set does not match current Profile destinations"
        )
    if observed_order != canonical:
        raise PayloadRoutingProjectionError(
            "dispatch-rule order does not match canonical longest-prefix ordering"
        )
    if len(set(priorities)) != len(priorities):
        raise PayloadRoutingProjectionError(
            "dispatch rule priorities must be unique"
        )
    if priorities != sorted(priorities):
        raise PayloadRoutingProjectionError(
            "dispatch rule priorities must increase with canonical dispatch order"
        )


def _route_sort_key(route: ManagedRouteSpec) -> tuple[object, ...]:
    return (
        route.table,
        int(route.destination.network_address),
        route.destination.prefixlen,
        route.route_type.value,
        route.role.value,
        route.metric,
        route.path_id.device_id if route.path_id is not None else "",
        route.path_id.selector_index if route.path_id is not None else -1,
        route.path_id.slot_index if route.path_id is not None else -1,
    )
