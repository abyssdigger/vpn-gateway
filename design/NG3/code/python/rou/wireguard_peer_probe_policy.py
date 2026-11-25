"""C.001 desired projection for D.002 WireGuard peer technical probes."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Iterable

from .network_policy_layout import (
    NetworkPolicyLayout,
    NetworkPolicyPlatformSpace,
    ProbePolicyAllocation,
    WireGuardPeerProbeOwner,
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
    """Project peer-specific /32 routing/local admission without creating path identity."""
    if not isinstance(layout, NetworkPolicyLayout):
        raise WireGuardPeerProbePolicyError(
            "layout must be NetworkPolicyLayout"
        )
    if not isinstance(network_platform, NetworkPolicyPlatformSpace):
        raise WireGuardPeerProbePolicyError(
            "network_platform must be NetworkPolicyPlatformSpace"
        )
    if not isinstance(local_platform, ProbeLocalPlatform):
        raise WireGuardPeerProbePolicyError(
            "local_platform must be ProbeLocalPlatform"
        )

    raw = tuple(intents)
    if any(not isinstance(item, WireGuardPeerProbeIntent) for item in raw):
        raise WireGuardPeerProbePolicyError(
            "intents must contain WireGuardPeerProbeIntent"
        )
    current = tuple(
        sorted(raw, key=lambda item: probe_owner_sort_key(item.owner))
    )
    by_owner = {}
    for item in current:
        if item.owner in by_owner:
            raise WireGuardPeerProbePolicyError(
                f"duplicate WireGuard peer probe owner {item.owner!r}"
            )
        by_owner[item.owner] = item

    allocation_by_owner = {}
    for allocation in layout.probe:
        if not isinstance(allocation, ProbePolicyAllocation):
            raise WireGuardPeerProbePolicyError(
                "layout probe allocations must contain ProbePolicyAllocation"
            )
        if allocation.owner in allocation_by_owner:
            raise WireGuardPeerProbePolicyError(
                f"duplicate probe allocation {allocation.owner!r}"
            )
        allocation_by_owner[allocation.owner] = allocation

    missing = set(by_owner) - set(allocation_by_owner)
    if missing:
        raise WireGuardPeerProbePolicyError(
            "WireGuard peer probe owner lacks shared probe allocation"
        )

    routes = []
    rules = []
    local_rules = []
    for intent in current:
        allocation = allocation_by_owner[intent.owner]
        if not network_platform.probe_tables.contains(allocation.table):
            raise WireGuardPeerProbePolicyError(
                "peer probe allocation table is outside platform probe pool"
            )
        if not network_platform.probe_rule_priorities.contains(
            allocation.rule_priority
        ):
            raise WireGuardPeerProbePolicyError(
                "peer probe allocation priority is outside platform probe pool"
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
