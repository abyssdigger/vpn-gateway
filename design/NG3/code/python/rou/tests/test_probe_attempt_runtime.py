from __future__ import annotations

from ipaddress import IPv4Address
import unittest

from rou.availability_confirmation import (
    AvailabilityConfirmationState,
)
from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import ProbePolicyOwner
from rou.probe_attempt_runtime import (
    ProbeAttemptPreconditions,
    ProbeAttemptStatus,
    ProbeSubjectRuntimeState,
    run_probe_attempt_once,
)
from rou.probe_policy import AvailabilityProbeIntent
from rou.probe_runtime import (
    AvailabilityProbeAgent,
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)


PATH = LogicalPathId("device", 0, 0)
EP = InterfaceIdentity("vpn0", 10)
TARGET = IPv4Address("198.51.100.7")
INTENT = AvailabilityProbeIntent(
    ProbePolicyOwner("corp", PATH),
    TARGET,
)
READY = ProbeAttemptPreconditions(True, True)


class StaticDriver:
    def __init__(self, observation):
        self.observation = observation
        self.calls = []

    def check(self, context):
        self.calls.append(context)
        return self.observation


class ContextChangingDriver:
    def __init__(self, agent):
        self.agent = agent
        self.calls = []

    def check(self, context):
        self.calls.append(context)
        self.agent.configure(
            AvailabilityProbeIntent(
                ProbePolicyOwner("corp", PATH),
                IPv4Address("203.0.113.9"),
            ),
            EP,
        )
        return ProbeTechnicalObservation(
            ProbeTechnicalOutcome.REPLY
        )


