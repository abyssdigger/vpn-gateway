"""Pure Release-1 host-boundary behavior-class projection.

The ordinary host does not need arbitrary Profile identity.  For remote-initiated
traffic it needs only the two already-normalized host-side behavior bits:
stateful return steering and ordinary-side gateway NAT.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .domain import Direction


class HostBoundaryBehaviorLane(str, Enum):
    STATEFUL_NO_NAT = "stateful_no_nat"
    STATEFUL_NAT = "stateful_nat"
    ROUTE_NO_NAT = "route_no_nat"
    ROUTE_NAT = "route_nat"

    @property
    def stateful_return(self) -> bool:
        return self in {
            HostBoundaryBehaviorLane.STATEFUL_NO_NAT,
            HostBoundaryBehaviorLane.STATEFUL_NAT,
        }

    @property
    def gateway_nat(self) -> bool:
        return self in {
            HostBoundaryBehaviorLane.STATEFUL_NAT,
            HostBoundaryBehaviorLane.ROUTE_NAT,
        }


@dataclass(frozen=True, slots=True)
class HostBoundaryBehaviorIntent:
    profile_id: str
    lane: HostBoundaryBehaviorLane

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise ValueError("profile_id must be non-empty text")
        if not isinstance(self.lane, HostBoundaryBehaviorLane):
            raise ValueError("lane must be HostBoundaryBehaviorLane")


@dataclass(frozen=True, slots=True)
class HostBoundaryBehaviorProfile:
    profile_id: str
    direction: Direction
    route_return: bool
    gateway_nat: bool

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise ValueError("profile_id must be non-empty text")
        if not isinstance(self.direction, Direction):
            raise ValueError("direction must be Direction")
        if type(self.route_return) is not bool:
            raise ValueError("route_return must be bool")
        if type(self.gateway_nat) is not bool:
            raise ValueError("gateway_nat must be bool")
        if self.direction is Direction.OUTBOUND and (
            self.route_return or self.gateway_nat
        ):
            raise ValueError(
                "outbound-only Profile cannot request remote-initiated host behavior"
            )


def classify_host_boundary_behavior(
    *,
    route_return: bool,
    gateway_nat: bool,
) -> HostBoundaryBehaviorLane:
    if type(route_return) is not bool or type(gateway_nat) is not bool:
        raise ValueError("route_return and gateway_nat must be bool")
    if route_return:
        return (
            HostBoundaryBehaviorLane.ROUTE_NAT
            if gateway_nat
            else HostBoundaryBehaviorLane.ROUTE_NO_NAT
        )
    return (
        HostBoundaryBehaviorLane.STATEFUL_NAT
        if gateway_nat
        else HostBoundaryBehaviorLane.STATEFUL_NO_NAT
    )


def build_host_boundary_behavior_intents(
    profiles: Iterable[HostBoundaryBehaviorProfile],
) -> tuple[HostBoundaryBehaviorIntent, ...]:
    current = tuple(profiles)
    if any(not isinstance(item, HostBoundaryBehaviorProfile) for item in current):
        raise ValueError("profiles must contain HostBoundaryBehaviorProfile values")
    ids = [item.profile_id for item in current]
    if len(set(ids)) != len(ids):
        raise ValueError("profile_ids must be unique")

    result = []
    for profile in sorted(current, key=lambda item: item.profile_id):
        if profile.direction not in {Direction.INBOUND, Direction.BIDIRECTIONAL}:
            continue
        result.append(
            HostBoundaryBehaviorIntent(
                profile_id=profile.profile_id,
                lane=classify_host_boundary_behavior(
                    route_return=profile.route_return,
                    gateway_nat=profile.gateway_nat,
                ),
            )
        )
    return tuple(result)
