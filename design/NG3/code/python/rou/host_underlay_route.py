"""Observation/normalization of ordinary-host underlay routes for VPN endpoint pins."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, ip_network
import json


class HostUnderlayRouteError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HostUnderlayPin:
    endpoint: IPv4Address
    interface: str
    gateway: IPv4Address | None
    source: IPv4Address | None
    protocol: int
    owned: bool = True
    present: bool = False

    @property
    def destination(self) -> IPv4Network:
        return IPv4Network(f"{self.endpoint}/32")


def parse_ordinary_route_get(
    raw_json: str,
    *,
    endpoint: IPv4Address,
    managed_interface: str,
    owner_protocol: int,
) -> HostUnderlayPin:
    """Normalize one ordinary main-table route-get result into an exact /32 pin.

    Release-1 intentionally does not attempt to reproduce arbitrary administrator RPDB
    policy. A route selected from a non-main table is rejected rather than copied into an
    unrelated table.
    """
    if not isinstance(endpoint, IPv4Address):
        raise HostUnderlayRouteError("endpoint must be IPv4Address")
    if not isinstance(managed_interface, str) or not managed_interface:
        raise HostUnderlayRouteError("managed_interface must be non-empty text")
    if type(owner_protocol) is not int or not 1 <= owner_protocol <= 255:
        raise HostUnderlayRouteError("owner_protocol must be in [1, 255]")

    try:
        rows = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        raise HostUnderlayRouteError("invalid ip route get JSON") from None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise HostUnderlayRouteError("ip route get must return exactly one object")
    row = rows[0]

    route_type = row.get("type", "unicast")
    if route_type != "unicast":
        raise HostUnderlayRouteError(
            f"underlay endpoint route type must be unicast, got {route_type!r}"
        )

    table = row.get("table", "main")
    if table not in {"main", 254}:
        raise HostUnderlayRouteError(
            f"underlay endpoint route must be selected from main table, got {table!r}"
        )

    dev = row.get("dev")
    if not isinstance(dev, str) or not dev:
        raise HostUnderlayRouteError("underlay endpoint route has no usable interface")
    if dev == managed_interface:
        raise HostUnderlayRouteError(
            "underlay endpoint currently resolves through managed boundary"
        )

    gateway = _optional_ipv4(row.get("gateway"), "gateway")
    source_value = row.get("prefsrc", row.get("src"))
    source = _optional_ipv4(source_value, "source")

    return HostUnderlayPin(
        endpoint=endpoint,
        interface=dev,
        gateway=gateway,
        source=source,
        protocol=owner_protocol,
    )


def classify_existing_exact_route(
    pin: HostUnderlayPin,
    raw_json: str,
) -> HostUnderlayPin:
    """Mark a matching pre-existing exact /32 as external rather than owned."""
    if not isinstance(pin, HostUnderlayPin):
        raise HostUnderlayRouteError("pin must be HostUnderlayPin")
    try:
        rows = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        raise HostUnderlayRouteError("invalid exact-route JSON") from None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise HostUnderlayRouteError("exact-route JSON must be an array of objects")
    matches = [
        row
        for row in rows
        if _route_destination(row.get("dst")) == pin.destination
    ]
    if not matches:
        return pin
    if len(matches) != 1:
        raise HostUnderlayRouteError("exact endpoint route is ambiguous")

    row = matches[0]
    if row.get("type", "unicast") != "unicast":
        raise HostUnderlayRouteError("existing exact endpoint route is not unicast")
    dev = row.get("dev")
    if dev != pin.interface:
        raise HostUnderlayRouteError(
            "existing exact endpoint route does not match observed ordinary interface"
        )
    gateway = _optional_ipv4(row.get("gateway"), "exact-route gateway")
    if gateway != pin.gateway:
        raise HostUnderlayRouteError(
            "existing exact endpoint route does not match observed ordinary gateway"
        )
    exact_source = _optional_ipv4(
        row.get("prefsrc", row.get("src")),
        "exact-route source",
    )
    if exact_source is not None and exact_source != pin.source:
        raise HostUnderlayRouteError(
            "existing exact endpoint route source conflicts with observed ordinary source"
        )

    existing_protocol = _optional_protocol(row.get("protocol"))
    return HostUnderlayPin(
        endpoint=pin.endpoint,
        interface=pin.interface,
        gateway=pin.gateway,
        source=pin.source,
        protocol=pin.protocol,
        owned=existing_protocol == pin.protocol,
        present=True,
    )


def render_pin_argv(pin: HostUnderlayPin) -> tuple[str, ...]:
    if not isinstance(pin, HostUnderlayPin):
        raise HostUnderlayRouteError("pin must be HostUnderlayPin")
    argv = [
        "ip",
        "-4",
        "route",
        "add",
        pin.destination.with_prefixlen,
    ]
    if pin.gateway is not None:
        argv.extend(("via", str(pin.gateway)))
    argv.extend(("dev", pin.interface))
    if pin.source is not None:
        argv.extend(("src", str(pin.source)))
    argv.extend(("proto", str(pin.protocol)))
    return tuple(argv)


def _route_destination(value: object) -> IPv4Network | None:
    if not isinstance(value, str) or value == "default":
        return None
    try:
        network = ip_network(value, strict=False)
    except ValueError:
        return None
    return network if isinstance(network, IPv4Network) else None


def _optional_protocol(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is int:
        return value if 0 <= value <= 255 else None
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if 0 <= parsed <= 255 else None
    return None


def _optional_ipv4(value: object, label: str) -> IPv4Address | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HostUnderlayRouteError(f"underlay {label} must be IPv4 text")
    try:
        return IPv4Address(value)
    except ValueError:
        raise HostUnderlayRouteError(f"underlay {label} is not IPv4") from None
