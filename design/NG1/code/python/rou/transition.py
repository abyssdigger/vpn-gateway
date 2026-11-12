from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .device_engine import DeviceBindingSnapshot
from .environment import EnvironmentSnapshot, KernelRoute, KernelRule
from .firewall_state import FirewallDesiredState
from .kernel_state import (
    BLACKHOLE_PROTOCOL,
    ROUTE_PROTOCOL,
    KernelDesiredState,
    KernelRouteSpec,
    KernelRuleSpec,
)
from .nat_state import NatDesiredState


class TransitionKind(str, Enum):
    BINDING_LIFECYCLE = "binding-lifecycle"
    STRUCTURAL = "structural"


@dataclass(frozen=True)
class TransitionAssessment:
    kind: TransitionKind
    reasons: tuple[str, ...]


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
    previous_firewall: FirewallDesiredState,
    desired_firewall: FirewallDesiredState,
    previous_nat: NatDesiredState,
    desired_nat: NatDesiredState,
    previous_bindings: DeviceBindingSnapshot,
    desired_bindings: DeviceBindingSnapshot,
    observed: EnvironmentSnapshot,
    observed_filter: str,
    observed_nat: str,
) -> TransitionAssessment:
    """Prove whether drift is an ordinary binding lifecycle transition.

    This intentionally recognizes only binding-set changes in schema version 1.
    Availability transitions remain architecturally incremental, but the production
    availability trigger is deferred; future DeviceManager work must persist enough
    availability history to prove that transition equivalently.

    Anything not proven here is structural/unknown and therefore uses the global barrier.
    """

    reasons: list[str] = []

    if observed.sysctl_map.get("net.ipv4.ip_forward") != "1":
        reasons.append("IPv4 forwarding is not verified open")

    if set(previous_kernel.owned_tables) != set(desired_kernel.owned_tables):
        reasons.append("owned routing-table allocation changed")

    if _binding_key(previous_bindings) == _binding_key(desired_bindings):
        reasons.append("bound interface generation did not change")


    previous_by_name = {
        (item.device_name, item.expected_index, item.identity.ifname):
        item.identity.ifindex
        for item in previous_bindings.bound
    }
    desired_by_name = {
        (item.device_name, item.expected_index, item.identity.ifname):
        item.identity.ifindex
        for item in desired_bindings.bound
    }
    for key in previous_by_name.keys() & desired_by_name.keys():
        if previous_by_name[key] != desired_by_name[key]:
            reasons.append(
                "same-name/new-ifindex replacement requires structural barrier "
                "with the current interface-name firewall backend"
            )
            break

    expected_rules = {_rule_key(item) for item in desired_kernel.rules}
    max_priority = max((item.priority for item in desired_kernel.rules), default=0)
    observed_rules = {
        _rule_key(item)
        for item in observed.rules
        if 1 <= item.priority <= max_priority
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

    if observed_filter not in {
        previous_firewall.canonical_save,
        desired_firewall.canonical_save,
    }:
        reasons.append("filter table is neither previous nor desired verified generation")

    if observed_nat not in {
        previous_nat.canonical_save,
        desired_nat.canonical_save,
    }:
        reasons.append("NAT table is neither previous nor desired verified generation")

    if reasons:
        return TransitionAssessment(
            TransitionKind.STRUCTURAL,
            tuple(reasons),
        )

    return TransitionAssessment(
        TransitionKind.BINDING_LIFECYCLE,
        (),
    )
