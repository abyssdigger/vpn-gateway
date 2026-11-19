from __future__ import annotations

from ipaddress import IPv4Address
import unittest

from rou.availability_confirmation import AvailabilityOutcome
from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import ProbePolicyOwner
from rou.probe_policy import AvailabilityProbeIntent
from rou.probe_runtime import (
    AvailabilityProbeAgent,
    ProbeRuntimeError,
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)


A = LogicalPathId("device", 0, 0)
B = LogicalPathId("device", 0, 1)
EP_A1 = InterfaceIdentity("vpn0", 10)
EP_A2 = InterfaceIdentity("vpn0", 11)
TARGET_A = IPv4Address("198.51.100.7")
TARGET_B = IPv4Address("203.0.113.9")


def intent(profile="corp", path=A, target=TARGET_A):
    return AvailabilityProbeIntent(
        ProbePolicyOwner(profile, path),
        target,
    )


class ProbeRuntimeTests(unittest.TestCase):
    def test_same_context_reconfigure_preserves_generation(self):
        agent = AvailabilityProbeAgent()
        one = agent.configure(intent(), EP_A1)
        two = agent.configure(intent(), EP_A1)
        self.assertEqual(one, two)
        self.assertEqual(one.generation, 1)
        self.assertIs(agent.current_context, two)

    def test_target_change_invalidates_old_attempt(self):
        agent = AvailabilityProbeAgent()
        old = agent.configure(intent(target=TARGET_A), EP_A1)
        new = agent.configure(intent(target=TARGET_B), EP_A1)
        self.assertEqual(new.generation, old.generation + 1)
        self.assertIsNone(
            agent.accept_result(
                old,
                ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY),
            )
        )

    def test_same_name_new_ifindex_invalidates_old_attempt(self):
        agent = AvailabilityProbeAgent()
        old = agent.configure(intent(), EP_A1)
        new = agent.configure(intent(), EP_A2)
        self.assertNotEqual(old.endpoint, new.endpoint)
        self.assertGreater(new.generation, old.generation)
        self.assertIsNone(
            agent.accept_result(
                old,
                ProbeTechnicalObservation(ProbeTechnicalOutcome.NO_REPLY),
            )
        )

    def test_subject_change_invalidates_old_attempt(self):
        agent = AvailabilityProbeAgent()
        old = agent.configure(intent(profile="corp", path=A), EP_A1)
        new = agent.configure(intent(profile="guest", path=B), EP_A1)
        self.assertNotEqual(old.intent.owner, new.intent.owner)
        self.assertIsNone(
            agent.accept_result(
                old,
                ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY),
            )
        )

    def test_disable_then_same_reconfigure_gets_fresh_generation(self):
        agent = AvailabilityProbeAgent()
        old = agent.configure(intent(), EP_A1)
        agent.disable()
        self.assertIsNone(agent.current_context)
        with self.assertRaisesRegex(ProbeRuntimeError, "not configured"):
            agent.begin_attempt()
        new = agent.configure(intent(), EP_A1)
        self.assertGreater(new.generation, old.generation)
        self.assertIsNone(
            agent.accept_result(
                old,
                ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY),
            )
        )

    def test_current_reply_maps_to_positive(self):
        agent = AvailabilityProbeAgent()
        current = agent.configure(intent(), EP_A1)
        result = agent.accept_result(
            current,
            ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY),
        )
        self.assertEqual(result.outcome, AvailabilityOutcome.POSITIVE)
        self.assertIsNone(result.diagnostic)
        self.assertEqual(result.context, current)

    def test_current_no_reply_maps_to_negative(self):
        agent = AvailabilityProbeAgent()
        current = agent.configure(intent(), EP_A1)
        result = agent.accept_result(
            current,
            ProbeTechnicalObservation(ProbeTechnicalOutcome.NO_REPLY),
        )
        self.assertEqual(result.outcome, AvailabilityOutcome.NEGATIVE)
        self.assertIsNone(result.diagnostic)

    def test_current_local_error_maps_to_no_evidence(self):
        agent = AvailabilityProbeAgent()
        current = agent.configure(intent(), EP_A1)
        result = agent.accept_result(
            current,
            ProbeTechnicalObservation(
                ProbeTechnicalOutcome.LOCAL_ERROR,
                "icmp worker unavailable",
            ),
        )
        self.assertEqual(result.outcome, AvailabilityOutcome.NO_EVIDENCE)
        self.assertEqual(result.diagnostic, "icmp worker unavailable")

    def test_local_error_requires_diagnostic(self):
        with self.assertRaisesRegex(ProbeRuntimeError, "diagnostic"):
            ProbeTechnicalObservation(ProbeTechnicalOutcome.LOCAL_ERROR)

    def test_successful_technical_observation_rejects_diagnostic(self):
        with self.assertRaisesRegex(ProbeRuntimeError, "must not carry"):
            ProbeTechnicalObservation(
                ProbeTechnicalOutcome.REPLY,
                "unexpected",
            )


if __name__ == "__main__":
    unittest.main()
