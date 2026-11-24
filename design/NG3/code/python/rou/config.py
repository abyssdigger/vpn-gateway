from __future__ import annotations

import ipaddress
import re
from typing import Any

from .domain import (
    DeviceStructuralIntent,
    Direction,
    ExpectedInterfaceSelector,
    ProfileStructuralIntent,
    SelectorKind,
    StructuralConfig,
)


class ConfigError(ValueError):
    pass


_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PREFIX_RE = re.compile(r"^(.+)\*/([1-9][0-9]*)$")
_TOP_LEVEL_KEYS = frozenset({"device", "profile"})
_DEVICE_STRUCTURAL_KEYS = frozenset({"enabled", "expected_interfaces"})
_PROFILE_STRUCTURAL_KEYS = frozenset(
    {"enabled", "direction", "destinations", "device_order"}
)


def _parse_structural_root(
    raw: dict[str, Any],
    *,
    top_level_keys: frozenset[str],
    device_keys: frozenset[str],
    profile_keys: frozenset[str],
) -> StructuralConfig:
    """Normalize the structural slice from an already parsed TOML document.

    Bounded higher-level configuration adapters may use this helper only after
    they validate every additional field they add to device_keys/profile_keys.
    """
    _reject_unknown_keys(raw, top_level_keys, "top level")
    raw_devices = _mapping(raw.get("device", {}), "device")
    raw_profiles = _mapping(raw.get("profile", {}), "profile")

    devices = {
        device_id: _parse_device(device_id, body, device_keys)
        for device_id, body in raw_devices.items()
    }
    profiles = {
        profile_id: _parse_profile(profile_id, body, profile_keys)
        for profile_id, body in raw_profiles.items()
    }

    _validate_profile_references(devices, profiles)
    active_device_ids = _active_device_ids(devices, profiles)
    _validate_active_selector_overlap(devices, active_device_ids)
    _validate_destination_ownership(profiles)
    _validate_first_release_inbound_capacity(devices, profiles)

    return StructuralConfig.build(
        devices=devices,
        profiles=profiles,
        active_device_ids=active_device_ids,
    )


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{where} must be a TOML table")
    return value


def _reject_unknown_keys(
    body: dict[str, Any],
    allowed: frozenset[str],
    where: str,
) -> None:
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise ConfigError(
            f"{where} has unsupported field(s): {', '.join(unknown)}"
        )


def _validate_id(value: str, kind: str) -> None:
    if not _ID_RE.fullmatch(value):
        raise ConfigError(
            f"invalid {kind} id {value!r}; expected [a-z0-9][a-z0-9-]*"
        )


def _enabled(body: dict[str, Any], where: str) -> bool:
    if "enabled" not in body:
        raise ConfigError(f"{where}.enabled is required")
    value = body["enabled"]
    if type(value) is not bool:
        raise ConfigError(f"{where}.enabled must be boolean")
    return value


def _parse_device(
    device_id: str,
    raw: Any,
    allowed_keys: frozenset[str] = _DEVICE_STRUCTURAL_KEYS,
) -> DeviceStructuralIntent:
    _validate_id(device_id, "Device")
    where = f"device.{device_id}"
    body = _mapping(raw, where)
    enabled = _enabled(body, where)
    if not enabled:
        return DeviceStructuralIntent(device_id=device_id, enabled=False)

    _reject_unknown_keys(body, allowed_keys, where)
    values = body.get("expected_interfaces")
    if not isinstance(values, list) or not values:
        raise ConfigError(
            f"{where}.expected_interfaces must be a non-empty array"
        )

    expected = tuple(
        _parse_selector(
            value,
            f"{where}.expected_interfaces[{index}]",
        )
        for index, value in enumerate(values)
    )
    _validate_selector_overlap(expected, where)

    return DeviceStructuralIntent(
        device_id=device_id,
        enabled=True,
        expected_interfaces=expected,
    )


def _parse_profile(
    profile_id: str,
    raw: Any,
    allowed_keys: frozenset[str] = _PROFILE_STRUCTURAL_KEYS,
) -> ProfileStructuralIntent:
    _validate_id(profile_id, "Profile")
    where = f"profile.{profile_id}"
    body = _mapping(raw, where)
    enabled = _enabled(body, where)
    if not enabled:
        return ProfileStructuralIntent(profile_id=profile_id, enabled=False)

    _reject_unknown_keys(body, allowed_keys, where)

    try:
        direction = Direction(body.get("direction"))
    except (TypeError, ValueError):
        raise ConfigError(
            f"{where}.direction must be outbound, inbound or bidirectional"
        ) from None

    raw_destinations = body.get("destinations")
    if not isinstance(raw_destinations, list) or not raw_destinations:
        raise ConfigError(f"{where}.destinations must be a non-empty array")
    parsed_destinations = tuple(
        _strict_ipv4_network(
            value,
            f"{where}.destinations[{index}]",
        )
        for index, value in enumerate(raw_destinations)
    )
    if len(set(parsed_destinations)) != len(parsed_destinations):
        raise ConfigError(f"{where}.destinations contains duplicates")
    destinations = tuple(
        sorted(
            parsed_destinations,
            key=lambda network: (
                int(network.network_address),
                network.prefixlen,
            ),
        )
    )

    order = body.get("device_order")
    if not isinstance(order, list) or not order:
        raise ConfigError(f"{where}.device_order must be a non-empty array")
    if any(not isinstance(value, str) for value in order):
        raise ConfigError(f"{where}.device_order entries must be strings")
    if len(set(order)) != len(order):
        raise ConfigError(f"{where}.device_order contains duplicates")

    return ProfileStructuralIntent(
        profile_id=profile_id,
        enabled=True,
        direction=direction,
        destinations=destinations,
        device_order=tuple(order),
    )


