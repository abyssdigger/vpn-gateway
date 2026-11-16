from __future__ import annotations

import unittest

from rou.binding import LogicalPathId
from rou.route_priority import RoutePriorityMove
from rou.route_priority_convergence import (
    RoutePriorityConvergenceError,
    RoutePriorityDeleteDuplicate,
    plan_route_priority_convergence,
)


A = LogicalPathId("oc", 0, 0)
B = LogicalPathId("oc", 0, 1)
C = LogicalPathId("wg", 0, 0)


def apply(observed, steps):
    state = {path_id: set(metrics) for path_id, metrics in observed.items()}

    for step in steps:
        if isinstance(step, RoutePriorityDeleteDuplicate):
            assert step.metric in state[step.path_id]
            assert len(state[step.path_id]) > 1
            state[step.path_id].remove(step.metric)
        else:
            assert isinstance(step, RoutePriorityMove)
            assert state[step.path_id] == {step.from_metric}
            occupied = {
                metric
                for path_metrics in state.values()
                for metric in path_metrics
            }
            assert step.to_metric not in occupied

            # A semantic Move models add-new -> verify -> delete-old. Both
            # copies exist transiently; the eligible path is never absent.
            state[step.path_id].add(step.to_metric)
            assert state[step.path_id]
            state[step.path_id].remove(step.from_metric)

        assert all(path_metrics for path_metrics in state.values())

    return state


class RoutePriorityConvergenceTests(unittest.TestCase):
    def test_clean_swap_reuses_semantic_make_before_break_moves(self):
        observed = {A: (10,), B: (20,)}
        desired = {A: 20, B: 10}
        steps = plan_route_priority_convergence(
            observed, desired, (10, 20, 30)
        )
        self.assertEqual(
            steps,
            (
                RoutePriorityMove(A, 10, 30),
                RoutePriorityMove(B, 20, 10),
                RoutePriorityMove(A, 30, 20),
            ),
        )
        self.assertEqual(apply(observed, steps), {A: {20}, B: {10}})

    def test_reobserved_partial_add_becomes_safe_duplicate_cleanup(self):
        observed = {A: (10, 30), B: (20,)}
        desired = {A: 20, B: 10}
        steps = plan_route_priority_convergence(
            observed, desired, (10, 20, 30)
        )
        self.assertEqual(steps[0], RoutePriorityDeleteDuplicate(A, 10))
        self.assertNotIn(RoutePriorityMove(A, 10, 30), steps)
        self.assertEqual(apply(observed, steps), {A: {20}, B: {10}})

    def test_reobserved_completed_add_only_needs_stale_cleanup(self):
        observed = {A: (10, 30), B: (20,)}
        desired = {A: 30, B: 20}
        steps = plan_route_priority_convergence(
            observed, desired, (10, 20, 30)
        )
        self.assertEqual(steps, (RoutePriorityDeleteDuplicate(A, 10),))
        self.assertEqual(apply(observed, steps), {A: {30}, B: {20}})

    def test_reobserved_completed_move_continues_from_actual_state(self):
        observed = {A: (30,), B: (20,)}
        desired = {A: 20, B: 10}
        steps = plan_route_priority_convergence(
            observed, desired, (10, 20, 30)
        )
        self.assertEqual(
            steps,
            (
                RoutePriorityMove(B, 20, 10),
                RoutePriorityMove(A, 30, 20),
            ),
        )
        self.assertEqual(apply(observed, steps), {A: {20}, B: {10}})

    def test_duplicate_frees_other_paths_target_before_clean_planning(self):
        observed = {A: (10, 30), B: (20,)}
        desired = {A: 20, B: 10}
        steps = plan_route_priority_convergence(
            observed, desired, (10, 20, 30)
        )
        self.assertEqual(steps[0], RoutePriorityDeleteDuplicate(A, 10))

    def test_nonblocking_duplicate_retains_lower_metric_deterministically(self):
        observed = {A: (10, 30), B: (20,)}
        desired = {A: 40, B: 20}
        steps = plan_route_priority_convergence(
            observed, desired, (10, 20, 30, 40)
        )
        self.assertEqual(steps[0], RoutePriorityDeleteDuplicate(A, 30))
        self.assertEqual(apply(observed, steps), {A: {40}, B: {20}})

    def test_exact_desired_state_is_noop(self):
        self.assertEqual(
            plan_route_priority_convergence(
                {A: (10,), B: (20,)},
                {A: 10, B: 20},
                (10, 20, 30),
            ),
            (),
        )

    def test_cycle_without_free_metric_or_duplicate_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityConvergenceError,
            "free owned metric",
        ):
            plan_route_priority_convergence(
                {A: (10,), B: (20,)},
                {A: 20, B: 10},
                (10, 20),
            )

    def test_missing_route_for_desired_path_is_not_priority_only(self):
        with self.assertRaisesRegex(
            RoutePriorityConvergenceError,
            "has no route",
        ):
            plan_route_priority_convergence(
                {A: (), B: (20,)},
                {A: 10, B: 20},
                (10, 20, 30),
            )

    def test_structural_membership_change_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityConvergenceError,
            "identical observed and desired path membership",
        ):
            plan_route_priority_convergence(
                {A: (10,)},
                {A: 10, B: 20},
                (10, 20, 30),
            )

    def test_same_metric_for_two_paths_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityConvergenceError,
            "multiple logical paths",
        ):
            plan_route_priority_convergence(
                {A: (10,), B: (10,)},
                {A: 10, B: 20},
                (10, 20, 30),
            )

    def test_observed_metric_outside_owned_space_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityConvergenceError,
            "outside owned working set",
        ):
            plan_route_priority_convergence(
                {A: (10, 99)},
                {A: 10},
                (10, 20),
            )

    def test_duplicate_exact_metric_for_one_path_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityConvergenceError,
            "duplicate route metrics",
        ):
            plan_route_priority_convergence(
                {A: (10, 10)},
                {A: 10},
                (10, 20),
            )

    def test_plan_is_deterministic_across_input_order(self):
        one = plan_route_priority_convergence(
            {A: (10,), B: (20,), C: (30,)},
            {A: 20, B: 30, C: 10},
            (10, 20, 30, 40, 50),
        )
        two = plan_route_priority_convergence(
            {C: (30,), B: (20,), A: (10,)},
            {C: 10, B: 30, A: 20},
            (50, 40, 30, 20, 10),
        )
        self.assertEqual(one, two)
        self.assertEqual(
            apply({A: (10,), B: (20,), C: (30,)}, one),
            {A: {20}, B: {30}, C: {10}},
        )


if __name__ == "__main__":
    unittest.main()
