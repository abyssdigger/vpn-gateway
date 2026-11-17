"""Canonical Release-1 human-facing VPN-GATE configuration grammar.

This module owns only external syntax validation and normalization. Lower runtime
materializers consume the typed result; they must not parse these strings again.
"""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from types import MappingProxyType
import re
import tomllib
from typing import Any, Mapping

from .config import ConfigError, _parse_structural_root
from .domain import Direction, StructuralConfig


_TOP_LEVEL_KEYS = frozenset({"device", "profile"})
_DEVICE_KEYS = frozenset(
    {
        "enabled",
        "expected_interfaces",
        "use_outbound_nat",
        "allow_vpn_client",
        "publish_vpn_server",
        "firewall",
    }
)
_PROFILE_KEYS = frozenset(
    {
        "enabled",
        "direction",
        "destinations",
        "device_order",
        "availability_check",
    }
)
_PROTOCOLS = frozenset({"tcp", "udp", "icmp"})
_TRANSPORT_PROTOCOLS = frozenset({"tcp", "udp"})
_FIREWALL_DIRECTIONS = frozenset({"in", "out"})
_FIREWALL_ACTIONS = frozenset({"allow", "deny", "reject"})
_IFNAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_CLIENT_RE = re.compile(
    r"^(tcp|udp)(?::([0-9]+))?>([^:>]+):([0-9]+)$"
)
_PUBLICATION_RE = re.compile(
    r"^(tcp|udp)(?:/([^:>]+))?:([0-9]+)(?:>([0-9]+))?$"
)


class Release1ConfigError(ConfigError):
    pass


@dataclass(frozen=True, slots=True)
class PortInterval:
    first: int
    last: int

    @property
    def is_single(self) -> bool:
        return self.first == self.last


@dataclass(frozen=True, slots=True)
class FirewallRuleConfig:
    direction: str
    action: str
    protocol: str | None = None
    source_ipv4_cidr: ipaddress.IPv4Network | None = None
    source_port: PortInterval | None = None
    destination_ipv4_cidr: ipaddress.IPv4Network | None = None
    destination_port: PortInterval | None = None
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class VpnClientTransportConfig:
    protocol: str
    remote_address: ipaddress.IPv4Address
    remote_port: int
    local_port: int | None = None


@dataclass(frozen=True, slots=True)
class PublicationHostSelector:
    kind: str  # any | ipv4 | interface
    value: ipaddress.IPv4Address | str | None = None


@dataclass(frozen=True, slots=True)
class VpnServerPublicationConfig:
    protocol: str
    host_selector: PublicationHostSelector
    host_port: int
    internal_port: int


@dataclass(frozen=True, slots=True)
class AvailabilityCheckConfig:
    mechanism: str
    target: ipaddress.IPv4Address | None = None


@dataclass(frozen=True, slots=True)
class DeviceRelease1Config:
    use_outbound_nat: bool | None
    allow_vpn_client: tuple[VpnClientTransportConfig, ...]
    publish_vpn_server: tuple[VpnServerPublicationConfig, ...]
    firewall: tuple[FirewallRuleConfig, ...] | None


@dataclass(frozen=True, slots=True)
class ProfileRelease1Config:
    ordinary_gateway_nat: bool
    availability_check: AvailabilityCheckConfig | None


@dataclass(frozen=True, slots=True)
class Release1Config:
    structural: StructuralConfig
    devices: Mapping[str, DeviceRelease1Config]
    profiles: Mapping[str, ProfileRelease1Config]