def _parse_selector(
    value: Any,
    where: str,
) -> ExpectedInterfaceSelector:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{where} must be a non-empty string")

    match = _PREFIX_RE.fullmatch(value)
    if match:
        prefix, quota_text = match.groups()
        _validate_selector_fragment(prefix, where)
        return ExpectedInterfaceSelector(
            kind=SelectorKind.PREFIX,
            value=prefix,
            quota=int(quota_text),
        )

    if "*" in value or "/" in value:
        raise ConfigError(
            f"{where} must be <ifname> or <prefix>*/<positive-quota>"
        )

    _validate_selector_fragment(value, where)
    return ExpectedInterfaceSelector(
        kind=SelectorKind.EXACT,
        value=value,
        quota=1,
    )


def _validate_selector_fragment(value: str, where: str) -> None:
    if not value:
        raise ConfigError(
            f"{where} interface name/prefix must not be empty"
        )
    if len(value.encode("utf-8")) > 15:
        raise ConfigError(
            f"{where} interface name/prefix exceeds Linux IFNAMSIZ-1"
        )
    if "*" in value or "/" in value:
        raise ConfigError(
            f"{where} contains selector syntax in the name/prefix"
        )


def _strict_ipv4_network(
    value: Any,
    where: str,
) -> ipaddress.IPv4Network:
    if not isinstance(value, str):
        raise ConfigError(f"{where} must be a string")
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError as exc:
        raise ConfigError(
            f"{where} is not a strict IPv4 CIDR: {exc}"
        ) from None
    if not isinstance(network, ipaddress.IPv4Network):
        raise ConfigError(f"{where} must be IPv4")
    return network


def _validate_selector_overlap(
    expected: tuple[ExpectedInterfaceSelector, ...],
    where: str,
) -> None:
    for left_index, left in enumerate(expected):
        for right_index in range(left_index + 1, len(expected)):
            right = expected[right_index]
            if left.overlaps(right):
                raise ConfigError(
                    f"{where}.expected_interfaces[{left_index}] overlaps "
                    f"expected_interfaces[{right_index}]"
                )


def _validate_profile_references(
    devices: dict[str, DeviceStructuralIntent],
    profiles: dict[str, ProfileStructuralIntent],
) -> None:
    for profile in profiles.values():
        if not profile.enabled:
            continue
        for device_id in profile.device_order:
            if device_id not in devices:
                raise ConfigError(
                    f"profile.{profile.profile_id}.device_order references "
                    f"unknown Device {device_id!r}"
                )


def _active_device_ids(
    devices: dict[str, DeviceStructuralIntent],
    profiles: dict[str, ProfileStructuralIntent],
) -> frozenset[str]:
    referenced = {
        device_id
        for profile in profiles.values()
        if profile.enabled
        for device_id in profile.device_order
    }
    return frozenset(
        device_id
        for device_id in referenced
        if devices[device_id].enabled
    )


def _validate_active_selector_overlap(
    devices: dict[str, DeviceStructuralIntent],
    active_device_ids: frozenset[str],
) -> None:
    flattened: list[
        tuple[str, int, ExpectedInterfaceSelector]
    ] = []
    for device_id in sorted(active_device_ids):
        for index, selector in enumerate(
            devices[device_id].expected_interfaces
        ):
            flattened.append((device_id, index, selector))

    for left_index, (left_device, left_slot, left) in enumerate(flattened):
        for right_device, right_slot, right in flattened[left_index + 1 :]:
            if left_device == right_device:
                continue
            if left.overlaps(right):
                raise ConfigError(
                    "active ExpectedInterface selectors overlap: "
                    f"device.{left_device}[{left_slot}] and "
                    f"device.{right_device}[{right_slot}]"
                )


def _validate_destination_ownership(
    profiles: dict[str, ProfileStructuralIntent],
) -> None:
    owners: dict[ipaddress.IPv4Network, str] = {}
    for profile in profiles.values():
        if not profile.enabled:
            continue
        for network in profile.destinations:
            previous = owners.get(network)
            if previous is not None:
                raise ConfigError(
                    f"destination {network} is duplicated by enabled Profiles "
                    f"{previous!r} and {profile.profile_id!r}"
                )
            owners[network] = profile.profile_id


def _validate_first_release_inbound_capacity(
    devices: dict[str, DeviceStructuralIntent],
    profiles: dict[str, ProfileStructuralIntent],
) -> None:
    for profile in profiles.values():
        if (
            not profile.enabled
            or profile.direction is Direction.OUTBOUND
        ):
            continue

        capacity = sum(
            devices[device_id].path_capacity
            for device_id in profile.device_order
            if devices[device_id].enabled
        )
        if capacity > 1:
            raise ConfigError(
                f"profile.{profile.profile_id} "
                f"direction={profile.direction.value!r} "
                "is unsupported in Release 1 when configured maximum "
                f"eligible logical-path capacity is {capacity}; expected <= 1"
            )
