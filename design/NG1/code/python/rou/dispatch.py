from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

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


def classify_device_to_host_profile(
    config: ActiveConfig,
    device_name: str,
    remote_source: IPv4Address,
) -> str | None:
    """Classify Device->host NEW traffic using filter-first semantics.

    Candidate Profiles are first restricted to enabled Profiles that reference the
    ingress Device. Longest-prefix matching is then performed only inside that filtered
    candidate set.

    This helper is exported for diagnostics/status and policy explanation. Kernel firewall
    materialization uses the equivalent ordered prefix-match rules directly; packets are
    not classified by calling this function at runtime.
    """

    candidates: list[tuple[IPv4Network, str]] = []

    for profile in config.profiles.values():
        if not profile.enabled or device_name not in profile.device_order:
            continue

        for network in profile.destinations:
            if remote_source in network:
                candidates.append((network, profile.name))

    if not candidates:
        return None

    network, profile_name = min(
        candidates,
        key=lambda item: (
            -item[0].prefixlen,
            int(item[0].network_address),
            item[1],
        ),
    )
    return profile_name
