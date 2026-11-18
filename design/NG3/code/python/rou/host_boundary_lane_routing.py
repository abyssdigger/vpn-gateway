"""Pure stack-side routing projection for selected host behavior lanes.

This module does not move marks across the host boundary.  It projects the
already-normalized Profile -> behavior-lane mapping into one ordinary-side
default route per current inbound-capable Profile table.  The existing stack
Profile-affinity mark/RPDB association selects that table.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import Iterable

from .host_boundary_behavior import (
    HostBoundaryBehaviorIntent,
    HostBoundaryBehaviorLane,
)
from .interface_identity import InterfaceIdentity
from .network_policy_layout import NetworkPolicyLayout
class HostBoundaryLaneRoutingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HostBoundaryLaneEndpoint:
    lane: HostBoundaryBehaviorLane
    endpoint: InterfaceIdentity
    gateway: IPv4Address

    def __post_init__(self) -> None:
        if not isinstance(self.lane, HostBoundaryBehaviorLane):
            raise HostBoundaryLaneRoutingError(
                "lane must be HostBoundaryBehaviorLane"
            )
        if not isinstance(self.endpoint, InterfaceIdentity):
            raise HostBoundaryLaneRoutingError(
                "endpoint must be InterfaceIdentity"
            )
        if not isinstance(self.gateway, IPv4Address):
            raise HostBoundaryLaneRoutingError("gateway must be IPv4Address")


@dataclass(frozen=True, slots=True)
class HostBoundaryLaneRouteSpec:
    profile_id: str
    table: int
    endpoint: InterfaceIdentity
    gateway: IPv4Address
    protocol: int
    metric: int

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise HostBoundaryLaneRoutingError(
                "profile_id must be non-empty text"
            )
        if type(self.table) is not int or not 1 <= self.table <= 0xFFFFFFFF:
            raise HostBoundaryLaneRoutingError("table must be a positive u32")
        if not isinstance(self.endpoint, InterfaceIdentity):
            raise HostBoundaryLaneRoutingError(
                "endpoint must be InterfaceIdentity"
            )
        if not isinstance(self.gateway, IPv4Address):
            raise HostBoundaryLaneRoutingError("gateway must be IPv4Address")
        if type(self.protocol) is not int or not 1 <= self.protocol <= 255:
            raise HostBoundaryLaneRoutingError(
                "protocol must be an integer in [1, 255]"
            )
        if type(self.metric) is not int or not 0 <= self.metric <= 0xFFFFFFFF:
            raise HostBoundaryLaneRoutingError(
                "metric must be an unsigned 32-bit integer"
            )


def build_host_boundary_lane_routes(
    behavior: Iterable[HostBoundaryBehaviorIntent],
    endpoints: Iterable[HostBoundaryLaneEndpoint],
    layout: NetworkPolicyLayout,
) -> tuple[HostBoundaryLaneRouteSpec, ...]:
    """Project one preferred ordinary-side default into each active Profile table."""
    if not isinstance(layout, NetworkPolicyLayout):
        raise HostBoundaryLaneRoutingError(
            "layout must be NetworkPolicyLayout"
        )

    current_behavior = tuple(behavior)
    if any(
        not isinstance(item, HostBoundaryBehaviorIntent)
        for item in current_behavior
    ):
        raise HostBoundaryLaneRoutingError(
            "behavior must contain HostBoundaryBehaviorIntent values"
        )
    if len({item.profile_id for item in current_behavior}) != len(
        current_behavior
    ):
        raise HostBoundaryLaneRoutingError("duplicate Profile behavior intent")

    endpoint_by_lane: dict[
        HostBoundaryBehaviorLane,
        HostBoundaryLaneEndpoint,
    ] = {}
    seen_endpoints: set[InterfaceIdentity] = set()
    for item in endpoints:
        if not isinstance(item, HostBoundaryLaneEndpoint):
            raise HostBoundaryLaneRoutingError(
                "endpoints must contain HostBoundaryLaneEndpoint values"
            )
        if item.lane in endpoint_by_lane:
            raise HostBoundaryLaneRoutingError(
                f"duplicate endpoint for behavior lane {item.lane.value}"
            )
        if item.endpoint in seen_endpoints:
            raise HostBoundaryLaneRoutingError(
                "one concrete endpoint cannot realize multiple behavior lanes"
            )
        endpoint_by_lane[item.lane] = item
        seen_endpoints.add(item.endpoint)

    table_by_profile = {
        item.profile_id: item
        for item in layout.payload
    }
    routes = []
    for intent in sorted(
        current_behavior,
        key=lambda item: item.profile_id,
    ):
        allocation = table_by_profile.get(intent.profile_id)
        if allocation is None:
            raise HostBoundaryLaneRoutingError(
                f"Profile {intent.profile_id!r} has no payload table allocation"
            )
        lane = endpoint_by_lane.get(intent.lane)
        if lane is None:
            raise HostBoundaryLaneRoutingError(
                f"behavior lane {intent.lane.value!r} has no current endpoint"
            )
        metric_space = allocation.metric_space
        if metric_space is None:
            # No current VPN path can produce remote-initiated traffic for this
            # Profile; keep its ordinary-side lane dormant.
            continue
        metric = metric_space.preference_slots[0]
        routes.append(
            HostBoundaryLaneRouteSpec(
                profile_id=intent.profile_id,
                table=allocation.table,
                endpoint=lane.endpoint,
                gateway=lane.gateway,
                protocol=allocation.path_route_protocol,
                metric=metric,
            )
        )
    return tuple(routes)
