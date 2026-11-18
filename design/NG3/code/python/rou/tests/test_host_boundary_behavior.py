from __future__ import annotations

import unittest

from rou.domain import Direction
from rou.host_boundary_behavior import (
    HostBoundaryBehaviorLane,
    HostBoundaryBehaviorProfile,
    build_host_boundary_behavior_intents,
    classify_host_boundary_behavior,
)


class HostBoundaryBehaviorTests(unittest.TestCase):
    def test_all_four_remote_initiated_behavior_classes(self):
        self.assertIs(
            classify_host_boundary_behavior(route_return=False, gateway_nat=False),
            HostBoundaryBehaviorLane.STATEFUL_NO_NAT,
        )
        self.assertIs(
            classify_host_boundary_behavior(route_return=False, gateway_nat=True),
            HostBoundaryBehaviorLane.STATEFUL_NAT,
        )
        self.assertIs(
            classify_host_boundary_behavior(route_return=True, gateway_nat=False),
            HostBoundaryBehaviorLane.ROUTE_NO_NAT,
        )
        self.assertIs(
            classify_host_boundary_behavior(route_return=True, gateway_nat=True),
            HostBoundaryBehaviorLane.ROUTE_NAT,
        )

    def test_projection_is_profile_count_independent_and_deterministic(self):
        profiles = (
            HostBoundaryBehaviorProfile("z", Direction.INBOUND, False, True),
            HostBoundaryBehaviorProfile("a", Direction.BIDIRECTIONAL, True, False),
            HostBoundaryBehaviorProfile("out", Direction.OUTBOUND, False, False),
        )
        result = build_host_boundary_behavior_intents(profiles)
        self.assertEqual(tuple(item.profile_id for item in result), ("a", "z"))
        self.assertEqual(
            tuple(item.lane for item in result),
            (
                HostBoundaryBehaviorLane.ROUTE_NO_NAT,
                HostBoundaryBehaviorLane.STATEFUL_NAT,
            ),
        )

    def test_outbound_only_cannot_request_remote_host_behavior(self):
        with self.assertRaisesRegex(ValueError, "outbound-only"):
            HostBoundaryBehaviorProfile(
                "bad", Direction.OUTBOUND, False, True
            )


if __name__ == "__main__":
    unittest.main()
