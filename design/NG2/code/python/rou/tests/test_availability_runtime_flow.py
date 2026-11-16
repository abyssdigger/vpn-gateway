from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.availability_probe_manager import AvailabilityProbeManager
from rou.availability_routing import AvailabilityWindowPolicy
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
from rou.payload_traffic_intent import ProfileProbeAssignment
from rou.payload_traffic_manager import PayloadTrafficManager
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
)
from rou.runtime_state_manager import RuntimeStateManager


A = InterfaceIdentity("a0", 10)
B = InterfaceIdentity("b0", 11)
C = InterfaceIdentity("c0", 12)


class FakeAdapter:
    def __init__(self):
        self.state = NetworkRulesState(
            StateKnowledge.UNKNOWN,
            None,
            fresh=False,
        )
        self.apply_specs = []
        self.apply_hook = None

    def apply(self, owner, spec):
        self.apply_specs.append(spec)
        hook = self.apply_hook
        self.apply_hook = None
        if hook is not None:
            hook()
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


class RecordingPayloadStatePublisher:
    def __init__(self):
        self.events = []

    def publish(self, info):
        self.events.append(info)


class PayloadRequestBridge:
    def __init__(self, manager):
        self.manager = manager
        self.events = []

    def publish(self, request):
        self.events.append(request)
        self.manager.handle_request(request)


class ProbeStateBridge:
    def __init__(self, runtime):
        self.runtime = runtime
        self.events = []

    def publish(self, info):
        self.events.append(info)
        self.runtime.handle_probe_state(info)


def payload():
    return PayloadTrafficStateRequest(
        (
            PayloadProfileRequest(
                "corp",
                PayloadDirection.OUTBOUND,
                (IPv4Network("10.0.0.0/8"),),
                (
                    PayloadPath(A),
                    PayloadPath(B),
                    PayloadPath(C),
                ),
            ),
        )
    )


def probe(probe_id, path, target):
    return AvailabilityProbeRequest(
        probe_id,
        path,
        IPv4Address(target),
        policy=AvailabilityWindowPolicy(10, 3),
    )


def probes():
    return AvailabilityProbeSetRequest(
        (
            probe("a", A, "203.0.113.10"),
            probe("b", B, "203.0.113.11"),
            probe("c", C, "203.0.113.12"),
        )
    )


class AvailabilityRuntimeFlowTests(unittest.TestCase):
    def setUp(self):
        self.payload_adapter = FakeAdapter()
        self.payload_state_publisher = RecordingPayloadStatePublisher()
        self.payload_manager = PayloadTrafficManager(
            self.payload_adapter,
            self.payload_state_publisher,
        )
        self.payload_bridge = PayloadRequestBridge(
            self.payload_manager
        )
        self.runtime = RuntimeStateManager(self.payload_bridge)

        self.probe_adapter = FakeAdapter()
        self.probe_bridge = ProbeStateBridge(self.runtime)
        self.probe_manager = AvailabilityProbeManager(
            self.probe_adapter,
            self.probe_bridge,
        )

        self.probe_request = probes()
        self.assignments = (
            ProfileProbeAssignment(
                "corp",
                ("a", "b", "c"),
            ),
        )

        self.runtime.update_payload_routing_inputs(
            payload(),
            self.probe_request,
            self.assignments,
        )
        self.probe_manager.handle_request(self.probe_request)

    def routing_projection(self):
        return [
            (
                spec.routing_domains[0].ordered_paths,
                spec.routing_domains[
                    0
                ].confirmed_live_prefix_length,
            )
            for spec in self.payload_adapter.apply_specs
        ]

    def test_good_news_during_active_payload_apply_is_coalesced_after_transaction(self):
        generation = self.probe_manager.observation_generation

        def c_recovers_during_b_transaction():
            matched = self.probe_manager.note_good_news(
                C,
                IPv4Address("203.0.113.12"),
                generation,
            )
            self.assertEqual(matched, 1)

        self.payload_adapter.apply_hook = (
            c_recovers_during_b_transaction
        )

        matched = self.probe_manager.note_good_news(
            B,
            IPv4Address("203.0.113.11"),
            generation,
        )

        self.assertEqual(matched, 1)
        self.assertEqual(
            self.routing_projection(),
            [
                ((A, B, C), 0),
                ((B, A, C), 1),
                ((B, C, A), 2),
            ],
        )
        self.assertEqual(
            self.payload_adapter.state.rules.routing_domains[
                0
            ].ordered_paths,
            (B, C, A),
        )

    def test_failure_window_demotes_without_removing_path(self):
        generation = self.probe_manager.observation_generation
        self.probe_manager.note_good_news(
            B,
            IPv4Address("203.0.113.11"),
            generation,
        )

        # Close the successful window, then three complete windows without
        # good news. No semantic per-attempt NO_REPLY exists.
        self.probe_manager.close_interval("b", generation)
        self.probe_manager.close_interval("b", generation)
        self.probe_manager.close_interval("b", generation)
        self.probe_manager.close_interval("b", generation)

        last_paths, live_prefix = self.routing_projection()[-1]
        self.assertEqual(last_paths, (B, A, C))
        self.assertEqual(live_prefix, 0)
        self.assertEqual(set(last_paths), {A, B, C})


if __name__ == "__main__":
    unittest.main()
