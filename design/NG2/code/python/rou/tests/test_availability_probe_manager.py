from ipaddress import IPv4Address
import unittest

from rou.availability_collector import AvailabilityHysteresisPolicy
from rou.availability_probe_manager import AvailabilityProbeManager
from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    ActionResult,
    NetworkRulesSpec,
    NetworkRulesState,
    StateKnowledge,
)
from rou.probe_rules import AvailabilityProbeRequest, AvailabilityProbeSetRequest


class RecordingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, value):
        self.events.append(value)


class FakeAdapter:
    def __init__(self):
        self.apply_success = True
        self.renew_success = True
        self.state = NetworkRulesState(StateKnowledge.UNKNOWN, None, fresh=False)
        self.apply_owners = []
        self.apply_specs = []
        self.renew_owners = []
        self.get_owners = []
        self.cleanup_owners = []

    def apply(self, owner, spec):
        self.apply_owners.append(owner)
        self.apply_specs.append(spec)
        if self.apply_success:
            self.state = NetworkRulesState(StateKnowledge.KNOWN, spec, fresh=True)
        return ActionResult(self.apply_success)

    def renew_state(self, owner):
        self.renew_owners.append(owner)
        return ActionResult(self.renew_success)

    def get_last_state(self, owner):
        self.get_owners.append(owner)
        return self.state

    def cleanup(self, owner):
        self.cleanup_owners.append(owner)
        return ActionResult(True)


def probe(probe_id, path, target, *, enabled=True, interval=10, failure=3, recovery=2):
    return AvailabilityProbeRequest(
        probe_id,
        path,
        IPv4Address(target),
        enabled=enabled,
        interval_seconds=interval,
        hysteresis=AvailabilityHysteresisPolicy(failure, recovery),
    )


def request(*items):
    return AvailabilityProbeSetRequest(tuple(items))


class AvailabilityProbeManagerTests(unittest.TestCase):
    def setUp(self):
        self.path = InterfaceIdentity("vpns00", 10)
        self.adapter = FakeAdapter()
        self.execution = RecordingPublisher()
        self.manager = AvailabilityProbeManager(
            self.adapter,
            execution_plan_publisher=self.execution,
        )

    def test_first_ready_request_publishes_execution_plan(self):
        self.manager.handle_request(
            request(probe("primary", self.path, "203.0.113.24"))
        )

        self.assertEqual(len(self.execution.events), 1)
        plan = self.execution.events[0]
        self.assertEqual(plan.generation, self.manager.observation_generation)
        self.assertEqual(plan.channels[0].priority.channel_id, "primary")

    def test_equivalent_request_preserves_generation_and_does_not_republish(self):
        wanted = request(probe("primary", self.path, "203.0.113.24"))
        self.manager.handle_request(wanted)
        generation = self.manager.observation_generation
        self.execution.events.clear()

        self.manager.handle_request(wanted)

        self.assertEqual(self.manager.observation_generation, generation)
        self.assertEqual(self.execution.events, [])
        self.assertEqual(len(self.adapter.renew_owners), 1)

    def test_policy_only_change_republishes_plan_without_new_physical_generation(self):
        first = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(first))
        generation = self.manager.observation_generation
        self.execution.events.clear()

        changed = probe(
            "primary",
            self.path,
            "203.0.113.24",
            interval=10,
            failure=5,
            recovery=4,
        )
        self.manager.handle_request(request(changed))

        self.assertEqual(self.manager.observation_generation, generation)
        self.assertEqual(len(self.execution.events), 1)
        self.assertEqual(
            self.execution.events[0].channels[0].priority.policy,
            changed.hysteresis,
        )

    def test_physical_change_quiesces_old_plan_before_new_generation(self):
        self.manager.handle_request(
            request(probe("primary", self.path, "203.0.113.24"))
        )
        first_generation = self.manager.observation_generation
        self.execution.events.clear()

        self.manager.handle_request(
            request(probe("primary", self.path, "203.0.113.25"))
        )

        self.assertEqual(len(self.execution.events), 2)
        self.assertIsNone(self.execution.events[0])
        self.assertNotEqual(
            self.execution.events[1].generation,
            first_generation,
        )

    def test_disabling_only_probe_quiesces_execution(self):
        first = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(first))
        self.execution.events.clear()

        self.manager.handle_request(
            request(
                AvailabilityProbeRequest(
                    first.probe_id,
                    first.path,
                    first.target,
                    enabled=False,
                    interval_seconds=first.interval_seconds,
                    hysteresis=first.hysteresis,
                )
            )
        )

        self.assertIsNone(self.manager.observation_generation)
        self.assertEqual(self.execution.events, [None])
        self.assertEqual(self.adapter.state.rules, NetworkRulesSpec())

    def test_shared_plane_logical_change_does_not_reapply_network_rules(self):
        first = probe("first", self.path, "203.0.113.24")
        second = probe("second", self.path, "203.0.113.24")
        self.manager.handle_request(request(first))
        apply_count = len(self.adapter.apply_owners)
        generation = self.manager.observation_generation

        self.manager.handle_request(request(first, second))

        self.assertEqual(len(self.adapter.apply_owners), apply_count)
        self.assertEqual(self.manager.observation_generation, generation)
        self.assertEqual(
            [item.priority.channel_id for item in self.execution.events[-1].channels],
            ["first", "second"],
        )

    def test_audit_repairs_drift_and_reopens_generation(self):
        wanted = request(probe("primary", self.path, "203.0.113.24"))
        self.manager.handle_request(wanted)
        first_generation = self.manager.observation_generation
        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )
        self.execution.events.clear()

        self.manager.audit()

        self.assertEqual(self.adapter.state.rules, self.adapter.apply_specs[-1])
        self.assertIsNotNone(self.manager.observation_generation)
        self.assertGreater(
            self.manager.observation_generation.sequence,
            first_generation.sequence,
        )
        self.assertIsNone(self.execution.events[0])

    def test_shutdown_quiesces_execution_and_cleans_same_owner(self):
        self.manager.handle_request(
            request(probe("primary", self.path, "203.0.113.24"))
        )
        self.execution.events.clear()

        result = self.manager.shutdown()

        self.assertTrue(result.success)
        self.assertEqual(self.execution.events, [None])
        self.assertIs(self.adapter.cleanup_owners[0], self.manager)


if __name__ == "__main__":
    unittest.main()
