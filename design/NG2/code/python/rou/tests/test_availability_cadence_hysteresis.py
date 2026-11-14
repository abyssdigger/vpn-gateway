from ipaddress import IPv4Address
import unittest

from rou.availability_probe_manager import AvailabilityProbeManager
from rou.availability_probe_policy import AvailabilityProbePolicy
from rou.availability_probe_state import AvailabilityProbeState
from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    ActionResult,
    NetworkRulesState,
    StateKnowledge,
)
from rou.probe_attempt import ProbeAttemptOutcome, ProbeAttemptResult
from rou.probe_rules import AvailabilityProbeRequest, AvailabilityProbeSetRequest


class RecordingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, info):
        self.events.append(info)


class ScriptedDriver:
    def __init__(self):
        self.calls = []
        self.results = {}

    def queue(self, probe_id, *results):
        self.results.setdefault(probe_id, []).extend(results)

    def execute(self, request, *, timeout_seconds):
        self.calls.append((request.probe_id, timeout_seconds))
        queue = self.results.get(request.probe_id, [])
        if queue:
            return queue.pop(0)
        return ProbeAttemptResult(ProbeAttemptOutcome.REPLY)


class FakeAdapter:
    def __init__(self):
        self.state = NetworkRulesState(
            StateKnowledge.UNKNOWN,
            None,
            fresh=False,
        )
        self.apply_count = 0
        self.renew_count = 0

    def apply(self, owner, spec):
        self.apply_count += 1
        self.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            spec,
            fresh=True,
        )
        return ActionResult(True)

    def renew_state(self, owner):
        self.renew_count += 1
        return ActionResult(True)

    def get_last_state(self, owner):
        return self.state

    def cleanup(self, owner):
        return ActionResult(True)


def policy(
    *,
    interval=10,
    retry=2,
    timeout=1,
    failure=1,
    recovery=1,
):
    return AvailabilityProbePolicy(
        interval_seconds=interval,
        retry_interval_seconds=retry,
        timeout_seconds=timeout,
        failure_threshold=failure,
        recovery_threshold=recovery,
    )


def probe(probe_id="primary", *, probe_policy=None, ifindex=10):
    return AvailabilityProbeRequest(
        probe_id,
        InterfaceIdentity("vpns00", ifindex),
        IPv4Address("203.0.113.24"),
        policy=probe_policy,
    )


class AvailabilityCadenceHysteresisTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeAdapter()
        self.publisher = RecordingPublisher()
        self.driver = ScriptedDriver()
        self.manager = AvailabilityProbeManager(
            self.adapter,
            self.publisher,
            self.driver,
        )

    def install(self, *probes):
        self.manager.handle_request(
            AvailabilityProbeSetRequest(tuple(probes))
        )
        self.publisher.events.clear()

    def test_policyless_probe_is_not_run_by_scheduler(self):
        self.install(probe())

        attempted = self.manager.run_due(0)

        self.assertEqual(attempted, ())
        self.assertEqual(self.driver.calls, [])

    def test_first_scheduled_probe_is_immediately_due_then_uses_regular_interval(self):
        self.install(probe(probe_policy=policy(interval=10, retry=2)))

        self.assertEqual(self.manager.run_due(100), ("primary",))
        self.assertEqual(self.driver.calls, [("primary", 1)])
        self.assertIs(
            self.publisher.events[-1].state,
            AvailabilityProbeState.REACHABLE,
        )

        self.assertEqual(self.manager.run_due(109.999), ())
        self.assertEqual(self.manager.run_due(110), ("primary",))
        self.assertEqual(len(self.driver.calls), 2)

    def test_initial_recovery_threshold_uses_retry_cadence_until_satisfied(self):
        self.install(
            probe(
                probe_policy=policy(
                    interval=10,
                    retry=2,
                    recovery=2,
                )
            )
        )

        self.assertEqual(self.manager.run_due(0), ("primary",))
        self.assertEqual(self.publisher.events, [])
        self.assertEqual(self.manager.run_due(1.999), ())

        self.assertEqual(self.manager.run_due(2), ("primary",))
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.REACHABLE,
        )

        self.assertEqual(self.manager.run_due(11.999), ())
        self.assertEqual(self.manager.run_due(12), ("primary",))

    def test_failure_hysteresis_retains_reachable_until_threshold(self):
        p = probe(
            probe_policy=policy(
                interval=10,
                retry=2,
                failure=2,
            )
        )
        self.install(p)
        self.manager.run_due(0)
        reachable = self.publisher.events[-1]
        self.assertIs(reachable.state, AvailabilityProbeState.REACHABLE)
        self.publisher.events.clear()

        self.driver.queue(
            "primary",
            ProbeAttemptResult(ProbeAttemptOutcome.NO_REPLY),
            ProbeAttemptResult(ProbeAttemptOutcome.NO_REPLY),
        )

        self.assertEqual(self.manager.run_due(10), ("primary",))
        self.assertEqual(self.publisher.events, [])
        self.assertEqual(self.manager.run_due(11.999), ())

        self.assertEqual(self.manager.run_due(12), ("primary",))
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNREACHABLE,
        )
        self.assertEqual(
            self.publisher.events[0].observation_generation,
            reachable.observation_generation,
        )

    def test_recovery_hysteresis_retains_unreachable_until_threshold(self):
        p = probe(
            probe_policy=policy(
                interval=10,
                retry=2,
                recovery=2,
            )
        )
        self.driver.queue(
            "primary",
            ProbeAttemptResult(ProbeAttemptOutcome.NO_REPLY),
        )
        self.install(p)
        self.manager.run_due(0)
        unreachable = self.publisher.events[-1]
        self.assertIs(unreachable.state, AvailabilityProbeState.UNREACHABLE)
        self.publisher.events.clear()

        self.driver.queue(
            "primary",
            ProbeAttemptResult(ProbeAttemptOutcome.REPLY),
            ProbeAttemptResult(ProbeAttemptOutcome.REPLY),
        )

        self.assertEqual(self.manager.run_due(10), ("primary",))
        self.assertEqual(self.publisher.events, [])
        self.assertEqual(self.manager.run_due(12), ("primary",))
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.REACHABLE,
        )
        self.assertEqual(
            self.publisher.events[0].observation_generation,
            unreachable.observation_generation,
        )

    def test_matching_evidence_cancels_pending_opposite_streak(self):
        p = probe(
            probe_policy=policy(
                interval=10,
                retry=2,
                failure=2,
            )
        )
        self.install(p)
        self.manager.run_due(0)
        self.publisher.events.clear()

        self.driver.queue(
            "primary",
            ProbeAttemptResult(ProbeAttemptOutcome.NO_REPLY),
            ProbeAttemptResult(ProbeAttemptOutcome.REPLY),
            ProbeAttemptResult(ProbeAttemptOutcome.NO_REPLY),
        )

        self.manager.run_due(10)
        self.manager.run_due(12)
        self.assertEqual(self.publisher.events, [])

        self.manager.run_due(22)
        self.assertEqual(self.publisher.events, [])

    def test_local_error_forgets_authoritative_verdict_and_retries(self):
        p = probe(probe_policy=policy(interval=10, retry=2))
        self.install(p)
        self.manager.run_due(0)
        self.publisher.events.clear()

        self.driver.queue(
            "primary",
            ProbeAttemptResult(
                ProbeAttemptOutcome.ERROR,
                "local failure",
            ),
        )

        self.assertEqual(self.manager.run_due(10), ("primary",))
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNKNOWN,
        )
        self.assertIsNone(
            self.publisher.events[0].observation_generation
        )
        self.assertEqual(self.manager.run_due(11.999), ())
        self.assertEqual(self.manager.run_due(12), ("primary",))

    def test_per_probe_schedules_are_independent(self):
        self.install(
            probe(
                "a",
                probe_policy=policy(interval=10, retry=2),
            ),
            probe(
                "b",
                probe_policy=policy(interval=20, retry=3),
            ),
        )

        self.assertEqual(self.manager.run_due(0), ("a", "b"))
        self.assertEqual(self.manager.run_due(10), ("a",))
        self.assertEqual(self.manager.run_due(20), ("a", "b"))

    def test_equivalent_snapshot_preserves_due_times(self):
        a = probe("a", probe_policy=policy(interval=10, retry=2))
        b = probe("b", probe_policy=policy(interval=20, retry=3))
        self.install(a, b)
        self.manager.run_due(0)
        generation = self.manager.observation_generation

        self.manager.handle_request(
            AvailabilityProbeSetRequest((b, a))
        )

        self.assertEqual(
            self.manager.observation_generation,
            generation,
        )
        self.assertEqual(self.manager.run_due(9), ())
        self.assertEqual(self.manager.run_due(10), ("a",))

    def test_policy_change_starts_new_epoch_without_structural_reapply(self):
        original = probe(
            probe_policy=policy(interval=10, retry=2)
        )
        self.install(original)
        self.manager.run_due(0)
        old_generation = self.manager.observation_generation
        apply_count = self.adapter.apply_count
        self.publisher.events.clear()

        changed = probe(
            probe_policy=policy(interval=30, retry=5)
        )
        self.manager.handle_request(
            AvailabilityProbeSetRequest((changed,))
        )

        self.assertEqual(self.adapter.apply_count, apply_count)
        self.assertGreater(
            self.manager.observation_generation.sequence,
            old_generation.sequence,
        )
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNKNOWN,
        )

    def test_generation_change_resets_pending_hysteresis(self):
        p = probe(
            probe_policy=policy(
                interval=10,
                retry=2,
                failure=2,
            )
        )
        self.install(p)
        self.manager.run_due(0)
        self.driver.queue(
            "primary",
            ProbeAttemptResult(ProbeAttemptOutcome.NO_REPLY),
        )
        self.manager.run_due(10)

        replacement = probe(
            probe_policy=p.policy,
            ifindex=11,
        )
        self.manager.handle_request(
            AvailabilityProbeSetRequest((replacement,))
        )
        self.publisher.events.clear()

        self.driver.queue(
            "primary",
            ProbeAttemptResult(ProbeAttemptOutcome.NO_REPLY),
        )
        self.assertEqual(self.manager.run_due(100), ("primary",))
        self.assertEqual(self.publisher.events, [])

    def test_invalid_now_is_rejected_without_attempts(self):
        self.install(probe(probe_policy=policy()))

        for value in (-1, float("inf"), float("nan"), True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.manager.run_due(value)

        self.assertEqual(self.driver.calls, [])


if __name__ == "__main__":
    unittest.main()
