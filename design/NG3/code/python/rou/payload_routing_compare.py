from __future__ import annotations

from dataclasses import dataclass

from .network_policy_layout import NetworkPolicyPlatformSpace
from .payload_routing_desired import (
    ManagedRouteSpec,
    ManagedRouteType,
    ManagedRuleSpec,
    PayloadRoutingDesiredState,
)
from .structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
    ReservedOwnerKind,
    ReservedPolicyConflict,
    StructuralRoutingObservation,
)


class PayloadRoutingComparisonError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PayloadRoutingComparison:
    confirmed_routes: tuple[ManagedRouteSpec, ...]
    missing_routes: tuple[ManagedRouteSpec, ...]
    stale_routes: tuple[ObservedManagedRoute, ...]
    confirmed_rules: tuple[ManagedRuleSpec, ...]
    missing_rules: tuple[ManagedRuleSpec, ...]
    stale_rules: tuple[ObservedManagedRule, ...]
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


def compare_payload_routing(
    desired: PayloadRoutingDesiredState,
    observed: StructuralRoutingObservation,
    platform: NetworkPolicyPlatformSpace,
) -> PayloadRoutingComparison:
    if not isinstance(desired, PayloadRoutingDesiredState):
        raise PayloadRoutingComparisonError(
            "desired must be PayloadRoutingDesiredState"
        )
    if not isinstance(observed, StructuralRoutingObservation):
        raise PayloadRoutingComparisonError(
            "observed must be StructuralRoutingObservation"
        )
    if not isinstance(platform, NetworkPolicyPlatformSpace):
        raise PayloadRoutingComparisonError(
            "platform must be NetworkPolicyPlatformSpace"
        )

    actual_routes = tuple(
        route
        for route in observed.routes
        if platform.payload_tables.contains(route.table)
    )
    actual_rules = tuple(
        rule
        for rule in observed.rules
        if platform.payload_rule_priorities.contains(rule.priority)
    )
    conflicts = tuple(
        conflict
        for conflict in observed.conflicts
        if conflict.owner is ReservedOwnerKind.PAYLOAD
    )

    desired_route_by_key = {}
    for route in desired.routes:
        key = _desired_route_key(route)
        if key in desired_route_by_key:
            raise PayloadRoutingComparisonError(
                "desired payload routing contains duplicate physical route identity"
            )
        desired_route_by_key[key] = route

    actual_route_by_key = {}
    for route in actual_routes:
        key = _observed_route_key(route)
        if key in actual_route_by_key:
            # Inventory should already surface this as conflict, but do not
            # silently collapse it if a caller constructs the value directly.
            conflicts = conflicts + (
                ReservedPolicyConflict(
                    owner=ReservedOwnerKind.PAYLOAD,
                    resource=f"route table={route.table}",
                    reason="comparison received duplicate actual payload route identity",
                ),
            )
        actual_route_by_key[key] = route

    desired_rule_by_key = {}
    for rule in desired.rules:
        key = _desired_rule_key(rule)
        if key in desired_rule_by_key:
            raise PayloadRoutingComparisonError(
                "desired payload routing contains duplicate physical rule identity"
            )
        desired_rule_by_key[key] = rule

    actual_rule_by_key = {}
    for rule in actual_rules:
        key = _observed_rule_key(rule)
        if key in actual_rule_by_key:
            conflicts = conflicts + (
                ReservedPolicyConflict(
                    owner=ReservedOwnerKind.PAYLOAD,
                    resource=f"rule priority={rule.priority}",
                    reason="comparison received duplicate actual payload rule identity",
                ),
            )
        actual_rule_by_key[key] = rule

    desired_route_keys = set(desired_route_by_key)
    actual_route_keys = set(actual_route_by_key)
    desired_rule_keys = set(desired_rule_by_key)
    actual_rule_keys = set(actual_rule_by_key)

    return PayloadRoutingComparison(
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
        conflicts=conflicts,
    )


def _desired_route_key(route: ManagedRouteSpec) -> tuple[object, ...]:
    return (
        route.table,
        int(route.destination.network_address),
        route.destination.prefixlen,
        route.route_type.value,
        route.role.value,
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
        route.role.value,
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


def _desired_rule_key(rule: ManagedRuleSpec) -> tuple[object, ...]:
    return (
        rule.priority,
        rule.table,
        rule.ingress.ifname,
        rule.ingress.ifindex,
        int(rule.destination.network_address),
        rule.destination.prefixlen,
        None,
        None,
        None,
        None,
        None,
    )


def _observed_rule_key(rule: ObservedManagedRule) -> tuple[object, ...]:
    return (
        rule.priority,
        rule.table,
        rule.ingress.ifname if rule.ingress else "",
        rule.ingress.ifindex if rule.ingress else -1,
        int(rule.destination.network_address) if rule.destination else -1,
        rule.destination.prefixlen if rule.destination else -1,
        rule.fwmark,
        rule.fwmask,
        rule.uid_start,
        rule.uid_end,
        rule.ipproto,
    )
