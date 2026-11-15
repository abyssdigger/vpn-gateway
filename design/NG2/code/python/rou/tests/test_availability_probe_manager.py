from ipaddress import IPv4Address
from threading import Event, Thread
import unittest

from rou.availability_probe_manager import AvailabilityProbeManager
from rou.availability_routing import AvailabilityWindowPolicy
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
from rou.probe_transport import (
    ProbeGoodNewsInfo,
    ProbeWindowBoundaryInfo,
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
        self.block_apply_number = None
        self.apply_entered = Event()
        self.apply_release = Event()
        self.apply_release.set()

    def apply(self, owner, spec: NetworkRulesSpec) -> ActionResult:
        self.apply_owners.append(owner)
        self.apply_specs.append(spec)
        if (
            self.block_apply_number is not None
            and len(self.apply_owners) == self.block_apply_number
        ):
            self.apply_entered.set()
            self.apply_release.wait(timeout=5)
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
        policy=AvailabilityWindowPolicy(10, 3),
    )


def request(*items: AvailabilityProbeRequest) -> AvailabilityProbeSetRequest:
    return AvailabilityProbeSetRequest(tuple(items))


class AvailabilityProbeManagerRulesTests(unittest.TestCase):
    def setUp(self):
        self.path = InterfaceIdentity("vpns00", 10)
        self.adapter = FakeAdapter()
        self.publisher = RecordingPublisher()
        self.execution_publisher = RecordingPublisher()
        self.manager = AvailabilityProbeManager(
            self.adapter,
            self.publisher,
            execution_plan_publisher=self.execution_publisher,
        )

    def test_first_ready_request_publishes_execution_plan(self):
        wanted = request(
            probe("primary", self.path, "203.0.113.24")
        )

        self.manager.handle_request(wanted)

        self.assertEqual(len(self.execution_publisher.events), 1)
        plan = self.execution_publisher.events[0]
        self.assertIsNotNone(plan)
        self.assertEqual(plan.generation, self.manager.observation_generation)
        self.assertEqual(len(plan.planes), 1)
        self.assertEqual(plan.windows[0].probe_id, "primary")

    def test_equivalent_request_does_not_republish_execution_plan(self):
        wanted = request(
            probe("primary", self.path, "203.0.113.24")
        )
        self.manager.handle_request(wanted)
        self.execution_publisher.events.clear()

        self.manager.handle_request(wanted)

        self.assertEqual(self.execution_publisher.events, [])

    def test_physical_generation_change_quiesces_before_new_plan(self):
        self.manager.handle_request(
            request(probe("primary", self.path, "203.0.113.24"))
        )
        first = self.execution_publisher.events[-1]
        self.execution_publisher.events.clear()

        self.manager.handle_request(
            request(probe("primary", self.path, "203.0.113.25"))
        )

        self.assertEqual(len(self.execution_publisher.events), 2)
        self.assertIsNone(self.execution_publisher.events[0])
        second = self.execution_publisher.events[1]
        self.assertIsNotNone(second)
        self.assertNotEqual(second.generation, first.generation)
        self.assertEqual(
            second.planes[0].target,
            IPv4Address("203.0.113.25"),
        )

    def test_logical_cadence_change_republishes_plan_without_generation_change(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))
        generation = self.manager.observation_generation
        self.execution_publisher.events.clear()

        changed = AvailabilityProbeRequest(
            primary.probe_id,
            primary.path,
            primary.target,
            policy=AvailabilityWindowPolicy(30, 2),
        )
        self.manager.handle_request(request(changed))

        self.assertEqual(self.manager.observation_generation, generation)
        self.assertEqual(len(self.execution_publisher.events), 1)
        changed_plan = self.execution_publisher.events[0]
        self.assertEqual(changed_plan.generation, generation)
        self.assertEqual(changed_plan.planes[0].interval_seconds, 30.0)
        self.assertEqual(changed_plan.windows[0].interval_seconds, 30.0)

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

    def test_disabling_only_probe_closes_physical_plane_and_epoch(self):
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
            policy=primary.policy,
        )
        self.manager.handle_request(request(disabled))

        self.assertIsNotNone(generation)
        self.assertEqual(len(self.adapter.apply_owners), apply_count + 1)
        self.assertIsNone(self.manager.observation_generation)
        self.assertEqual(self.adapter.state.rules, NetworkRulesSpec())
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNKNOWN,
        )
        self.assertEqual(
            self.publisher.events[0].reason,
            "probe disabled",
        )

    def test_reenable_recreates_plane_and_opens_new_epoch(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))
        first_generation = self.manager.observation_generation

        disabled = AvailabilityProbeRequest(
            primary.probe_id,
            primary.path,
            primary.target,
            enabled=False,
            policy=primary.policy,
        )
        self.manager.handle_request(request(disabled))
        self.assertIsNone(self.manager.observation_generation)
        self.assertEqual(
            self.publisher.events[-1].reason,
            "probe disabled",
        )

        apply_count = len(self.adapter.apply_owners)
        self.manager.handle_request(request(primary))

        self.assertEqual(len(self.adapter.apply_owners), apply_count + 1)
        second_generation = self.manager.observation_generation
        self.assertIsNotNone(second_generation)
        self.assertGreater(
            second_generation.sequence,
            first_generation.sequence,
        )
        self.assertIn(
            "no authoritative probe evidence",
            self.publisher.events[-1].reason,
        )

    def test_disabling_shared_probe_preserves_plane_and_epoch(self):
        first = probe("first", self.path, "203.0.113.24")
        second = probe("second", self.path, "203.0.113.24")
        self.manager.handle_request(request(first, second))
        generation = self.manager.observation_generation
        apply_count = len(self.adapter.apply_owners)
        self.publisher.events.clear()

        first_disabled = AvailabilityProbeRequest(
            first.probe_id,
            first.path,
            first.target,
            enabled=False,
            policy=first.policy,
        )
        self.manager.handle_request(request(first_disabled, second))

        self.assertEqual(self.manager.observation_generation, generation)
        self.assertEqual(len(self.adapter.apply_owners), apply_count)
        self.assertEqual(len(self.publisher.events), 1)
        self.assertEqual(self.publisher.events[0].probe_id, "first")
        self.assertEqual(self.publisher.events[0].reason, "probe disabled")

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

    def test_ready_generation_exposes_non_attempt_execution_plan(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))

        plan = self.manager.execution_plan

        self.assertIsNotNone(plan)
        self.assertEqual(plan.generation, self.manager.observation_generation)
        self.assertEqual(len(plan.planes), 1)
        self.assertEqual(plan.planes[0].path, self.path)
        self.assertEqual(plan.windows[0].probe_id, "primary")

    def test_no_ready_generation_exposes_no_execution_plan(self):
        primary = probe("primary", self.path, "203.0.113.24")
        disabled = AvailabilityProbeRequest(
            primary.probe_id,
            primary.path,
            primary.target,
            enabled=False,
            policy=primary.policy,
        )

        self.manager.handle_request(request(disabled))

        self.assertIsNone(self.manager.execution_plan)

    def test_generation_bound_execution_events_use_existing_evidence_logic(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))
        generation = self.manager.observation_generation
        self.publisher.events.clear()

        matched = self.manager.handle_good_news(
            ProbeGoodNewsInfo(
                primary.mechanism,
                primary.path,
                primary.target,
                generation,
            )
        )
        closed = self.manager.handle_window_boundary(
            ProbeWindowBoundaryInfo(
                primary.probe_id,
                generation,
            )
        )

        self.assertEqual(matched, 1)
        self.assertTrue(closed)
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.REACHABLE,
        )

    def test_good_news_immediately_publishes_reachable(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))
        generation = self.manager.observation_generation
        self.publisher.events.clear()

        matched = self.manager.note_good_news(
            self.path,
            primary.target,
            generation,
        )

        self.assertEqual(matched, 1)
        self.assertEqual(len(self.publisher.events), 1)
        info = self.publisher.events[0]
        self.assertEqual(info.probe_id, "primary")
        self.assertIs(info.state, AvailabilityProbeState.REACHABLE)
        self.assertEqual(info.observation_generation, generation)

    def test_no_good_news_uses_failure_interval_hysteresis(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))
        generation = self.manager.observation_generation
        self.publisher.events.clear()

        self.assertTrue(self.manager.close_interval("primary", generation))
        self.assertEqual(self.publisher.events, [])
        self.assertTrue(self.manager.close_interval("primary", generation))
        self.assertEqual(self.publisher.events, [])

        self.assertTrue(self.manager.close_interval("primary", generation))

        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNREACHABLE,
        )
        self.assertEqual(
            self.publisher.events[0].observation_generation,
            generation,
        )

    def test_good_news_resets_negative_integral(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))
        generation = self.manager.observation_generation
        self.publisher.events.clear()

        self.manager.note_good_news(
            self.path,
            primary.target,
            generation,
        )
        self.publisher.events.clear()

        self.manager.close_interval("primary", generation)
        self.manager.close_interval("primary", generation)
        self.assertEqual(self.publisher.events, [])

        self.manager.note_good_news(
            self.path,
            primary.target,
            generation,
        )
        self.assertEqual(self.publisher.events, [])

        self.manager.close_interval("primary", generation)
        self.manager.close_interval("primary", generation)
        self.manager.close_interval("primary", generation)
        self.assertEqual(self.publisher.events, [])
        self.manager.close_interval("primary", generation)

        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNREACHABLE,
        )

    def test_shared_physical_good_news_fans_out_to_enabled_consumers(self):
        first = probe("first", self.path, "203.0.113.24")
        second = probe("second", self.path, "203.0.113.24")
        self.manager.handle_request(request(first, second))
        generation = self.manager.observation_generation
        self.publisher.events.clear()

        matched = self.manager.note_good_news(
            self.path,
            first.target,
            generation,
        )

        self.assertEqual(matched, 2)
        self.assertEqual(
            {
                (item.probe_id, item.state)
                for item in self.publisher.events
            },
            {
                ("first", AvailabilityProbeState.REACHABLE),
                ("second", AvailabilityProbeState.REACHABLE),
            },
        )

    def test_generation_transition_serializes_concurrent_stale_good_news(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))
        stale = self.manager.observation_generation
        self.publisher.events.clear()

        self.adapter.block_apply_number = 2
        self.adapter.apply_release.clear()
        changed = probe("primary", self.path, "203.0.113.25")

        request_thread = Thread(
            target=self.manager.handle_request,
            args=(request(changed),),
        )
        request_thread.start()
        self.assertTrue(self.adapter.apply_entered.wait(timeout=2))

        result = []
        good_news_thread = Thread(
            target=lambda: result.append(
                self.manager.handle_good_news(
                    ProbeGoodNewsInfo(
                        primary.mechanism,
                        primary.path,
                        primary.target,
                        stale,
                    )
                )
            )
        )
        good_news_thread.start()

        self.assertTrue(good_news_thread.is_alive())

        self.adapter.apply_release.set()
        request_thread.join(timeout=2)
        good_news_thread.join(timeout=2)

        self.assertFalse(request_thread.is_alive())
        self.assertFalse(good_news_thread.is_alive())
        self.assertEqual(result, [0])
        self.assertNotEqual(self.manager.observation_generation, stale)
        self.assertFalse(
            any(
                item.state is AvailabilityProbeState.REACHABLE
                for item in self.publisher.events
            )
        )

    def test_stale_generation_good_news_and_boundary_are_ignored(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))
        stale = self.manager.observation_generation

        changed = probe("primary", self.path, "203.0.113.25")
        self.manager.handle_request(request(changed))
        current = self.manager.observation_generation
        self.assertNotEqual(stale, current)
        self.publisher.events.clear()

        self.assertEqual(
            self.manager.note_good_news(
                self.path,
                primary.target,
                stale,
            ),
            0,
        )
        self.assertFalse(
            self.manager.close_interval("primary", stale)
        )
        self.assertEqual(self.publisher.events, [])

    def test_logical_policy_change_resets_window_without_changing_rules_epoch(self):
        primary = probe("primary", self.path, "203.0.113.24")
        self.manager.handle_request(request(primary))
        generation = self.manager.observation_generation
        self.manager.note_good_news(
            self.path,
            primary.target,
            generation,
        )
        self.manager.close_interval("primary", generation)

        changed = AvailabilityProbeRequest(
            primary.probe_id,
            primary.path,
            primary.target,
            policy=AvailabilityWindowPolicy(10, 2),
        )
        self.publisher.events.clear()
        self.manager.handle_request(request(changed))

        self.assertEqual(self.manager.observation_generation, generation)
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNKNOWN,
        )

        self.publisher.events.clear()
        self.manager.close_interval("primary", generation)
        self.assertEqual(self.publisher.events, [])
        self.manager.close_interval("primary", generation)
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNREACHABLE,
        )

    def test_disabled_shared_consumer_does_not_receive_good_news(self):
        first = probe("first", self.path, "203.0.113.24")
        second = probe("second", self.path, "203.0.113.24")
        first_disabled = AvailabilityProbeRequest(
            first.probe_id,
            first.path,
            first.target,
            enabled=False,
            policy=first.policy,
        )
        self.manager.handle_request(request(first_disabled, second))
        generation = self.manager.observation_generation
        self.publisher.events.clear()

        matched = self.manager.note_good_news(
            self.path,
            second.target,
            generation,
        )

        self.assertEqual(matched, 1)
        self.assertEqual(len(self.publisher.events), 1)
        self.assertEqual(self.publisher.events[0].probe_id, "second")

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
        self.assertIsNone(self.execution_publisher.events[-1])
        self.assertEqual(len(self.adapter.cleanup_owners), 1)
        self.assertIs(self.adapter.cleanup_owners[0], self.manager)


if __name__ == "__main__":
    unittest.main()
