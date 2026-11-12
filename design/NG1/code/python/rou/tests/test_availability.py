from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.availability import (
    AvailabilityPolicy,
    AvailabilityTrackerState,
    InterfaceAvailabilityState,
    ProbeOutcome,
    reconcile_availability,
)
from rou.device_engine import InterfaceIdentity
from rou.domain import Availability


class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.identity = InterfaceIdentity("vpns00", 10)
        self.policy = AvailabilityPolicy(
            failure_threshold=2,
            recovery_threshold=3,
        )

    def step(self, previous, outcome, identity=None):
        identity = identity or self.identity
        return reconcile_availability(
            previous,
            (identity,),
            {identity: outcome},
            self.policy,
        )

    def test_thresholds_are_mandatory_positive_values(self):
        with self.assertRaises(ValueError):
            AvailabilityPolicy(0, 1)
        with self.assertRaises(ValueError):
            AvailabilityPolicy(1, 0)

    def test_failure_hysteresis_reaches_unavailable_only_at_threshold(self):
        first = self.step(
            AvailabilityTrackerState.empty(),
            ProbeOutcome.FAILURE,
        )
        self.assertEqual(
            first.availability[self.identity],
            Availability.UNKNOWN,
        )

        second = self.step(
            first.next_state,
            ProbeOutcome.FAILURE,
        )
        self.assertEqual(
            second.availability[self.identity],
            Availability.UNAVAILABLE,
        )

    def test_recovery_hysteresis_requires_full_success_threshold(self):
        unavailable = AvailabilityTrackerState({
            self.identity: InterfaceAvailabilityState(
                availability=Availability.UNAVAILABLE,
                failure_streak=2,
            )
        })

        first = self.step(unavailable, ProbeOutcome.SUCCESS)
        second = self.step(first.next_state, ProbeOutcome.SUCCESS)
        third = self.step(second.next_state, ProbeOutcome.SUCCESS)

        self.assertEqual(
            first.availability[self.identity],
            Availability.UNAVAILABLE,
        )
        self.assertEqual(
            second.availability[self.identity],
            Availability.UNAVAILABLE,
        )
        self.assertEqual(
            third.availability[self.identity],
            Availability.AVAILABLE,
        )

    def test_failure_after_available_requires_failure_threshold(self):
        available = AvailabilityTrackerState({
            self.identity: InterfaceAvailabilityState(
                availability=Availability.AVAILABLE,
                success_streak=3,
            )
        })

        first = self.step(available, ProbeOutcome.FAILURE)
        second = self.step(first.next_state, ProbeOutcome.FAILURE)

        self.assertEqual(
            first.availability[self.identity],
            Availability.AVAILABLE,
        )
        self.assertEqual(
            second.availability[self.identity],
            Availability.UNAVAILABLE,
        )

    def test_streaks_saturate_at_policy_thresholds(self):
        available = AvailabilityTrackerState({
            self.identity: InterfaceAvailabilityState(
                availability=Availability.AVAILABLE,
                success_streak=self.policy.recovery_threshold,
            )
        })
        still_available = self.step(available, ProbeOutcome.SUCCESS)
        self.assertEqual(
            still_available.next_state.by_interface[
                self.identity
            ].success_streak,
            self.policy.recovery_threshold,
        )

        unavailable = AvailabilityTrackerState({
            self.identity: InterfaceAvailabilityState(
                availability=Availability.UNAVAILABLE,
                failure_streak=self.policy.failure_threshold,
            )
        })
        still_unavailable = self.step(
            unavailable,
            ProbeOutcome.FAILURE,
        )
        self.assertEqual(
            still_unavailable.next_state.by_interface[
                self.identity
            ].failure_streak,
            self.policy.failure_threshold,
        )

    def test_indeterminate_preserves_state_and_streaks(self):
        previous = AvailabilityTrackerState({
            self.identity: InterfaceAvailabilityState(
                availability=Availability.UNKNOWN,
                failure_streak=1,
            )
        })
        result = self.step(previous, ProbeOutcome.INDETERMINATE)
        self.assertEqual(
            result.next_state.by_interface[self.identity],
            previous.by_interface[self.identity],
        )

    def test_missing_evidence_is_indeterminate(self):
        previous = AvailabilityTrackerState({
            self.identity: InterfaceAvailabilityState(
                availability=Availability.UNAVAILABLE,
                failure_streak=2,
            )
        })
        result = reconcile_availability(
            previous,
            (self.identity,),
            {},
            self.policy,
        )
        self.assertEqual(
            result.availability[self.identity],
            Availability.UNAVAILABLE,
        )

    def test_disappearing_generation_is_forgotten(self):
        previous = AvailabilityTrackerState({
            self.identity: InterfaceAvailabilityState(
                availability=Availability.UNAVAILABLE,
                failure_streak=2,
            )
        })
        result = reconcile_availability(
            previous,
            (),
            {},
            self.policy,
        )
        self.assertEqual(dict(result.next_state.by_interface), {})
        self.assertEqual(dict(result.availability), {})

    def test_same_name_new_ifindex_starts_unknown(self):
        previous = AvailabilityTrackerState({
            self.identity: InterfaceAvailabilityState(
                availability=Availability.UNAVAILABLE,
                failure_streak=2,
            )
        })
        fresh = InterfaceIdentity("vpns00", 11)
        result = reconcile_availability(
            previous,
            (fresh,),
            {},
            self.policy,
        )
        self.assertEqual(
            result.availability[fresh],
            Availability.UNKNOWN,
        )
        self.assertNotIn(self.identity, result.next_state.by_interface)

    def test_evidence_for_unobserved_generation_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "unobserved interface generation",
        ):
            reconcile_availability(
                AvailabilityTrackerState.empty(),
                (),
                {self.identity: ProbeOutcome.SUCCESS},
                self.policy,
            )

    def test_duplicate_observed_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate identity"):
            reconcile_availability(
                AvailabilityTrackerState.empty(),
                (self.identity, self.identity),
                {},
                self.policy,
            )


if __name__ == "__main__":
    unittest.main()
