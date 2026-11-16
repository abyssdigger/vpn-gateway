from __future__ import annotations

import unittest

from rou.binding import LogicalPathId
from rou.route_priority_convergence import (
    RoutePriorityAdd,
    RoutePriorityConvergenceError,
    RoutePriorityDelete,
    plan_route_priority_convergence,
)


A = LogicalPathId("oc", 0, 0)
B = LogicalPathId("oc", 0, 1)
C = LogicalPathId("wg", 0, 0)


def apply(observed, mutations):
    state = {path_id: set(metrics) for path_id, metrics in observed.items()}
    for mutation in mutations:
        if isinstance(mutation, RoutePriorityAdd):
            occupied = {
                metric
                for path_metrics in state.values()
                for metric in path_metrics
            }
            assert mutation.metric not in occupied
            state[mutation.path_id].add(mutation.metric)
        else:
            assert isinstance(mutation, RoutePriorityDelete)
            assert mutation.metric in state[mutation.path_id]
            assert len(state[mutation.path_id]) > 1
            state[mutation.path_id].remove(mutation.metric)

        assert all(path_metrics for path_metrics in state.values())
    return state


class RoutePriorityConvergenceTests(unittest.TestCase):
    def test_clean_swap_uses_safe_add_delete_sequence(self):
        observed = {A: (10,), B: (20,)}
        desired = {A: 20, B: 10}
        mutations = plan_route_priority_convergence(
            observed, desired, (10, 20, 30)
        )
        self.assertEqual(
            mutations,
            (
                RoutePriorityAdd(A, 30),
                RoutePriorityDelete(A, 10),
                RoutePriorityAdd(B, 10),
                RoutePriorityDelete(B, 20),
                RoutePriorityAdd(A, 20),
                RoutePriorityDelete(A, 30),
            ),
        )
        self.assertEqual(
            apply(observed, mutations),
            {A: {20}, B: {10}},
        )

    def test_reobserved_partial_add_does_not_replay_add(self):
        observed = {A: (10, 30), B: (20,)}
        desired = {A: 20, B: 10}
        mutations = plan_route_priority_convergence(
            observed, desired, (10, 20, 30)
        )
        self.assertEqual(mutations[0], RoutePriorityDelete(A, 10))
        self.assertNotIn(RoutePriorityAdd(A, 30), mutations)
        self.assertEqual(
            apply(observed, mutations),
            {A: {20}, B: {10}},
        )

    def test_reobserved_completed_add_only_needs_stale_delete(self):
        observed = {A: (10, 30), B: (20,)}
        desired = {A: 30, B: 20}
        mutations = plan_route_priority_convergence(
            observed, desired, (10, 20, 30)
        )
        self.assertEqual(mutations, (RoutePriorityDelete(A, 10),))
        self.assertEqual(
            apply(observed, mutations),
            {A: {30}, B: {20}},
        )

    def test_reobserved_completed_move_continues_from_actual_state(self):
        observed = {A: (30,), B: (20,)}
        desired = {A: 20, B: 10}
        mutations = plan_route_priority_convergence(
            observed, desired, (10, 20, 30)
        )
        self.assertEqual(
            mutations,
            (
                RoutePriorityAdd(B, 10),
                RoutePriorityDelete(B, 20),
                RoutePriorityAdd(A, 20),
                RoutePriorityDelete(A, 30),
            ),
        )
        self.assertEqual(
            apply(observed, mutations),
            {A: {20}, B: {10}},
        )

    def test_duplicate_can_supply_working_space_when_no_metric_is_free(self):
        observed = {A: (10, 30), B: (20,)}
        desired = {A: 20, B: 10}
        mutations = plan_route_priority_convergence(
            observed, desired, (10, 20, 30)
        )
        self.assertEqual(mutations[0], RoutePriorityDelete(A, 10))
        self.assertEqual(
            apply(observed, mutations),
            {A: {20}, B: {10}},
        )

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
            "free owned metric or a safely removable duplicate",
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
