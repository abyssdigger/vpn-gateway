"""Pure Release-1 probe-plane desired-state projection.

This module starts from already normalized availability subjects with a concrete IPv4
target. It does not derive targets, schedule probes, execute ICMP or own availability
hysteresis. It only projects the lower owner-scoped routing/local-policy preconditions
required by the accepted EXP-021/022/024 mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Network
from typing import Iterable

from .binding import LogicalPathId
from .interface_identity import InterfaceIdentity
from .network_policy_layout import (
    NetworkPolicyLayout,
    NetworkPolicyPlatformSpace,
    ProbePolicyAllocation,
    ProbePolicyOwner,
)
from .payload_routing_desired import ManagedRouteSpec, ManagedRouteType
from .route_priority_inventory import RoutePriorityPathRoute


class ProbePolicyProjectionError(ValueError):
    pass


class AvailabilityProbeMechanism(str, Enum):
    ICMP = "icmp"


@dataclass(frozen=True, slots=True)
class AvailabilityProbeIntent:
    owner: ProbePolicyOwner
    target: IPv4Address
    mechanism: AvailabilityProbeMechanism = AvailabilityProbeMechanism.ICMP

    def __post_init__(self) -> None:
        if not isinstance(self.owner, ProbePolicyOwner):
            raise ProbePolicyProjectionError(
                "owner must be ProbePolicyOwner"
            )
        if not isinstance(self.target, IPv4Address):
            raise ProbePolicyProjectionError(
                "target must be IPv4Address"
            )
        if not isinstance(self.mechanism, AvailabilityProbeMechanism):
            raise ProbePolicyProjectionError(
                "mechanism must be AvailabilityProbeMechanism"
            )
        if self.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise ProbePolicyProjectionError(
                "Release 1 supports only ICMP availability probes"
            )


@dataclass(frozen=True, slots=True)
class ProbeLocalPlatform:
    """Lower Linux selector allocation, not user/product policy."""

    process_uid: int
    conntrack_mark: int

    def __post_init__(self) -> None:
        if (
            type(self.process_uid) is not int
            or not 1 <= self.process_uid <= 0xFFFFFFFE
        ):
            raise ProbePolicyProjectionError(
                "process_uid must be a non-root Linux uid in [1, 2^32-2]"
            )
        if (
            type(self.conntrack_mark) is not int
            or not 1 <= self.conntrack_mark <= 0xFFFFFFFF
        ):
            raise ProbePolicyProjectionError(
                "conntrack_mark must be an integer in [1, 2^32-1]"
            )


@dataclass(frozen=True, slots=True)
class ProbeRuleSpec:
    owner: ProbePolicyOwner
    priority: int
    process_uid: int
    endpoint: InterfaceIdentity
    target: IPv4Address
    table: int
    mechanism: AvailabilityProbeMechanism = AvailabilityProbeMechanism.ICMP

    def __post_init__(self) -> None:
        if not isinstance(self.owner, ProbePolicyOwner):
            raise ProbePolicyProjectionError(
                "probe rule owner must be ProbePolicyOwner"
            )
        if (
            type(self.priority) is not int
            or not 1 <= self.priority < 0x1_0000_0000
        ):
            raise ProbePolicyProjectionError(
                "probe rule priority must be in [1, 2^32-1]"
            )
        if (
            type(self.process_uid) is not int
            or not 1 <= self.process_uid <= 0xFFFFFFFE
        ):
            raise ProbePolicyProjectionError(
                "probe rule process_uid must be a non-root Linux uid"
            )
        if not isinstance(self.endpoint, InterfaceIdentity):
            raise ProbePolicyProjectionError(
                "probe rule endpoint must be InterfaceIdentity"
            )
        if not isinstance(self.target, IPv4Address):
            raise ProbePolicyProjectionError(
                "probe rule target must be IPv4Address"
            )
        if type(self.table) is not int or not 1 <= self.table <= 0xFFFFFFFF:
            raise ProbePolicyProjectionError("invalid probe rule table")
        if self.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise ProbePolicyProjectionError(
                "probe routing rule mechanism must be ICMP"
            )


class ProbeLocalHook(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


@dataclass(frozen=True, slots=True)
class ProbeLocalRuleSpec:
    owner: ProbePolicyOwner
    hook: ProbeLocalHook
    endpoint: InterfaceIdentity
    target: IPv4Address
    conntrack_mark: int
    process_uid: int | None = None
    mechanism: AvailabilityProbeMechanism = AvailabilityProbeMechanism.ICMP

    def __post_init__(self) -> None:
        if not isinstance(self.owner, ProbePolicyOwner):
            raise ProbePolicyProjectionError(
                "probe local owner must be ProbePolicyOwner"
            )
        if not isinstance(self.hook, ProbeLocalHook):
            raise ProbePolicyProjectionError(
                "probe local hook must be ProbeLocalHook"
            )
        if not isinstance(self.endpoint, InterfaceIdentity):
            raise ProbePolicyProjectionError(
                "probe local endpoint must be InterfaceIdentity"
            )
        if not isinstance(self.target, IPv4Address):
            raise ProbePolicyProjectionError(
                "probe local target must be IPv4Address"
            )
        if self.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise ProbePolicyProjectionError(
                "probe local rule mechanism must be ICMP"
            )
        if (
            type(self.conntrack_mark) is not int
            or not 1 <= self.conntrack_mark <= 0xFFFFFFFF
        ):
            raise ProbePolicyProjectionError(
                "probe conntrack mark must be in [1, 2^32-1]"
            )
        if self.hook is ProbeLocalHook.OUTPUT:
            if (
                type(self.process_uid) is not int
                or not 1 <= self.process_uid <= 0xFFFFFFFE
            ):
                raise ProbePolicyProjectionError(
                    "probe OUTPUT requires a non-root Linux process_uid"
                )
        elif self.process_uid is not None:
            raise ProbePolicyProjectionError(
                "probe INPUT must not depend on receiving-socket uid"
            )


@dataclass(frozen=True, slots=True)
class ProbeNetworkPolicyDesiredState:
    routes: tuple[ManagedRouteSpec, ...]
    rules: tuple[ProbeRuleSpec, ...]
    local_rules: tuple[ProbeLocalRuleSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.routes, tuple) or not all(
            isinstance(item, ManagedRouteSpec)
            for item in self.routes
        ):
            raise ProbePolicyProjectionError(
                "routes must be a tuple of ManagedRouteSpec"
            )
        if not isinstance(self.rules, tuple) or not all(
            isinstance(item, ProbeRuleSpec)
            for item in self.rules
        ):
            raise ProbePolicyProjectionError(
                "rules must be a tuple of ProbeRuleSpec"
            )
        if not isinstance(self.local_rules, tuple) or not all(
            isinstance(item, ProbeLocalRuleSpec)
            for item in self.local_rules
        ):
            raise ProbePolicyProjectionError(
                "local_rules must be a tuple of ProbeLocalRuleSpec"
            )
        if len(set(self.routes)) != len(self.routes):
            raise ProbePolicyProjectionError(
                "duplicate desired probe route"
            )
        if len(set(self.rules)) != len(self.rules):
            raise ProbePolicyProjectionError(
                "duplicate desired probe routing rule"
            )
        if len(set(self.local_rules)) != len(self.local_rules):
            raise ProbePolicyProjectionError(
                "duplicate desired probe local rule"
            )


def build_probe_network_policy_desired_state(
    intents: Iterable[AvailabilityProbeIntent],
    layout: NetworkPolicyLayout,
    path_routes: Iterable[RoutePriorityPathRoute],
    network_platform: NetworkPolicyPlatformSpace,
    local_platform: ProbeLocalPlatform,
) -> ProbeNetworkPolicyDesiredState:
    """Project exact current probe preconditions without I/O."""
    if not isinstance(layout, NetworkPolicyLayout):
        raise ProbePolicyProjectionError(
            "layout must be NetworkPolicyLayout"
        )
    if not isinstance(network_platform, NetworkPolicyPlatformSpace):
        raise ProbePolicyProjectionError(
            "network_platform must be NetworkPolicyPlatformSpace"
        )
    if not isinstance(local_platform, ProbeLocalPlatform):
        raise ProbePolicyProjectionError(
            "local_platform must be ProbeLocalPlatform"
        )

    raw_intents = tuple(intents)
    if not all(
        isinstance(intent, AvailabilityProbeIntent)
        for intent in raw_intents
    ):
        raise ProbePolicyProjectionError(
            "intents must contain AvailabilityProbeIntent"
        )
    current_intents = tuple(sorted(
        raw_intents,
        key=lambda value: (
            value.owner.profile_id,
            value.owner.path_id,
            int(value.target),
        ),
    ))
    owner_to_intent: dict[ProbePolicyOwner, AvailabilityProbeIntent] = {}
    for intent in current_intents:
        if intent.owner in owner_to_intent:
            raise ProbePolicyProjectionError(
                f"duplicate availability probe owner {intent.owner!r}"
            )
        owner_to_intent[intent.owner] = intent

    allocation_by_owner: dict[ProbePolicyOwner, ProbePolicyAllocation] = {}
    for allocation in layout.probe:
        if not isinstance(allocation, ProbePolicyAllocation):
            raise ProbePolicyProjectionError(
                "layout probe allocations must contain ProbePolicyAllocation"
            )
        if allocation.owner in allocation_by_owner:
            raise ProbePolicyProjectionError(
                f"duplicate probe allocation {allocation.owner!r}"
            )
        allocation_by_owner[allocation.owner] = allocation

    if set(allocation_by_owner) != set(owner_to_intent):
        raise ProbePolicyProjectionError(
            "probe allocation owner set does not match current probe intents"
        )

    route_by_path = {}
    endpoint_owner = {}
    for route in path_routes:
        if not isinstance(route, RoutePriorityPathRoute):
            raise ProbePolicyProjectionError(
                "path_routes must contain RoutePriorityPathRoute"
            )
        if route.path_id in route_by_path:
            raise ProbePolicyProjectionError(
                f"duplicate path route realization for {route.path_id!r}"
            )
        previous = endpoint_owner.get(route.endpoint)
        if previous is not None and previous != route.path_id:
            raise ProbePolicyProjectionError(
                "one endpoint is realized for multiple logical paths"
            )
        route_by_path[route.path_id] = route
        endpoint_owner[route.endpoint] = route.path_id

    desired_routes: list[ManagedRouteSpec] = []
    desired_rules: list[ProbeRuleSpec] = []
    local_rules: list[ProbeLocalRuleSpec] = []

    for intent in current_intents:
        allocation = allocation_by_owner[intent.owner]
        if not network_platform.probe_tables.contains(allocation.table):
            raise ProbePolicyProjectionError(
                "probe allocation table is outside platform probe pool"
            )
        if not network_platform.probe_rule_priorities.contains(
            allocation.rule_priority
        ):
            raise ProbePolicyProjectionError(
                "probe allocation priority is outside platform probe pool"
            )

        path_route = route_by_path.get(intent.owner.path_id)
        if path_route is None:
            raise ProbePolicyProjectionError(
                f"probe owner has no current path realization: {intent.owner!r}"
            )

        desired_routes.append(
            ManagedRouteSpec(
                table=allocation.table,
                destination=IPv4Network(f"{intent.target}/32"),
                route_type=ManagedRouteType.UNICAST,
                protocol=network_platform.path_route_protocol,
                metric=network_platform.route_metrics.first_preference_metric,
                path_id=path_route.path_id,
                endpoint=path_route.endpoint,
                gateway=path_route.gateway,
                onlink=path_route.onlink,
            )
        )
        desired_routes.append(
            ManagedRouteSpec(
                table=allocation.table,
                destination=IPv4Network("0.0.0.0/0"),
                route_type=ManagedRouteType.BLACKHOLE,
                protocol=network_platform.guard_route_protocol,
                metric=network_platform.route_metrics.terminal_guard_metric,
            )
        )
        desired_rules.append(
            ProbeRuleSpec(
                owner=intent.owner,
                priority=allocation.rule_priority,
                process_uid=local_platform.process_uid,
                endpoint=path_route.endpoint,
                target=intent.target,
                table=allocation.table,
                mechanism=intent.mechanism,
            )
        )
        local_rules.extend(
            (
                ProbeLocalRuleSpec(
                    owner=intent.owner,
                    hook=ProbeLocalHook.OUTPUT,
                    endpoint=path_route.endpoint,
                    target=intent.target,
                    conntrack_mark=local_platform.conntrack_mark,
                    process_uid=local_platform.process_uid,
                    mechanism=intent.mechanism,
                ),
                ProbeLocalRuleSpec(
                    owner=intent.owner,
                    hook=ProbeLocalHook.INPUT,
                    endpoint=path_route.endpoint,
                    target=intent.target,
                    conntrack_mark=local_platform.conntrack_mark,
                    mechanism=intent.mechanism,
                ),
            )
        )

    return ProbeNetworkPolicyDesiredState(
        routes=tuple(sorted(desired_routes, key=_route_key)),
        rules=tuple(sorted(
            desired_rules,
            key=lambda rule: (
                rule.priority,
                rule.owner.profile_id,
                rule.owner.path_id,
                int(rule.target),
            ),
        )),
        local_rules=tuple(sorted(
            local_rules,
            key=lambda rule: (
                rule.owner.profile_id,
                rule.owner.path_id,
                rule.hook.value,
                int(rule.target),
            ),
        )),
    )


def _route_key(route: ManagedRouteSpec) -> tuple[object, ...]:
    return (
        route.table,
        int(route.destination.network_address),
        route.destination.prefixlen,
        route.route_type.value,
        route.metric,
        route.protocol,
    )
