"""Bulk most-specific Profile classification as disjoint IPv4 CIDR fragments."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network, collapse_addresses
from typing import Iterable

from .binding import LogicalPathId
from .domain import Direction
from .payload_profile import PayloadProfileRequest


class ProfilePrefixPartitionError(ValueError):
    pass


@dataclass(frozen=True, order=True, slots=True)
class ProfilePrefixFragment:
    profile_id: str
    remote_prefix: IPv4Network

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise ProfilePrefixPartitionError(
                "profile_id must be a non-empty string"
            )
        if not isinstance(self.remote_prefix, IPv4Network):
            raise ProfilePrefixPartitionError(
                "remote_prefix must be IPv4Network"
            )


def build_outbound_profile_partition(
    requests: Iterable[PayloadProfileRequest],
) -> tuple[ProfilePrefixFragment, ...]:
    """Partition outbound remote destination space by selected Profile."""
    profiles = _validate_requests(requests)
    candidates = tuple(
        profile
        for profile in profiles
        if profile.direction in {
            Direction.OUTBOUND,
            Direction.BIDIRECTIONAL,
        }
    )
    return _partition(candidates)


def build_inbound_profile_partition(
    requests: Iterable[PayloadProfileRequest],
    ingress_path: LogicalPathId,
) -> tuple[ProfilePrefixFragment, ...]:
    """Partition inbound remote source space after ingress-path restriction."""
    if not isinstance(ingress_path, LogicalPathId):
        raise ProfilePrefixPartitionError(
            "ingress_path must be LogicalPathId"
        )
    profiles = _validate_requests(requests)
    candidates = tuple(
        profile
        for profile in profiles
        if profile.direction in {
            Direction.INBOUND,
            Direction.BIDIRECTIONAL,
        }
        and ingress_path in profile.ordered_paths
    )
    return _partition(candidates)


def _validate_requests(
    requests: Iterable[PayloadProfileRequest],
) -> tuple[PayloadProfileRequest, ...]:
    profiles = tuple(requests)
    seen_ids: set[str] = set()
    for profile in profiles:
        if not isinstance(profile, PayloadProfileRequest):
            raise ProfilePrefixPartitionError(
                "requests must contain PayloadProfileRequest"
            )
        if profile.profile_id in seen_ids:
            raise ProfilePrefixPartitionError(
                f"duplicate Profile request {profile.profile_id!r}"
            )
        seen_ids.add(profile.profile_id)
        if not isinstance(profile.direction, Direction):
            raise ProfilePrefixPartitionError(
                f"Profile {profile.profile_id!r} has invalid direction"
            )

        seen_destinations: set[IPv4Network] = set()
        for network in profile.destinations:
            if not isinstance(network, IPv4Network):
                raise ProfilePrefixPartitionError(
                    f"Profile {profile.profile_id!r} has non-IPv4 destination"
                )
            if network in seen_destinations:
                raise ProfilePrefixPartitionError(
                    f"Profile {profile.profile_id!r} repeats destination {network}"
                )
            seen_destinations.add(network)
    return profiles


def _partition(
    candidates: tuple[PayloadProfileRequest, ...],
) -> tuple[ProfilePrefixFragment, ...]:
    if not candidates:
        return ()

    owners: dict[IPv4Network, str] = {}
    collapsed_by_profile: dict[str, tuple[IPv4Network, ...]] = {}
    for profile in candidates:
        for network in profile.destinations:
            previous = owners.get(network)
            if previous is not None and previous != profile.profile_id:
                raise ProfilePrefixPartitionError(
                    f"exact destination {network} belongs to multiple candidate "
                    f"Profiles: {previous!r}, {profile.profile_id!r}"
                )
            owners[network] = profile.profile_id

        collapsed_by_profile[profile.profile_id] = tuple(
            collapse_addresses(profile.destinations)
        )

    entries = tuple(
        (profile_id, network)
        for profile_id, networks in collapsed_by_profile.items()
        for network in networks
    )

    fragments: list[ProfilePrefixFragment] = []
    for owner, network in entries:
        blockers = sorted(
            (
                other_network
                for other_owner, other_network in entries
                if other_owner != owner
                and other_network.prefixlen > network.prefixlen
                and other_network.subnet_of(network)
            ),
            key=lambda value: (
                value.prefixlen,
                int(value.network_address),
            ),
        )
        remaining = [network]
        for blocker in blockers:
            next_remaining: list[IPv4Network] = []
            for fragment in remaining:
                if not fragment.overlaps(blocker):
                    next_remaining.append(fragment)
                    continue
                if blocker.subnet_of(fragment):
                    next_remaining.extend(fragment.address_exclude(blocker))
                    continue
                if fragment.subnet_of(blocker):
                    continue
                raise ProfilePrefixPartitionError(
                    "unexpected partial IPv4 CIDR overlap"
                )
            remaining = next_remaining

        fragments.extend(
            ProfilePrefixFragment(owner, fragment)
            for fragment in remaining
        )

    collapsed_fragments: list[ProfilePrefixFragment] = []
    for owner in sorted(collapsed_by_profile):
        owner_networks = tuple(
            fragment.remote_prefix
            for fragment in fragments
            if fragment.profile_id == owner
        )
        collapsed_fragments.extend(
            ProfilePrefixFragment(owner, network)
            for network in collapse_addresses(owner_networks)
        )

    _validate_disjoint(collapsed_fragments)
    return tuple(
        sorted(
            collapsed_fragments,
            key=lambda item: (
                int(item.remote_prefix.network_address),
                item.remote_prefix.prefixlen,
                item.profile_id,
            ),
        )
    )


def _validate_disjoint(
    fragments: list[ProfilePrefixFragment],
) -> None:
    for index, left in enumerate(fragments):
        for right in fragments[index + 1 :]:
            if left.remote_prefix.overlaps(right.remote_prefix):
                raise ProfilePrefixPartitionError(
                    "partition produced overlapping Profile fragments: "
                    f"{left!r}, {right!r}"
                )