def parse_release1_config(text: str) -> Release1Config:
    """Parse the canonical Release-1 TOML surface.

    Historical aliases are intentionally rejected. Disabled placeholders retain
    the structural model's shallow-validation semantics.
    """
    try:
        raw = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, TypeError) as exc:
        raise Release1ConfigError(f"invalid TOML: {exc}") from None

    if not isinstance(raw, dict):
        raise Release1ConfigError("top level must be a TOML table")
    unknown_top = sorted(set(raw) - _TOP_LEVEL_KEYS)
    if unknown_top:
        raise Release1ConfigError(
            "top level has unsupported field(s): " + ", ".join(unknown_top)
        )

    raw_devices = _table(raw.get("device", {}), "device")
    raw_profiles = _table(raw.get("profile", {}), "profile")

    normalized_profiles: dict[str, Any] = {}
    profile_modes: dict[str, tuple[Direction, bool]] = {}
    for profile_id, raw_body in raw_profiles.items():
        body = _table(raw_body, f"profile.{profile_id}")
        normalized = dict(body)
        if _is_enabled(body):
            direction, gateway_nat = _parse_direction(
                body.get("direction"),
                f"profile.{profile_id}.direction",
            )
            normalized["direction"] = direction.value
            profile_modes[profile_id] = (direction, gateway_nat)
        normalized_profiles[profile_id] = normalized

    normalized_root = {
        "device": raw_devices,
        "profile": normalized_profiles,
    }
    structural = _parse_structural_root(
        normalized_root,
        top_level_keys=_TOP_LEVEL_KEYS,
        device_keys=_DEVICE_KEYS,
        profile_keys=_PROFILE_KEYS,
    )

    ordinary_to_vpn_devices = {
        device_id
        for profile in structural.profiles.values()
        if profile.enabled
        and profile.direction in {Direction.OUTBOUND, Direction.BIDIRECTIONAL}
        for device_id in profile.device_order
        if structural.devices[device_id].enabled
    }

    devices: dict[str, DeviceRelease1Config] = {}
    for device_id, raw_body in raw_devices.items():
        body = _table(raw_body, f"device.{device_id}")
        if not structural.devices[device_id].enabled:
            devices[device_id] = DeviceRelease1Config(None, (), (), None)
            continue

        nat_value = body.get("use_outbound_nat")
        if device_id in ordinary_to_vpn_devices and "use_outbound_nat" not in body:
            raise Release1ConfigError(
                f"device.{device_id}.use_outbound_nat is required because "
                "the Device is eligible for ordinary-to-VPN traffic"
            )
        if "use_outbound_nat" in body and type(nat_value) is not bool:
            raise Release1ConfigError(
                f"device.{device_id}.use_outbound_nat must be boolean"
            )

        client_values = _string_or_array(
            body.get("allow_vpn_client"),
            f"device.{device_id}.allow_vpn_client",
        )
        publication_values = _string_or_array(
            body.get("publish_vpn_server"),
            f"device.{device_id}.publish_vpn_server",
        )
        firewall = _parse_firewall(
            body.get("firewall"),
            f"device.{device_id}.firewall",
        )

        devices[device_id] = DeviceRelease1Config(
            use_outbound_nat=nat_value if type(nat_value) is bool else None,
            allow_vpn_client=tuple(
                _parse_client_transport(
                    value,
                    f"device.{device_id}.allow_vpn_client[{index}]",
                )
                for index, value in enumerate(client_values)
            ),
            publish_vpn_server=tuple(
                _parse_publication(
                    value,
                    f"device.{device_id}.publish_vpn_server[{index}]",
                )
                for index, value in enumerate(publication_values)
            ),
            firewall=firewall,
        )

    profiles: dict[str, ProfileRelease1Config] = {}
    for profile_id, raw_body in raw_profiles.items():
        body = _table(raw_body, f"profile.{profile_id}")
        if not structural.profiles[profile_id].enabled:
            profiles[profile_id] = ProfileRelease1Config(False, None)
            continue
        _, gateway_nat = profile_modes[profile_id]
        profiles[profile_id] = ProfileRelease1Config(
            ordinary_gateway_nat=gateway_nat,
            availability_check=_parse_availability(
                body.get("availability_check"),
                f"profile.{profile_id}.availability_check",
            ),
        )

    return Release1Config(
        structural=structural,
        devices=MappingProxyType(devices),
        profiles=MappingProxyType(profiles),
    )