class ProbeAttemptRuntimeTests(unittest.TestCase):
    def test_lower_preconditions_block_driver_execution(self):
        agent = AvailabilityProbeAgent()
        driver = StaticDriver(
            ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)
        )
        state = ProbeSubjectRuntimeState()

        result = run_probe_attempt_once(
            agent,
            driver,
            INTENT,
            EP,
            state,
            ProbeAttemptPreconditions(
                routing_confirmed=False,
                local_policy_confirmed=True,
            ),
            degradation_threshold=2,
            recovery_threshold=2,
        )

        self.assertEqual(
            result.status,
            ProbeAttemptStatus.PRECONDITION_FAILED,
        )
        self.assertEqual(driver.calls, [])
        self.assertEqual(result.next_state, state)

    def test_negative_evidence_advances_degradation_hysteresis(self):
        agent = AvailabilityProbeAgent()
        driver = StaticDriver(
            ProbeTechnicalObservation(
                ProbeTechnicalOutcome.NO_REPLY
            )
        )
        state = ProbeSubjectRuntimeState()

        first = run_probe_attempt_once(
            agent,
            driver,
            INTENT,
            EP,
            state,
            READY,
            degradation_threshold=2,
            recovery_threshold=2,
        )
        self.assertEqual(
            first.status,
            ProbeAttemptStatus.EVIDENCE_APPLIED,
        )
        self.assertFalse(first.availability_problem)
        self.assertFalse(first.next_state.availability_known)
        self.assertEqual(first.next_state.availability_label, "unknown")
        self.assertEqual(
            first.next_state.confirmation.degradation_progress,
            1,
        )

        second = run_probe_attempt_once(
            agent,
            driver,
            INTENT,
            EP,
            first.next_state,
            READY,
            degradation_threshold=2,
            recovery_threshold=2,
        )
        self.assertTrue(second.availability_problem)
        self.assertTrue(second.next_state.availability_known)
        self.assertEqual(
            second.next_state.availability_label,
            "not available",
        )
        self.assertEqual(
            second.next_state.confirmation.degradation_progress,
            0,
        )

    def test_positive_evidence_recovers_confirmed_problem(self):
        agent = AvailabilityProbeAgent()
        current = agent.configure(INTENT, EP)
        driver = StaticDriver(
            ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)
        )
        state = ProbeSubjectRuntimeState(
            AvailabilityConfirmationState(
                availability_problem=True,
                recovery_progress=1,
            ),
            context=current,
            availability_known=True,
        )
        result = run_probe_attempt_once(
            agent,
            driver,
            INTENT,
            EP,
            state,
            READY,
            degradation_threshold=2,
            recovery_threshold=2,
        )
        self.assertFalse(result.availability_problem)
        self.assertTrue(result.next_state.availability_known)
        self.assertEqual(result.next_state.availability_label, "available")

    def test_initial_positive_establishes_known_available(self):
        agent = AvailabilityProbeAgent()
        result = run_probe_attempt_once(
            agent,
            StaticDriver(
                ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)
            ),
            INTENT,
            EP,
            ProbeSubjectRuntimeState(),
            READY,
            degradation_threshold=2,
            recovery_threshold=2,
        )
        self.assertTrue(result.next_state.availability_known)
        self.assertEqual(result.next_state.availability_label, "available")

    def test_local_error_is_no_evidence_and_does_not_advance_state(self):
        agent = AvailabilityProbeAgent()
        current = agent.configure(INTENT, EP)
        driver = StaticDriver(
            ProbeTechnicalObservation(
                ProbeTechnicalOutcome.LOCAL_ERROR,
                "worker unavailable",
            )
        )
        state = ProbeSubjectRuntimeState(
            AvailabilityConfirmationState(
                degradation_progress=1
            ),
            context=current,
            availability_known=False,
        )
        result = run_probe_attempt_once(
            agent,
            driver,
            INTENT,
            EP,
            state,
            READY,
            degradation_threshold=3,
            recovery_threshold=2,
        )
        self.assertEqual(result.next_state, state)
        self.assertEqual(result.diagnostic, "worker unavailable")

    def test_context_change_during_driver_discards_late_reply(self):
        agent = AvailabilityProbeAgent()
        current = agent.configure(INTENT, EP)
        driver = ContextChangingDriver(agent)
        state = ProbeSubjectRuntimeState(
            AvailabilityConfirmationState(
                degradation_progress=1
            ),
            context=current,
            availability_known=False,
        )
        result = run_probe_attempt_once(
            agent,
            driver,
            INTENT,
            EP,
            state,
            READY,
            degradation_threshold=2,
            recovery_threshold=2,
        )
        self.assertEqual(
            result.status,
            ProbeAttemptStatus.STALE_RESULT_DISCARDED,
        )
        self.assertNotEqual(result.next_state, state)
        self.assertFalse(result.next_state.availability_known)
        self.assertEqual(result.next_state.availability_label, "unknown")
        self.assertEqual(
            result.next_state.confirmation,
            AvailabilityConfirmationState(),
        )
        self.assertEqual(
            result.next_state.context,
            agent.current_context,
        )
        self.assertIsNone(result.evidence)

    def test_target_change_resets_old_confirmed_problem_to_unknown(self):
        agent = AvailabilityProbeAgent()
        current = agent.configure(INTENT, EP)
        old = ProbeSubjectRuntimeState(
            AvailabilityConfirmationState(
                availability_problem=True,
            ),
            context=current,
            availability_known=True,
        )
        replacement = AvailabilityProbeIntent(
            ProbePolicyOwner("corp", PATH),
            IPv4Address("203.0.113.9"),
        )
        result = run_probe_attempt_once(
            agent,
            StaticDriver(
                ProbeTechnicalObservation(
                    ProbeTechnicalOutcome.LOCAL_ERROR,
                    "new target not ready",
                )
            ),
            replacement,
            EP,
            old,
            READY,
            degradation_threshold=2,
            recovery_threshold=2,
        )
        self.assertFalse(result.next_state.availability_known)
        self.assertEqual(result.next_state.availability_label, "unknown")
        self.assertFalse(
            result.next_state.confirmation.availability_problem
        )
        self.assertNotEqual(result.next_state.context, current)

    def test_ifindex_change_resets_known_available_to_unknown(self):
        agent = AvailabilityProbeAgent()
        current = agent.configure(INTENT, EP)
        old = ProbeSubjectRuntimeState(
            AvailabilityConfirmationState(),
            context=current,
            availability_known=True,
        )
        replacement = InterfaceIdentity("vpn0", 11)
        result = run_probe_attempt_once(
            agent,
            StaticDriver(
                ProbeTechnicalObservation(
                    ProbeTechnicalOutcome.LOCAL_ERROR,
                    "replacement path not ready",
                )
            ),
            INTENT,
            replacement,
            old,
            READY,
            degradation_threshold=2,
            recovery_threshold=2,
        )
        self.assertFalse(result.next_state.availability_known)
        self.assertEqual(result.next_state.availability_label, "unknown")
        self.assertEqual(
            result.next_state.confirmation,
            AvailabilityConfirmationState(),
        )

    def test_unchecked_preconditions_require_both_lower_owners(self):
        value = ProbeAttemptPreconditions(
            routing_confirmed=True,
            local_policy_confirmed=False,
        )
        self.assertFalse(value.confirmed)


if __name__ == "__main__":
    unittest.main()
