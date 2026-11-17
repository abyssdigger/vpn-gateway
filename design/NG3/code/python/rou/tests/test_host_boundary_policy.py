import unittest
from ipaddress import IPv4Network

from rou.domain import Direction
from rou.host_boundary_policy import (
    HostBoundaryProfileIntent,
    build_host_boundary_policy,
)


class HostBoundaryPolicyTests(unittest.TestCase):
    def p(self, profile_id, direction, destinations, *, route_return=False):
        return HostBoundaryProfileIntent(
            profile_id=profile_id,
            direction=direction,
            destinations=tuple(IPv4Network(x) for x in destinations),
            route_return=route_return,
        )

    def test_direction_matrix(self):
        plan = build_host_boundary_policy(
            (
                self.p("out", Direction.OUTBOUND, ["10.1.0.0/16"]),
                self.p("in", Direction.INBOUND, ["10.2.0.0/16"]),
                self.p(
                    "in-route",
                    Direction.INBOUND,
                    ["10.3.0.0/16"],
                    route_return=True,
                ),
                self.p("both", Direction.BIDIRECTIONAL, ["10.4.0.0/16"]),
            )
        )
        self.assertEqual(
            [str(item.destination) for item in plan.bootstrap_routes],
            ["10.1.0.0/16", "10.3.0.0/16", "10.4.0.0/16"],
        )
        by_profile = {
            item.profile_id: item.stateful_return
            for item in plan.return_classifier
        }
        self.assertEqual(
            by_profile,
            {"in": True, "in-route": False, "both": True},
        )

    def test_more_specific_route_return_blocks_broader_stateful_fallthrough(self):
        plan = build_host_boundary_policy(
            (
                self.p("broad", Direction.INBOUND, ["10.0.0.0/8"]),
                self.p(
                    "specific",
                    Direction.INBOUND,
                    ["10.20.0.0/16"],
                    route_return=True,
                ),
            )
        )
        self.assertEqual(
            [
                (str(item.remote_prefix), item.stateful_return)
                for item in plan.return_classifier
            ],
            [("10.20.0.0/16", False), ("10.0.0.0/8", True)],
        )

    def test_bidirectional_route_return_still_needs_only_one_bootstrap_route(self):
        plan = build_host_boundary_policy(
            (
                self.p(
                    "both",
                    Direction.BIDIRECTIONAL,
                    ["192.0.2.0/24"],
                    route_return=True,
                ),
            )
        )
        self.assertEqual(len(plan.bootstrap_routes), 1)
        self.assertFalse(plan.return_classifier[0].stateful_return)

    def test_full_tunnel_is_explicit_in_plan(self):
        plan = build_host_boundary_policy(
            (
                self.p("full", Direction.OUTBOUND, ["0.0.0.0/0"]),
            )
        )
        self.assertTrue(plan.full_tunnel)
        self.assertEqual(
            str(plan.bootstrap_routes[0].destination),
            "0.0.0.0/0",
        )

    def test_outbound_route_return_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outbound-only"):
            self.p(
                "bad",
                Direction.OUTBOUND,
                ["10.0.0.0/8"],
                route_return=True,
            )


if __name__ == "__main__":
    unittest.main()
