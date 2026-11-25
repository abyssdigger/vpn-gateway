"""Shared C.001 projection for semantic probes bound to one current path."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Iterable

from .network_policy_layout import (
    NetworkPolicyLayout,
    NetworkPolicyPlatformSpace,
    ProbePolicyAllocation,
    ProbeSemanticOwner,
    is_probe_semantic_owner,
    probe_owner_sort_key,
)
from .payload_routing_desired import ManagedRouteSpec, ManagedRouteType
from .probe_policy import (
    AvailabilityProbeMechanism,
    ProbeLocalHook,
    ProbeLocalPlatform,
    ProbeLocalRuleSpec,
    ProbeNetworkPolicyDesiredState,
    ProbeRuleSpec,
)
from .route_priority_inventory import RoutePriorityPathRoute


class BoundProbePolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BoundProbeIntent:
    owner: ProbeSemanticOwner
    target: IPv4Address
    path_route: RoutePriorityPathRoute
    mechanism: AvailabilityProbeMechanism = AvailabilityProbeMechanism.ICMP

    def __post_init__(self) -> None:
        if not is_probe_semantic_owner(self.owner):
            raise BoundProbePolicyError(
                "owner must be a supported ProbeSemanticOwner"
            )
        if not isinstance(self.target, IPv4Address):
            raise BoundProbePolicyError("target must be IPv4Address")
        if not isinstance(self.path_route, RoutePriorityPathRoute):
            raise BoundProbePolicyError(
                "path_route must be RoutePriorityPathRoute"
            )
        if self.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise BoundProbePolicyError(
                "Release 1 bound probes must use ICMP"
            )


def build_bound_probe_policy_desired_state(
    intents: Iterable[BoundProbeIntent],
    layout: NetworkPolicyLayout,
    network_platform: NetworkPolicyPlatformSpace,
    local_platform: ProbeLocalPlatform,
) -> ProbeNetworkPolicyDesiredState:
    """Project an already-semantic probe owner onto the shared physical plane."""
    if not isinstance(layout, NetworkPolicyLayout):
        raise BoundProbePolicyError("layout must be NetworkPolicyLayout")
    if not isinstance(network_platform, NetworkPolicyPlatformSpace):
        raise BoundProbePolicyError(
            "network_platform must be NetworkPolicyPlatformSpace"
        )
    if not isinstance(local_platform, ProbeLocalPlatform):
        raise BoundProbePolicyError(
            "local_platform must be ProbeLocalPlatform"
        )

    raw = tuple(intents)
    if any(not isinstance(item, BoundProbeIntent) for item in raw):
        raise BoundProbePolicyError(
            "intents must contain BoundProbeIntent"
        )
    current = tuple(
        sorted(raw, key=lambda item: probe_owner_sort_key(item.owner))
    )
    by_owner = {}
    for item in current:
        if item.owner in by_owner:
            raise BoundProbePolicyError(
                f"duplicate bound probe owner {item.owner!r}"
            )
        by_owner[item.owner] = item

    allocation_by_owner = {}
    for allocation in layout.probe:
        if not isinstance(allocation, ProbePolicyAllocation):
            raise BoundProbePolicyError(
                "layout probe allocations must contain ProbePolicyAllocation"
            )
        if allocation.owner in allocation_by_owner:
            raise BoundProbePolicyError(
                f"duplicate probe allocation {allocation.owner!r}"
            )
        allocation_by_owner[allocation.owner] = allocation

    if set(by_owner) - set(allocation_by_owner):
        raise BoundProbePolicyError(
            "bound probe owner lacks shared probe allocation"
        )

    routes = []
    rules = []
    local_rules = []
    for intent in current:
        allocation = allocation_by_owner[intent.owner]
        if not network_platform.probe_tables.contains(allocation.table):
            raise BoundProbePolicyError(
                "bound probe allocation table is outside platform probe pool"
            )
        if not network_platform.probe_rule_priorities.contains(
            allocation.rule_priority
        ):
            raise BoundProbePolicyError(
                "bound probe allocation priority is outside platform probe pool"
            )

        route = intent.path_route
        routes.extend(
            (
                ManagedRouteSpec(
                    table=allocation.table,
                    destination=IPv4Network(f"{intent.target}/32"),
                    route_type=ManagedRouteType.UNICAST,
                    protocol=network_platform.path_route_protocol,
                    metric=network_platform.route_metrics.first_preference_metric,
                    path_id=route.path_id,
                    endpoint=route.endpoint,
                    gateway=route.gateway,
                    onlink=route.onlink,
                ),
                ManagedRouteSpec(
                    table=allocation.table,
                    destination=IPv4Network("0.0.0.0/0"),
                    route_type=ManagedRouteType.BLACKHOLE,
                    protocol=network_platform.guard_route_protocol,
                    metric=network_platform.route_metrics.terminal_guard_metric,
                ),
            )
        )
        rules.append(
            ProbeRuleSpec(
                owner=intent.owner,
                priority=allocation.rule_priority,
                process_uid=local_platform.process_uid,
                endpoint=route.endpoint,
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
                    endpoint=route.endpoint,
                    target=intent.target,
                    conntrack_mark=local_platform.conntrack_mark,
                    process_uid=local_platform.process_uid,
                    mechanism=intent.mechanism,
                ),
                ProbeLocalRuleSpec(
                    owner=intent.owner,
                    hook=ProbeLocalHook.INPUT,
                    endpoint=route.endpoint,
                    target=intent.target,
                    conntrack_mark=local_platform.conntrack_mark,
                    mechanism=intent.mechanism,
                ),
            )
        )

    return ProbeNetworkPolicyDesiredState(
        routes=tuple(sorted(routes, key=_route_key)),
        rules=tuple(
            sorted(
                rules,
                key=lambda item: (
                    item.priority,
                    probe_owner_sort_key(item.owner),
                    int(item.target),
                ),
            )
        ),
        local_rules=tuple(
            sorted(
                local_rules,
                key=lambda item: (
                    probe_owner_sort_key(item.owner),
                    item.hook.value,
                    int(item.target),
                ),
            )
        ),
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
