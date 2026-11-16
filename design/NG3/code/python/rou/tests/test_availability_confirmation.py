from __future__ import annotations

import unittest

from rou.availability_confirmation import (
    AvailabilityConfirmationState,
    AvailabilityOutcome,
    apply_availability_evidence,
)


class AvailabilityConfirmationTests(unittest.TestCase):
    def test_negative_evidence_establishes_problem_at_threshold(self):
        state = AvailabilityConfirmationState()
        state = apply_availability_evidence(
            state, AvailabilityOutcome.NEGATIVE,
            degradation_threshold=2, recovery_threshold=2,
        )
        self.assertEqual(state.degradation_progress, 1)
        self.assertFalse(state.availability_problem)
        state = apply_availability_evidence(
            state, AvailabilityOutcome.NEGATIVE,
            degradation_threshold=2, recovery_threshold=2,
        )
        self.assertEqual(state, AvailabilityConfirmationState(availability_problem=True))

    def test_positive_clears_degradation_progress(self):
        state = AvailabilityConfirmationState(degradation_progress=1)
        next_state = apply_availability_evidence(
            state, AvailabilityOutcome.POSITIVE,
            degradation_threshold=3, recovery_threshold=2,
        )
        self.assertEqual(next_state, AvailabilityConfirmationState())

    def test_positive_evidence_recovers_at_threshold(self):
        state = AvailabilityConfirmationState(availability_problem=True)
        state = apply_availability_evidence(
            state, AvailabilityOutcome.POSITIVE,
            degradation_threshold=2, recovery_threshold=2,
        )
        self.assertEqual(state.recovery_progress, 1)
        state = apply_availability_evidence(
            state, AvailabilityOutcome.POSITIVE,
            degradation_threshold=2, recovery_threshold=2,
        )
        self.assertEqual(state, AvailabilityConfirmationState())

    def test_negative_clears_recovery_progress(self):
        state = AvailabilityConfirmationState(
            availability_problem=True,
            recovery_progress=1,
        )
        next_state = apply_availability_evidence(
            state, AvailabilityOutcome.NEGATIVE,
            degradation_threshold=2, recovery_threshold=3,
        )
        self.assertEqual(next_state, AvailabilityConfirmationState(availability_problem=True))

    def test_no_evidence_is_neutral(self):
        states = (
            AvailabilityConfirmationState(degradation_progress=1),
            AvailabilityConfirmationState(availability_problem=True, recovery_progress=1),
        )
        for state in states:
            with self.subTest(state=state):
                self.assertIs(
                    apply_availability_evidence(
                        state, AvailabilityOutcome.NO_EVIDENCE,
                        degradation_threshold=3, recovery_threshold=3,
                    ),
                    state,
                )

    def test_thresholds_are_positive_integers(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    apply_availability_evidence(
                        AvailabilityConfirmationState(), AvailabilityOutcome.NEGATIVE,
                        degradation_threshold=value, recovery_threshold=1,
                    )


if __name__ == "__main__":
    unittest.main()
