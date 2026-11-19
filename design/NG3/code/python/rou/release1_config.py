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
from .port_bundle import PortBundle, PortSpan


_TOP_LEVEL_KEYS = frozenset({"default_snat_address", "device", "profile"})
_DEVICE_KEYS = frozenset(
    {
        "enabled",
        "expected_interfaces",
        "availability_check",
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
    r"^(tcp|udp)(?:/([^:>]+))?:([^>]+)(?:>([^>]+))?$"
)


class Release1ConfigError(ConfigError):
    pass


@dataclass(frozen=True, slots=True)
class FirewallRuleConfig:
    direction: str
    action: str
    protocol: str | None = None
    source_ipv4_cidr: ipaddress.IPv4Network | None = None
    source_ports: PortBundle | None = None
    destination_ipv4_cidr: ipaddress.IPv4Network | None = None
    destination_ports: PortBundle | None = None
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
    host_ports: PortBundle
    internal_ports: PortBundle


@dataclass(frozen=True, slots=True)
class AvailabilityCheckConfig:
    mechanism: str
    target: ipaddress.IPv4Address | None = None


@dataclass(frozen=True, slots=True)
class DeviceRelease1Config:
    availability_check: AvailabilityCheckConfig | None
    use_outbound_nat: bool | None
    allow_vpn_client: tuple[VpnClientTransportConfig, ...]
    publish_vpn_server: tuple[VpnServerPublicationConfig, ...]
    firewall: tuple[FirewallRuleConfig, ...] | None


@dataclass(frozen=True, slots=True)
class ProfileRelease1Config:
    effective_snat_address: ipaddress.IPv4Address | None
    availability_check: AvailabilityCheckConfig | None
    availability_uses_device_default: bool = False
    reserve_device_ids: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Release1Config:
    structural: StructuralConfig
    devices: Mapping[str, DeviceRelease1Config]
    profiles: Mapping[str, ProfileRelease1Config]
    default_snat_address: ipaddress.IPv4Address | None = None


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

    default_snat_address = _parse_optional_snat_address(
        raw.get("default_snat_address"),
        "default_snat_address",
    )
    raw_devices = _table(raw.get("device", {}), "device")
    raw_profiles = _table(raw.get("profile", {}), "profile")

    normalized_profiles: dict[str, Any] = {}
    profile_modes: dict[str, tuple[Direction, ipaddress.IPv4Address | None]] = {}
    profile_reserve_devices: dict[str, frozenset[str]] = {}
    for profile_id, raw_body in raw_profiles.items():
        body = _table(raw_body, f"profile.{profile_id}")
        normalized = dict(body)
        if _is_enabled(body):
            direction, effective_snat_address = _parse_direction(
                body.get("direction"),
                f"profile.{profile_id}.direction",
                default_snat_address=default_snat_address,
            )
            normalized["direction"] = direction.value
            device_order, reserve_devices = _parse_device_memberships(
                body.get("device_order"),
                f"profile.{profile_id}.device_order",
            )
            normalized["device_order"] = list(device_order)
            profile_modes[profile_id] = (direction, effective_snat_address)
            profile_reserve_devices[profile_id] = reserve_devices
        normalized_profiles[profile_id] = normalized

    normalized_root = {
        "device": raw_devices,
        "profile": normalized_profiles,
    }
    try:
        structural = _parse_structural_root(
            normalized_root,
            top_level_keys=_TOP_LEVEL_KEYS,
            device_keys=_DEVICE_KEYS,
            profile_keys=_PROFILE_KEYS,
        )
    except ConfigError as exc:
        raise Release1ConfigError(str(exc)) from None

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
            devices[device_id] = DeviceRelease1Config(None, None, (), (), None)
            continue

        default_availability_check = _parse_availability_description(
            body.get("availability_check"),
            f"device.{device_id}.availability_check",
        )

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
            availability_check=default_availability_check,
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
            profiles[profile_id] = ProfileRelease1Config(None, None)
            continue
        _, effective_snat_address = profile_modes[profile_id]
        availability_check, uses_device_default = _parse_profile_availability(
            body.get("availability_check"),
            f"profile.{profile_id}.availability_check",
        )
        profiles[profile_id] = ProfileRelease1Config(
            effective_snat_address=effective_snat_address,
            availability_check=availability_check,
            availability_uses_device_default=uses_device_default,
            reserve_device_ids=profile_reserve_devices[profile_id],
        )

    untranslated_remote_ranges = tuple(
        destination
        for profile_id, structural_profile in structural.profiles.items()
        if structural_profile.enabled
        and profiles[profile_id].effective_snat_address is None
        for destination in structural_profile.destinations
    )
    for profile_id, profile in profiles.items():
        if profile.effective_snat_address is not None:
            for destination in untranslated_remote_ranges:
                if profile.effective_snat_address in destination:
                    raise Release1ConfigError(
                        f"profile.{profile_id} effective SNAT address "
                        f"{profile.effective_snat_address} overlaps untranslated "
                        f"remote source range {destination}"
                    )

    for profile_id, profile in profiles.items():
        if not profile.availability_uses_device_default:
            continue
        for device_id in structural.profiles[profile_id].device_order:
            if not structural.devices[device_id].enabled:
                continue
            if devices[device_id].availability_check is None:
                raise Release1ConfigError(
                    f"device.{device_id}.availability_check is required by "
                    f"profile.{profile_id}.availability_check = \"default\""
                )

    return Release1Config(
        structural=structural,
        devices=MappingProxyType(devices),
        profiles=MappingProxyType(profiles),
        default_snat_address=default_snat_address,
    )


def _table(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Release1ConfigError(f"{where} must be a TOML table")
    return value


def _is_enabled(body: dict[str, Any]) -> bool:
    return body.get("enabled") is True


def _parse_direction(
    value: Any,
    where: str,
    *,
    default_snat_address: ipaddress.IPv4Address | None,
) -> tuple[Direction, ipaddress.IPv4Address | None]:
    if value == "outbound":
        return Direction.OUTBOUND, None
    if value in {"inbound", "bidirectional"}:
        return (
            Direction.INBOUND if value == "inbound" else Direction.BIDIRECTIONAL,
            None,
        )
    if isinstance(value, str) and "route-return" in value:
        raise Release1ConfigError(
            f"{where}: +route-return is historical and no longer supported"
        )
    if isinstance(value, str) and value.startswith("outbound+snat"):
        raise Release1ConfigError(
            f"{where}: +snat is meaningful only for VPN-to-ordinary traffic"
        )

    for base, direction in (
        ("inbound", Direction.INBOUND),
        ("bidirectional", Direction.BIDIRECTIONAL),
    ):
        bare = f"{base}+snat"
        explicit_prefix = bare + ">"
        if value == bare:
            if default_snat_address is None:
                raise Release1ConfigError(
                    f"{where}: bare +snat requires top-level default_snat_address"
                )
            return direction, default_snat_address
        if isinstance(value, str) and value.startswith(explicit_prefix):
            address_text = value[len(explicit_prefix):]
            address = _parse_snat_address(address_text, where)
            return direction, address

    raise Release1ConfigError(
        f"{where} must be one canonical Release-1 direction form: outbound, inbound, "
        "inbound+snat, inbound+snat>IPv4, bidirectional, bidirectional+snat or "
        "bidirectional+snat>IPv4"
    )


def _parse_optional_snat_address(
    value: Any,
    where: str,
) -> ipaddress.IPv4Address | None:
    if value is None:
        return None
    return _parse_snat_address(value, where)


def _parse_snat_address(
    value: Any,
    where: str,
) -> ipaddress.IPv4Address:
    if not isinstance(value, str):
        raise Release1ConfigError(f"{where} must contain an IPv4 unicast address")
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        raise Release1ConfigError(
            f"{where} must contain an IPv4 unicast address"
        ) from None
    if (
        address.is_unspecified
        or address.is_multicast
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
    ):
        raise Release1ConfigError(
            f"{where} must contain an IPv4 unicast address usable on the managed boundary"
        )
    return address


def _parse_device_memberships(
    value: Any,
    where: str,
) -> tuple[tuple[str, ...], frozenset[str]]:
    if not isinstance(value, list) or not value:
        raise Release1ConfigError(f"{where} must be a non-empty array")

    device_ids: list[str] = []
    reserve_devices: set[str] = set()
    for index, item in enumerate(value):
        item_where = f"{where}[{index}]"
        if not isinstance(item, str):
            raise Release1ConfigError(f"{item_where} must be a string")

        parts = item.split(":")
        if len(parts) == 1:
            device_id = parts[0]
        elif len(parts) == 2 and parts[1] == "reserve":
            device_id = parts[0]
            reserve_devices.add(device_id)
        else:
            suffix = ":".join(parts[1:]) if len(parts) > 1 else ""
            raise Release1ConfigError(
                f"{item_where} has unsupported membership suffix {suffix!r}; "
                'only ":reserve" is supported'
            )
        device_ids.append(device_id)

    if len(set(device_ids)) != len(device_ids):
        raise Release1ConfigError(
            f"{where} contains duplicate Device membership after suffix normalization"
        )

    return tuple(device_ids), frozenset(reserve_devices)


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
            "host-port-bundle[>internal-port-bundle]"
        )
    protocol, selector_text, host_text, internal_text = match.groups()
    host_ports = _parse_port_bundle(host_text, f"{where} host ports")
    internal_ports = (
        host_ports
        if internal_text is None
        else _parse_port_bundle(internal_text, f"{where} internal ports")
    )
    if host_ports.cardinality != internal_ports.cardinality:
        raise Release1ConfigError(
            f"{where} host/internal port bundles must have equal cardinality "
            "for positional 1:1 mapping"
        )
    selector = _publication_selector(selector_text, where)
    return VpnServerPublicationConfig(
        protocol=protocol,
        host_selector=selector,
        host_ports=host_ports,
        internal_ports=internal_ports,
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
    source_ports = None
    destination_network = None
    destination_ports = None
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
        network, ports = _network_and_ports(tokens[index], f"{where} {clause}")
        index += 1
        if clause == "from":
            source_network, source_ports = network, ports
        else:
            destination_network, destination_ports = network, ports

    if (source_ports is not None or destination_ports is not None) and (
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
        source_ports=source_ports,
        destination_ipv4_cidr=destination_network,
        destination_ports=destination_ports,
        comment=comment,
    )


def _network_and_ports(
    value: str,
    where: str,
) -> tuple[ipaddress.IPv4Network, PortBundle | None]:
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
        None
        if port_text is None
        else _parse_port_bundle(port_text, f"{where} ports")
    )


def _parse_port_bundle(value: str, where: str) -> PortBundle:
    if not isinstance(value, str) or not value or any(ch.isspace() for ch in value):
        raise Release1ConfigError(
            f"{where} must be a compact comma-separated port bundle without spaces"
        )
    spans = []
    for index, item in enumerate(value.split(",")):
        if not item:
            raise Release1ConfigError(f"{where} contains an empty item")
        if "-" in item:
            parts = item.split("-")
            if len(parts) != 2:
                raise Release1ConfigError(f"{where}[{index}] has invalid range syntax")
            first = _port(parts[0], f"{where}[{index}] range start")
            last = _port(parts[1], f"{where}[{index}] range end")
        else:
            first = last = _port(item, f"{where}[{index}]")
        try:
            spans.append(PortSpan(first, last))
        except ValueError as exc:
            raise Release1ConfigError(f"{where}[{index}]: {exc}") from None
    try:
        return PortBundle(tuple(spans))
    except ValueError as exc:
        raise Release1ConfigError(f"{where}: {exc}") from None


def _parse_availability_description(
    value: Any,
    where: str,
) -> AvailabilityCheckConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise Release1ConfigError(
            f"{where} must be a table with mechanism and target"
        )
    unknown = sorted(set(value) - {"mechanism", "target"})
    if unknown:
        raise Release1ConfigError(
            f"{where} has unsupported field(s): " + ", ".join(unknown)
        )
    if value.get("mechanism") != "icmp":
        raise Release1ConfigError(
            f'{where}.mechanism must be "icmp"'
        )
    target_value = value.get("target")
    if not isinstance(target_value, str):
        raise Release1ConfigError(
            f"{where}.target must be an exact IPv4 address"
        )
    try:
        target = ipaddress.IPv4Address(target_value)
    except ipaddress.AddressValueError:
        raise Release1ConfigError(
            f"{where}.target must be an exact IPv4 address"
        ) from None
    return AvailabilityCheckConfig("icmp", target)


def _parse_profile_availability(
    value: Any,
    where: str,
) -> tuple[AvailabilityCheckConfig | None, bool]:
    if value is None:
        return None, False
    if value == "default":
        return None, True
    return _parse_availability_description(value, where), False


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
