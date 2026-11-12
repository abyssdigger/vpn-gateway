from __future__ import annotations

import ipaddress
from pathlib import Path
import re
import tomllib
from typing import Any

from .domain import (
    ActiveConfig,
    Device,
    Direction,
    EnvelopeAction,
    EnvelopeDirection,
    EnvelopeProtocol,
    ExpectedInterface,
    InterfaceMatch,
    MatchKind,
    NatMode,
    PortRange,
    Profile,
    Publication,
    TrafficEnvelope,
    TrafficEnvelopeRule,
    TransportProtocol,
)
from .metrics import MetricLayoutError, compile_all_metric_layouts


class ConfigError(ValueError):
    pass


_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PREFIX_RE = re.compile(r"^(.+)\*/([1-9][0-9]*)$")
_PUBLICATION_RE = re.compile(
    r"^([0-9]+)(?::([0-9]+))?/(tcp|udp)"
    r"(?:>([0-9]+)(?::([0-9]+))?)?$"
)
_PORT_RE = re.compile(r"^([0-9]+)(?:-([0-9]+))?$")

_TOP_LEVEL_KEYS = frozenset({"schema_version", "device", "profile"})
_ENABLED_DEVICE_KEYS = frozenset(
    {
        "enabled",
        "expected_interfaces",
        "nat",
        "publications",
        "traffic_envelope",
    }
)
_ENABLED_PROFILE_KEYS = frozenset(
    {"enabled", "direction", "destinations", "device_order"}
)
_ENVELOPE_KEYS = frozenset({"default", "rules"})
_ENVELOPE_RULE_KEYS = frozenset(
    {
        "direction",
        "action",
        "source",
        "destination",
        "protocol",
        "source_ports",
        "destination_ports",
    }
)


def _error(message: str) -> ConfigError:
    return ConfigError(message)


def _require_mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(f"{where} must be a TOML table")
    return value


def _validate_id(value: str, kind: str) -> None:
    if not _ID_RE.fullmatch(value):
        raise _error(
            f"invalid {kind} id {value!r}; expected [a-z0-9][a-z0-9-]*"
        )


def _enabled(body: dict[str, Any], where: str) -> bool:
    if "enabled" not in body:
        raise _error(f"{where}.enabled is required")
    value = body["enabled"]
    if type(value) is not bool:
        raise _error(f"{where}.enabled must be boolean")
    return value


def _reject_unknown_keys(
    body: dict[str, Any],
    allowed: frozenset[str],
    where: str,
) -> None:
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise _error(
            f"{where} has unsupported field(s): {', '.join(unknown)}"
        )


def _validate_if_fragment(value: str, where: str) -> None:
    if not value:
        raise _error(f"{where} interface name/prefix must not be empty")
    if len(value.encode("utf-8")) > 15:
        raise _error(
            f"{where} interface name/prefix exceeds Linux IFNAMSIZ-1"
        )
    if value in {".", ".."} or any(
        ch.isspace() or ch in "/:*" for ch in value
    ):
        raise _error(
            f"{where} contains characters not valid in an interface name/prefix"
        )


def _strict_ipv4_network(value: Any, where: str) -> ipaddress.IPv4Network:
    if not isinstance(value, str):
        raise _error(f"{where} must be a string")
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError as exc:
        raise _error(
            f"{where} is not a strict IPv4 CIDR: {exc}"
        ) from None
    if not isinstance(network, ipaddress.IPv4Network):
        raise _error(f"{where} must be IPv4")
    return network


def _parse_expected_interface(value: Any, where: str) -> ExpectedInterface:
    if not isinstance(value, str):
        raise _error(f"{where} must be a string")

    match = _PREFIX_RE.fullmatch(value)
    if match:
        prefix, quota_text = match.groups()
        _validate_if_fragment(prefix, where)
        return ExpectedInterface(
            InterfaceMatch(MatchKind.PREFIX, prefix),
            int(quota_text),
        )

    if "*" in value or "/" in value:
        raise _error(
            f"{where} must be <ifname> or <prefix>*/<positive-quota>"
        )

    _validate_if_fragment(value, where)
    return ExpectedInterface(InterfaceMatch(MatchKind.EXACT, value), 1)


def _port_range(start_text: str, end_text: str | None, where: str) -> PortRange:
    start = int(start_text)
    end = start if end_text is None else int(end_text)
    try:
        return PortRange(start, end)
    except ValueError as exc:
        raise _error(f"{where}: {exc}") from None


