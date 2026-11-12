from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .device_engine import DeviceBindingSnapshot
from .environment import EnvironmentSnapshot, KernelRoute, KernelRule
from .kernel_allocation import MAX_OWNED_RULE_PRIORITY
from .kernel_state import (
    BLACKHOLE_PROTOCOL,
    ROUTE_PROTOCOL,
    KernelDesiredState,
    KernelRouteSpec,
    KernelRuleSpec,
)


class TransitionKind(str, Enum):
    BINDING_LIFECYCLE = "binding-lifecycle"
    ROUTE_ADDITIVE = "route-additive"
    STRUCTURAL = "structural"


@dataclass(frozen=True)
class TransitionAssessment:
    kind: TransitionKind
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PolicyGenerationObservation:
    filter_matches_previous: bool
    filter_matches_desired: bool
    nat_matches_previous: bool
    nat_matches_desired: bool
    ruleset_owned: bool = True

    @property
    def filter_known(self) -> bool:
        return self.filter_matches_previous or self.filter_matches_desired

    @property
    def nat_known(self) -> bool:
        return self.nat_matches_previous or self.nat_matches_desired


def _route_key(route: KernelRoute | KernelRouteSpec) -> tuple:
    return (
        route.table,
        route.destination,
        route.route_type,
        route.protocol,
        route.metric,
        route.ifname,
        tuple((item.ifname, item.weight) for item in route.nexthops),
    )


def _rule_key(rule: KernelRule | KernelRuleSpec) -> tuple:
    return (
        rule.priority,
        rule.iif,
        rule.destination,
        rule.table,
        rule.action,
    )


def _binding_key(snapshot: DeviceBindingSnapshot) -> tuple:
    return tuple(
        (
            item.device_name,
            item.expected_index,
            item.identity.ifname,
            item.identity.ifindex,
        )
        for item in snapshot.bound
    )


def assess_binding_lifecycle(
    previous_kernel: KernelDesiredState,
    desired_kernel: KernelDesiredState,
    policy_generation: PolicyGenerationObservation,
    previous_bindings: DeviceBindingSnapshot,
    desired_bindings: DeviceBindingSnapshot,
    observed: EnvironmentSnapshot,
) -> TransitionAssessment:
    """Prove whether drift is an ordinary binding lifecycle transition.

    This recognizes proven binding-set changes and route-only additive repair in schema
    version 1.
    Availability transitions remain architecturally incremental, but the production
    availability trigger is deferred; future DeviceManager work must persist enough
    availability history to prove that transition equivalently.

    Firewall/NAT backend details are deliberately outside this classifier. The caller
    supplies proof that observed policy is exactly a previous or desired verified
    generation. With the production ifindex-aware nft backend, same-name/new-ifindex is
    therefore an ordinary old-generation removal plus fresh-generation addition.

    Anything not proven here is structural/unknown and therefore uses the global barrier.
    """

    reasons: list[str] = []

    if observed.sysctl_map.get("net.ipv4.ip_forward") != "1":
        reasons.append("IPv4 forwarding is not verified open")

    if set(previous_kernel.owned_tables) != set(desired_kernel.owned_tables):
        reasons.append("owned routing-table allocation changed")

    binding_changed = (
        _binding_key(previous_bindings)
        != _binding_key(desired_bindings)
    )

    expected_rules = {_rule_key(item) for item in desired_kernel.rules}
    observed_rules = {
        _rule_key(item)
        for item in observed.rules
        if 1 <= item.priority <= MAX_OWNED_RULE_PRIORITY
    }
    if observed_rules != expected_rules:
        reasons.append("owned RPDB state is not exactly desired")

    allowed_routes = {
        _route_key(item)
        for item in previous_kernel.routes
    } | {
        _route_key(item)
        for item in desired_kernel.routes
    }

    desired_tables = set(desired_kernel.owned_tables)
    for route in observed.routes:
        key = _route_key(route)
        if route.table in desired_tables and key not in allowed_routes:
            reasons.append(
                "owned Profile table contains route outside previous/new generations"
            )
            break
        if (
            route.protocol in {ROUTE_PROTOCOL, BLACKHOLE_PROTOCOL}
            and route.table not in desired_tables
        ):
            reasons.append("ROU-tagged route exists outside desired Profile tables")
            break


    observed_route_keys = {
        _route_key(route)
        for route in observed.routes
        if route.table in desired_tables
    }
    desired_route_keys = {
        _route_key(route)
        for route in desired_kernel.routes
    }
    required_blackholes = {
        _route_key(route)
        for route in desired_kernel.routes
        if route.route_type == "blackhole"
    }
    missing_blackholes = required_blackholes - observed_route_keys
    if missing_blackholes:
        reasons.append(
            "terminal Profile blackhole is missing; incremental repair cannot "
            "safely preserve Profile-local fail-close"
        )

    if not policy_generation.ruleset_owned:
        reasons.append("nft ruleset contains foreign tables")

    if not policy_generation.filter_known:
        reasons.append(
            "filter policy is neither previous nor desired verified generation"
        )

    if not policy_generation.nat_known:
        reasons.append(
            "NAT policy is neither previous nor desired verified generation"
        )

    if reasons:
        return TransitionAssessment(
            TransitionKind.STRUCTURAL,
            tuple(reasons),
        )

    if binding_changed:
        return TransitionAssessment(
            TransitionKind.BINDING_LIFECYCLE,
            (),
        )

    # A verified removal commit deliberately releases a normal metric slot. On the next
    # reconcile the same binding generation may gain a newly available normal route.
    # More generally, an unexpectedly missing desired unicast route is safe to restore
    # without a global barrier when the entire observed owned route set is a strict subset
    # of the unchanged desired generation, RPDB/policy are already exact desired, and the
    # terminal blackholes remain continuously installed.
    previous_route_keys = {
        _route_key(route)
        for route in previous_kernel.routes
    }
    previous_rule_keys = {
        _rule_key(rule)
        for rule in previous_kernel.rules
    }
    desired_rule_keys = {
        _rule_key(rule)
        for rule in desired_kernel.rules
    }
    route_additive = (
        previous_route_keys == desired_route_keys
        and previous_rule_keys == desired_rule_keys
        and observed_route_keys < desired_route_keys
        and observed_route_keys <= desired_route_keys
        and policy_generation.filter_matches_desired
        and policy_generation.nat_matches_desired
    )
    if route_additive:
        return TransitionAssessment(
            TransitionKind.ROUTE_ADDITIVE,
            (),
        )

    return TransitionAssessment(
        TransitionKind.STRUCTURAL,
        ("no binding change and transition is not proven route-additive",),
    )
