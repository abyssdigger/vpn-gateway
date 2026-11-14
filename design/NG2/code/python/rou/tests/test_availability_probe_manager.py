from ipaddress import IPv4Address
import unittest

from rou.availability_probe_manager import AvailabilityProbeManager
from rou.availability_probe_state import AvailabilityProbeState
from rou.probe_attempt import ProbeAttemptOutcome, ProbeAttemptResult
from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    ActionResult,
    NetworkRulesSpec,
    NetworkRulesState,
    StateKnowledge,
)
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
)


class RecordingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, info):
        self.events.append(info)




class FakeDriver:
    def __init__(self):
        self.calls = []
        self.result = ProbeAttemptResult(ProbeAttemptOutcome.REPLY)
        self.before_return = None

    def execute(self, request, *, timeout_seconds):
        self.calls.append((request, timeout_seconds))
        if self.before_return is not None:
            self.before_return()
        return self.result


class FakeAdapter:
    def __init__(self):
        self.apply_success = True
        self.renew_success = True
        self.state = NetworkRulesState(
            StateKnowledge.UNKNOWN,
            None,
            fresh=False,
        )
        self.apply_owners = []
        self.apply_specs = []
        self.renew_owners = []
        self.get_owners = []
        self.cleanup_owners = []

    def apply(self, owner, spec: NetworkRulesSpec) -> ActionResult:
        self.apply_owners.append(owner)
        self.apply_specs.append(spec)
        if self.apply_success:
            self.state = NetworkRulesState(
                StateKnowledge.KNOWN,
                spec,
                fresh=True,
            )
        return ActionResult(self.apply_success)

    def renew_state(self, owner) -> ActionResult:
        self.renew_owners.append(owner)
        return ActionResult(self.renew_success)

    def get_last_state(self, owner) -> NetworkRulesState:
        self.get_owners.append(owner)
        return self.state

    def cleanup(self, owner) -> ActionResult:
        self.cleanup_owners.append(owner)
        return ActionResult(True)


def probe(
    probe_id: str,
    path: InterfaceIdentity,
    target: str,
) -> AvailabilityProbeRequest:
    return AvailabilityProbeRequest(
        probe_id,
        path,
        IPv4Address(target),
    )


def request(*items: AvailabilityProbeRequest) -> AvailabilityProbeSetRequest:
    return AvailabilityProbeSetRequest(tuple(items))


