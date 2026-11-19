"""Linux argv-only Driver for NG3 ordinary-host route/RPDB boundary state."""

from __future__ import annotations

from dataclasses import dataclass
import json

from ipaddress import IPv4Address, IPv4Network, ip_network

from .host_underlay_route import (
    HostUnderlayPin,
    classify_existing_exact_route,
    parse_ordinary_route_get,
    render_pin_argv,
)
from .iproute_priority_backend import CommandRunner
from .linux_host_boundary_policy import (
    HostBoundaryReturnRouteSpec,
    HostBoundaryRouteSpec,
    HostBoundaryRuleSpec,
)


@dataclass(slots=True)
class LinuxHostBoundaryRouteBackend:
    runner: CommandRunner
    network_namespace: str | None = None

    def __post_init__(self) -> None:
        if self.network_namespace is not None and (
            not isinstance(self.network_namespace, str)
            or not self.network_namespace
        ):
            raise ValueError("network_namespace must be non-empty text or None")

    def observe_underlay_pin(
        self,
        endpoint: IPv4Address,
        *,
        managed_interface: str,
        owner_protocol: int,
    ) -> HostUnderlayPin:
        if not isinstance(endpoint, IPv4Address):
            raise ValueError("endpoint must be IPv4Address")
        raw = self.runner.run(
            self._cmd("ip", "-j", "-4", "route", "get", str(endpoint))
        )
        candidate = parse_ordinary_route_get(
            raw,
            endpoint=endpoint,
            managed_interface=managed_interface,
            owner_protocol=owner_protocol,
        )
        exact = self.runner.run(
            self._cmd(
                "ip", "-j", "-4", "route", "show",
                "table", "main",
            )
        )
        return classify_existing_exact_route(candidate, exact)

    def add_underlay_pin(self, pin: HostUnderlayPin) -> None:
        if not isinstance(pin, HostUnderlayPin):
            raise ValueError("pin must be HostUnderlayPin")
        if pin.present:
            return
        if not pin.owned:
            return
        self.runner.run(self._cmd(*render_pin_argv(pin)))

    def delete_underlay_pin(self, pin: HostUnderlayPin) -> None:
        if not isinstance(pin, HostUnderlayPin):
            raise ValueError("pin must be HostUnderlayPin")
        if not pin.owned:
            return
        self.runner.run(self._cmd(*self._route_delete(
            destination=pin.destination.with_prefixlen,
            interface=pin.interface,
            gateway=None if pin.gateway is None else str(pin.gateway),
            source=None if pin.source is None else str(pin.source),
            protocol=pin.protocol,
            table=None,
        )))

    def bootstrap_route_present(self, route: HostBoundaryRouteSpec) -> bool:
        if not isinstance(route, HostBoundaryRouteSpec):
            raise ValueError("route must be HostBoundaryRouteSpec")
        raw = self.runner.run(
            self._cmd(
                "ip", "-j", "-4", "route", "show",
                "table", "main",
            )
        )
        return _exact_route_present(
            raw,
            destination=route.destination.with_prefixlen,
            gateway=None if route.via is None else str(route.via),
            interface=route.interface,
            protocol=route.protocol,
        )

    def return_route_present(self, route: HostBoundaryReturnRouteSpec) -> bool:
        if not isinstance(route, HostBoundaryReturnRouteSpec):
            raise ValueError("route must be HostBoundaryReturnRouteSpec")
        # Query table=all so an absent custom table is represented as an empty
        # result rather than an iproute2 "FIB table does not exist" command failure.
        raw = self.runner.run(
            self._cmd("ip", "-j", "-4", "route", "show", "table", "all")
        )
        return _exact_return_route_present(raw, route)

    def return_rule_present(self, rule: HostBoundaryRuleSpec) -> bool:
        if not isinstance(rule, HostBoundaryRuleSpec):
            raise ValueError("rule must be HostBoundaryRuleSpec")
        raw = self.runner.run(self._cmd("ip", "-j", "-4", "rule", "show"))
        return _exact_rule_present(raw, rule)

    def add_bootstrap_route(self, route: HostBoundaryRouteSpec) -> None:
        if not isinstance(route, HostBoundaryRouteSpec):
            raise ValueError("route must be HostBoundaryRouteSpec")
        argv = [
            "ip", "-4", "route", "add",
            route.destination.with_prefixlen,
        ]
        if route.via is not None:
            argv.extend(("via", str(route.via)))
        argv.extend(("dev", route.interface, "proto", str(route.protocol)))
        self.runner.run(self._cmd(*argv))

    def delete_bootstrap_route(self, route: HostBoundaryRouteSpec) -> None:
        if not isinstance(route, HostBoundaryRouteSpec):
            raise ValueError("route must be HostBoundaryRouteSpec")
        argv = [
            "ip", "-4", "route", "del",
            route.destination.with_prefixlen,
        ]
        if route.via is not None:
            argv.extend(("via", str(route.via)))
        argv.extend(("dev", route.interface, "proto", str(route.protocol)))
        self.runner.run(self._cmd(*argv))

    def add_return_route(self, route: HostBoundaryReturnRouteSpec) -> None:
        if not isinstance(route, HostBoundaryReturnRouteSpec):
            raise ValueError("route must be HostBoundaryReturnRouteSpec")
        argv = ["ip", "-4", "route", "add", "default"]
        if route.via is not None:
            argv.extend(("via", str(route.via)))
        argv.extend((
            "dev", route.interface,
            "table", str(route.table),
            "proto", str(route.protocol),
        ))
        self.runner.run(self._cmd(*argv))

    def delete_return_route(self, route: HostBoundaryReturnRouteSpec) -> None:
        if not isinstance(route, HostBoundaryReturnRouteSpec):
            raise ValueError("route must be HostBoundaryReturnRouteSpec")
        argv = ["ip", "-4", "route", "del", "default"]
        if route.via is not None:
            argv.extend(("via", str(route.via)))
        argv.extend((
            "dev", route.interface,
            "table", str(route.table),
            "proto", str(route.protocol),
        ))
        self.runner.run(self._cmd(*argv))

    def add_return_rule(self, rule: HostBoundaryRuleSpec) -> None:
        if not isinstance(rule, HostBoundaryRuleSpec):
            raise ValueError("rule must be HostBoundaryRuleSpec")
        self.runner.run(self._cmd(
            "ip", "-4", "rule", "add",
            "priority", str(rule.priority),
            "fwmark", hex(rule.mark),
            "lookup", str(rule.table),
        ))

    def delete_return_rule(self, rule: HostBoundaryRuleSpec) -> None:
        if not isinstance(rule, HostBoundaryRuleSpec):
            raise ValueError("rule must be HostBoundaryRuleSpec")
        self.runner.run(self._cmd(
            "ip", "-4", "rule", "del",
            "priority", str(rule.priority),
            "fwmark", hex(rule.mark),
            "lookup", str(rule.table),
        ))

    def _cmd(self, *args: str) -> tuple[str, ...]:
        if self.network_namespace is None:
            return tuple(args)
        return ("ip", "netns", "exec", self.network_namespace, *args)

    @staticmethod
    def _route_delete(
        *,
        destination: str,
        interface: str,
        gateway: str | None,
        source: str | None,
        protocol: int,
        table: int | None,
    ) -> tuple[str, ...]:
        argv = ["ip", "-4", "route", "del", destination]
        if gateway is not None:
            argv.extend(("via", gateway))
        argv.extend(("dev", interface))
        if source is not None:
            argv.extend(("src", source))
        if table is not None:
            argv.extend(("table", str(table)))
        argv.extend(("proto", str(protocol)))
        return tuple(argv)



