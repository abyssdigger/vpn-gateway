"""Pure NG3 host-boundary routing/return-policy planning.

This module does not mutate Linux state. It projects accepted Profile semantics onto the
minimal host-boundary responsibilities proven/required by EXP-053.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .domain import Direction


@dataclass(frozen=True, slots=True)
class HostBoundaryProfileIntent:
    profile_id: str
    direction: Direction
    destinations: tuple[IPv4Network, ...]
    route_return: bool = False

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
        if self.route_return and self.direction is Direction.OUTBOUND:
            raise ValueError("route_return is invalid for outbound-only Profile")


@dataclass(frozen=True, slots=True)
class HostBootstrapRouteIntent:
    destination: IPv4Network
    profile_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HostReturnClassifierRule:
    remote_prefix: IPv4Network
    profile_id: str
    stateful_return: bool


@dataclass(frozen=True, slots=True)
class HostBoundaryPolicyPlan:
    bootstrap_routes: tuple[HostBootstrapRouteIntent, ...]
    return_classifier: tuple[HostReturnClassifierRule, ...]
    full_tunnel: bool


def build_host_boundary_policy(
    profiles: tuple[HostBoundaryProfileIntent, ...],
) -> HostBoundaryPolicyPlan:
    """Project Profile direction onto narrow ordinary-host boundary policy.

    Bootstrap route is required when ordinary side may initiate, or when an inbound Profile
    explicitly opts out of stateful return steering.

    Return classifier includes every remote-initiated Profile prefix, including route-return
    prefixes. Explicit negative/route verdicts are necessary so a more-specific opt-out cannot
    fall through to a broader stateful Profile prefix.
    """
    if any(not isinstance(profile, HostBoundaryProfileIntent) for profile in profiles):
        raise ValueError("profiles must contain HostBoundaryProfileIntent values")
    ids = [profile.profile_id for profile in profiles]
    if len(set(ids)) != len(ids):
        raise ValueError("profile_ids must be unique")

    route_owners: dict[IPv4Network, set[str]] = {}
    classifier: list[HostReturnClassifierRule] = []
    seen_prefix_owner: dict[IPv4Network, str] = {}

    for profile in profiles:
        requires_bootstrap = (
            profile.direction in {Direction.OUTBOUND, Direction.BIDIRECTIONAL}
            or profile.route_return
        )
        permits_remote_init = profile.direction in {
            Direction.INBOUND,
            Direction.BIDIRECTIONAL,
        }

        for destination in profile.destinations:
            previous = seen_prefix_owner.get(destination)
            if previous is not None and previous != profile.profile_id:
                raise ValueError(
                    f"exact destination {destination} belongs to both "
                    f"{previous!r} and {profile.profile_id!r}"
                )
            seen_prefix_owner[destination] = profile.profile_id

            if requires_bootstrap:
                route_owners.setdefault(destination, set()).add(profile.profile_id)

            if permits_remote_init:
                classifier.append(
                    HostReturnClassifierRule(
                        remote_prefix=destination,
                        profile_id=profile.profile_id,
                        stateful_return=not profile.route_return,
                    )
                )

    bootstrap = tuple(
        HostBootstrapRouteIntent(
            destination=network,
            profile_ids=tuple(sorted(owners)),
        )
        for network, owners in sorted(
            route_owners.items(),
            key=lambda item: (int(item[0].network_address), item[0].prefixlen),
        )
    )
    classifier.sort(
        key=lambda rule: (
            -rule.remote_prefix.prefixlen,
            int(rule.remote_prefix.network_address),
            rule.profile_id,
        )
    )

    return HostBoundaryPolicyPlan(
        bootstrap_routes=bootstrap,
        return_classifier=tuple(classifier),
        full_tunnel=any(
            route.destination == IPv4Network("0.0.0.0/0")
            for route in bootstrap
        ),
    )
