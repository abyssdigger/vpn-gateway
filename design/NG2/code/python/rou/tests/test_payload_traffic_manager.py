from ipaddress import IPv4Address, IPv4Network
from threading import Event, Thread
import unittest

from rou.availability_collector import (
    AvailabilityGoodNews,
    AvailabilityHysteresisPolicy,
    AvailabilityPriorityChannel,
    AvailabilityPriorityConfig,
    AvailabilityTick,
    ProfileAvailabilityAssignment,
)
from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    ActionResult,
    NetworkRulesSpec,
    NetworkRulesState,
    StateKnowledge,
)
from rou.payload_rules import (
    PayloadDirection,
    PayloadPath,
    PayloadProfileRequest,
    PayloadTrafficStateRequest,
)
from rou.payload_rules_state import (
    Convergence,
    Knowledge,
    Safety,
    Service,
)
from rou.payload_traffic_manager import PayloadTrafficManager

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
        self.apply_hook = None
        self.renew_owners = []
        self.get_owners = []
        self.cleanup_owners = []

    def apply(self, owner, spec: NetworkRulesSpec) -> ActionResult:
        self.apply_owners.append(owner)
        self.apply_specs.append(spec)
        hook = self.apply_hook
        self.apply_hook = None
        if hook is not None:
            hook()
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


def _request(path: InterfaceIdentity) -> PayloadTrafficStateRequest:
    return PayloadTrafficStateRequest(
        (
            PayloadProfileRequest(
                "corp",
                PayloadDirection.OUTBOUND,
                (IPv4Network("10.0.0.0/8"),),
                (PayloadPath(path),),
            ),
        )
    )


