from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .domain import ActiveConfig


@dataclass(frozen=True)
class DispatchEntry:
    destination: IPv4Network
    profile_name: str


def compile_profile_dispatch(config: ActiveConfig) -> tuple[DispatchEntry, ...]:
    """Return host0 Profile dispatch in normative longest-prefix-first order."""

    entries = [
        DispatchEntry(destination, profile.name)
        for profile in config.profiles.values()
        if profile.enabled
        for destination in profile.destinations
    ]

    return tuple(
        sorted(
            entries,
            key=lambda item: (
                -item.destination.prefixlen,
                int(item.destination.network_address),
            ),
        )
    )
