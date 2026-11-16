from __future__ import annotations

from ipaddress import IPv4Address
from typing import Iterable

from .binding import LogicalPathId
from .domain import Direction
from .payload_profile import PayloadProfileRequest


class ProfileClassificationError(ValueError):
    pass


def classify_outbound_profile(
    requests: Iterable[PayloadProfileRequest],
    remote_destination: IPv4Address,
) -> PayloadProfileRequest | None:
    return _most_specific_matching(
        (
            request
            for request in requests
            if request.direction in {Direction.OUTBOUND, Direction.BIDIRECTIONAL}
        ),
        remote_destination,
    )


def classify_inbound_profile(
    requests: Iterable[PayloadProfileRequest],
    ingress_path: LogicalPathId,
    remote_source: IPv4Address,
) -> PayloadProfileRequest | None:
    return _most_specific_matching(
        (
            request
            for request in requests
            if request.direction in {Direction.INBOUND, Direction.BIDIRECTIONAL}
            and ingress_path in request.ordered_paths
        ),
        remote_source,
    )


def _most_specific_matching(
    candidates: Iterable[PayloadProfileRequest],
    remote_address: IPv4Address,
) -> PayloadProfileRequest | None:
    best_request: PayloadProfileRequest | None = None
    best_prefixlen = -1
    for request in candidates:
        matching_prefixlens = [
            network.prefixlen
            for network in request.destinations
            if remote_address in network
        ]
        if not matching_prefixlens:
            continue
        prefixlen = max(matching_prefixlens)
        if prefixlen > best_prefixlen:
            best_request = request
            best_prefixlen = prefixlen
            continue
        if prefixlen == best_prefixlen:
            raise ProfileClassificationError(
                f"ambiguous Profile classification at /{prefixlen}: "
                f"{best_request.profile_id!r} and {request.profile_id!r}"
            )
    return best_request
