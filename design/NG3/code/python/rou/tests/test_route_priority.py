from __future__ import annotations

import unittest

from rou.binding import LogicalPathId
from rou.route_priority import RoutePriorityPlanError, plan_route_priority_moves


A = LogicalPathId("oc", 0, 0)
B = LogicalPathId("oc", 0, 1)
C = LogicalPathId("oc", 0, 2)


def apply(current, moves):
    state = dict(current)
    for move in moves:
        assert state[move.path_id] == move.from_metric
        assert move.to_metric not in state.values()
        state[move.path_id] = move.to_metric
    return state


class RoutePriorityPlannerTests(unittest.TestCase):
    def test_direct_move_into_free_desired_metric(self):
        current = {A: 10, B: 20}
        desired = {A: 30, B: 20}
        moves = plan_route_priority_moves(current, desired, (10, 20, 30))
        self.assertEqual([(m.path_id, m.from_metric, m.to_metric) for m in moves], [(A, 10, 30)])
        self.assertEqual(apply(current, moves), desired)

    def test_swap_uses_next_unused_scratch_metric(self):
        current = {A: 10, B: 20}
        desired = {A: 20, B: 10}
        moves = plan_route_priority_moves(current, desired, (10, 20, 30))
        self.assertEqual(
            [(m.path_id, m.from_metric, m.to_metric) for m in moves],
            [(A, 10, 30), (B, 20, 10), (A, 30, 20)],
        )
        self.assertEqual(apply(current, moves), desired)

    def test_three_path_cycle_reaches_desired_assignment(self):
        current = {A: 10, B: 20, C: 30}
        desired = {A: 20, B: 30, C: 10}
        moves = plan_route_priority_moves(current, desired, (10, 20, 30, 40))
        self.assertEqual(apply(current, moves), desired)
        self.assertTrue(all(m.to_metric != m.from_metric for m in moves))

    def test_noop_is_empty_plan(self):
        current = {A: 10, B: 20}
        self.assertEqual(plan_route_priority_moves(current, current, (10, 20, 30)), ())

    def test_membership_change_is_rejected(self):
        with self.assertRaisesRegex(RoutePriorityPlanError, "identical"):
            plan_route_priority_moves({A: 10}, {A: 10, B: 20}, (10, 20, 30))

    def test_duplicate_assignment_metric_is_rejected(self):
        with self.assertRaisesRegex(RoutePriorityPlanError, "duplicate metrics"):
            plan_route_priority_moves({A: 10, B: 10}, {A: 10, B: 20}, (10, 20, 30))
        with self.assertRaisesRegex(RoutePriorityPlanError, "duplicate metrics"):
            plan_route_priority_moves({A: 10, B: 20}, {A: 10, B: 10}, (10, 20, 30))

    def test_metric_outside_owned_set_is_rejected(self):
        with self.assertRaisesRegex(RoutePriorityPlanError, "outside owned"):
            plan_route_priority_moves({A: 10}, {A: 20}, (10,))

    def test_cycle_without_free_metric_is_rejected(self):
        with self.assertRaisesRegex(RoutePriorityPlanError, "free owned metric"):
            plan_route_priority_moves(
                {A: 10, B: 20},
                {A: 20, B: 10},
                (10, 20),
            )

    def test_plan_is_deterministic(self):
        current = {A: 10, B: 20, C: 30}
        desired = {A: 30, B: 10, C: 20}
        one = plan_route_priority_moves(current, desired, (10, 20, 30, 40, 50))
        two = plan_route_priority_moves(current, desired, (50, 40, 30, 20, 10))
        self.assertEqual(one, two)


if __name__ == "__main__":
    unittest.main()
