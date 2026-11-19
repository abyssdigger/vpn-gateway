"""Fresh ordinary-host IPv4 local-address facts for stack-private gateway NAT."""

from __future__ import annotations

from ipaddress import IPv4Address
import json
from typing import Protocol, Sequence


class HostLocalIPv4ObservationError(ValueError):
    pass


class HostLocalIPv4Runner(Protocol):
    def run(self, argv: Sequence[str]) -> str: ...


def observe_host_local_ipv4_addresses(
    runner: HostLocalIPv4Runner,
) -> tuple[IPv4Address, ...]:
    """Return exact currently assigned ordinary-host IPv4 local addresses.

    These are read-only exclusion facts for Profile gateway NAT inside STACK.
    No interface/address ownership is acquired here.
    """
    try:
        rows = json.loads(
            runner.run(("ip", "-j", "-4", "addr", "show"))
        )
    except (TypeError, json.JSONDecodeError):
        raise HostLocalIPv4ObservationError(
            "invalid host IPv4 address JSON"
        ) from None
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) for row in rows
    ):
        raise HostLocalIPv4ObservationError(
            "host IPv4 address JSON must be an array of objects"
        )

    result: set[IPv4Address] = set()
    for row in rows:
        info = row.get("addr_info", ())
        if not isinstance(info, list):
            raise HostLocalIPv4ObservationError(
                "host IPv4 addr_info must be an array"
            )
        for item in info:
            if not isinstance(item, dict):
                raise HostLocalIPv4ObservationError(
                    "host IPv4 addr_info entries must be objects"
                )
            if item.get("family") != "inet":
                continue
            local = item.get("local")
            if not isinstance(local, str):
                raise HostLocalIPv4ObservationError(
                    "host IPv4 local address is missing or invalid"
                )
            try:
                result.add(IPv4Address(local))
            except ValueError:
                raise HostLocalIPv4ObservationError(
                    f"invalid host IPv4 local address {local!r}"
                ) from None

    return tuple(sorted(result, key=int))
