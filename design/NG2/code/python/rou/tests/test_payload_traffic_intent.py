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
from rou.payload_traffic_intent import (
    PayloadTrafficIntentCalculator,
    ProbeProfileEvidenceCalculator,
    ProfileAvailabilityEvidence,
    ProfileProbeAssignment,
)
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
)


A = InterfaceIdentity("a0", 10)
B = InterfaceIdentity("b0", 11)
C = InterfaceIdentity("c0", 12)
D = InterfaceIdentity("d0", 13)


def request(
    order,
    *,
    name="corp",
    destination="10.0.0.0/8",
):
    return PayloadTrafficStateRequest(
        (
            PayloadProfileRequest(
                name,
                PayloadDirection.OUTBOUND,
                (IPv4Network(destination),),
                tuple(PayloadPath(identity) for identity in order),
            ),
        )
    )


def identities(wanted: PayloadTrafficStateRequest):
    return tuple(
        path.identity
        for path in wanted.profiles[0].ordered_paths
    )


class ProbeProfileEvidenceCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.calc = ProbeProfileEvidenceCalculator()
        self.generation = ProbeObservationGeneration(1)

    def probe(self, probe_id, path, target, *, enabled=True):
        return AvailabilityProbeRequest(
            probe_id,
            path,
            IPv4Address(target),
            enabled=enabled,
            policy=AvailabilityWindowPolicy(10, 3),
        )

    def test_only_reachable_enabled_probe_confirms_path(self):
        pri = self.probe("pri", A, "203.0.113.10")
        sec = self.probe("sec", B, "203.0.113.11")
        states = (
            AvailabilityProbeStateInfo(
                "pri",
                AvailabilityProbeState.UNREACHABLE,
                observation_generation=self.generation,
            ),
            AvailabilityProbeStateInfo(
                "sec",
                AvailabilityProbeState.REACHABLE,
                observation_generation=self.generation,
            ),
        )

        result = self.calc.calculate(
            AvailabilityProbeSetRequest((pri, sec)),
            states,
            (ProfileProbeAssignment("corp", ("pri", "sec")),),
        )

        self.assertEqual(
            result,
            (
                ProfileAvailabilityEvidence(
                    "corp",
                    frozenset((B,)),
                ),
            ),
        )

    def test_enabled_probe_without_state_keeps_active_empty_evidence(self):
        pri = self.probe("pri", A, "203.0.113.10")

        result = self.calc.calculate(
            AvailabilityProbeSetRequest((pri,)),
            (),
            (ProfileProbeAssignment("corp", ("pri",)),),
        )

        self.assertEqual(
            result,
            (
                ProfileAvailabilityEvidence(
                    "corp",
                    frozenset(),
                ),
            ),
        )

    def test_all_assigned_probes_disabled_make_boundary_inactive(self):
        pri = self.probe(
            "pri",
            A,
            "203.0.113.10",
            enabled=False,
        )

        result = self.calc.calculate(
            AvailabilityProbeSetRequest((pri,)),
            (
                AvailabilityProbeStateInfo(
                    "pri",
                    AvailabilityProbeState.UNKNOWN,
                    reason="probe disabled",
                ),
            ),
            (ProfileProbeAssignment("corp", ("pri",)),),
        )

        self.assertEqual(
            result,
            (
                ProfileAvailabilityEvidence("corp", None),
            ),
        )

    def test_one_logical_probe_may_feed_multiple_profiles(self):
        shared = self.probe("shared", A, "203.0.113.10")
        states = (
            AvailabilityProbeStateInfo(
                "shared",
                AvailabilityProbeState.REACHABLE,
                observation_generation=self.generation,
            ),
        )

        result = self.calc.calculate(
            AvailabilityProbeSetRequest((shared,)),
            states,
            (
                ProfileProbeAssignment("corp", ("shared",)),
                ProfileProbeAssignment("lab", ("shared",)),
            ),
        )

        self.assertEqual(
            result,
            (
                ProfileAvailabilityEvidence("corp", frozenset((A,))),
                ProfileAvailabilityEvidence("lab", frozenset((A,))),
            ),
        )

    def test_unknown_probe_assignment_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown probe_id"):
            self.calc.calculate(
                AvailabilityProbeSetRequest(()),
                (),
                (ProfileProbeAssignment("corp", ("missing",)),),
            )


class PayloadTrafficIntentCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.calc = PayloadTrafficIntentCalculator()
        self.configured = request((A, B, C, D))

    def evidence(self, *paths):
        return (
            ProfileAvailabilityEvidence(
                "corp",
                frozenset(paths),
            ),
        )

    def test_startup_bubbles_live_paths_in_configured_priority(self):
        effective = self.calc.calculate(
            self.configured,
            previous_configured=None,
            current_effective=None,
            availability=self.evidence(B, C),
        )

        self.assertEqual(identities(effective), (B, C, A, D))
        self.assertEqual(
            effective.profiles[0].confirmed_live_prefix_length,
            2,
        )

    def test_no_live_evidence_preserves_current_effective_order(self):
        current = request((B, C, A, D))

        effective = self.calc.calculate(
            self.configured,
            previous_configured=self.configured,
            current_effective=current,
            availability=self.evidence(),
        )

        self.assertEqual(identities(effective), (B, C, A, D))
        self.assertEqual(
            effective.profiles[0].confirmed_live_prefix_length,
            0,
        )

    def test_recovered_higher_priority_path_returns_to_top(self):
        current = request((B, C, A, D))

        effective = self.calc.calculate(
            self.configured,
            previous_configured=self.configured,
            current_effective=current,
            availability=self.evidence(A, B, C),
        )

        self.assertEqual(identities(effective), (A, B, C, D))
        self.assertEqual(
            effective.profiles[0].confirmed_live_prefix_length,
            3,
        )

    def test_inactive_availability_rebases_to_configured_order(self):
        current = request((B, C, A, D))

        effective = self.calc.calculate(
            self.configured,
            previous_configured=self.configured,
            current_effective=current,
            availability=(
                ProfileAvailabilityEvidence("corp", None),
            ),
        )

        self.assertEqual(identities(effective), (A, B, C, D))
        self.assertIsNone(
            effective.profiles[0].confirmed_live_prefix_length
        )

    def test_configured_priority_change_rebases_before_live_promotion(self):
        previous = self.configured
        current = request((B, C, A, D))
        changed = request((D, C, B, A))

        effective = self.calc.calculate(
            changed,
            previous_configured=previous,
            current_effective=current,
            availability=self.evidence(B, C),
        )

        self.assertEqual(identities(effective), (C, B, D, A))
        self.assertEqual(
            effective.profiles[0].confirmed_live_prefix_length,
            2,
        )

    def test_membership_change_rebases_before_live_promotion(self):
        previous = self.configured
        current = request((B, C, A, D))
        changed = request((A, B, D))

        effective = self.calc.calculate(
            changed,
            previous_configured=previous,
            current_effective=current,
            availability=self.evidence(B),
        )

        self.assertEqual(identities(effective), (B, A, D))
        self.assertEqual(
            effective.profiles[0].confirmed_live_prefix_length,
            1,
        )

    def test_single_path_remains_routed_when_unconfirmed(self):
        configured = request((A,))

        effective = self.calc.calculate(
            configured,
            previous_configured=configured,
            current_effective=configured,
            availability=self.evidence(),
        )

        self.assertEqual(identities(effective), (A,))
        self.assertEqual(
            effective.profiles[0].confirmed_live_prefix_length,
            0,
        )

    def test_noneligible_live_evidence_is_rejected(self):
        foreign = InterfaceIdentity("foreign0", 99)

        with self.assertRaisesRegex(ValueError, "non-eligible"):
            self.calc.calculate(
                self.configured,
                previous_configured=self.configured,
                current_effective=self.configured,
                availability=self.evidence(foreign),
            )

    def test_unknown_profile_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown Profile"):
            self.calc.calculate(
                self.configured,
                previous_configured=self.configured,
                current_effective=self.configured,
                availability=(
                    ProfileAvailabilityEvidence(
                        "foreign",
                        frozenset(),
                    ),
                ),
            )

    def test_missing_profile_evidence_means_inactive_availability(self):
        current = request((B, C, A, D))

        effective = self.calc.calculate(
            self.configured,
            previous_configured=self.configured,
            current_effective=current,
            availability=(),
        )

        self.assertEqual(identities(effective), (A, B, C, D))
        self.assertIsNone(
            effective.profiles[0].confirmed_live_prefix_length
        )


if __name__ == "__main__":
    unittest.main()
