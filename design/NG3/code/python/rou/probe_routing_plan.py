"""Fail-closed planning for bounded probe route/RPDB convergence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .payload_routing_desired import ManagedRouteSpec, ManagedRouteType
from .probe_policy import ProbeRuleSpec
from .probe_routing_compare import ProbeRoutingComparison
from .structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
)


class ProbeRoutingStepKind(str, Enum):
    WITHDRAW_RULE = "withdraw_rule"
    ADD_GUARD_ROUTE = "add_guard_route"
    DELETE_PATH_ROUTE = "delete_path_route"
    DELETE_GUARD_ROUTE = "delete_guard_route"
    ADD_PATH_ROUTE = "add_path_route"
    ADD_RULE = "add_rule"


@dataclass(frozen=True, slots=True)
class ProbeRoutingMutationStep:
    kind: ProbeRoutingStepKind
    desired_route: ManagedRouteSpec | None = None
    observed_route: ObservedManagedRoute | None = None
    desired_rule: ProbeRuleSpec | None = None
    observed_rule: ObservedManagedRule | None = None

    def __post_init__(self) -> None:
        operands = (
            self.desired_route is not None,
            self.observed_route is not None,
            self.desired_rule is not None,
            self.observed_rule is not None,
        )
        if sum(operands) != 1:
            raise ValueError(
                "exactly one probe routing mutation operand is required"
            )


class ProbeRoutingPlanError(ValueError):
    pass


def probe_routing_rank(
    comparison: ProbeRoutingComparison,
) -> tuple[int, int, int, int]:
    """Lexicographic convergence rank.

    The first component counts currently installed probe selectors that point
    into a route table whose contents are not exact. Withdrawing such a rule
    may create one additional missing desired rule, so ordinary difference
    cardinality is not a valid safety-progress metric. The lexicographic rank
    makes that fail-closed withdrawal a strict improvement.
    """
    if not isinstance(comparison, ProbeRoutingComparison):
        raise ProbeRoutingPlanError(
            "comparison must be ProbeRoutingComparison"
        )
    drift_tables = _drift_tables(comparison)
    active_drift_rules = sum(
        1
        for rule in comparison.observed_rules
        if rule.table in drift_tables
    )
    route_diff = (
        len(comparison.missing_routes)
        + len(comparison.stale_routes)
    )
    return (
        active_drift_rules,
        route_diff,
        len(comparison.stale_rules),
        len(comparison.missing_rules),
    )


def select_probe_routing_step(
    comparison: ProbeRoutingComparison,
) -> ProbeRoutingMutationStep | None:
    """Select one fail-closed mutation.

    Ordering:
      active selector into drifted table -> withdraw
      stale selector                    -> withdraw
      missing terminal guard            -> add
      stale path route                  -> delete
      stale guard                       -> delete
      missing path route                -> add
      missing selector                  -> add
      exact state                       -> none

    A selector is never added while any route content remains non-exact.
    """
    if not isinstance(comparison, ProbeRoutingComparison):
        raise ProbeRoutingPlanError(
            "comparison must be ProbeRoutingComparison"
        )
    if comparison.conflicts:
        raise ProbeRoutingPlanError(
            "probe routing contains reserved-owner conflicts"
        )

    drift_tables = _drift_tables(comparison)
    active_drift = tuple(
        rule
        for rule in comparison.observed_rules
        if rule.table in drift_tables
    )
    if active_drift:
        return ProbeRoutingMutationStep(
            ProbeRoutingStepKind.WITHDRAW_RULE,
            observed_rule=min(active_drift, key=_observed_rule_key),
        )

    if comparison.stale_rules:
        return ProbeRoutingMutationStep(
            ProbeRoutingStepKind.WITHDRAW_RULE,
            observed_rule=min(
                comparison.stale_rules,
                key=_observed_rule_key,
            ),
        )

    missing_guards = tuple(
        route
        for route in comparison.missing_routes
        if route.route_type is ManagedRouteType.BLACKHOLE
    )
    if missing_guards:
        return ProbeRoutingMutationStep(
            ProbeRoutingStepKind.ADD_GUARD_ROUTE,
            desired_route=min(missing_guards, key=_desired_route_key),
        )

    stale_paths = tuple(
        route
        for route in comparison.stale_routes
        if route.route_type is ManagedRouteType.UNICAST
    )
    if stale_paths:
        return ProbeRoutingMutationStep(
            ProbeRoutingStepKind.DELETE_PATH_ROUTE,
            observed_route=min(stale_paths, key=_observed_route_key),
        )

    stale_guards = tuple(
        route
        for route in comparison.stale_routes
        if route.route_type is ManagedRouteType.BLACKHOLE
    )
    if stale_guards:
        return ProbeRoutingMutationStep(
            ProbeRoutingStepKind.DELETE_GUARD_ROUTE,
            observed_route=min(stale_guards, key=_observed_route_key),
        )

    missing_paths = tuple(
        route
        for route in comparison.missing_routes
        if route.route_type is ManagedRouteType.UNICAST
    )
    if missing_paths:
        return ProbeRoutingMutationStep(
            ProbeRoutingStepKind.ADD_PATH_ROUTE,
            desired_route=min(missing_paths, key=_desired_route_key),
        )

    if comparison.missing_rules:
        if comparison.missing_routes or comparison.stale_routes:
            raise ProbeRoutingPlanError(
                "probe selector cannot be added before route table is exact"
            )
        return ProbeRoutingMutationStep(
            ProbeRoutingStepKind.ADD_RULE,
            desired_rule=min(
                comparison.missing_rules,
                key=_desired_rule_key,
            ),
        )

    if comparison.confirmed:
        return None

    raise ProbeRoutingPlanError(
        "probe routing is not exact but no safe mutation step exists"
    )


def _drift_tables(
    comparison: ProbeRoutingComparison,
) -> set[int]:
    return {
        route.table
        for route in (
            comparison.missing_routes
            + comparison.stale_routes
        )
    }


def _desired_route_key(
    route: ManagedRouteSpec,
) -> tuple[object, ...]:
    return (
        route.table,
        int(route.destination.network_address),
        route.destination.prefixlen,
        route.route_type.value,
        route.metric,
        route.protocol,
    )


def _observed_route_key(
    route: ObservedManagedRoute,
) -> tuple[object, ...]:
    return (
        route.table,
        int(route.destination.network_address),
        route.destination.prefixlen,
        route.route_type.value,
        route.metric,
        route.protocol,
    )


def _observed_rule_key(
    rule: ObservedManagedRule,
) -> tuple[object, ...]:
    return (
        rule.priority,
        rule.table,
        int(rule.destination.network_address)
        if rule.destination is not None
        else -1,
    )


def _desired_rule_key(
    rule: ProbeRuleSpec,
) -> tuple[object, ...]:
    return (
        rule.priority,
        rule.table,
        int(rule.target),
        rule.process_uid,
    )
