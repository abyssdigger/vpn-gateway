from ipaddress import IPv4Network
import unittest

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
        self.renew_owners = []
        self.get_owners = []
        self.cleanup_owners = []

    def apply(self, owner, spec: NetworkRulesSpec) -> ActionResult:
        self.apply_owners.append(owner)
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
        request = _request(self.path)

        # Materialize once, then make a later apply operation fail while fresh observation
        # still shows the requested rules.
        self.manager.handle_request(request)
        self.publisher.events.clear()
        self.adapter.apply_success = False

        self.manager.handle_request(request)

        self.assertEqual(len(self.adapter.renew_owners), 1)
        self.assertEqual(len(self.publisher.events), 0)

    def test_semantically_unchanged_info_is_not_republished(self):
        request = _request(self.path)

        self.manager.handle_request(request)
        self.manager.handle_request(request)

        self.assertEqual(len(self.publisher.events), 1)
        self.assertEqual(len(self.adapter.apply_owners), 2)

    def test_changed_observation_is_published(self):
        request = _request(self.path)
        self.manager.handle_request(request)

        self.adapter.apply_success = False
        self.adapter.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            NetworkRulesSpec(),
            fresh=True,
        )
        self.manager.handle_request(request)

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


if __name__ == "__main__":
    unittest.main()
