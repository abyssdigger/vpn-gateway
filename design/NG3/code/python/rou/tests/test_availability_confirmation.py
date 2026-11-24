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

    def test_state_requires_strict_boolean_and_integer_progress(self):
        invalid = (
            {"availability_problem": 1},
            {"degradation_progress": True},
            {"degradation_progress": 0.5},
            {"recovery_progress": True, "availability_problem": True},
            {"recovery_progress": 0.5, "availability_problem": True},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    AvailabilityConfirmationState(**kwargs)

    def test_unknown_outcome_is_rejected_not_interpreted_as_evidence(self):
        with self.assertRaisesRegex(ValueError, "AvailabilityOutcome"):
            apply_availability_evidence(
                AvailabilityConfirmationState(),
                "negative",
                degradation_threshold=1,
                recovery_threshold=1,
            )

    def test_progress_outside_current_threshold_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exceeds"):
            apply_availability_evidence(
                AvailabilityConfirmationState(degradation_progress=3),
                AvailabilityOutcome.NO_EVIDENCE,
                degradation_threshold=2,
                recovery_threshold=2,
            )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            apply_availability_evidence(
                AvailabilityConfirmationState(
                    availability_problem=True,
                    recovery_progress=3,
                ),
                AvailabilityOutcome.NO_EVIDENCE,
                degradation_threshold=2,
                recovery_threshold=2,
            )


if __name__ == "__main__":
    unittest.main()