def _parse_publication(value: Any, where: str) -> Publication:
    if not isinstance(value, str):
        raise _error(f"{where} must be a string")
    match = _PUBLICATION_RE.fullmatch(value)
    if match is None:
        raise _error(
            f"{where} must be "
            "<external-port-or-range>/<tcp|udp>[><internal-port-or-range>]"
        )

    ext_start, ext_end, protocol_text, int_start, int_end = match.groups()
    external = _port_range(ext_start, ext_end, f"{where} external range")
    internal = (
        external
        if int_start is None
        else _port_range(int_start, int_end, f"{where} internal range")
    )
    try:
        return Publication(
            protocol=TransportProtocol(protocol_text),
            external=external,
            internal=internal,
        )
    except ValueError as exc:
        raise _error(f"{where}: {exc}") from None


def _parse_port_ranges(value: Any, where: str) -> tuple[PortRange, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise _error(f"{where} must be an array of port/range strings")

    ranges: list[PortRange] = []
    for index, raw in enumerate(value):
        item_where = f"{where}[{index}]"
        if not isinstance(raw, str):
            raise _error(f"{item_where} must be a string")
        match = _PORT_RE.fullmatch(raw)
        if match is None:
            raise _error(f"{item_where} must be N or A-B")
        candidate = _port_range(*match.groups(), item_where)
        for previous in ranges:
            if candidate.overlaps(previous):
                raise _error(
                    f"{where} contains overlapping ranges "
                    f"{previous.start}-{previous.end} and "
                    f"{candidate.start}-{candidate.end}"
                )
        ranges.append(candidate)
    return tuple(ranges)


def _parse_envelope_rule(
    raw: Any,
    where: str,
) -> TrafficEnvelopeRule:
    body = _require_mapping(raw, where)
    _reject_unknown_keys(body, _ENVELOPE_RULE_KEYS, where)

    try:
        direction = EnvelopeDirection(body.get("direction"))
    except (TypeError, ValueError):
        raise _error(
            f"{where}.direction must be from-device or to-device"
        ) from None

    try:
        action = EnvelopeAction(body.get("action"))
    except (TypeError, ValueError):
        raise _error(f"{where}.action must be allow or drop") from None

    try:
        protocol = EnvelopeProtocol(body.get("protocol", "any"))
    except (TypeError, ValueError):
        raise _error(
            f"{where}.protocol must be any, tcp, udp or icmp"
        ) from None

    source = (
        None
        if "source" not in body
        else _strict_ipv4_network(body["source"], f"{where}.source")
    )
    destination = (
        None
        if "destination" not in body
        else _strict_ipv4_network(
            body["destination"],
            f"{where}.destination",
        )
    )
    source_ports = _parse_port_ranges(
        body.get("source_ports"),
        f"{where}.source_ports",
    )
    destination_ports = _parse_port_ranges(
        body.get("destination_ports"),
        f"{where}.destination_ports",
    )

    try:
        return TrafficEnvelopeRule(
            direction=direction,
            action=action,
            source=source,
            destination=destination,
            protocol=protocol,
            source_ports=source_ports,
            destination_ports=destination_ports,
        )
    except ValueError as exc:
        raise _error(f"{where}: {exc}") from None


def _parse_traffic_envelope(
    raw: Any,
    where: str,
) -> TrafficEnvelope:
    body = _require_mapping(raw, where)
    _reject_unknown_keys(body, _ENVELOPE_KEYS, where)

    try:
        default_action = EnvelopeAction(body.get("default"))
    except (TypeError, ValueError):
        raise _error(f"{where}.default must be allow or drop") from None

    raw_rules = body.get("rules", [])
    if not isinstance(raw_rules, list):
        raise _error(f"{where}.rules must be an array of tables")

    return TrafficEnvelope(
        default_action=default_action,
        rules=tuple(
            _parse_envelope_rule(
                rule,
                f"{where}.rules[{index}]",
            )
            for index, rule in enumerate(raw_rules)
        ),
    )


def _parse_device(name: str, raw: Any) -> Device:
    _validate_id(name, "Device")
    where = f"device.{name}"
    body = _require_mapping(raw, where)
    enabled = _enabled(body, where)
    if not enabled:
        return Device(name=name, enabled=False)

    _reject_unknown_keys(body, _ENABLED_DEVICE_KEYS, where)

    values = body.get("expected_interfaces")
    if not isinstance(values, list) or not values:
        raise _error(
            f"{where}.expected_interfaces must be a non-empty array"
        )
    expected = tuple(
        _parse_expected_interface(
            value,
            f"{where}.expected_interfaces[{index}]",
        )
        for index, value in enumerate(values)
    )
    _validate_selector_overlap(expected, where)

    try:
        nat = NatMode(body.get("nat"))
    except (TypeError, ValueError):
        raise _error(f"{where}.nat must be none or masquerade") from None

    raw_publications = body.get("publications", [])
    if not isinstance(raw_publications, list):
        raise _error(f"{where}.publications must be an array")
    publications = tuple(
        _parse_publication(
            value,
            f"{where}.publications[{index}]",
        )
        for index, value in enumerate(raw_publications)
    )

    envelope = (
        None
        if "traffic_envelope" not in body
        else _parse_traffic_envelope(
            body["traffic_envelope"],
            f"{where}.traffic_envelope",
        )
    )

    return Device(
        name=name,
        enabled=True,
        expected_interfaces=expected,
        nat=nat,
        publications=publications,
        traffic_envelope=envelope,
    )


def _parse_profile(name: str, raw: Any) -> Profile:
    _validate_id(name, "Profile")
    where = f"profile.{name}"
    body = _require_mapping(raw, where)
    enabled = _enabled(body, where)
    if not enabled:
        return Profile(name=name, enabled=False)

    _reject_unknown_keys(body, _ENABLED_PROFILE_KEYS, where)

    try:
        direction = Direction(body.get("direction"))
    except (TypeError, ValueError):
        allowed = ", ".join(item.value for item in Direction)
        raise _error(
            f"{where}.direction must be one of: {allowed}"
        ) from None

    raw_destinations = body.get("destinations")
    if not isinstance(raw_destinations, list) or not raw_destinations:
        raise _error(
            f"{where}.destinations must be a non-empty array"
        )
    destinations: list[ipaddress.IPv4Network] = []
    seen_destinations: set[ipaddress.IPv4Network] = set()
    for index, value in enumerate(raw_destinations):
        network = _strict_ipv4_network(
            value,
            f"{where}.destinations[{index}]",
        )
        if network in seen_destinations:
            raise _error(
                f"{where}.destinations contains duplicate {network}"
            )
        seen_destinations.add(network)
        destinations.append(network)

    raw_order = body.get("device_order")
    if not isinstance(raw_order, list) or not raw_order:
        raise _error(
            f"{where}.device_order must be a non-empty array"
        )
    order: list[str] = []
    seen_names: set[str] = set()
    for index, value in enumerate(raw_order):
        if not isinstance(value, str):
            raise _error(
                f"{where}.device_order[{index}] must be a Device id string"
            )
        _validate_id(value, "Device reference")
        if value in seen_names:
            raise _error(
                f"{where}.device_order contains duplicate Device id {value!r}"
            )
        seen_names.add(value)
        order.append(value)

    return Profile(
        name=name,
        enabled=True,
        direction=direction,
        destinations=tuple(destinations),
        device_order=tuple(order),
    )


def _validate_selector_overlap(
    expected: tuple[ExpectedInterface, ...],
    where: str,
) -> None:
    for left_index, left in enumerate(expected):
        for right_index in range(left_index + 1, len(expected)):
            right = expected[right_index]
            if left.match.overlaps(right.match):
                raise _error(
                    f"{where}.expected_interfaces[{left_index}] overlaps "
                    f"expected_interfaces[{right_index}]"
                )


def _validate_references(config: ActiveConfig) -> None:
    for profile in config.profiles.values():
        if not profile.enabled:
            continue
        for name in profile.device_order:
            if name not in config.devices:
                raise _error(
                    f"profile.{profile.name}.device_order references "
                    f"unknown Device {name!r}"
                )


def _validate_global_destinations(config: ActiveConfig) -> None:
    owners: dict[ipaddress.IPv4Network, str] = {}
    for profile in config.profiles.values():
        if not profile.enabled:
            continue
        for network in profile.destinations:
            previous = owners.get(network)
            if previous is not None:
                raise _error(
                    f"destination {network} is duplicated by enabled Profiles "
                    f"{previous!r} and {profile.name!r}"
                )
            owners[network] = profile.name


def _validate_active_selector_overlap(config: ActiveConfig) -> None:
    active = config.active_device_names
    flattened: list[tuple[str, int, ExpectedInterface]] = []
    for device_name in sorted(active):
        device = config.devices[device_name]
        for index, expected in enumerate(device.expected_interfaces):
            flattened.append((device_name, index, expected))

    for left_index, (left_device, left_slot, left) in enumerate(flattened):
        for right_device, right_slot, right in flattened[left_index + 1:]:
            if left_device == right_device:
                continue
            if left.match.overlaps(right.match):
                raise _error(
                    "active ExpectedInterface selectors overlap: "
                    f"device.{left_device}[{left_slot}] and "
                    f"device.{right_device}[{right_slot}]"
                )


def _validate_publication_collisions(config: ActiveConfig) -> None:
    active = config.active_device_names
    entries: list[tuple[str, Publication]] = []
    for device_name in sorted(active):
        for publication in config.devices[device_name].publications:
            entries.append((device_name, publication))

    for left_index, (left_device, left) in enumerate(entries):
        for right_device, right in entries[left_index + 1:]:
            if left.protocol is not right.protocol:
                continue

            if left.external.overlaps(right.external):
                raise _error(
                    f"active publication external {left.protocol.value} ranges "
                    f"overlap: device.{left_device} "
                    f"{left.external.start}-{left.external.end} and "
                    f"device.{right_device} "
                    f"{right.external.start}-{right.external.end}"
                )

            if (
                left_device != right_device
                and left.internal.overlaps(right.internal)
            ):
                raise _error(
                    f"active publication internal {left.protocol.value} ranges "
                    f"overlap across Devices: device.{left_device} "
                    f"{left.internal.start}-{left.internal.end} and "
                    f"device.{right_device} "
                    f"{right.internal.start}-{right.internal.end}"
                )



def _validate_remote_initiated_profiles(config: ActiveConfig) -> None:
    for profile in config.profiles.values():
        if not profile.enabled or profile.direction is Direction.OUTBOUND:
            continue

        active_devices = [
            config.devices[name]
            for name in profile.device_order
            if config.devices[name].enabled
        ]
        capacity = sum(device.interface_quota for device in active_devices)
        if capacity != 1:
            raise _error(
                f"profile.{profile.name} direction={profile.direction.value!r} "
                "requires active interface capacity exactly 1; "
                f"got {capacity}"
            )

        missing_restrictive_envelope = [
            device.name
            for device in active_devices
            if (
                device.traffic_envelope is None
                or device.traffic_envelope.default_action
                is not EnvelopeAction.DROP
            )
        ]
        if missing_restrictive_envelope:
            raise _error(
                f"profile.{profile.name} direction={profile.direction.value!r} "
                "requires traffic_envelope default='drop' on every active "
                "referenced Device; missing/restrictive-default violation: "
                + ", ".join(sorted(missing_restrictive_envelope))
            )

def parse_active_config(text: str) -> ActiveConfig:
    try:
        root = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise _error(f"invalid TOML: {exc}") from None

    unknown_top = sorted(set(root) - _TOP_LEVEL_KEYS)
    if unknown_top:
        raise _error(
            f"unsupported top-level field(s): {', '.join(unknown_top)}"
        )

    version = root.get("schema_version")
    if type(version) is not int or version != 1:
        raise _error("schema_version = 1 is required")

    raw_devices = _require_mapping(root.get("device", {}), "device")
    raw_profiles = _require_mapping(root.get("profile", {}), "profile")

    devices = {
        name: _parse_device(name, raw)
        for name, raw in raw_devices.items()
    }
    profiles = {
        name: _parse_profile(name, raw)
        for name, raw in raw_profiles.items()
    }
    config = ActiveConfig(devices=devices, profiles=profiles)

    _validate_references(config)
    _validate_global_destinations(config)
    _validate_active_selector_overlap(config)
    _validate_publication_collisions(config)
    _validate_remote_initiated_profiles(config)

    try:
        compile_all_metric_layouts(config)
    except MetricLayoutError as exc:
        raise _error(str(exc)) from None

    return config


def load_active_config(path: str | Path) -> ActiveConfig:
    return parse_active_config(Path(path).read_text(encoding="utf-8"))
