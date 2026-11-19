"""Linux mutation Driver for Release-1 probe route/RPDB owner state."""

from __future__ import annotations

from dataclasses import dataclass

from .iproute_priority_backend import CommandRunner
from .linux_structural_routing import LinuxStructuralRoutingBackend
from .network_policy_layout import NetworkPolicyPlatformSpace
from .payload_routing_desired import ManagedRouteSpec, ManagedRouteType
from .probe_policy import (
    AvailabilityProbeMechanism,
    ProbeRuleSpec,
)
from .structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
)


class LinuxProbeRoutingError(ValueError):
    pass


@dataclass(slots=True)
class LinuxProbeRoutingBackend:
    """Thin owner-safe wrapper over shared route rendering plus EXP-065 RPDB."""

    runner: CommandRunner
    namespace: str
    platform: NetworkPolicyPlatformSpace

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")
        if not isinstance(self.platform, NetworkPolicyPlatformSpace):
            raise ValueError("platform must be NetworkPolicyPlatformSpace")

    def add_route(self, spec: ManagedRouteSpec) -> None:
        self._validate_desired_route(spec)
        self._shared().add_route(spec)

    def delete_route(self, route: ObservedManagedRoute) -> None:
        self._validate_observed_route(route)
        self._shared().delete_route(route)

    def add_rule(self, spec: ProbeRuleSpec) -> None:
        if not isinstance(spec, ProbeRuleSpec):
            raise ValueError("spec must be ProbeRuleSpec")
        self._validate_rule_resources(spec.priority, spec.table)
        if spec.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise LinuxProbeRoutingError(
                "Release 1 probe RPDB supports only ICMP"
            )
        self.runner.run(
            (
                "ip", "-n", self.namespace, "-4", "rule", "add",
                "priority", str(spec.priority),
                "uidrange", f"{spec.process_uid}-{spec.process_uid}",
                "ipproto", "icmp",
                "to", f"{spec.target}/32",
                "lookup", str(spec.table),
            )
        )

    def delete_rule(self, rule: ObservedManagedRule) -> None:
        if not isinstance(rule, ObservedManagedRule):
            raise ValueError("rule must be ObservedManagedRule")
        self._validate_rule_resources(rule.priority, rule.table)
        if (
            rule.ingress is not None
            or rule.destination is None
            or rule.destination.prefixlen != 32
            or rule.fwmark is not None
            or rule.fwmask is not None
            or rule.uid_start is None
            or rule.uid_end is None
            or rule.uid_start != rule.uid_end
            or rule.ipproto != 1
            or not 1 <= rule.uid_start <= 0xFFFFFFFE
        ):
            raise LinuxProbeRoutingError(
                "observed rule is not an exact Release-1 probe RPDB rule"
            )
        self.runner.run(
            (
                "ip", "-n", self.namespace, "-4", "rule", "del",
                "priority", str(rule.priority),
                "uidrange", f"{rule.uid_start}-{rule.uid_end}",
                "ipproto", "1",
                "to", rule.destination.with_prefixlen,
                "lookup", str(rule.table),
            )
        )

    def _validate_desired_route(self, spec: ManagedRouteSpec) -> None:
        if not isinstance(spec, ManagedRouteSpec):
            raise ValueError("spec must be ManagedRouteSpec")
        if not self.platform.probe_tables.contains(spec.table):
            raise LinuxProbeRoutingError(
                "probe route table is outside reserved probe table pool"
            )
        expected_protocol = (
            self.platform.guard_route_protocol
            if spec.route_type is ManagedRouteType.BLACKHOLE
            else self.platform.path_route_protocol
        )
        expected_metric = (
            self.platform.route_metrics.terminal_guard_metric
            if spec.route_type is ManagedRouteType.BLACKHOLE
            else self.platform.route_metrics.first_preference_metric
        )
        if spec.protocol != expected_protocol or spec.metric != expected_metric:
            raise LinuxProbeRoutingError(
                "probe route role protocol/metric differs from platform contract"
            )

    def _validate_observed_route(self, route: ObservedManagedRoute) -> None:
        if not isinstance(route, ObservedManagedRoute):
            raise ValueError("route must be ObservedManagedRoute")
        if not self.platform.probe_tables.contains(route.table):
            raise LinuxProbeRoutingError(
                "observed route is outside reserved probe table pool"
            )
        expected_protocol = (
            self.platform.guard_route_protocol
            if route.route_type is ManagedRouteType.BLACKHOLE
            else self.platform.path_route_protocol
        )
        expected_metric = (
            self.platform.route_metrics.terminal_guard_metric
            if route.route_type is ManagedRouteType.BLACKHOLE
            else self.platform.route_metrics.first_preference_metric
        )
        if route.protocol != expected_protocol or route.metric != expected_metric:
            raise LinuxProbeRoutingError(
                "observed probe route role differs from platform contract"
            )

    def _validate_rule_resources(self, priority: int, table: int) -> None:
        if not self.platform.probe_rule_priorities.contains(priority):
            raise LinuxProbeRoutingError(
                "probe rule priority is outside reserved probe pool"
            )
        if not self.platform.probe_tables.contains(table):
            raise LinuxProbeRoutingError(
                "probe rule table is outside reserved probe pool"
            )

    def _shared(self) -> LinuxStructuralRoutingBackend:
        return LinuxStructuralRoutingBackend(self.runner, self.namespace)
