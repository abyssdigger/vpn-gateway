"""Linux Driver for EXP-048-backed structural payload route/RPDB mutation."""

from __future__ import annotations

from dataclasses import dataclass

from .iproute_priority_backend import CommandRunner
from .payload_routing_desired import (
    ManagedRouteSpec,
    ManagedRouteType,
    ManagedRuleSpec,
)
from .structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
)


class LinuxStructuralRoutingError(ValueError):
    pass


@dataclass(slots=True)
class LinuxStructuralRoutingDriver:
    """Narrow argv-only mutation Driver.

    Authoritative observation and postcondition verification belong to the
    outer structural Enforcer. This Driver renders only EXP-048-backed
    payload route/RPDB operations.
    """

    runner: CommandRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")

    def add_route(self, spec: ManagedRouteSpec) -> None:
        if not isinstance(spec, ManagedRouteSpec):
            raise ValueError("spec must be ManagedRouteSpec")
        self.runner.run(self._desired_route_command("add", spec))

    def delete_route(self, route: ObservedManagedRoute) -> None:
        if not isinstance(route, ObservedManagedRoute):
            raise ValueError("route must be ObservedManagedRoute")
        self.runner.run(self._observed_route_delete_command(route))

    def add_rule(self, spec: ManagedRuleSpec) -> None:
        if not isinstance(spec, ManagedRuleSpec):
            raise ValueError("spec must be ManagedRuleSpec")
        self.runner.run(
            (
                "ip", "-n", self.namespace, "-4", "rule", "add",
                "priority", str(spec.priority),
                "iif", spec.ingress.ifname,
                "to", spec.destination.with_prefixlen,
                "lookup", str(spec.table),
            )
        )

    def delete_rule(self, rule: ObservedManagedRule) -> None:
        if not isinstance(rule, ObservedManagedRule):
            raise ValueError("rule must be ObservedManagedRule")
        if (
            rule.ingress is None
            or rule.destination is None
            or rule.fwmark is not None
            or rule.fwmask is not None
            or rule.uid_start is not None
            or rule.uid_end is not None
            or rule.ipproto is not None
        ):
            raise LinuxStructuralRoutingError(
                "observed rule is not an exact payload dispatch rule"
            )
        self.runner.run(
            (
                "ip", "-n", self.namespace, "-4", "rule", "del",
                "priority", str(rule.priority),
                "iif", rule.ingress.ifname,
                "to", rule.destination.with_prefixlen,
                "lookup", str(rule.table),
            )
        )

    def _desired_route_command(
        self,
        action: str,
        spec: ManagedRouteSpec,
    ) -> tuple[str, ...]:
        if action not in ("add", "del"):
            raise ValueError("action must be add or del")
        command = [
            "ip", "-n", self.namespace, "-4", "route", action,
            spec.route_type.value,
            _render_destination(spec.destination),
            "table", str(spec.table),
            "proto", str(spec.protocol),
            "metric", str(spec.metric),
        ]
        if spec.route_type is ManagedRouteType.BLACKHOLE:
            return tuple(command)

        assert spec.endpoint is not None
        if spec.gateway is not None:
            command.extend(("via", str(spec.gateway)))
        command.extend(("dev", spec.endpoint.ifname))
        if spec.onlink:
            command.append("onlink")
        return tuple(command)

    def _observed_route_delete_command(
        self,
        route: ObservedManagedRoute,
    ) -> tuple[str, ...]:
        command = [
            "ip", "-n", self.namespace, "-4", "route", "del",
            route.route_type.value,
            _render_destination(route.destination),
            "table", str(route.table),
            "proto", str(route.protocol),
            "metric", str(route.metric),
        ]

        if route.route_type is ManagedRouteType.BLACKHOLE:
            if (
                route.endpoint is not None
                or route.gateway is not None
                or route.onlink
            ):
                raise LinuxStructuralRoutingError(
                    "observed blackhole route carries path fields"
                )
            return tuple(command)

        if route.endpoint is None:
            raise LinuxStructuralRoutingError(
                "observed unicast route has no current endpoint identity"
            )
        if route.gateway is not None:
            command.extend(("via", str(route.gateway)))
        command.extend(("dev", route.endpoint.ifname))
        if route.onlink:
            command.append("onlink")
        return tuple(command)


def _render_destination(destination) -> str:
    if destination.prefixlen == 0:
        return "default"
    return destination.with_prefixlen


# Transitional alias; current code uses the Driver role name.
LinuxStructuralRoutingBackend = LinuxStructuralRoutingDriver