class AvailabilityProbeManagerRulesTests(unittest.TestCase):
    def setUp(self):
        self.path = InterfaceIdentity("vpns00", 10)
        self.adapter = FakeAdapter()
        self.publisher = RecordingPublisher()
        self.driver = FakeDriver()
        self.manager = AvailabilityProbeManager(
            self.adapter,
            self.publisher,
            self.driver,
        )

    def test_first_request_uses_manager_as_owner_and_opens_ready_epoch(self):
        wanted = request(
            probe("primary", self.path, "203.0.113.24")
        )

        result = self.manager.handle_request(wanted)

        self.assertIsNone(result)
        self.assertIs(self.adapter.apply_owners[0], self.manager)
        self.assertIs(self.adapter.get_owners[0], self.manager)
        self.assertIsNotNone(self.manager.observation_generation)
        self.assertEqual(self.manager.observation_generation.sequence, 1)

        self.assertEqual(len(self.publisher.events), 1)
        info = self.publisher.events[0]
        self.assertEqual(info.probe_id, "primary")
        self.assertIs(info.state, AvailabilityProbeState.UNKNOWN)
        self.assertIsNone(info.observation_generation)
        self.assertIn("no authoritative probe evidence", info.reason)

    def test_equivalent_reordered_snapshot_is_idempotent_and_preserves_epoch(self):
        first = probe("first", self.path, "203.0.113.24")
        second = probe("second", self.path, "203.0.113.25")
        initial = request(first, second)

        self.manager.handle_request(initial)
        generation = self.manager.observation_generation
        apply_count = len(self.adapter.apply_owners)
        self.publisher.events.clear()

        self.manager.handle_request(
            AvailabilityProbeSetRequest(tuple(reversed(initial.probes)))
        )

        self.assertEqual(len(self.adapter.apply_owners), apply_count)
        self.assertEqual(len(self.adapter.renew_owners), 1)
        self.assertEqual(self.manager.observation_generation, generation)
        self.assertEqual(self.publisher.events, [])


    def test_logical_probe_change_reuses_equivalent_physical_rules(self):
        first = probe("first", self.path, "203.0.113.24")
        second = probe("second", self.path, "203.0.113.24")

        self.manager.handle_request(request(first))
        initial_apply_count = len(self.adapter.apply_owners)
        first_observation = self.manager.attempt_once(
            "first",
            timeout_seconds=1,
        )

        self.manager.handle_request(request(first, second))

        self.assertEqual(
            len(self.adapter.apply_owners),
            initial_apply_count,
        )
        self.assertGreaterEqual(len(self.adapter.renew_owners), 3)

        second_observation = self.manager.attempt_once(
            "first",
            timeout_seconds=1,
        )
        self.assertEqual(
            second_observation.observation_generation,
            first_observation.observation_generation,
        )

    def test_added_logical_probe_on_same_plane_preserves_existing_verdict(self):
        first = probe("first", self.path, "203.0.113.24")
        second = probe("second", self.path, "203.0.113.24")

        self.manager.handle_request(request(first))
        first_info = self.manager.evaluate_once(
            "first",
            timeout_seconds=1,
        )
        generation = self.manager.observation_generation
        self.publisher.events.clear()

        self.manager.handle_request(request(first, second))

        self.assertEqual(
            self.manager.observation_generation,
            generation,
        )
        self.assertEqual(len(self.publisher.events), 1)
        self.assertEqual(self.publisher.events[0].probe_id, "second")
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNKNOWN,
        )
        self.publisher.events.clear()

        self.manager.audit()

        self.assertEqual(self.publisher.events, [])
        self.assertEqual(
            self.manager._latest_published["first"],
            first_info,
        )

    def test_semantically_changed_snapshot_starts_new_ready_epoch(self):
        self.manager.handle_request(
            request(probe("primary", self.path, "203.0.113.24"))
        )
        first_generation = self.manager.observation_generation

        self.manager.handle_request(
            request(probe("primary", self.path, "203.0.113.25"))
        )

        second_generation = self.manager.observation_generation
        self.assertIsNotNone(first_generation)
        self.assertIsNotNone(second_generation)
        self.assertGreater(
            second_generation.sequence,
            first_generation.sequence,
        )
        self.assertEqual(len(self.adapter.apply_owners), 2)

    def test_drift_audit_invalidates_old_epoch_and_repair_opens_new_epoch(self):
        wanted = request(
            probe("primary", self.path, "203.0.113.24")
        )
        self.manager.handle_request(wanted)
        first_generation = self.manager.observation_generation
        desired = self.adapter.state.rules

        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )

        self.manager.audit()

        self.assertEqual(self.adapter.state.rules, desired)
        self.assertIsNotNone(self.manager.observation_generation)
        self.assertGreater(
            self.manager.observation_generation.sequence,
            first_generation.sequence,
        )

    def test_failed_repair_leaves_no_ready_epoch_and_publishes_rules_unknown(self):
        wanted = request(
            probe("primary", self.path, "203.0.113.24")
        )
        self.manager.handle_request(wanted)

        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )
        self.adapter.apply_success = False
        self.publisher.events.clear()

        self.manager.audit()

        self.assertIsNone(self.manager.observation_generation)
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNKNOWN,
        )
        self.assertEqual(
            self.publisher.events[0].reason,
            "probe rules are not ready",
        )

    def test_empty_probe_set_has_no_readiness_epoch(self):
        self.manager.handle_request(request())

        self.assertIsNone(self.manager.observation_generation)
        self.assertEqual(self.publisher.events, [])

    def test_removed_probe_is_invalidated_then_forgotten_for_future_readd(self):
        primary = probe("primary", self.path, "203.0.113.24")

        self.manager.handle_request(request(primary))
        self.assertEqual(len(self.publisher.events), 1)

        self.manager.handle_request(request())

        self.assertEqual(len(self.publisher.events), 2)
        removed = self.publisher.events[-1]
        self.assertEqual(removed.probe_id, "primary")
        self.assertIs(removed.state, AvailabilityProbeState.UNKNOWN)
        self.assertEqual(removed.reason, "probe no longer requested")

        self.manager.handle_request(request(primary))

        self.assertEqual(len(self.publisher.events), 3)
        self.assertEqual(
            [item.probe_id for item in self.publisher.events],
            ["primary", "primary", "primary"],
        )
        self.assertIn(
            "no authoritative probe evidence",
            self.publisher.events[-1].reason,
        )


    def test_attempt_once_returns_raw_observation_only_after_post_rules_check(self):
        wanted = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(wanted))
        generation = self.manager.observation_generation

        observation = self.manager.attempt_once(
            "primary",
            timeout_seconds=3,
        )

        self.assertIsNotNone(observation)
        self.assertEqual(observation.probe_id, "primary")
        self.assertEqual(observation.observation_generation, generation)
        self.assertIs(
            observation.result.outcome,
            ProbeAttemptOutcome.REPLY,
        )
        self.assertEqual(self.driver.calls, [(wanted, 3)])
        self.assertEqual(len(self.adapter.renew_owners), 2)
        self.assertEqual(len(self.publisher.events), 1)

    def test_attempt_once_repairs_nonready_rules_before_driver(self):
        wanted = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(wanted))
        old_generation = self.manager.observation_generation
        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )
        initial_apply_count = len(self.adapter.apply_owners)

        observation = self.manager.attempt_once(
            "primary",
            timeout_seconds=1,
        )

        self.assertIsNotNone(observation)
        self.assertEqual(
            len(self.adapter.apply_owners),
            initial_apply_count + 1,
        )
        self.assertGreater(
            observation.observation_generation.sequence,
            old_generation.sequence,
        )
        self.assertEqual(len(self.driver.calls), 1)

    def test_attempt_once_does_not_run_driver_when_rules_cannot_be_repaired(self):
        wanted = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(wanted))
        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )
        self.adapter.apply_success = False

        observation = self.manager.attempt_once(
            "primary",
            timeout_seconds=1,
        )

        self.assertIsNone(observation)
        self.assertEqual(self.driver.calls, [])
        self.assertIsNone(self.manager.observation_generation)

    def test_post_attempt_rules_drift_discards_raw_outcome(self):
        wanted = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(wanted))
        self.publisher.events.clear()

        def drift_after_probe():
            self.adapter.state = NetworkRulesState(
                StateKnowledge.KNOWN,
                NetworkRulesSpec(),
                fresh=True,
            )

        self.driver.before_return = drift_after_probe

        observation = self.manager.attempt_once(
            "primary",
            timeout_seconds=1,
        )

        self.assertIsNone(observation)
        self.assertIsNone(self.manager.observation_generation)
        self.assertEqual(len(self.driver.calls), 1)
        self.assertEqual(len(self.publisher.events), 1)
        self.assertEqual(
            self.publisher.events[0].reason,
            "probe rules are not ready",
        )

    def test_driver_error_remains_raw_local_attempt_observation(self):
        wanted = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(wanted))
        self.driver.result = ProbeAttemptResult(
            ProbeAttemptOutcome.ERROR,
            "local execution failure",
        )

        observation = self.manager.attempt_once(
            "primary",
            timeout_seconds=1,
        )

        self.assertIsNotNone(observation)
        self.assertIs(
            observation.result.outcome,
            ProbeAttemptOutcome.ERROR,
        )
        self.assertEqual(
            observation.result.diagnostic,
            "local execution failure",
        )
        self.assertIs(
            self.publisher.events[-1].state,
            AvailabilityProbeState.UNKNOWN,
        )

    def test_attempt_once_rejects_unknown_probe_id(self):
        self.manager.handle_request(
            request(probe("primary", self.path, "203.0.113.24"))
        )

        with self.assertRaisesRegex(ValueError, "unknown active probe_id"):
            self.manager.attempt_once(
                "missing",
                timeout_seconds=1,
            )

        self.assertEqual(self.driver.calls, [])

    def test_audit_before_first_request_is_noop(self):
        self.manager.audit()

        self.assertEqual(self.adapter.renew_owners, [])
        self.assertEqual(self.adapter.apply_owners, [])
        self.assertEqual(self.publisher.events, [])

    def test_shutdown_invalidates_epoch_and_cleans_same_owner(self):
        self.manager.handle_request(
            request(probe("primary", self.path, "203.0.113.24"))
        )

        result = self.manager.shutdown()

        self.assertTrue(result.success)
        self.assertIsNone(self.manager.observation_generation)
        self.assertEqual(len(self.adapter.cleanup_owners), 1)
        self.assertIs(self.adapter.cleanup_owners[0], self.manager)


if __name__ == "__main__":
    unittest.main()
