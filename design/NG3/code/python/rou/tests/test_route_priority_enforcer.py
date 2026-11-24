from __future__ import annotations

import unittest

from rou.binding import LogicalPathId
from rou.route_priority import RoutePriorityMove
from rou.route_priority_convergence import RoutePriorityDeleteDuplicate
from rou.route_priority_enforcer import (
    RoutePriorityEnforcementStatus,
    RoutePrioritySnapshot,
    converge_route_priority_once,
)


A = LogicalPathId("oc", 0, 0)
B = LogicalPathId("oc", 0, 1)


class FakeBackend:
    def __init__(self, routes):
        self.routes = {
            path_id: set(metrics)
            for path_id, metrics in routes.items()
        }
        self.observations = 0
        self.mutations = []
        self.fail_move_after_add_once = False
        self.fail_delete_once = False
        self.ignore_move_once = False

    def observe_route_priority(self):
        self.observations += 1
        return RoutePrioritySnapshot.build(self.routes)

    def delete_duplicate_route(self, step):
        self.mutations.append(step)
        if self.fail_delete_once:
            self.fail_delete_once = False
            raise RuntimeError("delete failed")
        if step.metric not in self.routes[step.path_id]:
            raise RuntimeError("route copy missing")
        if len(self.routes[step.path_id]) <= 1:
            raise RuntimeError("would delete last path copy")
        self.routes[step.path_id].remove(step.metric)

    def move_route_priority(self, move):
        self.mutations.append(move)
        if self.routes[move.path_id] != {move.from_metric}:
            raise RuntimeError("move source no longer authoritative")
        occupied = {
            metric
            for path_metrics in self.routes.values()
            for metric in path_metrics
        }
        if move.to_metric in occupied:
            raise RuntimeError("move destination is occupied")

        if self.ignore_move_once:
            self.ignore_move_once = False
            return

        # Semantic make-before-break implementation: add, verify presence,
        # then delete old. A failure after the add leaves a duplicate state
        # for the caller's mandatory fresh observation.
        self.routes[move.path_id].add(move.to_metric)
        if move.to_metric not in self.routes[move.path_id]:
            raise RuntimeError("new route was not verified")

        if self.fail_move_after_add_once:
            self.fail_move_after_add_once = False
            raise RuntimeError("delete-old phase failed")

        self.routes[move.path_id].remove(move.from_metric)


class RoutePriorityExecutorTests(unittest.TestCase):
    def test_success_requires_fresh_final_observation(self):
        backend = FakeBackend({A: (10,), B: (20,)})
        result = converge_route_priority_once(
            backend,
            {A: 20, B: 10},
            (10, 20, 30),
        )
        self.assertEqual(result.status, RoutePriorityEnforcementStatus.SUCCESS)
        self.assertTrue(result.confirmed)
        self.assertEqual(result.final.routes[A], frozenset((20,)))
        self.assertEqual(result.final.routes[B], frozenset((10,)))
        self.assertEqual(backend.observations, 2)
        self.assertEqual(result.completed_steps, result.planned_steps)

    def test_partial_move_failure_discards_tail_and_reobserves_duplicate(self):
        backend = FakeBackend({A: (10,), B: (20,)})
        backend.fail_move_after_add_once = True

        result = converge_route_priority_once(
            backend,
            {A: 20, B: 10},
            (10, 20, 30),
        )

        self.assertEqual(result.status, RoutePriorityEnforcementStatus.APPLY_FAILED)
        self.assertFalse(result.confirmed)
        self.assertEqual(result.completed_steps, ())
        self.assertIsInstance(result.failed_step, RoutePriorityMove)
        self.assertEqual(result.final.routes[A], frozenset((10, 30)))
        self.assertEqual(result.final.routes[B], frozenset((20,)))
        self.assertEqual(len(backend.mutations), 1)
        self.assertEqual(backend.observations, 2)

    def test_next_attempt_replans_from_reobserved_partial_state(self):
        backend = FakeBackend({A: (10,), B: (20,)})
        backend.fail_move_after_add_once = True

        failed = converge_route_priority_once(
            backend,
            {A: 20, B: 10},
            (10, 20, 30),
        )
        self.assertEqual(failed.status, RoutePriorityEnforcementStatus.APPLY_FAILED)

        recovered = converge_route_priority_once(
            backend,
            {A: 20, B: 10},
            (10, 20, 30),
        )
        self.assertEqual(recovered.status, RoutePriorityEnforcementStatus.SUCCESS)
        self.assertIsInstance(
            recovered.planned_steps[0],
            RoutePriorityDeleteDuplicate,
        )
        self.assertEqual(recovered.final.routes[A], frozenset((20,)))
        self.assertEqual(recovered.final.routes[B], frozenset((10,)))

    def test_duplicate_delete_failure_also_stops_and_reobserves(self):
        backend = FakeBackend({A: (10, 30), B: (20,)})
        backend.fail_delete_once = True

        result = converge_route_priority_once(
            backend,
            {A: 20, B: 10},
            (10, 20, 30),
        )

        self.assertEqual(result.status, RoutePriorityEnforcementStatus.APPLY_FAILED)
        self.assertIsInstance(
            result.failed_step,
            RoutePriorityDeleteDuplicate,
        )
        self.assertEqual(len(backend.mutations), 1)
        self.assertEqual(backend.observations, 2)
        self.assertEqual(result.final.routes[A], frozenset((10, 30)))

    def test_command_success_without_state_change_fails_postcondition(self):
        backend = FakeBackend({A: (10,), B: (20,)})
        backend.ignore_move_once = True

        result = converge_route_priority_once(
            backend,
            {A: 20, B: 10},
            (10, 20, 30),
        )

        # A later planned move observes the stale in-memory physical state and
        # fails; this is still apply failure, not false success.
        self.assertEqual(result.status, RoutePriorityEnforcementStatus.APPLY_FAILED)
        self.assertFalse(result.confirmed)
        self.assertGreaterEqual(backend.observations, 2)

    def test_noop_still_verifies_with_second_observation(self):
        backend = FakeBackend({A: (10,), B: (20,)})

        result = converge_route_priority_once(
            backend,
            {A: 10, B: 20},
            (10, 20, 30),
        )

        self.assertEqual(result.status, RoutePriorityEnforcementStatus.SUCCESS)
        self.assertEqual(result.planned_steps, ())
        self.assertEqual(backend.observations, 2)

    def test_final_postcondition_mismatch_is_not_success(self):
        class TamperingBackend(FakeBackend):
            def observe_route_priority(self):
                snapshot = super().observe_route_priority()
                if self.observations >= 2:
                    return RoutePrioritySnapshot.build(
                        {A: (99,), B: snapshot.routes[B]}
                    )
                return snapshot

        backend = TamperingBackend({A: (10,), B: (20,)})

        result = converge_route_priority_once(
            backend,
            {A: 10, B: 20},
            (10, 20, 30, 99),
        )

        self.assertEqual(
            result.status,
            RoutePriorityEnforcementStatus.POSTCONDITION_FAILED,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(result.completed_steps, ())

    def test_result_preserves_initial_and_final_evidence(self):
        backend = FakeBackend({A: (10,), B: (20,)})

        result = converge_route_priority_once(
            backend,
            {A: 20, B: 10},
            (10, 20, 30),
        )

        self.assertEqual(result.initial.routes[A], frozenset((10,)))
        self.assertEqual(result.initial.routes[B], frozenset((20,)))
        self.assertEqual(result.final.routes[A], frozenset((20,)))
        self.assertEqual(result.final.routes[B], frozenset((10,)))


if __name__ == "__main__":
    unittest.main()
