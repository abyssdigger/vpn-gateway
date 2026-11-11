from __future__ import annotations

from dataclasses import dataclass
import json

from .device_engine import EnvironmentInterface, InterfaceIdentity


class EnvironmentParseError(ValueError):
    pass


@dataclass(frozen=True)
class EnvironmentSnapshot:
    interfaces: tuple[EnvironmentInterface, ...]


def parse_ip_link_json(text: str) -> EnvironmentSnapshot:
    """Parse ordered `ip -j link show` output into the interface part of a fresh snapshot."""

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EnvironmentParseError(f"invalid ip-link JSON: {exc}") from None

    if not isinstance(raw, list):
        raise EnvironmentParseError("ip-link JSON root must be an array")

    out: list[EnvironmentInterface] = []
    seen_names: set[str] = set()
    seen_indexes: set[int] = set()

    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            raise EnvironmentParseError(f"interface[{position}] must be an object")

        ifname = item.get("ifname")
        ifindex = item.get("ifindex")

        if not isinstance(ifname, str) or not ifname:
            raise EnvironmentParseError(
                f"interface[{position}].ifname must be a non-empty string"
            )
        if len(ifname.encode("utf-8")) > 15:
            raise EnvironmentParseError(
                f"interface[{position}].ifname exceeds Linux IFNAMSIZ-1"
            )
        if type(ifindex) is not int or ifindex <= 0:
            raise EnvironmentParseError(
                f"interface[{position}].ifindex must be a positive integer"
            )

        if ifname in seen_names:
            raise EnvironmentParseError(
                f"duplicate interface name {ifname!r} in one snapshot"
            )
        if ifindex in seen_indexes:
            raise EnvironmentParseError(
                f"duplicate ifindex {ifindex} in one snapshot"
            )

        seen_names.add(ifname)
        seen_indexes.add(ifindex)
        out.append(EnvironmentInterface(InterfaceIdentity(ifname, ifindex)))

    return EnvironmentSnapshot(tuple(out))
