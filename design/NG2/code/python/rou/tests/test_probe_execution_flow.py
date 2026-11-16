from ipaddress import IPv4Address
import time
import unittest

from rou.availability_probe_manager import AvailabilityProbeManager
from rou.availability_probe_state import AvailabilityProbeState
from rou.availability_routing import AvailabilityWindowPolicy
from rou.interface_identity import InterfaceIdentity
from rou.linux_probe_execution import (
    LinuxProbeExecutionAgent,
    ProbeSendResult,
)
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


PATH = InterfaceIdentity("vpns00", 10)
TARGET = IPv4Address("203.0.113.24")


class RecordingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, value):
        self.events.append(value)


class ForwardingPublisher:
    def __init__(self):
        self.handler = None
        self.events = []

    def publish(self, value):
        self.events.append(value)
        if self.handler is not None:
            self.handler(value)


class FakeAdapter:
    def __init__(self):
        self.state = NetworkRulesState(
            StateKnowledge.UNKNOWN,
            None,
            fresh=False,
        )

    def apply(self, owner, spec: NetworkRulesSpec) -> ActionResult:
        self.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            spec,
            fresh=True,
        )
        return ActionResult(True)

    def renew_state(self, owner) -> ActionResult:
        return ActionResult(True)

    def get_last_state(self, owner) -> NetworkRulesState:
        return self.state

    def cleanup(self, owner) -> ActionResult:
        return ActionResult(True)


class FakeSendDriver:
    def __init__(self):
        self.result = ProbeSendResult(False)
        self.calls = []

    def execute_send(self, path, target, *, timeout_seconds):
        self.calls.append((path, target, timeout_seconds))
        return self.result


def request():
    return AvailabilityProbeSetRequest(
        (
            AvailabilityProbeRequest(
                "primary",
                PATH,
                TARGET,
                policy=AvailabilityWindowPolicy(10, 3),
            ),
        )
    )


class ProbeExecutionFlowTests(unittest.TestCase):
    def setUp(self):
        self.state_publisher = RecordingPublisher()
        self.plan_publisher = ForwardingPublisher()
        self.good_publisher = ForwardingPublisher()
        self.boundary_publisher = ForwardingPublisher()
        self.diagnostic_publisher = RecordingPublisher()
        self.driver = FakeSendDriver()

        self.agent = LinuxProbeExecutionAgent(
            self.driver,
            self.good_publisher,
            self.boundary_publisher,
            self.diagnostic_publisher,
            timeout_seconds=1,
            clock=lambda: 100.0,
        )
        self.manager = AvailabilityProbeManager(
            FakeAdapter(),
            self.state_publisher,
            execution_plan_publisher=self.plan_publisher,
        )

        self.plan_publisher.handler = self.agent.update_plan
        self.good_publisher.handler = self.manager.handle_good_news
        self.boundary_publisher.handler = self.manager.handle_window_boundary

    def wait_for_calls(self, count):
        deadline = time.monotonic() + 2
        while len(self.driver.calls) < count and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertGreaterEqual(len(self.driver.calls), count)

    def wait_for_state(self, state):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if any(item.state is state for item in self.state_publisher.events):
                return
            time.sleep(0.005)
        self.fail(f"state {state} was not published")

    def test_ready_manager_plan_drives_immediate_send_and_good_news_round_trip(self):
        self.driver.result = ProbeSendResult(True)

        self.manager.handle_request(request())
        self.agent.process_due(100.0)

        self.wait_for_calls(1)
        self.wait_for_state(AvailabilityProbeState.REACHABLE)

        self.assertEqual(len(self.plan_publisher.events), 1)
        self.assertIsNotNone(self.plan_publisher.events[0])
        self.assertEqual(len(self.good_publisher.events), 1)
        self.assertEqual(
            self.good_publisher.events[0].generation,
            self.manager.observation_generation,
        )

    def test_no_reply_never_crosses_execution_event_boundary(self):
        self.driver.result = ProbeSendResult(False)

        self.manager.handle_request(request())
        self.agent.process_due(100.0)
        self.wait_for_calls(1)

        self.assertEqual(self.good_publisher.events, [])
        self.assertFalse(
            any(
                item.state is AvailabilityProbeState.UNREACHABLE
                for item in self.state_publisher.events
            )
        )

        self.agent.process_due(130.0)

        self.wait_for_state(AvailabilityProbeState.UNREACHABLE)
        self.assertEqual(len(self.boundary_publisher.events), 1)
        self.assertEqual(
            self.boundary_publisher.events[0].elapsed_intervals,
            3,
        )

    def test_physical_generation_change_quiesces_old_plan_before_replacement(self):
        self.manager.handle_request(request())
        first = self.plan_publisher.events[-1]

        changed = AvailabilityProbeSetRequest(
            (
                AvailabilityProbeRequest(
                    "primary",
                    PATH,
                    IPv4Address("203.0.113.25"),
                    policy=AvailabilityWindowPolicy(10, 3),
                ),
            )
        )
        self.plan_publisher.events.clear()

        self.manager.handle_request(changed)

        self.assertEqual(len(self.plan_publisher.events), 2)
        self.assertIsNone(self.plan_publisher.events[0])
        replacement = self.plan_publisher.events[1]
        self.assertIsNotNone(replacement)
        self.assertNotEqual(replacement.generation, first.generation)
        self.assertEqual(
            replacement.planes[0].target,
            IPv4Address("203.0.113.25"),
        )


if __name__ == "__main__":
    unittest.main()
