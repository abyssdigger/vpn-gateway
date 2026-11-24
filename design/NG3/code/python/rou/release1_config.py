"""Canonical VPN-GATE configuration grammar and normalization.

The Release-1 parser remains frozen to its historical surface. The current parser
layers explicit managed-VPN intent on top without changing Release-1 semantics.
Lower runtime materializers consume typed results; they do not parse user strings.
""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import base64
import ipaddress
from pathlib import PurePosixPath
from types import MappingProxyType
import re
import tomllib
from typing import Any, Mapping

from .config import ConfigError, _parse_structural_root
from .ip_port import IP_PORT_MAX, IP_PORT_MIN, is_ip_port
from .domain import Direction, StructuralConfig
from .port_bundle import PortBundle, PortSpan
from .operational_log import OperationalLogLevel


_TOP_LEVEL_KEYS = frozenset(
    {
        "default_snat_address",
        "helper_routing_interfaces",
        "helper_routing_policy",
        "log_level",
        "device",
        "profile",
    }
)
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


class HelperRoutingPolicy(str, Enum):
    PEACEFUL = "peaceful"


class HelperRoutingSelectorKind(str, Enum):
    LOCAL = "local"
    EXTERNAL = "external"
    ANY = "any"
    INTERFACE = "interface"


@dataclass(frozen=True, slots=True)
class HelperRoutingSelector:
    kind: HelperRoutingSelectorKind
    interface: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, HelperRoutingSelectorKind):
            raise ValueError("kind must be HelperRoutingSelectorKind")
        if self.kind is HelperRoutingSelectorKind.INTERFACE:
            if not isinstance(self.interface, str) or not self.interface:
                raise ValueError("interface selector requires an interface name")
        elif self.interface is not None:
            raise ValueError("special helper selector cannot carry interface name")


@dataclass(frozen=True, slots=True)
class FirewallRuleConfig:
    direction: str
    action: str
    protocol: str | None = None
    source_ipv4_cidr: ipaddress.IPv4Network | None = None
    source_ports: PortBundle | None = None
    destination_ipv4_cidr: ipaddress.IPv4Network | None = None
    destination_ports: PortBundle | None = None
    path_ifname: str | None = None
    private_peer_ipv4: ipaddress.IPv4Address | None = None
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
    helper_routing_interfaces: tuple[HelperRoutingSelector, ...] = ()
    helper_routing_policy: HelperRoutingPolicy = HelperRoutingPolicy.PEACEFUL
    log_level: OperationalLogLevel = OperationalLogLevel.INFO


class ManagedVpnKind(str, Enum):
    WIREGUARD = "wireguard"


@dataclass(frozen=True, slots=True)
class ManagedWireGuardPeerConfig:
    peer_id: str
    public_key: str
    endpoint_address: ipaddress.IPv4Address
    endpoint_port: int
    probe_target: ipaddress.IPv4Address
    preshared_key_file: str | None = None


@dataclass(frozen=True, slots=True)
class ManagedWireGuardConfig:
    kind: ManagedVpnKind
    interface: str
    address: ipaddress.IPv4Interface
    private_key_file: str
    listen_port: int | None
    peers: tuple[ManagedWireGuardPeerConfig, ...]
    shared_prefixes: tuple[ipaddress.IPv4Network, ...] = ()


@dataclass(frozen=True, slots=True)
class CurrentConfig:
    base: Release1Config
    managed_vpns: Mapping[str, ManagedWireGuardConfig]

    @property
    def structural(self) -> StructuralConfig:
        return self.base.structural

    @property
    def devices(self) -> Mapping[str, DeviceRelease1Config]:
        return self.base.devices

    @property
    def profiles(self) -> Mapping[str, ProfileRelease1Config]:
        return self.base.profiles


def parse_current_config(text: str) -> CurrentConfig:
    """Parse the current surface while preserving Release-1 compatibility."""
    try:
        raw = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, TypeError) as exc:
        raise CurrentConfigError(f"invalid TOML: {exc}") from None
    return _parse_current_raw(raw)


class CurrentConfigError(Release1ConfigError):
    pass


def _parse_current_raw(raw: Any) -> CurrentConfig:
    if not isinstance(raw, dict):
        raise CurrentConfigError("top level must be a TOML table")

    raw_devices = raw.get("device", {})
    if not isinstance(raw_devices, dict):
        raise CurrentConfigError("device must be a TOML table")

    transformed = dict(raw)
    transformed_devices: dict[str, Any] = {}
    managed_bases: dict[str, ManagedWireGuardConfig] = {}

    for device_id, raw_body in raw_devices.items():
        if not isinstance(raw_body, dict):
            transformed_devices[device_id] = raw_body
            continue

        body = dict(raw_body)
        if body.get("enabled") is True and "managed_vpn" in body:
            where = f"device.{device_id}"
            if "expected_interfaces" in body:
                raise CurrentConfigError(
                    f"{where} must not combine managed_vpn and expected_interfaces"
                )
            if "allow_vpn_client" in body:
                raise CurrentConfigError(
                    f"{where} must not combine managed_vpn and allow_vpn_client"
                )
            managed = _parse_managed_wireguard(
                body["managed_vpn"],
                f"{where}.managed_vpn",
            )
            managed_bases[device_id] = managed
            body.pop("managed_vpn")
            body["expected_interfaces"] = [managed.interface]
            body["allow_vpn_client"] = [
                _render_managed_peer_transport(managed, peer)
                for peer in managed.peers
            ]
        elif "managed_vpn" in body:
            # Disabled placeholders remain intentionally shallow.
            body.pop("managed_vpn")

        transformed_devices[device_id] = body

    transformed["device"] = transformed_devices
    try:
        base = _parse_release1_raw(transformed)
    except Release1ConfigError as exc:
        raise CurrentConfigError(str(exc)) from None

    managed: dict[str, ManagedWireGuardConfig] = {}
    for device_id, intent in managed_bases.items():
        shared = {
            network
            for profile in base.structural.profiles.values()
            if profile.enabled and device_id in profile.device_order
            for network in profile.destinations
        }
        shared_prefixes = tuple(
            sorted(
                shared,
                key=lambda network: (
                    int(network.network_address),
                    network.prefixlen,
                ),
            )
        )
        exact_business_targets = {
            network.network_address
            for network in shared_prefixes
            if network.prefixlen == 32
        }
        for peer in intent.peers:
            if peer.probe_target in exact_business_targets:
                raise CurrentConfigError(
                    f"device.{device_id}.managed_vpn peer {peer.peer_id!r} "
                    f"probe_target {peer.probe_target} is also an exact Profile "
                    "destination"
                )
        managed[device_id] = replace(
            intent,
            shared_prefixes=shared_prefixes,
        )

    return CurrentConfig(
        base=base,
        managed_vpns=MappingProxyType(managed),
    )


def parse_release1_config(text: str) -> Release1Config:
    """Parse the canonical Release-1 TOML surface."""
    try:
        raw = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, TypeError) as exc:
        raise Release1ConfigError(f"invalid TOML: {exc}") from None
    return _parse_release1_raw(raw)


def _parse_release1_raw(raw: Any) -> Release1Config:
    """Normalize an already parsed Release-1 document."""
    if not isinstance(raw, dict):
        raise Release1ConfigError("top level must be a TOML table")
    unknown_top = sorted(set(raw) - _TOP_LEVEL_KEYS)
    if unknown_top:
        raise Release1ConfigError(
            "top level has unsupported field(s): " + ", ".join(unknown_top)
        )

    log_level = _parse_operational_log_level(raw.get("log_level", "info"))
    default_snat_address = _parse_optional_snat_address(
        raw.get("default_snat_address"),
        "default_snat_address",
    )
    helper_routing_interfaces = _parse_helper_routing_interfaces(
        raw.get("helper_routing_interfaces", ":none")
    )
    helper_routing_policy = _parse_helper_routing_policy(
        raw.get("helper_routing_policy", "peaceful")
    )
    raw_devices = _table(raw.get("device", {}), "device")
    raw_profiles = _table(raw.get("profile", {}), "profile")

    normalized_profiles: dict[str, Any] = {}
    profile_modes: dict[str, tuple[Direction, ipaddress.IPv4Address | None]] = {}
    profile_reserve_devices: dict[str, frozenset[str]] = {}
    for profile_id, raw_body in raw_profiles.items():
        body = _table(raw_body, f"profile.{profile_id}")
        normalized = dict(body)
        if body.get("enabled") is True:
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
        helper_routing_interfaces=helper_routing_interfaces,
        helper_routing_policy=helper_routing_policy,
        log_level=log_level,
    )


_MANAGED_VPN_KEYS = frozenset(
    {
        "kind",
        "interface",
        "address",
        "private_key_file",
        "listen_port",
        "peers",
    }
)
_MANAGED_WG_PEER_KEYS = frozenset(
    {
        "id",
        "public_key",
        "endpoint",
        "probe_target",
        "preshared_key_file",
    }
)
_CURRENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _parse_managed_wireguard(value: Any, where: str) -> ManagedWireGuardConfig:
    if not isinstance(value, dict):
        raise CurrentConfigError(f"{where} must be a TOML table")
    _reject_current_unknown(value, _MANAGED_VPN_KEYS, where)

    if value.get("kind") != ManagedVpnKind.WIREGUARD.value:
        raise CurrentConfigError(
            f'{where}.kind must be exactly "wireguard"'
        )

    interface = value.get("interface")
    if (
        not isinstance(interface, str)
        or not _IFNAME_RE.fullmatch(interface)
        or len(interface.encode("utf-8")) > 15
    ):
        raise CurrentConfigError(
            f"{where}.interface must be an exact Linux interface name"
        )

    address_value = value.get("address")
    if not isinstance(address_value, str):
        raise CurrentConfigError(
            f"{where}.address must be a canonical IPv4 interface prefix"
        )
    try:
        address = ipaddress.ip_interface(address_value)
    except ValueError:
        raise CurrentConfigError(
            f"{where}.address must be a canonical IPv4 interface prefix"
        ) from None
    if (
        not isinstance(address, ipaddress.IPv4Interface)
        or str(address) != address_value
    ):
        raise CurrentConfigError(
            f"{where}.address must be a canonical IPv4 interface prefix"
        )

    private_key_file = _parse_secret_file_reference(
        value.get("private_key_file"),
        f"{where}.private_key_file",
    )

    listen_port_value = value.get("listen_port")
    if listen_port_value is None:
        listen_port = None
    elif (
        type(listen_port_value) is not int
        or not IP_PORT_MIN <= listen_port_value <= IP_PORT_MAX
    ):
        raise CurrentConfigError(
            f"{where}.listen_port must be an integer in "
            f"{IP_PORT_MIN}..{IP_PORT_MAX}"
        )
    else:
        listen_port = listen_port_value

    raw_peers = value.get("peers")
    if not isinstance(raw_peers, list) or not raw_peers:
        raise CurrentConfigError(
            f"{where}.peers must be a non-empty array of tables"
        )
    peers = tuple(
        _parse_managed_wireguard_peer(
            item,
            f"{where}.peers[{index}]",
        )
        for index, item in enumerate(raw_peers)
    )

    for label, values in (
        ("id", [peer.peer_id for peer in peers]),
        ("public_key", [peer.public_key for peer in peers]),
        ("probe_target", [peer.probe_target for peer in peers]),
    ):
        if len(set(values)) != len(values):
            raise CurrentConfigError(
                f"{where}.peers contains duplicate {label}"
            )

    return ManagedWireGuardConfig(
        kind=ManagedVpnKind.WIREGUARD,
        interface=interface,
        address=address,
        private_key_file=private_key_file,
        listen_port=listen_port,
        peers=peers,
    )


def _parse_managed_wireguard_peer(
    value: Any,
    where: str,
) -> ManagedWireGuardPeerConfig:
    if not isinstance(value, dict):
        raise CurrentConfigError(f"{where} must be a TOML table")
    _reject_current_unknown(value, _MANAGED_WG_PEER_KEYS, where)

    peer_id = value.get("id")
    if not isinstance(peer_id, str) or not _CURRENT_ID_RE.fullmatch(peer_id):
        raise CurrentConfigError(
            f"{where}.id must match [a-z0-9][a-z0-9-]*"
        )

    public_key = _parse_wireguard_public_key(
        value.get("public_key"),
        f"{where}.public_key",
    )
    endpoint_address, endpoint_port = _parse_wireguard_endpoint(
        value.get("endpoint"),
        f"{where}.endpoint",
    )
    probe_target = _parse_exact_ipv4(
        value.get("probe_target"),
        f"{where}.probe_target",
    )

    preshared = value.get("preshared_key_file")
    preshared_key_file = (
        None
        if preshared is None
        else _parse_secret_file_reference(
            preshared,
            f"{where}.preshared_key_file",
        )
    )

    return ManagedWireGuardPeerConfig(
        peer_id=peer_id,
        public_key=public_key,
        endpoint_address=endpoint_address,
        endpoint_port=endpoint_port,
        probe_target=probe_target,
        preshared_key_file=preshared_key_file,
    )


def _parse_wireguard_public_key(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise CurrentConfigError(
            f"{where} must be a canonical WireGuard public key"
        )
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise CurrentConfigError(
            f"{where} must be a canonical WireGuard public key"
        ) from None
    if (
        len(decoded) != 32
        or base64.b64encode(decoded).decode("ascii") != value
    ):
        raise CurrentConfigError(
            f"{where} must be a canonical WireGuard public key"
        )
    return value


def _parse_wireguard_endpoint(
    value: Any,
    where: str,
) -> tuple[ipaddress.IPv4Address, int]:
    if not isinstance(value, str) or value.count(":") != 1:
        raise CurrentConfigError(
            f"{where} must be exact-IPv4:UDP-port"
        )
    address_text, port_text = value.split(":", 1)
    address = _parse_exact_ipv4(address_text, f"{where} address")
    if not port_text.isdigit():
        raise CurrentConfigError(
            f"{where} UDP port must be an integer"
        )
    port = int(port_text)
    if (
        str(port) != port_text
        or not IP_PORT_MIN <= port <= IP_PORT_MAX
    ):
        raise CurrentConfigError(
            f"{where} UDP port must be in {IP_PORT_MIN}..{IP_PORT_MAX}"
        )
    return address, port


def _parse_exact_ipv4(value: Any, where: str) -> ipaddress.IPv4Address:
    if not isinstance(value, str):
        raise CurrentConfigError(f"{where} must be an exact IPv4 address")
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        raise CurrentConfigError(
            f"{where} must be an exact IPv4 address"
        ) from None
    if str(address) != value:
        raise CurrentConfigError(
            f"{where} must be a canonical exact IPv4 address"
        )
    return address


def _parse_secret_file_reference(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise CurrentConfigError(
            f"{where} must be a canonical absolute file path"
        )
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or value == "/"
        or str(path) != value
        or ".." in path.parts
    ):
        raise CurrentConfigError(
            f"{where} must be a canonical absolute file path"
        )
    return value


def _render_managed_peer_transport(
    intent: ManagedWireGuardConfig,
    peer: ManagedWireGuardPeerConfig,
) -> str:
    local = (
        ""
        if intent.listen_port is None
        else f":{intent.listen_port}"
    )
    return (
        f"udp{local}>{peer.endpoint_address}:{peer.endpoint_port}"
    )


def _reject_current_unknown(
    body: Mapping[str, Any],
    allowed: frozenset[str],
    where: str,
) -> None:
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise CurrentConfigError(
            f"{where} has unsupported field(s): {', '.join(unknown)}"
        )


def _parse_operational_log_level(value: Any) -> OperationalLogLevel:
    if isinstance(value, str):
        try:
            return OperationalLogLevel(value)
        except ValueError:
            pass
    raise Release1ConfigError(
        'log_level must be exactly one of "error", "warning", "info", "debug"'
    )


def _parse_helper_routing_policy(value: Any) -> HelperRoutingPolicy:
    if value == "peaceful":
        return HelperRoutingPolicy.PEACEFUL
    raise Release1ConfigError(
        'helper_routing_policy must be exactly "peaceful" in Release 1'
    )


def _parse_helper_routing_interfaces(
    value: Any,
) -> tuple[HelperRoutingSelector, ...]:
    if not isinstance(value, str) or not value:
        raise Release1ConfigError(
            "helper_routing_interfaces must be a non-empty canonical selector string"
        )
    parts = value.split(",")
    if any(not item or item.strip() != item for item in parts):
        raise Release1ConfigError(
            "helper_routing_interfaces must not contain empty or whitespace-padded selectors"
        )
    if len(set(parts)) != len(parts):
        raise Release1ConfigError(
            "helper_routing_interfaces contains duplicate selectors"
        )

    complete = {":none", ":external", ":any"}
    if complete.intersection(parts):
        if len(parts) != 1:
            raise Release1ConfigError(
                "helper_routing_interfaces :none, :external and :any must appear alone"
            )
        token = parts[0]
        if token == ":none":
            return ()
        return (
            HelperRoutingSelector(
                HelperRoutingSelectorKind.EXTERNAL
                if token == ":external"
                else HelperRoutingSelectorKind.ANY
            ),
        )

    selectors: list[HelperRoutingSelector] = []
    has_local = False
    exact_interfaces: list[str] = []
    for token in parts:
        if token == ":local":
            has_local = True
            continue
        if token.startswith(":"):
            raise Release1ConfigError(
                f"helper_routing_interfaces has unsupported selector {token!r}"
            )
        if not _IFNAME_RE.fullmatch(token) or len(token.encode("utf-8")) > 15:
            raise Release1ConfigError(
                f"helper_routing_interfaces has invalid Linux interface name {token!r}"
            )
        exact_interfaces.append(token)

    if has_local and "lo" in exact_interfaces:
        raise Release1ConfigError(
            "helper_routing_interfaces must not redundantly combine :local and lo"
        )
    if has_local:
        selectors.append(HelperRoutingSelector(HelperRoutingSelectorKind.LOCAL))
    selectors.extend(
        HelperRoutingSelector(HelperRoutingSelectorKind.INTERFACE, interface)
        for interface in sorted(exact_interfaces)
    )
    if not selectors:
        raise Release1ConfigError(
            "helper_routing_interfaces must select :none or at least one routing interface scope"
        )
    return tuple(selectors)


def render_helper_routing_interfaces(
    selectors: tuple[HelperRoutingSelector, ...],
) -> str:
    if not isinstance(selectors, tuple) or any(
        not isinstance(item, HelperRoutingSelector) for item in selectors
    ):
        raise ValueError("selectors must be a tuple of HelperRoutingSelector")
    if not selectors:
        return ":none"
    rendered = []
    for selector in selectors:
        if selector.kind is HelperRoutingSelectorKind.LOCAL:
            rendered.append(":local")
        elif selector.kind is HelperRoutingSelectorKind.EXTERNAL:
            rendered.append(":external")
        elif selector.kind is HelperRoutingSelectorKind.ANY:
            rendered.append(":any")
        else:
            assert selector.interface is not None
            rendered.append(selector.interface)
    return ",".join(rendered)


def _table(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Release1ConfigError(f"{where} must be a TOML table")
    return value


def _parse_direction(
    value: Any,
    where: str,
    *,
    default_snat_address: ipaddress.IPv4Address | None,
) -> tuple[Direction, ipaddress.IPv4Address | None]:
    if value == "outbound":
        return Direction.OUTBOUND, None
    if isinstance(value, str) and value in {"inbound", "bidirectional"}:
        return (
            Direction.INBOUND if value == "inbound" else Direction.BIDIRECTIONAL,
            None,
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
    path_ifname = None
    private_peer = None
    seen: set[str] = set()

    while index < len(tokens):
        clause = tokens[index]
        if clause not in {"from", "to", "via"}:
            raise Release1ConfigError(
                f"{where} has unexpected token {clause!r}"
            )
        if clause in seen:
            raise Release1ConfigError(
                f"{where} contains duplicate {clause!r} clause"
            )
        seen.add(clause)
        index += 1

        if clause == "via":
            if index >= len(tokens):
                raise Release1ConfigError(
                    f"{where} via clause requires 'if <exact-ifname>' or 'peer <IPv4>'"
                )
            mode = tokens[index]
            index += 1
            if mode == "if":
                if index >= len(tokens):
                    raise Release1ConfigError(
                        f"{where} via if clause requires an exact interface name"
                    )
                candidate = tokens[index]
                if (
                    not _IFNAME_RE.fullmatch(candidate)
                    or len(candidate.encode("utf-8")) > 15
                    or "*" in candidate
                ):
                    raise Release1ConfigError(
                        f"{where} via if must be an exact Linux interface name"
                    )
                path_ifname = candidate
                index += 1
                continue
            if mode == "peer":
                if index >= len(tokens):
                    raise Release1ConfigError(
                        f"{where} via peer clause requires an IPv4 address"
                    )
                try:
                    private_peer = ipaddress.IPv4Address(tokens[index])
                except ipaddress.AddressValueError as exc:
                    raise Release1ConfigError(
                        f"{where} via peer must be an IPv4 address: {exc}"
                    ) from None
                index += 1
                continue
            raise Release1ConfigError(
                f"{where} via clause must be 'via if <exact-ifname>' "
                "or 'via peer <IPv4>'"
            )

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
        path_ifname=path_ifname,
        private_peer_ipv4=private_peer,
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
            f"{where} must be an integer in [{IP_PORT_MIN}, {IP_PORT_MAX}]"
        )
    if not is_ip_port(parsed):
        raise Release1ConfigError(
            f"{where} must be an integer in [{IP_PORT_MIN}, {IP_PORT_MAX}]"
        )
    return parsed