def _table(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Release1ConfigError(f"{where} must be a TOML table")
    return value


def _is_enabled(body: dict[str, Any]) -> bool:
    return body.get("enabled") is True


def _parse_direction(value: Any, where: str) -> tuple[Direction, bool]:
    if value == "outbound":
        return Direction.OUTBOUND, False
    if value == "inbound":
        return Direction.INBOUND, False
    if value == "bidirectional":
        return Direction.BIDIRECTIONAL, False
    if value == "inbound+masquerade":
        return Direction.INBOUND, True
    if value == "bidirectional+masquerade":
        return Direction.BIDIRECTIONAL, True
    if value == "outbound+masquerade":
        raise Release1ConfigError(
            f"{where}: +masquerade is meaningful only for VPN-to-ordinary traffic"
        )
    raise Release1ConfigError(
        f"{where} must be outbound, inbound, bidirectional, "
        "inbound+masquerade or bidirectional+masquerade"
    )


def _string_or_array(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, list) and value:
        if any(not isinstance(item, str) for item in value):
            raise Release1ConfigError(f"{where} entries must be strings")
        values = tuple(value)
    else:
        raise Release1ConfigError(
            f"{where} must be a non-empty string or non-empty array of strings"
        )
    if any(not item for item in values):
        raise Release1ConfigError(f"{where} entries must not be empty")
    if len(set(values)) != len(values):
        raise Release1ConfigError(f"{where} contains duplicates")
    return values


def _parse_client_transport(
    value: str,
    where: str,
) -> VpnClientTransportConfig:
    match = _CLIENT_RE.fullmatch(value)
    if match is None:
        raise Release1ConfigError(
            f"{where} must be tcp|udp[:local-port]>remote-IPv4:remote-port"
        )
    protocol, local_text, address_text, remote_text = match.groups()
    try:
        remote_address = ipaddress.IPv4Address(address_text)
    except ipaddress.AddressValueError:
        raise Release1ConfigError(
            f"{where} remote endpoint must be an exact IPv4 address"
        ) from None
    return VpnClientTransportConfig(
        protocol=protocol,
        remote_address=remote_address,
        remote_port=_port(remote_text, f"{where} remote port"),
        local_port=(
            None
            if local_text is None
            else _port(local_text, f"{where} local port")
        ),
    )


def _parse_publication(
    value: str,
    where: str,
) -> VpnServerPublicationConfig:
    match = _PUBLICATION_RE.fullmatch(value)
    if match is None:
        raise Release1ConfigError(
            f"{where} must be tcp|udp[/host-IPv4|host-interface]:"
            "host-port[>internal-port]"
        )
    protocol, selector_text, host_text, internal_text = match.groups()
    host_port = _port(host_text, f"{where} host port")
    selector = _publication_selector(selector_text, where)
    return VpnServerPublicationConfig(
        protocol=protocol,
        host_selector=selector,
        host_port=host_port,
        internal_port=(
            host_port
            if internal_text is None
            else _port(internal_text, f"{where} internal port")
        ),
    )


def _publication_selector(
    value: str | None,
    where: str,
) -> PublicationHostSelector:
    if value is None:
        return PublicationHostSelector("any", None)
    try:
        return PublicationHostSelector("ipv4", ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        pass
    if (
        not _IFNAME_RE.fullmatch(value)
        or len(value.encode("utf-8")) > 15
        or "*" in value
    ):
        raise Release1ConfigError(
            f"{where} host selector must be an IPv4 address or Linux interface name"
        )
    return PublicationHostSelector("interface", value)


def _parse_firewall(
    value: Any,
    where: str,
) -> tuple[FirewallRuleConfig, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise Release1ConfigError(
            f"{where} must be a non-empty ordered array of rule strings"
        )
    if any(not isinstance(item, str) or not item for item in value):
        raise Release1ConfigError(f"{where} entries must be non-empty strings")
    return tuple(
        _parse_firewall_rule(item, f"{where}[{index}]")
        for index, item in enumerate(value)
    )


def _parse_firewall_rule(value: str, where: str) -> FirewallRuleConfig:
    comment = None
    rule_text = value
    if " # " in value:
        rule_text, comment = value.split(" # ", 1)
        if not comment:
            raise Release1ConfigError(f"{where} comment must not be empty")

    tokens = rule_text.split()
    if len(tokens) < 2:
        raise Release1ConfigError(
            f"{where} must start with <in|out> <allow|deny|reject>"
        )
    direction, action = tokens[:2]
    if direction not in _FIREWALL_DIRECTIONS:
        raise Release1ConfigError(f"{where} direction must be in or out")
    if action not in _FIREWALL_ACTIONS:
        raise Release1ConfigError(
            f"{where} action must be allow, deny or reject"
        )

    index = 2
    protocol = None
    if index < len(tokens) and tokens[index] in _PROTOCOLS:
        protocol = tokens[index]
        index += 1

    source_network = None
    source_port = None
    destination_network = None
    destination_port = None
    seen: set[str] = set()

    while index < len(tokens):
        clause = tokens[index]
        if clause not in {"from", "to"}:
            raise Release1ConfigError(
                f"{where} has unexpected token {clause!r}"
            )
        if clause in seen:
            raise Release1ConfigError(
                f"{where} contains duplicate {clause!r} clause"
            )
        seen.add(clause)
        index += 1
        if index >= len(tokens):
            raise Release1ConfigError(
                f"{where} {clause} clause requires an IPv4 CIDR"
            )
        network, port = _network_and_port(tokens[index], f"{where} {clause}")
        index += 1
        if clause == "from":
            source_network, source_port = network, port
        else:
            destination_network, destination_port = network, port

    if (source_port is not None or destination_port is not None) and (
        protocol not in _TRANSPORT_PROTOCOLS
    ):
        raise Release1ConfigError(
            f"{where} port selectors require explicit tcp or udp protocol"
        )

    return FirewallRuleConfig(
        direction=direction,
        action=action,
        protocol=protocol,
        source_ipv4_cidr=source_network,
        source_port=source_port,
        destination_ipv4_cidr=destination_network,
        destination_port=destination_port,
        comment=comment,
    )


def _network_and_port(
    value: str,
    where: str,
) -> tuple[ipaddress.IPv4Network, PortInterval | None]:
    network_text = value
    port_text = None
    if ":" in value:
        network_text, port_text = value.rsplit(":", 1)
        if not port_text:
            raise Release1ConfigError(f"{where} has an empty port selector")
    try:
        network = ipaddress.ip_network(network_text, strict=True)
    except ValueError as exc:
        raise Release1ConfigError(
            f"{where} is not a strict IPv4 CIDR: {exc}"
        ) from None
    if not isinstance(network, ipaddress.IPv4Network):
        raise Release1ConfigError(f"{where} must be IPv4")
    return network, (
        None if port_text is None else _port_interval(port_text, where)
    )


def _port_interval(value: str, where: str) -> PortInterval:
    if "-" not in value:
        port = _port(value, f"{where} port")
        return PortInterval(port, port)
    parts = value.split("-")
    if len(parts) != 2:
        raise Release1ConfigError(f"{where} has invalid port range")
    first = _port(parts[0], f"{where} range start")
    last = _port(parts[1], f"{where} range end")
    if first > last:
        raise Release1ConfigError(
            f"{where} port range start must be <= end"
        )
    return PortInterval(first, last)


def _parse_availability(
    value: Any,
    where: str,
) -> AvailabilityCheckConfig | None:
    if value is None:
        return None
    if value == "icmp":
        return AvailabilityCheckConfig("icmp", None)
    if isinstance(value, str) and value.startswith("icmp/"):
        address_text = value[5:]
        try:
            target = ipaddress.IPv4Address(address_text)
        except ipaddress.AddressValueError:
            raise Release1ConfigError(
                f"{where} explicit target must be an IPv4 address"
            ) from None
        return AvailabilityCheckConfig("icmp", target)
    raise Release1ConfigError(
        f'{where} must be "icmp" or "icmp/<IPv4>"'
    )


def _port(value: Any, where: str) -> int:
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
    elif type(value) is int:
        parsed = value
    else:
        raise Release1ConfigError(
            f"{where} must be an integer in [1, 65535]"
        )
    if not 1 <= parsed <= 65535:
        raise Release1ConfigError(
            f"{where} must be an integer in [1, 65535]"
        )
    return parsed
