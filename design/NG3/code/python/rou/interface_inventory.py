from __future__ import annotations

import json

from .interface_identity import InterfaceIdentity


class InterfaceInventoryError(ValueError):
    pass


def parse_ip_link_inventory(text: str) -> tuple[InterfaceIdentity, ...]:
    """Parse one full ordered `ip -j link show` snapshot."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InterfaceInventoryError(f"invalid ip-link JSON: {exc}") from None
    if not isinstance(raw, list):
        raise InterfaceInventoryError("ip-link JSON root must be an array")

    out: list[InterfaceIdentity] = []
    seen_names: set[str] = set()
    seen_indexes: set[int] = set()

    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            raise InterfaceInventoryError(f"interface[{position}] must be an object")

        ifname = item.get("ifname")
        ifindex = item.get("ifindex")

        if not isinstance(ifname, str) or not ifname:
            raise InterfaceInventoryError(
                f"interface[{position}].ifname must be a non-empty string"
            )
        if len(ifname.encode("utf-8")) > 15:
            raise InterfaceInventoryError(
                f"interface[{position}].ifname exceeds Linux IFNAMSIZ-1"
            )
        if type(ifindex) is not int or ifindex <= 0:
            raise InterfaceInventoryError(
                f"interface[{position}].ifindex must be a positive integer"
            )
        if ifname in seen_names:
            raise InterfaceInventoryError(
                f"duplicate interface name {ifname!r} in one snapshot"
            )
        if ifindex in seen_indexes:
            raise InterfaceInventoryError(
                f"duplicate ifindex {ifindex} in one snapshot"
            )

        seen_names.add(ifname)
        seen_indexes.add(ifindex)
        out.append(InterfaceIdentity(ifname=ifname, ifindex=ifindex))

    return tuple(out)
