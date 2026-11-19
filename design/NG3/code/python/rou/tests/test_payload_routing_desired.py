from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.direct_device_route import realize_direct_device_path_routes
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.host_boundary_behavior import (
    HostBoundaryBehaviorIntent,
    HostBoundaryBehaviorLane,
)
from rou.host_boundary_lane_routing import (
    HostBoundaryLaneEndpoint,
    build_host_boundary_lane_routes,
)
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.network_policy_layout import (
    NetworkPolicyLayout,
    PayloadDispatchRule,
    allocate_network_policy_layout,
)
from rou.payload_profile import PayloadProfileRequest
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.payload_routing_desired import (
    ManagedRouteRole,
    ManagedRouteType,
    PayloadRoutingProjectionError,
    build_payload_routing_desired_state,
)
from rou.binding import PathBinding


A = LogicalPathId("a", 0, 0)
B = LogicalPathId("b", 0, 0)
EP_A = InterfaceIdentity("patha", 10)
EP_B = InterfaceIdentity("pathb", 20)
HOST = InterfaceIdentity("host0", 5)


def profile(profile_id, destinations, paths):
    return PayloadProfileRequest(
        profile_id=profile_id,
        direction=Direction.OUTBOUND,
        destinations=tuple(IPv4Network(value) for value in destinations),
        ordered_paths=tuple(paths),
    )


def build(profiles, path_routes):
    layout = allocate_network_policy_layout(
        profiles,
        (),
        NG3_LINUX_POLICY_PLATFORM,
    )
    return build_payload_routing_desired_state(
        profiles,
        layout,
        path_routes,
        HOST,
    )


