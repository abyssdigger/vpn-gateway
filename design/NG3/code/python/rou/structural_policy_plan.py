"""Pure phase ordering for guarded cross-domain structural convergence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .composite_nft_plan import (
    CompositeNftMutationStep,
    CompositeNftPlanError,
    select_composite_nft_step,
)
from .composite_nft_policy import (
    CompositeNftDesiredState,
    CompositeNftPolicyComparison,
)
from .payload_routing_compare import PayloadRoutingComparison
from .payload_routing_desired import (
    ManagedRouteSpec,
    ManagedRouteType,
    ManagedRuleSpec,
)
from .structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
)


class StructuralPolicyStepKind(str, Enum):
    ADD_GUARD_ROUTE = "add_guard_route"
    DELETE_ROUTING_RULE = "delete_routing_rule"
    DELETE_ROUTING_ROUTE = "delete_routing_route"
    ADD_PATH_ROUTE = "add_path_route"
    APPLY_NFT_STEP = "apply_nft_step"
    ADD_ROUTING_RULE = "add_routing_rule"


@dataclass(frozen=True, slots=True)
class StructuralPolicyMutationStep:
    kind: StructuralPolicyStepKind
    desired_route: ManagedRouteSpec | None = None
    observed_route: ObservedManagedRoute | None = None
    desired_rule: ManagedRuleSpec | None = None
    observed_rule: ObservedManagedRule | None = None
    nft_step: CompositeNftMutationStep | None = None

    def __post_init__(self) -> None:
        operands = (
            self.desired_route is not None,
            self.observed_route is not None,
            self.desired_rule is not None,
            self.observed_rule is not None,
            self.nft_step is not None,
        )
        if sum(operands) != 1:
            raise ValueError("exactly one structural mutation operand is required")


class StructuralPolicyPlanError(ValueError):
    pass


def select_structural_policy_step(
    routing: PayloadRoutingComparison,
    nft: CompositeNftPolicyComparison,
    nft_desired: CompositeNftDesiredState,
) -> StructuralPolicyMutationStep | None:
    """Select one exact-before-release mutation while ForwardingGate is closed.

    Ordering:
      desired guards
      -> stale RPDB dispatch
      -> stale ordinary routes / stale guards
      -> missing ordinary routes
      -> nft convergence
      -> missing desired RPDB dispatch
      -> exact state
    """
    if not isinstance(routing, PayloadRoutingComparison):
        raise StructuralPolicyPlanError(
            "routing must be PayloadRoutingComparison"
        )
    if not isinstance(nft, CompositeNftPolicyComparison):
        raise StructuralPolicyPlanError(
            "nft must be CompositeNftPolicyComparison"
        )
    if not isinstance(nft_desired, CompositeNftDesiredState):
        raise StructuralPolicyPlanError(
            "nft_desired must be CompositeNftDesiredState"
        )
    if routing.conflicts:
        raise StructuralPolicyPlanError(
            "payload routing contains reserved-owner conflicts"
        )
    if nft.conflicts:
        raise StructuralPolicyPlanError(
            "composite nft policy contains conflicts"
        )

    missing_guards = tuple(
        route
        for route in routing.missing_routes
        if route.route_type is ManagedRouteType.BLACKHOLE
    )
    if missing_guards:
        return StructuralPolicyMutationStep(
            kind=StructuralPolicyStepKind.ADD_GUARD_ROUTE,
            desired_route=min(missing_guards, key=_desired_route_key),
        )

    if routing.stale_rules:
        return StructuralPolicyMutationStep(
            kind=StructuralPolicyStepKind.DELETE_ROUTING_RULE,
            observed_rule=min(
                routing.stale_rules,
                key=_observed_rule_key,
            ),
        )

    if routing.stale_routes:
        return StructuralPolicyMutationStep(
            kind=StructuralPolicyStepKind.DELETE_ROUTING_ROUTE,
            observed_route=min(
                routing.stale_routes,
                key=_stale_route_cleanup_key,
            ),
        )

    missing_paths = tuple(
        route
        for route in routing.missing_routes
        if route.route_type is ManagedRouteType.UNICAST
    )
    if missing_paths:
        return StructuralPolicyMutationStep(
            kind=StructuralPolicyStepKind.ADD_PATH_ROUTE,
            desired_route=min(missing_paths, key=_desired_route_key),
        )

    if not nft.desired_confirmed:
        try:
            nft_step = select_composite_nft_step(
                nft,
                nft_desired.local_publication,
            )
        except CompositeNftPlanError as exc:
            raise StructuralPolicyPlanError(str(exc)) from exc
        if nft_step is None:
            raise StructuralPolicyPlanError(
                "nft state is not exact but no safe nft step exists"
            )
        return StructuralPolicyMutationStep(
            kind=StructuralPolicyStepKind.APPLY_NFT_STEP,
            nft_step=nft_step,
        )

    if routing.missing_rules:
        return StructuralPolicyMutationStep(
            kind=StructuralPolicyStepKind.ADD_ROUTING_RULE,
            desired_rule=min(
                routing.missing_rules,
                key=_desired_rule_key,
            ),
        )

    if routing.confirmed and nft.desired_confirmed:
        return None

    raise StructuralPolicyPlanError(
        "structural state is not exact but no safe mutation step exists"
    )


def _desired_route_key(route: ManagedRouteSpec) -> tuple[object, ...]:
    return (
        route.table,
        int(route.destination.network_address),
        route.destination.prefixlen,
        route.route_type.value,
        route.metric,
        route.protocol,
    )


def _observed_rule_key(rule: ObservedManagedRule) -> tuple[object, ...]:
    return (
        rule.priority,
        rule.table,
        int(rule.destination.network_address)
        if rule.destination is not None
        else -1,
        rule.destination.prefixlen
        if rule.destination is not None
        else -1,
    )


def _desired_rule_key(rule: ManagedRuleSpec) -> tuple[object, ...]:
    return (
        rule.priority,
        rule.table,
        int(rule.destination.network_address),
        rule.destination.prefixlen,
    )


def _stale_route_cleanup_key(
    route: ObservedManagedRoute,
) -> tuple[object, ...]:
    # Preserve restrictive stale guards until stale ordinary path routes have
    # been removed from the same closed-barrier cleanup phase.
    return (
        0 if route.route_type is ManagedRouteType.UNICAST else 1,
        route.table,
        int(route.destination.network_address),
        route.destination.prefixlen,
        route.metric,
        route.protocol,
    )
