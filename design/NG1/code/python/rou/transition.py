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

    This intentionally recognizes only binding-set changes in schema version 1.
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

    if _binding_key(previous_bindings) == _binding_key(desired_bindings):
        reasons.append("bound interface generation did not change")

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
    required_blackholes = {
        _route_key(route)
        for route in desired_kernel.routes
        if route.route_type == "blackhole"
    }
    missing_blackholes = required_blackholes - observed_route_keys
    if missing_blackholes:
        reasons.append(
            "terminal Profile blackhole is missing; lifecycle repair cannot "
            "safely preserve Profile-local fail-close"
        )

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

    return TransitionAssessment(
        TransitionKind.BINDING_LIFECYCLE,
        (),
    )
