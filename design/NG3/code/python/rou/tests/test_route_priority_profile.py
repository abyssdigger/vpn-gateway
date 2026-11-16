from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.route_priority import RoutePriorityMove
from rou.route_priority_convergence import RoutePriorityDeleteDuplicate
from rou.route_priority_executor import RoutePrioritySnapshot
from rou.route_priority_profile import (
    RoutePriorityDomainId,
    RoutePriorityDomainRequest,
    RoutePriorityProfileStatus,
    converge_route_priority_profile_once,
)


A = LogicalPathId("a", 0, 0)
B = LogicalPathId("b", 0, 0)
DESIRED = {A: 20, B: 10}
METRICS = (10, 20, 30)


class FakeBackend:
    def __init__(self, routes, *, fail_move=False, drift_on_final=None):
        self.routes = {
            path_id: set(metrics)
            for path_id, metrics in routes.items()
        }
        self.fail_move = fail_move
        self.drift_on_final = drift_on_final
        self.observe_calls = 0
        self.mutation_calls = 0

    def observe_route_priority(self):
        self.observe_calls += 1
        if (
            self.drift_on_final is not None
            and self.observe_calls >= self.drift_on_final
        ):
            self.routes[A] = {99}
        return RoutePrioritySnapshot.build(self.routes)

    def delete_duplicate_route(self, step):
        self.mutation_calls += 1
        assert isinstance(step, RoutePriorityDeleteDuplicate)
        self.routes[step.path_id].remove(step.metric)

    def move_route_priority(self, move):
        self.mutation_calls += 1
        assert isinstance(move, RoutePriorityMove)
        self.routes[move.path_id].add(move.to_metric)
        if self.fail_move:
            self.fail_move = False
            raise RuntimeError("simulated partial move failure")
        self.routes[move.path_id].remove(move.from_metric)


def request(profile, destination, backend):
    return RoutePriorityDomainRequest(
        domain_id=RoutePriorityDomainId(
            profile_id=profile,
            destination=IPv4Network(destination),
        ),
        backend=backend,
        desired=DESIRED,
        working_metrics=METRICS,
    )


class RoutePriorityProfileTests(unittest.TestCase):
    def test_all_domains_require_fresh_final_confirmation(self):
        one = FakeBackend({A: (10,), B: (20,)})
        two = FakeBackend({A: (10,), B: (20,)})

        result = converge_route_priority_profile_once(
            (
                request("p", "10.2.0.0/16", two),
                request("p", "10.1.0.0/16", one),
            )
        )

        self.assertEqual(result.status, RoutePriorityProfileStatus.SUCCESS)
        self.assertTrue(result.confirmed)
        self.assertEqual(
            [str(outcome.domain_id.destination) for outcome in result.domains],
            ["10.1.0.0/16", "10.2.0.0/16"],
        )
        self.assertTrue(all(outcome.confirmed for outcome in result.domains))
        self.assertGreaterEqual(one.observe_calls, 3)
        self.assertGreaterEqual(two.observe_calls, 3)

    def test_one_domain_failure_does_not_skip_fresh_attempt_for_other_domain(self):
        failing = FakeBackend({A: (10,), B: (20,)}, fail_move=True)
        healthy = FakeBackend({A: (10,), B: (20,)})

        result = converge_route_priority_profile_once(
            (
                request("p", "10.1.0.0/16", failing),
                request("p", "10.2.0.0/16", healthy),
            )
        )

        self.assertEqual(
            result.status,
            RoutePriorityProfileStatus.UNCONFIRMED,
        )
        self.assertGreater(healthy.mutation_calls, 0)
        first, second = result.domains
        self.assertFalse(first.confirmed)
        self.assertTrue(second.confirmed)

    def test_final_pass_detects_drift_after_earlier_attempt_success(self):
        drifting = FakeBackend(
            {A: (10,), B: (20,)},
            drift_on_final=3,
        )
        healthy = FakeBackend({A: (10,), B: (20,)})

        result = converge_route_priority_profile_once(
            (
                request("p", "10.1.0.0/16", drifting),
                request("p", "10.2.0.0/16", healthy),
            )
        )

        self.assertEqual(
            result.status,
            RoutePriorityProfileStatus.UNCONFIRMED,
        )
        self.assertFalse(result.domains[0].confirmed)
        self.assertTrue(result.domains[1].confirmed)

    def test_attempt_failure_can_still_end_confirmed_if_final_state_is_exact(self):
        class ApplyWholeDesiredThenRaiseBackend(FakeBackend):
            def move_route_priority(self, move):
                self.mutation_calls += 1
                # Simulate a transport/backend error reported after the
                # external system has nevertheless reached the full desired
                # postcondition. The Executor attempt must still report its
                # mutation failure, while the Profile coordinator bases final
                # success on a later fresh authoritative observation.
                self.routes[A] = {20}
                self.routes[B] = {10}
                raise RuntimeError("transport reported failure after apply")

        backend = ApplyWholeDesiredThenRaiseBackend({A: (10,), B: (20,)})

        result = converge_route_priority_profile_once(
            (request("p", "10.1.0.0/16", backend),)
        )

        self.assertEqual(
            result.status,
            RoutePriorityProfileStatus.SUCCESS,
        )
        outcome = result.domains[0]
        self.assertTrue(outcome.confirmed)
        self.assertIsNone(outcome.attempt_error)
        self.assertIsNotNone(outcome.attempt)
        self.assertEqual(outcome.attempt.status.value, "apply_failed")
        self.assertIsNotNone(outcome.attempt.error)

    def test_no_domains_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            converge_route_priority_profile_once(())

    def test_mixed_profiles_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "mix profile IDs"):
            converge_route_priority_profile_once(
                (
                    request(
                        "p1",
                        "10.1.0.0/16",
                        FakeBackend({A: (10,), B: (20,)}),
                    ),
                    request(
                        "p2",
                        "10.2.0.0/16",
                        FakeBackend({A: (10,), B: (20,)}),
                    ),
                )
            )

    def test_duplicate_domain_is_rejected(self):
        one = request(
            "p",
            "10.1.0.0/16",
            FakeBackend({A: (10,), B: (20,)}),
        )
        two = request(
            "p",
            "10.1.0.0/16",
            FakeBackend({A: (10,), B: (20,)}),
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            converge_route_priority_profile_once((one, two))


if __name__ == "__main__":
    unittest.main()
