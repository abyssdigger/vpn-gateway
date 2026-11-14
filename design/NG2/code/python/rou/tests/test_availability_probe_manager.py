from ipaddress import IPv4Address
import unittest

from rou.availability_probe_manager import AvailabilityProbeManager
from rou.availability_probe_state import AvailabilityProbeState
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
        self.manager = AvailabilityProbeManager(
            self.adapter,
            self.publisher,
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

    def test_logical_probe_addition_reuses_same_physical_rules_and_epoch(self):
        first = probe("first", self.path, "203.0.113.24")
        second = probe("second", self.path, "203.0.113.24")

        self.manager.handle_request(request(first))
        generation = self.manager.observation_generation
        apply_count = len(self.adapter.apply_owners)
        self.publisher.events.clear()

        self.manager.handle_request(request(first, second))

        self.assertEqual(len(self.adapter.apply_owners), apply_count)
        self.assertEqual(self.manager.observation_generation, generation)
        self.assertEqual(len(self.publisher.events), 1)
        self.assertEqual(self.publisher.events[0].probe_id, "second")
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNKNOWN,
        )

    def test_disable_is_logical_only_and_invalidates_only_that_probe(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))
        generation = self.manager.observation_generation
        apply_count = len(self.adapter.apply_owners)
        self.publisher.events.clear()

        disabled = AvailabilityProbeRequest(
            primary.probe_id,
            primary.path,
            primary.target,
            enabled=False,
        )
        self.manager.handle_request(request(disabled))

        self.assertEqual(self.manager.observation_generation, generation)
        self.assertEqual(len(self.adapter.apply_owners), apply_count)
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNKNOWN,
        )

    def test_semantically_changed_physical_probe_starts_new_ready_epoch(self):
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