def _exact_route_present(
    raw_json: str,
    *,
    destination: str,
    gateway: str | None,
    interface: str,
    protocol: int,
) -> bool:
    try:
        rows = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        raise RuntimeError("invalid host-boundary route JSON") from None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("host-boundary route JSON must be an array of objects")
    expected_network = _parse_route_destination(destination)
    matches = [
        row
        for row in rows
        if _parse_route_destination(row.get("dst", "default")) == expected_network
    ]
    if not matches:
        return False
    if len(matches) != 1:
        raise RuntimeError("host-boundary exact route is ambiguous")
    row = matches[0]
    if row.get("type", "unicast") != "unicast":
        raise RuntimeError("host-boundary exact route is not unicast")
    if row.get("dev") != interface or row.get("gateway") != gateway:
        raise RuntimeError("host-boundary exact route next hop is foreign/conflicting")
    actual_protocol = _decimal(row.get("protocol"))
    if actual_protocol != protocol:
        raise RuntimeError("host-boundary exact route protocol owner mismatch")
    metric = row.get("metric")
    if metric not in (None, 0, "0"):
        raise RuntimeError("host-boundary exact route carries unexpected metric")
    return True


def _exact_return_route_present(
    raw_json: str,
    desired: HostBoundaryReturnRouteSpec,
) -> bool:
    try:
        rows = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        raise RuntimeError("invalid host-boundary route JSON") from None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("host-boundary route JSON must be an array of objects")
    matches = [
        row
        for row in rows
        if _decimal(row.get("table")) == desired.table
        and row.get("dst", "default") == "default"
    ]
    if not matches:
        return False
    if len(matches) != 1:
        raise RuntimeError("host-boundary return table default is ambiguous")
    row = matches[0]
    if row.get("type", "unicast") != "unicast":
        raise RuntimeError("host-boundary return route is not unicast")
    expected_gateway = None if desired.via is None else str(desired.via)
    if row.get("dev") != desired.interface or row.get("gateway") != expected_gateway:
        raise RuntimeError("host-boundary return route next hop is foreign/conflicting")
    if _decimal(row.get("protocol")) != desired.protocol:
        raise RuntimeError("host-boundary return route protocol owner mismatch")
    metric = row.get("metric")
    if metric not in (None, 0, "0"):
        raise RuntimeError("host-boundary return route carries unexpected metric")
    return True


