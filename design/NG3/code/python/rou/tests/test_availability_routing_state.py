from __future__ import annotations

import unittest

from rou.availability_routing_state import (
    AvailabilityRoutingState,
    project_availability_routing,
)
from rou.binding import LogicalPathId


A = LogicalPathId("primary", 0, 0)
B = LogicalPathId("backup", 0, 0)
C = LogicalPathId("other", 0, 0)
OLD = LogicalPathId("gone", 0, 0)


class AvailabilityRoutingStateTests(unittest.TestCase):
    def test_initial_projection_selects_first_usable_baseline_path(self):
        result = project_availability_routing(
            (A, B, C),
            (),
            AvailabilityRoutingState(),
        )
        self.assertEqual(result.effective_order, (A, B, C))
        self.assertEqual(result.next_state.active_path, A)

    def test_failure_moves_active_to_next_usable_path(self):
        result = project_availability_routing(
            (A, B, C),
            (A,),
            AvailabilityRoutingState(A),
        )
        self.assertEqual(result.effective_order, (B, C, A))
        self.assertEqual(result.next_state.active_path, B)

    def test_recovery_keeps_ordinary_active_sticky(self):
        result = project_availability_routing(
            (A, B, C),
            (),
            AvailabilityRoutingState(B),
        )
        self.assertEqual(result.effective_order, (B, A, C))
        self.assertEqual(result.next_state.active_path, B)

    def test_recovery_preempts_reserve_active(self):
        result = project_availability_routing(
            (A, B, C),
            (),
            AvailabilityRoutingState(B),
            reserve_device_ids=("backup",),
        )
        self.assertEqual(result.effective_order, (A, B, C))
        self.assertEqual(result.next_state.active_path, A)

    def test_disappeared_active_is_replaced_without_stale_state_error(self):
        result = project_availability_routing(
            (A, B),
            (),
            AvailabilityRoutingState(OLD),
        )
        self.assertEqual(result.effective_order, (A, B))
        self.assertEqual(result.next_state.active_path, A)

    def test_all_paths_problematic_clear_active_identity(self):
        result = project_availability_routing(
            (A, B),
            (A, B),
            AvailabilityRoutingState(A),
        )
        self.assertEqual(result.effective_order, (A, B))
        self.assertIsNone(result.next_state.active_path)

    def test_empty_membership_clears_stale_active_identity(self):
        result = project_availability_routing(
            (),
            (),
            AvailabilityRoutingState(A),
        )
        self.assertEqual(result.effective_order, ())
        self.assertIsNone(result.next_state.active_path)


if __name__ == "__main__":
    unittest.main()
