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
from rou.probe_attempt import ProbeAttemptOutcome, ProbeAttemptResult
from rou.probe_rules import AvailabilityProbeRequest, AvailabilityProbeSetRequest


class RecordingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, info):
        self.events.append(info)


class FakeDriver:
    def __init__(self):
        self.result = ProbeAttemptResult(ProbeAttemptOutcome.REPLY)

    def execute(self, request, *, timeout_seconds):
        return self.result


class FakeAdapter:
    def __init__(self):
        self.state = NetworkRulesState(
            StateKnowledge.UNKNOWN,
            None,
            fresh=False,
        )

    def apply(self, owner, spec):
        self.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            spec,
            fresh=True,
        )
        return ActionResult(True)

    def renew_state(self, owner):
        return ActionResult(True)

    def get_last_state(self, owner):
        return self.state

    def cleanup(self, owner):
        return ActionResult(True)


def probe():
    return AvailabilityProbeRequest(
        "primary",
        InterfaceIdentity("vpns00", 10),
        IPv4Address("203.0.113.24"),
    )


class AvailabilityVerdictPolicyTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeAdapter()
        self.publisher = RecordingPublisher()
        self.driver = FakeDriver()
        self.manager = AvailabilityProbeManager(
            self.adapter,
            self.publisher,
            self.driver,
        )
        self.manager.handle_request(
            AvailabilityProbeSetRequest((probe(),))
        )
        self.publisher.events.clear()

    def test_reply_publishes_reachable_with_current_generation(self):
        info = self.manager.evaluate_once(
            "primary",
            timeout_seconds=1,
        )

        self.assertIsNotNone(info)
        self.assertIs(info.state, AvailabilityProbeState.REACHABLE)
        self.assertIsNotNone(info.observation_generation)
        self.assertEqual(self.publisher.events, [info])

    def test_no_reply_publishes_unreachable_with_current_generation(self):
        self.driver.result = ProbeAttemptResult(
            ProbeAttemptOutcome.NO_REPLY
        )

        info = self.manager.evaluate_once(
            "primary",
            timeout_seconds=1,
        )

        self.assertIsNotNone(info)
        self.assertIs(info.state, AvailabilityProbeState.UNREACHABLE)
        self.assertIsNotNone(info.observation_generation)
        self.assertEqual(self.publisher.events, [info])

    def test_local_error_publishes_unknown_without_generation(self):
        self.driver.result = ProbeAttemptResult(
            ProbeAttemptOutcome.ERROR,
            "local execution failure",
        )

        info = self.manager.evaluate_once(
            "primary",
            timeout_seconds=1,
        )

        self.assertIsNotNone(info)
        self.assertIs(info.state, AvailabilityProbeState.UNKNOWN)
        self.assertIsNone(info.observation_generation)
        self.assertIn("local probe execution error", info.reason)
        self.assertEqual(self.publisher.events, [info])

    def test_ready_audit_preserves_authoritative_verdict_same_generation(self):
        reachable = self.manager.evaluate_once(
            "primary",
            timeout_seconds=1,
        )
        self.publisher.events.clear()

        self.manager.audit()

        self.assertEqual(self.publisher.events, [])

        again = self.manager.evaluate_once(
            "primary",
            timeout_seconds=1,
        )
        self.assertEqual(again, reachable)
        self.assertEqual(self.publisher.events, [])

    def test_new_rules_generation_invalidates_old_verdict(self):
        reachable = self.manager.evaluate_once(
            "primary",
            timeout_seconds=1,
        )
        self.publisher.events.clear()

        replacement = AvailabilityProbeRequest(
            "primary",
            InterfaceIdentity("vpns00", 11),
            IPv4Address("203.0.113.24"),
        )
        self.manager.handle_request(
            AvailabilityProbeSetRequest((replacement,))
        )

        self.assertEqual(len(self.publisher.events), 1)
        invalidated = self.publisher.events[0]
        self.assertIs(invalidated.state, AvailabilityProbeState.UNKNOWN)
        self.assertIsNone(invalidated.observation_generation)
        self.assertGreater(
            self.manager.observation_generation.sequence,
            reachable.observation_generation.sequence,
        )

    def test_invalid_post_attempt_rules_do_not_publish_remote_verdict(self):
        def drift():
            self.adapter.state = NetworkRulesState(
                StateKnowledge.KNOWN,
                NetworkRulesSpec(),
                fresh=True,
            )

        original_execute = self.driver.execute

        def execute_with_drift(request, *, timeout_seconds):
            result = original_execute(
                request,
                timeout_seconds=timeout_seconds,
            )
            drift()
            return result

        self.driver.execute = execute_with_drift

        info = self.manager.evaluate_once(
            "primary",
            timeout_seconds=1,
        )

        self.assertIsNone(info)
        self.assertEqual(len(self.publisher.events), 1)
        self.assertIs(
            self.publisher.events[0].state,
            AvailabilityProbeState.UNKNOWN,
        )
        self.assertEqual(
            self.publisher.events[0].reason,
            "probe rules are not ready",
        )


if __name__ == "__main__":
    unittest.main()