class PayloadRoutingDesiredStateTests(unittest.TestCase):
    def test_complete_profile_state_contains_guard_paths_and_dispatch(self):
        corp = profile(
            "corp",
            ("10.0.0.0/8", "10.1.0.0/16"),
            (A, B),
        )
        routes = realize_direct_device_path_routes(
            (
                PathBinding(A, EP_A),
                PathBinding(B, EP_B),
            )
        )
        desired = build((corp,), routes)

        guards = [
            route
            for route in desired.routes
            if route.route_type is ManagedRouteType.BLACKHOLE
        ]
        unicast = [
            route
            for route in desired.routes
            if route.route_type is ManagedRouteType.UNICAST
        ]

        self.assertEqual(len(guards), 1)
        self.assertEqual(guards[0].destination, IPv4Network("0.0.0.0/0"))
        self.assertEqual(guards[0].protocol, 201)
        self.assertEqual(guards[0].metric, 0xFFFFFFFF)
        self.assertEqual(len(unicast), 4)

        by_destination = {}
        for route in unicast:
            by_destination.setdefault(route.destination, []).append(route)
        self.assertEqual(
            [route.metric for route in by_destination[IPv4Network("10.0.0.0/8")]],
            [1, 2],
        )
        self.assertEqual(
            {route.endpoint for route in unicast},
            {EP_A, EP_B},
        )

        self.assertEqual(
            [
                (str(rule.destination), rule.priority, rule.ingress)
                for rule in desired.rules
            ],
            [
                ("10.1.0.0/16", 0x4000, HOST),
                ("10.0.0.0/8", 0x4001, HOST),
            ],
        )

    def test_zero_path_profile_keeps_guard_and_dispatch_only(self):
        empty = profile("empty", ("203.0.113.0/24",), ())
        desired = build((empty,), ())

        self.assertEqual(len(desired.routes), 1)
        self.assertEqual(
            desired.routes[0].route_type,
            ManagedRouteType.BLACKHOLE,
        )
        self.assertEqual(len(desired.rules), 1)
        self.assertEqual(
            desired.rules[0].destination,
            IPv4Network("203.0.113.0/24"),
        )

    def test_default_profile_has_unicast_default_better_than_guard(self):
        default = profile("default", ("0.0.0.0/0",), (A,))
        routes = realize_direct_device_path_routes((PathBinding(A, EP_A),))
        desired = build((default,), routes)

        defaults = [
            route
            for route in desired.routes
            if route.destination == IPv4Network("0.0.0.0/0")
        ]
        self.assertEqual(len(defaults), 2)
        normal = next(
            route for route in defaults
            if route.route_type is ManagedRouteType.UNICAST
        )
        guard = next(
            route for route in defaults
            if route.route_type is ManagedRouteType.BLACKHOLE
        )
        self.assertLess(normal.metric, guard.metric)


    def test_host_boundary_lane_default_is_explicit_non_path_route_role(self):
        inbound = PayloadProfileRequest(
            profile_id="corp",
            direction=Direction.INBOUND,
            destinations=(IPv4Network("10.0.0.0/8"),),
            ordered_paths=(A,),
        )
        layout = allocate_network_policy_layout(
            (inbound,),
            (),
            NG3_LINUX_POLICY_PLATFORM,
        )
        path_routes = realize_direct_device_path_routes(
            (PathBinding(A, EP_A),)
        )
        lane_endpoint = InterfaceIdentity("lane-nat", 30)
        lane_routes = build_host_boundary_lane_routes(
            (
                HostBoundaryBehaviorIntent(
                    "corp",
                    HostBoundaryBehaviorLane.STATEFUL_NAT,
                ),
            ),
            (
                HostBoundaryLaneEndpoint(
                    HostBoundaryBehaviorLane.STATEFUL_NAT,
                    lane_endpoint,
                    IPv4Address("198.18.64.5"),
                ),
            ),
            layout,
        )
        desired = build_payload_routing_desired_state(
            (inbound,),
            layout,
            path_routes,
            HOST,
            lane_routes,
        )

        lane = next(
            route
            for route in desired.routes
            if route.role is ManagedRouteRole.HOST_BOUNDARY_LANE
        )
        self.assertEqual(lane.destination, IPv4Network("0.0.0.0/0"))
        self.assertIsNone(lane.path_id)
        self.assertEqual(lane.endpoint, lane_endpoint)
        self.assertEqual(str(lane.gateway), "198.18.64.5")
        self.assertEqual(lane.protocol, 204)
        self.assertLess(lane.metric, 0xFFFFFFFF)

    def test_missing_path_realization_is_rejected(self):
        corp = profile("corp", ("10.0.0.0/8",), (A, B))
        routes = realize_direct_device_path_routes((PathBinding(A, EP_A),))

        with self.assertRaisesRegex(
            PayloadRoutingProjectionError,
            "physical path-route set does not exactly match",
        ):
            build((corp,), routes)

    def test_stale_layout_profile_set_is_rejected(self):
        current = profile("corp", ("10.0.0.0/8",), (A,))
        stale_profile = profile("old", ("192.0.2.0/24",), (A,))
        stale_layout = allocate_network_policy_layout(
            (stale_profile,),
            (),
            NG3_LINUX_POLICY_PLATFORM,
        )
        routes = realize_direct_device_path_routes((PathBinding(A, EP_A),))

        with self.assertRaisesRegex(
            PayloadRoutingProjectionError,
            "Profile set does not match",
        ):
            build_payload_routing_desired_state(
                (current,),
                stale_layout,
                routes,
                HOST,
            )

    def test_stale_dispatch_set_is_rejected(self):
        corp = profile("corp", ("10.0.0.0/8",), (A,))
        layout = allocate_network_policy_layout(
            (corp,),
            (),
            NG3_LINUX_POLICY_PLATFORM,
        )
        bad = NetworkPolicyLayout(
            payload=layout.payload,
            probe=layout.probe,
            dispatch_rules=(
                PayloadDispatchRule(
                    profile_id="corp",
                    destination=IPv4Network("192.0.2.0/24"),
                    priority=0x4000,
                    table=layout.payload[0].table,
                ),
            ),
            nft_family=layout.nft_family,
            nft_table=layout.nft_table,
        )
        routes = realize_direct_device_path_routes((PathBinding(A, EP_A),))

        with self.assertRaisesRegex(
            PayloadRoutingProjectionError,
            "dispatch-rule set",
        ):
            build_payload_routing_desired_state(
                (corp,),
                bad,
                routes,
                HOST,
            )

    def test_extra_stale_path_realization_is_rejected(self):
        corp = profile("corp", ("10.0.0.0/8",), (A,))
        routes = realize_direct_device_path_routes(
            (
                PathBinding(A, EP_A),
                PathBinding(B, EP_B),
            )
        )
        with self.assertRaisesRegex(
            PayloadRoutingProjectionError,
            "exactly match",
        ):
            build((corp,), routes)

    def test_one_endpoint_cannot_realize_two_payload_paths(self):
        corp = profile("corp", ("10.0.0.0/8",), (A, B))
        routes = (
            RoutePriorityPathRoute(A, EP_A),
            RoutePriorityPathRoute(B, EP_A),
        )
        with self.assertRaisesRegex(
            PayloadRoutingProjectionError,
            "multiple logical paths",
        ):
            build((corp,), routes)

    def test_noncanonical_or_duplicate_dispatch_priorities_are_rejected(self):
        corp = profile(
            "corp",
            ("10.0.0.0/8", "10.1.0.0/16"),
            (A,),
        )
        layout = allocate_network_policy_layout(
            (corp,),
            (),
            NG3_LINUX_POLICY_PLATFORM,
        )
        routes = realize_direct_device_path_routes((PathBinding(A, EP_A),))

        reversed_rules = tuple(reversed(layout.dispatch_rules))
        bad_order = NetworkPolicyLayout(
            payload=layout.payload,
            probe=layout.probe,
            dispatch_rules=reversed_rules,
            nft_family=layout.nft_family,
            nft_table=layout.nft_table,
        )
        with self.assertRaisesRegex(
            PayloadRoutingProjectionError,
            "canonical longest-prefix ordering",
        ):
            build_payload_routing_desired_state(
                (corp,), bad_order, routes, HOST
            )

        first, second = layout.dispatch_rules
        duplicate_priority = NetworkPolicyLayout(
            payload=layout.payload,
            probe=layout.probe,
            dispatch_rules=(
                first,
                PayloadDispatchRule(
                    profile_id=second.profile_id,
                    destination=second.destination,
                    priority=first.priority,
                    table=second.table,
                ),
            ),
            nft_family=layout.nft_family,
            nft_table=layout.nft_table,
        )
        with self.assertRaisesRegex(
            PayloadRoutingProjectionError,
            "priorities must be unique",
        ):
            build_payload_routing_desired_state(
                (corp,), duplicate_priority, routes, HOST
            )

    def test_host_boundary_requires_full_interface_identity(self):
        corp = profile("corp", ("10.0.0.0/8",), (A,))
        layout = allocate_network_policy_layout(
            (corp,),
            (),
            NG3_LINUX_POLICY_PLATFORM,
        )
        routes = realize_direct_device_path_routes((PathBinding(A, EP_A),))

        with self.assertRaisesRegex(
            PayloadRoutingProjectionError,
            "host_boundary",
        ):
            build_payload_routing_desired_state(
                (corp,),
                layout,
                routes,
                "host0",  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
