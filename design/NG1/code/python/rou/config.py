from __future__ import annotations

import ipaddress
from pathlib import Path
import re
import tomllib
from typing import Any

from .domain import ActiveConfig, Device, Direction, ExpectedInterface, InterfaceMatch, MatchKind, Profile
from .metrics import MetricLayoutError, compile_all_metric_layouts


class ConfigError(ValueError):
    pass


_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PREFIX_RE = re.compile(r"^(.+)\*/([1-9][0-9]*)$")
_TOP_LEVEL_KEYS = frozenset({"device", "profile"})
_ENABLED_DEVICE_KEYS = frozenset({"enabled", "expected_interfaces"})
_ENABLED_PROFILE_KEYS = frozenset({"enabled", "direction", "destinations", "device_order"})


def _error(message: str) -> ConfigError:
    return ConfigError(message)


def _require_mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(f"{where} must be a TOML table")
    return value


def _validate_id(value: str, kind: str) -> None:
    if not _ID_RE.fullmatch(value):
        raise _error(f"invalid {kind} id {value!r}; expected [a-z0-9][a-z0-9-]*")


def _enabled(body: dict[str, Any], where: str) -> bool:
    if "enabled" not in body:
        raise _error(f"{where}.enabled is required")
    value = body["enabled"]
    if type(value) is not bool:
        raise _error(f"{where}.enabled must be boolean")
    return value


def _reject_unknown_keys(body: dict[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise _error(f"{where} has unsupported field(s): {', '.join(unknown)}")


def _validate_if_fragment(value: str, where: str) -> None:
    if not value:
        raise _error(f"{where} interface name/prefix must not be empty")
    if len(value.encode("utf-8")) > 15:
        raise _error(f"{where} interface name/prefix exceeds Linux IFNAMSIZ-1")
    if value in {".", ".."} or any(ch.isspace() or ch in "/:*" for ch in value):
        raise _error(f"{where} contains characters not valid in an interface name/prefix")


def _parse_expected_interface(value: Any, where: str) -> ExpectedInterface:
    if not isinstance(value, str):
        raise _error(f"{where} must be a string")

    m = _PREFIX_RE.fullmatch(value)
    if m:
        prefix, quota_text = m.groups()
        _validate_if_fragment(prefix, where)
        quota = int(quota_text)
        return ExpectedInterface(InterfaceMatch(MatchKind.PREFIX, prefix), quota)

    if "*" in value or "/" in value:
        raise _error(f"{where} must be <ifname> or <prefix>*/<positive-quota>")

    _validate_if_fragment(value, where)
    return ExpectedInterface(InterfaceMatch(MatchKind.EXACT, value), 1)


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
        raise _error(f"{where}.expected_interfaces must be a non-empty array")

    expected = tuple(
        _parse_expected_interface(value, f"{where}.expected_interfaces[{index}]")
        for index, value in enumerate(values)
    )
    _validate_selector_overlap(expected, where)
    return Device(name=name, enabled=True, expected_interfaces=expected)


def _parse_profile(name: str, raw: Any) -> Profile:
    _validate_id(name, "Profile")
    where = f"profile.{name}"
    body = _require_mapping(raw, where)
    enabled = _enabled(body, where)
    if not enabled:
        return Profile(name=name, enabled=False)

    _reject_unknown_keys(body, _ENABLED_PROFILE_KEYS, where)

    raw_direction = body.get("direction")
    try:
        direction = Direction(raw_direction)
    except (TypeError, ValueError):
        allowed = ", ".join(item.value for item in Direction)
        raise _error(f"{where}.direction must be one of: {allowed}") from None

    raw_destinations = body.get("destinations")
    if not isinstance(raw_destinations, list) or not raw_destinations:
        raise _error(f"{where}.destinations must be a non-empty array")
    destinations = []
    seen_destinations = set()
    for index, value in enumerate(raw_destinations):
        if not isinstance(value, str):
            raise _error(f"{where}.destinations[{index}] must be a string")
        try:
            network = ipaddress.ip_network(value, strict=True)
        except ValueError as exc:
            raise _error(f"{where}.destinations[{index}] is not a strict IPv4 CIDR: {exc}") from None
        if not isinstance(network, ipaddress.IPv4Network):
            raise _error(f"{where}.destinations[{index}] must be IPv4")
        if network in seen_destinations:
            raise _error(f"{where}.destinations contains duplicate {network}")
        seen_destinations.add(network)
        destinations.append(network)

    raw_order = body.get("device_order")
    if not isinstance(raw_order, list) or not raw_order:
        raise _error(f"{where}.device_order must be a non-empty array")
    order = []
    seen_names = set()
    for index, value in enumerate(raw_order):
        if not isinstance(value, str):
            raise _error(f"{where}.device_order[{index}] must be a Device id string")
        _validate_id(value, "Device reference")
        if value in seen_names:
            raise _error(f"{where}.device_order contains duplicate Device id {value!r}")
        seen_names.add(value)
        order.append(value)

    return Profile(
        name=name,
        enabled=True,
        direction=direction,
        destinations=tuple(destinations),
        device_order=tuple(order),
    )


def _validate_selector_overlap(expected: tuple[ExpectedInterface, ...], where: str) -> None:
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
                raise _error(f"profile.{profile.name}.device_order references unknown Device {name!r}")


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
                    f"device.{left_device}[{left_slot}] and device.{right_device}[{right_slot}]"
                )


def parse_active_config(text: str) -> ActiveConfig:
    try:
        root = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise _error(f"invalid TOML: {exc}") from None

    unknown_top = sorted(set(root) - _TOP_LEVEL_KEYS)
    if unknown_top:
        raise _error(f"unsupported top-level field(s): {', '.join(unknown_top)}")

    raw_devices = _require_mapping(root.get("device", {}), "device")
    raw_profiles = _require_mapping(root.get("profile", {}), "profile")

    devices = {name: _parse_device(name, raw) for name, raw in raw_devices.items()}
    profiles = {name: _parse_profile(name, raw) for name, raw in raw_profiles.items()}
    config = ActiveConfig(devices=devices, profiles=profiles)

    _validate_references(config)
    _validate_global_destinations(config)
    _validate_active_selector_overlap(config)
    try:
        compile_all_metric_layouts(config)
    except MetricLayoutError as exc:
        raise _error(str(exc)) from None
    return config


def load_active_config(path: str | Path) -> ActiveConfig:
    return parse_active_config(Path(path).read_text(encoding="utf-8"))