def _exact_rule_present(raw_json: str, desired: HostBoundaryRuleSpec) -> bool:
    try:
        rows = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        raise RuntimeError("invalid host-boundary rule JSON") from None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("host-boundary rule JSON must be an array of objects")
    matches = [
        row for row in rows
        if _decimal(row.get("priority")) == desired.priority
    ]
    if not matches:
        return False
    if len(matches) != 1:
        raise RuntimeError("host-boundary return rule priority is ambiguous")
    row = matches[0]
    if row.get("src") not in (None, "all"):
        raise RuntimeError("host-boundary return rule has foreign source selector")
    if _decimal(row.get("table")) != desired.table:
        raise RuntimeError("host-boundary return rule table mismatch")
    if _mark(row.get("fwmark")) != desired.mark:
        raise RuntimeError("host-boundary return rule mark mismatch")
    mask = row.get("fwmask")
    if mask is not None and _mark(mask) != 0xFFFFFFFF:
        raise RuntimeError("host-boundary return rule mask mismatch")
    for forbidden in ("iif", "oif", "dst", "sport", "dport", "ipproto"):
        if forbidden in row:
            raise RuntimeError(
                f"host-boundary return rule carries unsupported selector {forbidden!r}"
            )
    return True


def _parse_route_destination(value: object) -> IPv4Network | None:
    if value == "default":
        return IPv4Network("0.0.0.0/0")
    if not isinstance(value, str):
        return None
    try:
        network = ip_network(value, strict=False)
    except ValueError:
        return None
    return network if isinstance(network, IPv4Network) else None


def _decimal(value: object) -> int | None:
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _mark(value: object) -> int | None:
    if type(value) is int:
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None