class PayloadTrafficManagerTests(unittest.TestCase):
    def setUp(self):
        self.path = InterfaceIdentity("vpns00", 10)
        self.adapter = FakeAdapter()
        self.publisher = RecordingPublisher()
        self.manager = PayloadTrafficManager(
            self.adapter,
            self.publisher,
        )

    def test_invalid_request_does_not_mutate_adapter(self):
        invalid = PayloadTrafficStateRequest(
            (
                PayloadProfileRequest(
                    "a",
                    PayloadDirection.OUTBOUND,
                    (IPv4Network("10.0.0.0/8"),),
                    (PayloadPath(self.path),),
                ),
                PayloadProfileRequest(
                    "b",
                    PayloadDirection.OUTBOUND,
                    (IPv4Network("10.0.0.0/8"),),
                    (PayloadPath(self.path),),
                ),
            )
        )

        with self.assertRaises(ValueError):
            self.manager.handle_request(invalid)

        self.assertEqual(self.adapter.apply_owners, [])
        self.assertEqual(self.publisher.events, [])

    def test_request_uses_manager_instance_as_adapter_owner(self):
        result = self.manager.handle_request(_request(self.path))

        self.assertIsNone(result)
        self.assertIs(self.adapter.apply_owners[0], self.manager)
        self.assertIs(self.adapter.get_owners[0], self.manager)

    def test_successful_request_publishes_current_payload_state(self):
        self.manager.handle_request(_request(self.path))

        self.assertEqual(len(self.publisher.events), 1)
        info = self.publisher.events[0]
        self.assertIs(info.rules_state.knowledge, Knowledge.KNOWN)
        self.assertIs(info.rules_state.convergence, Convergence.MATCHED)
        self.assertIs(info.rules_state.safety, Safety.SAFE)
        self.assertIs(info.rules_state.service, Service.READY)
        self.assertEqual(
            info.profiles[0].observed_paths,
            (self.path,),
        )

    def test_apply_failure_refreshes_observation_before_interpretation(self):
        self.adapter.apply_success = False
        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )

        self.manager.handle_request(_request(self.path))

        self.assertEqual(len(self.adapter.renew_owners), 1)
        self.assertIs(self.adapter.renew_owners[0], self.manager)
        self.assertEqual(len(self.publisher.events), 1)
        info = self.publisher.events[0]
        self.assertIs(info.rules_state.convergence, Convergence.DIVERGED)
        self.assertIs(info.rules_state.safety, Safety.SAFE)
        self.assertIs(info.rules_state.service, Service.ISOLATED)

    def test_apply_and_refresh_failure_publish_unknown_observation_state(self):
        self.adapter.apply_success = False
        self.adapter.renew_success = False
        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=False,
        )

        self.manager.handle_request(_request(self.path))

        self.assertEqual(len(self.publisher.events), 1)
        info = self.publisher.events[0]
        self.assertIs(info.rules_state.knowledge, Knowledge.UNKNOWN)
        self.assertIs(info.rules_state.convergence, Convergence.UNKNOWN)
        self.assertIs(info.rules_state.safety, Safety.UNKNOWN)
        self.assertIs(info.rules_state.service, Service.UNKNOWN)
        self.assertIsNone(info.profiles[0].observed_paths)

    def test_apply_failure_does_not_force_failed_state(self):
        first = _request(self.path)
        second_path = InterfaceIdentity("vpns01", 11)
        second = _request(second_path)

        self.manager.handle_request(first)
        self.publisher.events.clear()
        self.adapter.apply_success = False

        self.manager.handle_request(second)

        self.assertEqual(len(self.adapter.renew_owners), 1)
        self.assertEqual(len(self.publisher.events), 1)
        info = self.publisher.events[-1]
        self.assertIs(info.rules_state.convergence, Convergence.DIVERGED)
        self.assertEqual(
            info.profiles[0].observed_paths,
            (self.path,),
        )

    def test_reentrant_superseding_requests_are_coalesced_after_active_apply(self):
        first = InterfaceIdentity("vpns00", 10)
        second = InterfaceIdentity("vpns01", 11)
        third = InterfaceIdentity("vpns02", 12)
        initial = _request(first)
        superseded = _request(second)
        latest = _request(third)

        def during_first_apply():
            self.manager.handle_request(superseded)
            self.manager.handle_request(latest)

        self.adapter.apply_hook = during_first_apply

        self.manager.handle_request(initial)

        self.assertEqual(len(self.adapter.apply_specs), 2)
        applied_paths = [
            spec.routing_domains[0].ordered_paths
            for spec in self.adapter.apply_specs
        ]
        self.assertEqual(
            applied_paths,
            [
                (first,),
                (third,),
            ],
        )
        self.assertEqual(
            self.adapter.get_last_state(self.manager).rules.routing_domains[
                0
            ].ordered_paths,
            (third,),
        )

    def test_concurrent_requests_share_one_transaction_executor(self):
        first = InterfaceIdentity("vpns00", 10)
        second = InterfaceIdentity("vpns01", 11)
        third = InterfaceIdentity("vpns02", 12)
        started = Event()
        release = Event()

        def block_first_apply():
            started.set()
            self.assertTrue(release.wait(2))

        self.adapter.apply_hook = block_first_apply
        worker = Thread(
            target=self.manager.handle_request,
            args=(_request(first),),
        )
        worker.start()
        self.assertTrue(started.wait(2))

        # These calls execute while the first Adapter.apply() is still blocked.
        # They must only replace pending desired state.
        self.manager.handle_request(_request(second))
        self.manager.handle_request(_request(third))

        release.set()
        worker.join(2)
        self.assertFalse(worker.is_alive())

        self.assertEqual(
            [
                spec.routing_domains[0].ordered_paths
                for spec in self.adapter.apply_specs
            ],
            [
                (first,),
                (third,),
            ],
        )

    def test_unexpected_apply_exception_releases_executor_ownership(self):
        first = _request(InterfaceIdentity("vpns00", 10))
        second = _request(InterfaceIdentity("vpns01", 11))

        def fail_once():
            raise RuntimeError("injected unexpected failure")

        self.adapter.apply_hook = fail_once

        with self.assertRaisesRegex(RuntimeError, "injected"):
            self.manager.handle_request(first)

        # A later event must be able to become executor rather than only queueing
        # forever behind the failed call.
        self.manager.handle_request(second)

        self.assertEqual(
            self.adapter.apply_specs[-1].routing_domains[0].ordered_paths,
            (InterfaceIdentity("vpns01", 11),),
        )

    def test_reentrant_audit_waits_until_active_apply_completes(self):
        request = _request(self.path)

        def during_apply():
            self.manager.audit()

        self.adapter.apply_hook = during_apply

        self.manager.handle_request(request)

        self.assertEqual(len(self.adapter.apply_specs), 1)
        self.assertEqual(len(self.adapter.renew_owners), 1)
        self.assertIs(self.adapter.renew_owners[0], self.manager)

    def test_reentrant_request_precedes_deferred_audit(self):
        first = InterfaceIdentity("vpns00", 10)
        second = InterfaceIdentity("vpns01", 11)
        initial = _request(first)
        latest = _request(second)

        def during_first_apply():
            self.manager.audit()
            self.manager.handle_request(latest)

        self.adapter.apply_hook = during_first_apply

        self.manager.handle_request(initial)

        self.assertEqual(
            [
                spec.routing_domains[0].ordered_paths
                for spec in self.adapter.apply_specs
            ],
            [
                (first,),
                (second,),
            ],
        )
        self.assertEqual(len(self.adapter.renew_owners), 1)

    def test_semantically_unchanged_info_is_not_republished(self):
        request = _request(self.path)

        self.manager.handle_request(request)
        self.manager.handle_request(request)

        self.assertEqual(len(self.publisher.events), 1)
        self.assertEqual(len(self.adapter.apply_owners), 1)

    def test_changed_observation_is_published(self):
        request = _request(self.path)
        self.manager.handle_request(request)

        self.adapter.apply_success = False
        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )
        self.manager.audit()

        self.assertEqual(len(self.publisher.events), 2)
        self.assertIs(
            self.publisher.events[-1].rules_state.service,
            Service.ISOLATED,
        )

    def test_audit_before_first_request_is_noop(self):
        self.manager.audit()

        self.assertEqual(self.adapter.renew_owners, [])
        self.assertEqual(self.adapter.apply_owners, [])
        self.assertEqual(self.publisher.events, [])

    def test_matched_audit_observes_without_reapplying(self):
        request = _request(self.path)
        self.manager.handle_request(request)
        initial_apply_count = len(self.adapter.apply_owners)
        self.publisher.events.clear()

        self.manager.audit()

        self.assertEqual(len(self.adapter.renew_owners), 1)
        self.assertEqual(len(self.adapter.apply_owners), initial_apply_count)
        self.assertEqual(self.publisher.events, [])

    def test_drift_audit_repairs_current_desired_without_new_request(self):
        request = _request(self.path)
        self.manager.handle_request(request)
        desired = self.adapter.state.rules
        initial_apply_count = len(self.adapter.apply_owners)
        self.publisher.events.clear()

        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )

        self.manager.audit()

        self.assertEqual(len(self.adapter.renew_owners), 1)
        self.assertEqual(
            len(self.adapter.apply_owners),
            initial_apply_count + 1,
        )
        self.assertEqual(self.publisher.events, [])
        self.assertEqual(self.adapter.state.rules, desired)

    def test_matched_isolated_intent_is_not_repaired_as_drift(self):
        request = PayloadTrafficStateRequest(
            (
                PayloadProfileRequest(
                    "corp",
                    PayloadDirection.OUTBOUND,
                    (IPv4Network("10.0.0.0/8"),),
                    (),
                ),
            )
        )
        self.manager.handle_request(request)
        initial_apply_count = len(self.adapter.apply_owners)
        self.publisher.events.clear()

        self.assertEqual(
            self.adapter.state.rules.routing_domains[0].ordered_paths,
            (),
        )
        self.manager.audit()

        self.assertEqual(len(self.adapter.apply_owners), initial_apply_count)
        self.assertEqual(self.publisher.events, [])

    def test_failed_drift_repair_publishes_observed_isolation(self):
        request = _request(self.path)
        self.manager.handle_request(request)
        self.publisher.events.clear()

        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )
        self.adapter.apply_success = False

        self.manager.audit()

        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].rules_state.service,
            Service.ISOLATED,
        )

    def test_recovery_after_failed_audit_publishes_ready_transition(self):
        request = _request(self.path)
        self.manager.handle_request(request)
        self.publisher.events.clear()

        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )
        self.adapter.apply_success = False
        self.manager.audit()

        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[-1].rules_state.service,
            Service.ISOLATED,
        )

        self.adapter.apply_success = True
        self.manager.audit()

        self.assertEqual(len(self.publisher.events), 2)
        self.assertIs(
            self.publisher.events[-1].rules_state.service,
            Service.READY,
        )
        self.assertIs(
            self.publisher.events[-1].rules_state.convergence,
            Convergence.MATCHED,
        )

    def test_unknown_audit_attempts_repair(self):
        request = _request(self.path)
        self.manager.handle_request(request)
        initial_apply_count = len(self.adapter.apply_owners)
        self.publisher.events.clear()

        self.adapter.renew_success = False
        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=False,
        )

        self.manager.audit()

        self.assertEqual(
            len(self.adapter.apply_owners),
            initial_apply_count + 1,
        )
        self.assertEqual(self.publisher.events, [])

    def test_shutdown_cleans_adapter_state_with_same_owner_identity(self):
        result = self.manager.shutdown()

        self.assertTrue(result.success)
        self.assertEqual(len(self.adapter.cleanup_owners), 1)
        self.assertIs(self.adapter.cleanup_owners[0], self.manager)


class PayloadTrafficAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.a = InterfaceIdentity("vpns00", 10)
        self.b = InterfaceIdentity("vpns01", 11)
        self.c = InterfaceIdentity("vpns02", 12)
        self.adapter = FakeAdapter()
        self.publisher = RecordingPublisher()
        self.manager = PayloadTrafficManager(self.adapter, self.publisher)
        self.policy = AvailabilityHysteresisPolicy(2, 3)

        self.payload = PayloadTrafficStateRequest(
            (
                PayloadProfileRequest(
                    "corp",
                    PayloadDirection.OUTBOUND,
                    (IPv4Network("10.0.0.0/8"),),
                    (
                        PayloadPath(self.a),
                        PayloadPath(self.b),
                        PayloadPath(self.c),
                    ),
                ),
            )
        )
        self.config = AvailabilityPriorityConfig(
            (
                AvailabilityPriorityChannel("a", self.a, True, self.policy),
                AvailabilityPriorityChannel("b", self.b, True, self.policy),
                AvailabilityPriorityChannel("c", self.c, True, self.policy),
            ),
            (
                ProfileAvailabilityAssignment("corp", ("a", "b", "c")),
            ),
        )

        self.manager.handle_request(self.payload)
        self.assertIsNone(
            self.adapter.state.rules.routing_domains[0].preferred_prefix_length
        )
        self.manager.configure_availability(self.config)

    def channel(self, channel_id):
        return next(
            item for item in self.config.channels
            if item.channel_id == channel_id
        )

    def order(self):
        return self.adapter.state.rules.routing_domains[0].ordered_paths

    def tick(self, channel_id):
        return self.manager.handle_availability_tick(
            AvailabilityTick(self.channel(channel_id))
        )

    def good(self, channel_id):
        return self.manager.handle_availability_good_news(
            AvailabilityGoodNews(self.channel(channel_id))
        )

    def test_inactive_availability_is_true_payload_noop(self):
        manager = PayloadTrafficManager(FakeAdapter(), RecordingPublisher())
        adapter = manager._adapter

        manager.handle_request(self.payload)

        domain = adapter.state.rules.routing_domains[0]
        self.assertEqual(domain.ordered_paths, (self.a, self.b, self.c))
        self.assertIsNone(domain.preferred_prefix_length)

    def test_active_availability_preserves_configured_order_initially(self):
        self.assertEqual(self.order(), (self.a, self.b, self.c))
        self.assertIsNone(
            self.adapter.state.rules.routing_domains[0].preferred_prefix_length
        )

    def test_failure_ticks_move_only_problem_path_down(self):
        self.tick("a")
        self.assertEqual(self.order(), (self.a, self.b, self.c))

        self.tick("a")

        self.assertEqual(self.order(), (self.b, self.c, self.a))
        self.assertEqual(
            self.adapter.state.rules.routing_domains[0].preferred_prefix_length,
            2,
        )

    def test_delayed_good_news_can_recover_in_one_materialization_cycle(self):
        self.tick("a")
        self.tick("a")
        self.assertEqual(self.order(), (self.b, self.c, self.a))

        self.good("a")
        self.good("a")
        self.good("a")

        self.assertEqual(self.order(), (self.a, self.b, self.c))
        self.assertIsNone(
            self.adapter.state.rules.routing_domains[0].preferred_prefix_length
        )

    def test_tick_without_good_news_breaks_partial_recovery(self):
        self.tick("a")
        self.tick("a")
        self.good("a")
        self.good("a")
        self.tick("a")
        self.tick("a")
        self.good("a")

        self.assertEqual(self.order(), (self.b, self.c, self.a))

    def test_disabled_channel_has_no_availability_problem_by_definition(self):
        self.tick("a")
        self.tick("a")
        self.assertEqual(self.order(), (self.b, self.c, self.a))

        disabled = AvailabilityPriorityConfig(
            tuple(
                AvailabilityPriorityChannel(
                    item.channel_id,
                    item.path,
                    item.channel_id != "a",
                    item.policy,
                )
                for item in self.config.channels
            ),
            self.config.assignments,
        )
        self.manager.configure_availability(disabled)

        self.assertEqual(self.order(), (self.a, self.b, self.c))

    def test_policy_change_preserves_problem_flag_but_resets_progress(self):
        self.tick("a")
        self.tick("a")
        self.good("a")
        self.good("a")

        changed_policy = AvailabilityHysteresisPolicy(5, 4)
        changed = AvailabilityPriorityConfig(
            tuple(
                AvailabilityPriorityChannel(
                    item.channel_id,
                    item.path,
                    item.enabled,
                    (
                        changed_policy
                        if item.channel_id == "a"
                        else item.policy
                    ),
                )
                for item in self.config.channels
            ),
            self.config.assignments,
        )
        self.manager.configure_availability(changed)
        self.config = changed

        self.assertEqual(self.order(), (self.b, self.c, self.a))

        for _ in range(3):
            self.good("a")
        self.assertEqual(self.order(), (self.b, self.c, self.a))

        self.good("a")
        self.assertEqual(self.order(), (self.a, self.b, self.c))

    def test_path_with_multiple_channels_is_problem_only_when_all_are_problem(self):
        extra = AvailabilityPriorityChannel(
            "a-secondary",
            self.a,
            True,
            self.policy,
        )
        config = AvailabilityPriorityConfig(
            self.config.channels + (extra,),
            (
                ProfileAvailabilityAssignment(
                    "corp",
                    ("a", "a-secondary", "b", "c"),
                ),
            ),
        )
        self.manager.configure_availability(config)
        self.config = config

        for _ in range(2):
            self.tick("a")
        self.assertEqual(self.order(), (self.a, self.b, self.c))

        for _ in range(2):
            self.tick("a-secondary")
        self.assertEqual(self.order(), (self.b, self.c, self.a))

    def test_stale_channel_descriptor_is_ignored_after_policy_change(self):
        stale = self.channel("a")
        changed = AvailabilityPriorityConfig(
            tuple(
                AvailabilityPriorityChannel(
                    item.channel_id,
                    item.path,
                    item.enabled,
                    (
                        AvailabilityHysteresisPolicy(7, 5)
                        if item.channel_id == "a"
                        else item.policy
                    ),
                )
                for item in self.config.channels
            ),
            self.config.assignments,
        )
        self.manager.configure_availability(changed)
        self.config = changed

        self.assertFalse(
            self.manager.handle_availability_good_news(
                AvailabilityGoodNews(stale)
            )
        )

    def test_availability_updates_share_existing_serial_executor(self):
        started = Event()
        release = Event()

        def block_apply():
            started.set()
            self.assertTrue(release.wait(2))

        self.adapter.apply_hook = block_apply
        worker = Thread(
            target=lambda: (
                self.tick("a"),
                self.tick("a"),
            )
        )
        worker.start()
        self.assertTrue(started.wait(2))

        self.good("b")
        self.tick("b")

        release.set()
        worker.join(2)
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
