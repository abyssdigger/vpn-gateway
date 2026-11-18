from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.host_boundary_behavior import (
    HostBoundaryBehaviorIntent,
    HostBoundaryBehaviorLane,
)
from rou.host_boundary_lane_routing import (
    HostBoundaryLaneEndpoint,
    build_host_boundary_lane_routes,
)
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.network_policy_layout import allocate_network_policy_layout
from rou.payload_profile import PayloadProfileRequest


PATH = LogicalPathId("vpn", 0, 0)


def profile(profile_id: str, *, current: bool) -> PayloadProfileRequest:
    return PayloadProfileRequest(
        profile_id=profile_id,
        direction=Direction.INBOUND,
        destinations=(IPv4Network("10.0.0.0/8"),),
        ordered_paths=(PATH,) if current else (),
    )


class HostBoundaryLaneRoutingTests(unittest.TestCase):
    def test_current_profile_gets_default_via_selected_lane(self):
        p = profile("p", current=True)
        layout = allocate_network_policy_layout(
            (p,), (), NG3_LINUX_POLICY_PLATFORM
        )
        endpoint = InterfaceIdentity("lane1", 41)
        routes = build_host_boundary_lane_routes(
            (
                HostBoundaryBehaviorIntent(
                    "p", HostBoundaryBehaviorLane.STATEFUL_NAT
                ),
            ),
            (
                HostBoundaryLaneEndpoint(
                    HostBoundaryBehaviorLane.STATEFUL_NAT,
                    endpoint,
                    IPv4Address("198.18.64.5"),
                ),
            ),
            layout,
        )
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].profile_id, "p")
        self.assertEqual(routes[0].table, layout.payload[0].table)
        self.assertEqual(routes[0].endpoint, endpoint)
        self.assertEqual(str(routes[0].gateway), "198.18.64.5")

    def test_zero_path_profile_keeps_lane_dormant(self):
        p = profile("p", current=False)
        layout = allocate_network_policy_layout(
            (p,), (), NG3_LINUX_POLICY_PLATFORM
        )
        routes = build_host_boundary_lane_routes(
            (
                HostBoundaryBehaviorIntent(
                    "p", HostBoundaryBehaviorLane.STATEFUL_NO_NAT
                ),
            ),
            (
                HostBoundaryLaneEndpoint(
                    HostBoundaryBehaviorLane.STATEFUL_NO_NAT,
                    InterfaceIdentity("lane0", 40),
                    IPv4Address("198.18.64.1"),
                ),
            ),
            layout,
        )
        self.assertEqual(routes, ())

    def test_missing_selected_lane_is_fail_closed(self):
        p = profile("p", current=True)
        layout = allocate_network_policy_layout(
            (p,), (), NG3_LINUX_POLICY_PLATFORM
        )
        with self.assertRaisesRegex(ValueError, "has no current endpoint"):
            build_host_boundary_lane_routes(
                (
                    HostBoundaryBehaviorIntent(
                        "p", HostBoundaryBehaviorLane.ROUTE_NAT
                    ),
                ),
                (),
                layout,
            )


if __name__ == "__main__":
    unittest.main()
