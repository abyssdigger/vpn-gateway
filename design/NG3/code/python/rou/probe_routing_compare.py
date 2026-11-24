from __future__ import annotations

from dataclasses import dataclass

from .network_policy_layout import NetworkPolicyPlatformSpace
from .payload_routing_desired import ManagedRouteSpec, ManagedRouteType
from .probe_policy import (
    AvailabilityProbeMechanism,
    ProbeNetworkPolicyDesiredState,
    ProbeRuleSpec,
)
from .structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
    ReservedOwnerKind,
    ReservedPolicyConflict,
    StructuralRoutingObservation,
)


class ProbeRoutingComparisonError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProbeRoutingComparison:
    confirmed_routes: tuple[ManagedRouteSpec, ...]
    missing_routes: tuple[ManagedRouteSpec, ...]
    stale_routes: tuple[ObservedManagedRoute, ...]
    confirmed_rules: tuple[ProbeRuleSpec, ...]
    missing_rules: tuple[ProbeRuleSpec, ...]
    stale_rules: tuple[ObservedManagedRule, ...]
    observed_rules: tuple[ObservedManagedRule, ...]
    conflicts: tuple[ReservedPolicyConflict, ...]

    @property
    def confirmed(self) -> bool:
        return not (
            self.missing_routes
            or self.stale_routes
            or self.missing_rules
            or self.stale_rules
            or self.conflicts
        )


def compare_probe_routing(
    desired: ProbeNetworkPolicyDesiredState,
    observed: StructuralRoutingObservation,
    platform: NetworkPolicyPlatformSpace,
) -> ProbeRoutingComparison:
    if not isinstance(desired, ProbeNetworkPolicyDesiredState):
        raise ProbeRoutingComparisonError(
            "desired must be ProbeNetworkPolicyDesiredState"
        )
    if not isinstance(observed, StructuralRoutingObservation):
        raise ProbeRoutingComparisonError(
            "observed must be StructuralRoutingObservation"
        )
    if not isinstance(platform, NetworkPolicyPlatformSpace):
        raise ProbeRoutingComparisonError(
            "platform must be NetworkPolicyPlatformSpace"
        )

    actual_routes = tuple(
        route
        for route in observed.routes
        if platform.probe_tables.contains(route.table)
    )
    actual_rules = tuple(
        rule
        for rule in observed.rules
        if platform.probe_rule_priorities.contains(rule.priority)
    )
    conflicts = tuple(
        conflict
        for conflict in observed.conflicts
        if conflict.owner is ReservedOwnerKind.PROBE
    )

    desired_route_by_key = {}
    for route in desired.routes:
        key = _desired_route_key(route)
        if key in desired_route_by_key:
            raise ProbeRoutingComparisonError(
                "desired probe routing contains duplicate physical route identity"
            )
        desired_route_by_key[key] = route

    actual_route_by_key = {}
    for route in actual_routes:
        key = _observed_route_key(route)
        if key in actual_route_by_key:
            conflicts = conflicts + (
                ReservedPolicyConflict(
                    owner=ReservedOwnerKind.PROBE,
                    resource=f"route table={route.table}",
                    reason="comparison received duplicate actual probe route identity",
                ),
            )
        actual_route_by_key[key] = route

    desired_rule_by_key = {}
    for rule in desired.rules:
        key = _desired_rule_key(rule)
        if key in desired_rule_by_key:
            raise ProbeRoutingComparisonError(
                "desired probe routing contains duplicate physical rule identity"
            )
        desired_rule_by_key[key] = rule

    actual_rule_by_key = {}
    for rule in actual_rules:
        key = _observed_rule_key(rule)
        if key in actual_rule_by_key:
            conflicts = conflicts + (
                ReservedPolicyConflict(
                    owner=ReservedOwnerKind.PROBE,
                    resource=f"rule priority={rule.priority}",
                    reason="comparison received duplicate actual probe rule identity",
                ),
            )
        actual_rule_by_key[key] = rule

    desired_route_keys = set(desired_route_by_key)
    actual_route_keys = set(actual_route_by_key)
    desired_rule_keys = set(desired_rule_by_key)
    actual_rule_keys = set(actual_rule_by_key)

    return ProbeRoutingComparison(
        confirmed_routes=tuple(
            desired_route_by_key[key]
            for key in sorted(desired_route_keys & actual_route_keys)
        ),
        missing_routes=tuple(
            desired_route_by_key[key]
            for key in sorted(desired_route_keys - actual_route_keys)
        ),
        stale_routes=tuple(
            actual_route_by_key[key]
            for key in sorted(actual_route_keys - desired_route_keys)
        ),
        confirmed_rules=tuple(
            desired_rule_by_key[key]
            for key in sorted(desired_rule_keys & actual_rule_keys)
        ),
        missing_rules=tuple(
            desired_rule_by_key[key]
            for key in sorted(desired_rule_keys - actual_rule_keys)
        ),
        stale_rules=tuple(
            actual_rule_by_key[key]
            for key in sorted(actual_rule_keys - desired_rule_keys)
        ),
        observed_rules=tuple(
            actual_rule_by_key[key]
            for key in sorted(actual_rule_keys)
        ),
        conflicts=conflicts,
    )


def _desired_route_key(route: ManagedRouteSpec) -> tuple[object, ...]:
    return (
        route.table,
        int(route.destination.network_address),
        route.destination.prefixlen,
        route.route_type.value,
        route.protocol,
        route.metric,
        _expected_effective_scope(route),
        route.endpoint.ifname if route.endpoint else "",
        route.endpoint.ifindex if route.endpoint else -1,
        str(route.gateway) if route.gateway else "",
        route.onlink,
    )


def _observed_route_key(route: ObservedManagedRoute) -> tuple[object, ...]:
    return (
        route.table,
        int(route.destination.network_address),
        route.destination.prefixlen,
        route.route_type.value,
        route.protocol,
        route.metric,
        0 if route.scope is None else route.scope,
        route.endpoint.ifname if route.endpoint else "",
        route.endpoint.ifindex if route.endpoint else -1,
        str(route.gateway) if route.gateway else "",
        route.onlink,
    )


def _expected_effective_scope(route: ManagedRouteSpec) -> int:
    if route.route_type is ManagedRouteType.BLACKHOLE:
        return 0
    if route.gateway is None:
        return 253
    return 0


def _desired_rule_key(rule: ProbeRuleSpec) -> tuple[object, ...]:
    if rule.mechanism is not AvailabilityProbeMechanism.ICMP:
        raise ProbeRoutingComparisonError(
            "Release 1 probe comparison supports only ICMP"
        )
    return (
        rule.priority,
        rule.table,
        int(rule.target),
        32,
        rule.process_uid,
        rule.process_uid,
        1,
        rule.endpoint.ifname,
        rule.endpoint.ifindex,
        None,
        None,
    )


def _observed_rule_key(rule: ObservedManagedRule) -> tuple[object, ...]:
    return (
        rule.priority,
        rule.table,
        int(rule.destination.network_address) if rule.destination else -1,
        rule.destination.prefixlen if rule.destination else -1,
        rule.uid_start,
        rule.uid_end,
        rule.ipproto,
        rule.egress.ifname if rule.egress else "",
        rule.egress.ifindex if rule.egress else -1,
        rule.fwmark,
        rule.fwmask,
    )
