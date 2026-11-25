"""C.001 desired projection for D.002 WireGuard recoverable-group probes."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Iterable

from .network_policy_layout import (
    NetworkPolicyLayout,
    NetworkPolicyPlatformSpace,
    ProbePolicyAllocation,
    WireGuardGroupProbeOwner,
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
    """Project group endpoint routing/local admission without new path identity."""
    if not isinstance(layout, NetworkPolicyLayout):
        raise WireGuardGroupProbePolicyError(
            "layout must be NetworkPolicyLayout"
        )
    if not isinstance(network_platform, NetworkPolicyPlatformSpace):
        raise WireGuardGroupProbePolicyError(
            "network_platform must be NetworkPolicyPlatformSpace"
        )
    if not isinstance(local_platform, ProbeLocalPlatform):
        raise WireGuardGroupProbePolicyError(
            "local_platform must be ProbeLocalPlatform"
        )

    raw = tuple(intents)
    if any(not isinstance(item, WireGuardGroupProbeIntent) for item in raw):
        raise WireGuardGroupProbePolicyError(
            "intents must contain WireGuardGroupProbeIntent"
        )
    current = tuple(
        sorted(raw, key=lambda item: probe_owner_sort_key(item.owner))
    )
    by_owner = {}
    for item in current:
        if item.owner in by_owner:
            raise WireGuardGroupProbePolicyError(
                f"duplicate WireGuard group probe owner {item.owner!r}"
            )
        by_owner[item.owner] = item

    allocation_by_owner = {}
    for allocation in layout.probe:
        if not isinstance(allocation, ProbePolicyAllocation):
            raise WireGuardGroupProbePolicyError(
                "layout probe allocations must contain ProbePolicyAllocation"
            )
        if allocation.owner in allocation_by_owner:
            raise WireGuardGroupProbePolicyError(
                f"duplicate probe allocation {allocation.owner!r}"
            )
        allocation_by_owner[allocation.owner] = allocation

    missing = set(by_owner) - set(allocation_by_owner)
    if missing:
        raise WireGuardGroupProbePolicyError(
            "WireGuard group probe owner lacks shared probe allocation"
        )

    routes = []
    rules = []
    local_rules = []
    for intent in current:
        allocation = allocation_by_owner[intent.owner]
        if not network_platform.probe_tables.contains(allocation.table):
            raise WireGuardGroupProbePolicyError(
                "group probe allocation table is outside platform probe pool"
            )
        if not network_platform.probe_rule_priorities.contains(
            allocation.rule_priority
        ):
            raise WireGuardGroupProbePolicyError(
                "group probe allocation priority is outside platform probe pool"
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
