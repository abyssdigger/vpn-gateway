from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.availability_probe_state import (
    AvailabilityProbeState,
    AvailabilityProbeStateInfo,
    ProbeObservationGeneration,
)
from rou.availability_routing import AvailabilityWindowPolicy
from rou.interface_identity import InterfaceIdentity
from rou.payload_rules import (
    PayloadDirection,
    PayloadPath,
    PayloadProfileRequest,
    PayloadTrafficStateRequest,
)
from rou.payload_traffic_intent import ProfileProbeAssignment
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
)
from rou.runtime_state_manager import RuntimeStateManager


A = InterfaceIdentity("a0", 10)
B = InterfaceIdentity("b0", 11)
C = InterfaceIdentity("c0", 12)
D = InterfaceIdentity("d0", 13)


class RecordingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, request):
        self.events.append(request)


def payload(order):
    return PayloadTrafficStateRequest(
        (
            PayloadProfileRequest(
                "corp",
                PayloadDirection.OUTBOUND,
                (IPv4Network("10.0.0.0/8"),),
                tuple(PayloadPath(identity) for identity in order),
            ),
        )
    )


def probe(probe_id, path, target, *, enabled=True):
    return AvailabilityProbeRequest(
        probe_id,
        path,
        IPv4Address(target),
        enabled=enabled,
        policy=AvailabilityWindowPolicy(10, 3),
    )


def probe_set(*items):
    return AvailabilityProbeSetRequest(tuple(items))


def identities(request):
    return tuple(
        path.identity
        for path in request.profiles[0].ordered_paths
    )


class RuntimeStateManagerAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.publisher = RecordingPublisher()
        self.manager = RuntimeStateManager(self.publisher)
        self.generation = ProbeObservationGeneration(1)
        self.probes = probe_set(
            probe("a", A, "203.0.113.10"),
            probe("b", B, "203.0.113.11"),
            probe("c", C, "203.0.113.12"),
            probe("d", D, "203.0.113.13"),
        )
        self.assignments = (
            ProfileProbeAssignment(
                "corp",
                ("a", "b", "c", "d"),
            ),
        )

    def update(self, configured=None, probes=None, assignments=None):
        self.manager.update_payload_routing_inputs(
            configured or payload((A, B, C, D)),
            probes or self.probes,
            assignments or self.assignments,
        )

    def state(self, probe_id, state):
        return AvailabilityProbeStateInfo(
            probe_id,
            state,
            observation_generation=(
                self.generation
                if state is not AvailabilityProbeState.UNKNOWN
                else None
            ),
        )

    def test_initial_active_probe_set_publishes_zero_live_boundary(self):
        self.update()

        self.assertEqual(len(self.publisher.events), 1)
        effective = self.publisher.events[-1]
        self.assertEqual(identities(effective), (A, B, C, D))
        self.assertEqual(
            effective.profiles[0].confirmed_live_prefix_length,
            0,
        )

    def test_reachable_probe_events_bubble_live_paths(self):
        self.update()
        self.publisher.events.clear()

        self.manager.handle_probe_state(
            self.state("b", AvailabilityProbeState.REACHABLE)
        )
        self.manager.handle_probe_state(
            self.state("c", AvailabilityProbeState.REACHABLE)
        )

        self.assertEqual(
            [identities(item) for item in self.publisher.events],
            [
                (B, A, C, D),
                (B, C, A, D),
            ],
        )
        self.assertEqual(
            self.publisher.events[-1].profiles[
                0
            ].confirmed_live_prefix_length,
            2,
        )

    def test_loss_of_all_live_evidence_preserves_current_order(self):
        self.update()
        self.manager.handle_probe_state(
            self.state("b", AvailabilityProbeState.REACHABLE)
        )
        self.manager.handle_probe_state(
            self.state("c", AvailabilityProbeState.REACHABLE)
        )
        self.publisher.events.clear()

        self.manager.handle_probe_state(
            self.state("b", AvailabilityProbeState.UNREACHABLE)
        )
        self.manager.handle_probe_state(
            self.state("c", AvailabilityProbeState.UNREACHABLE)
        )

        self.assertEqual(
            identities(self.publisher.events[-1]),
            (C, B, A, D),
        )
        self.assertEqual(
            self.publisher.events[-1].profiles[
                0
            ].confirmed_live_prefix_length,
            0,
        )

    def test_disabling_all_assigned_probes_rebases_to_configured_order(self):
        self.update()
        self.manager.handle_probe_state(
            self.state("b", AvailabilityProbeState.REACHABLE)
        )
        self.manager.handle_probe_state(
            self.state("c", AvailabilityProbeState.REACHABLE)
        )

        disabled = probe_set(
            probe("a", A, "203.0.113.10", enabled=False),
            probe("b", B, "203.0.113.11", enabled=False),
            probe("c", C, "203.0.113.12", enabled=False),
            probe("d", D, "203.0.113.13", enabled=False),
        )
        self.publisher.events.clear()

        self.update(probes=disabled)

        effective = self.publisher.events[-1]
        self.assertEqual(identities(effective), (A, B, C, D))
        self.assertIsNone(
            effective.profiles[0].confirmed_live_prefix_length
        )

    def test_configured_priority_change_rebases_before_current_live_evidence(self):
        self.update()
        self.manager.handle_probe_state(
            self.state("b", AvailabilityProbeState.REACHABLE)
        )
        self.manager.handle_probe_state(
            self.state("c", AvailabilityProbeState.REACHABLE)
        )
        self.publisher.events.clear()

        self.update(configured=payload((D, C, B, A)))

        self.assertEqual(
            identities(self.publisher.events[-1]),
            (C, B, D, A),
        )

    def test_changed_probe_definition_invalidates_cached_positive_evidence(self):
        self.update()
        self.manager.handle_probe_state(
            self.state("b", AvailabilityProbeState.REACHABLE)
        )
        self.assertEqual(
            identities(self.publisher.events[-1]),
            (B, A, C, D),
        )

        changed = probe_set(
            probe("a", A, "203.0.113.10"),
            probe("b", B, "203.0.113.99"),
            probe("c", C, "203.0.113.12"),
            probe("d", D, "203.0.113.13"),
        )
        self.publisher.events.clear()

        self.update(probes=changed)

        effective = self.publisher.events[-1]
        self.assertEqual(identities(effective), (B, A, C, D))
        self.assertEqual(
            effective.profiles[0].confirmed_live_prefix_length,
            0,
        )

    def test_removed_probe_state_event_cannot_change_current_payload(self):
        self.update()
        without_b = probe_set(
            probe("a", A, "203.0.113.10"),
            probe("c", C, "203.0.113.12"),
            probe("d", D, "203.0.113.13"),
        )
        assignments = (
            ProfileProbeAssignment(
                "corp",
                ("a", "c", "d"),
            ),
        )
        self.update(probes=without_b, assignments=assignments)
        self.publisher.events.clear()

        self.manager.handle_probe_state(
            self.state("b", AvailabilityProbeState.REACHABLE)
        )

        self.assertEqual(self.publisher.events, [])

    def test_duplicate_latest_probe_state_is_idempotent(self):
        self.update()
        reachable = self.state(
            "b",
            AvailabilityProbeState.REACHABLE,
        )

        self.manager.handle_probe_state(reachable)
        self.publisher.events.clear()
        self.manager.handle_probe_state(reachable)

        self.assertEqual(self.publisher.events, [])


if __name__ == "__main__":
    unittest.main()
