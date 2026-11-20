"""Pure authoritative host managed-destination routing projection.

This module currently backs the alpha prototype of the postponed aggressive host-routing
helper child VPNG0001-R2.R3.R1. It is not the selected lowering for the simple Release-1
lifecycle helper VPNG0001-R2.R2.

The ordinary host needs only one routing fact: which IPv4 destinations belong to the
managed VPN-GATE domain.  Profile permission and established-flow affinity remain inside
the managed domain.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Iterable

from .domain import Direction


@dataclass(frozen=True, slots=True)
class HostManagedRoutingProfile:
    profile_id: str
    direction: Direction
    destinations: tuple[IPv4Network, ...]
    effective_snat_address: IPv4Address | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise ValueError("profile_id must be non-empty text")
        if not isinstance(self.direction, Direction):
            raise ValueError("direction must be Direction")
        if not self.destinations:
            raise ValueError("destinations must be non-empty")
        if any(not isinstance(item, IPv4Network) for item in self.destinations):
            raise ValueError("destinations must contain IPv4Network values")
        if len(set(self.destinations)) != len(self.destinations):
            raise ValueError("destinations must not contain exact duplicates")
        if self.effective_snat_address is not None and not isinstance(
            self.effective_snat_address, IPv4Address
        ):
            raise ValueError("effective_snat_address must be IPv4Address or None")


@dataclass(frozen=True, slots=True)
class HostManagedRouteIntent:
    destination: IPv4Network
    profile_ids: tuple[str, ...]
    via_stack_service: bool = False


@dataclass(frozen=True, slots=True)
class HostManagedRoutingPlan:
    routes: tuple[HostManagedRouteIntent, ...]
    full_tunnel: bool


def build_host_managed_routing_plan(
    profiles: Iterable[HostManagedRoutingProfile],
) -> HostManagedRoutingPlan:
    """Project enabled Profile destinations and SNAT identities into host routes.

    Direction does not change route presence.  An inbound-only remote destination still
    needs a host route for legitimate replies; an unauthorized ordinary-originated NEW
    packet that reaches STACK is rejected by managed policy rather than by host routing.
    """
    items = tuple(profiles)
    if any(not isinstance(item, HostManagedRoutingProfile) for item in items):
        raise ValueError("profiles must contain HostManagedRoutingProfile values")
    ids = [item.profile_id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError("profile_ids must be unique")

    owners: dict[IPv4Network, set[str]] = {}
    snat_identities: set[IPv4Network] = set()
    for profile in items:
        for destination in profile.destinations:
            owners.setdefault(destination, set()).add(profile.profile_id)
        if profile.effective_snat_address is not None:
            identity = IPv4Network(f"{profile.effective_snat_address}/32")
            owners.setdefault(identity, set()).add(profile.profile_id)
            snat_identities.add(identity)

    routes = tuple(
        HostManagedRouteIntent(
            destination=destination,
            profile_ids=tuple(sorted(profile_ids)),
            via_stack_service=destination in snat_identities,
        )
        for destination, profile_ids in sorted(
            owners.items(),
            key=lambda item: (
                -item[0].prefixlen,
                int(item[0].network_address),
            ),
        )
    )
    return HostManagedRoutingPlan(
        routes=routes,
        full_tunnel=IPv4Network("0.0.0.0/0") in owners,
    )
