"""Pure stack-side routing projection for selected host behavior lanes.

This module does not move marks across the host boundary.  It projects the
already-normalized Profile -> behavior-lane mapping into one ordinary-side
default route per current inbound-capable Profile table.  The existing stack
Profile-affinity mark/RPDB association selects that table.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Iterable

from .host_boundary_behavior import (
    HostBoundaryBehaviorIntent,
    HostBoundaryBehaviorLane,
)
from .interface_identity import InterfaceIdentity
from .network_policy_layout import NetworkPolicyLayout
from .payload_routing_desired import ManagedRouteSpec, ManagedRouteType


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


def build_host_boundary_lane_routes(
    behavior: Iterable[HostBoundaryBehaviorIntent],
    endpoints: Iterable[HostBoundaryLaneEndpoint],
    layout: NetworkPolicyLayout,
) -> tuple[ManagedRouteSpec, ...]:
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
        routes.append(
            ManagedRouteSpec(
                table=allocation.table,
                destination=IPv4Network("0.0.0.0/0"),
                route_type=ManagedRouteType.UNICAST,
                protocol=allocation.path_route_protocol,
                metric=allocation.metric_space.first_preference_metric,
                path_id=None,
                endpoint=lane.endpoint,
                gateway=lane.gateway,
                onlink=False,
            )
        )
    return tuple(routes)
