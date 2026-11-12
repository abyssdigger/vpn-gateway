from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.availability import (
    AvailabilityPolicy,
    AvailabilityTrackerState,
    ProbeOutcome,
)
from rou.availability_supervision import (
    DetectorEvidenceMissing,
    DetectorEvidenceStale,
    DetectorFreshnessPolicy,
    DetectorSupervisionError,
    TimedProbeSample,
    reconcile_supervised_availability,
    require_fresh_evidence,
)
from rou.device_engine import InterfaceIdentity


class AvailabilitySupervisionTests(unittest.TestCase):
    def setUp(self):
        self.identity = InterfaceIdentity("vpns00", 10)
        self.policy = DetectorFreshnessPolicy(max_age_seconds=5.0)

    def test_fresh_sample_is_returned(self):
        result = require_fresh_evidence(
            (self.identity,),
            {
                self.identity: TimedProbeSample(
                    ProbeOutcome.SUCCESS,
                    monotonic_time=7.0,
                )
            },
            now_monotonic=10.0,
            policy=self.policy,
        )
        self.assertEqual(
            result.outcomes[self.identity],
            ProbeOutcome.SUCCESS,
        )

    def test_sample_exactly_at_age_limit_is_fresh(self):
        result = require_fresh_evidence(
            (self.identity,),
            {
                self.identity: TimedProbeSample(
                    ProbeOutcome.FAILURE,
                    monotonic_time=5.0,
                )
            },
            now_monotonic=10.0,
            policy=self.policy,
        )
        self.assertEqual(
            result.outcomes[self.identity],
            ProbeOutcome.FAILURE,
        )

    def test_missing_current_generation_is_explicit_error(self):
        with self.assertRaises(DetectorEvidenceMissing):
            require_fresh_evidence(
                (self.identity,),
                {},
                now_monotonic=10.0,
                policy=self.policy,
            )

    def test_stale_sample_is_explicit_error(self):
        with self.assertRaisesRegex(
            DetectorEvidenceStale,
            "age=6.000000s",
        ):
            require_fresh_evidence(
                (self.identity,),
                {
                    self.identity: TimedProbeSample(
                        ProbeOutcome.SUCCESS,
                        monotonic_time=4.0,
                    )
                },
                now_monotonic=10.0,
                policy=self.policy,
            )

    def test_future_sample_timestamp_is_rejected(self):
        with self.assertRaisesRegex(
            DetectorSupervisionError,
            "future",
        ):
            require_fresh_evidence(
                (self.identity,),
                {
                    self.identity: TimedProbeSample(
                        ProbeOutcome.SUCCESS,
                        monotonic_time=11.0,
                    )
                },
                now_monotonic=10.0,
                policy=self.policy,
            )

    def test_same_name_new_ifindex_does_not_inherit_old_sample(self):
        fresh = InterfaceIdentity("vpns00", 11)
        with self.assertRaises(DetectorEvidenceMissing):
            require_fresh_evidence(
                (fresh,),
                {
                    self.identity: TimedProbeSample(
                        ProbeOutcome.SUCCESS,
                        monotonic_time=10.0,
                    )
                },
                now_monotonic=10.0,
                policy=self.policy,
            )

    def test_samples_for_disappeared_generations_are_ignored(self):
        result = require_fresh_evidence(
            (),
            {
                self.identity: TimedProbeSample(
                    ProbeOutcome.FAILURE,
                    monotonic_time=0.0,
                )
            },
            now_monotonic=100.0,
            policy=self.policy,
        )
        self.assertEqual(dict(result.outcomes), {})

    def test_duplicate_observed_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate identity"):
            require_fresh_evidence(
                (self.identity, self.identity),
                {},
                now_monotonic=10.0,
                policy=self.policy,
            )

    def test_nonpositive_freshness_policy_is_rejected(self):
        for value in (0.0, -1.0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    DetectorFreshnessPolicy(value)

    def test_supervised_reconcile_advances_only_from_fresh_evidence(self):
        availability_policy = AvailabilityPolicy(
            failure_threshold=2,
            recovery_threshold=2,
        )
        first = reconcile_supervised_availability(
            AvailabilityTrackerState.empty(),
            (self.identity,),
            {
                self.identity: TimedProbeSample(
                    ProbeOutcome.FAILURE,
                    monotonic_time=9.0,
                )
            },
            now_monotonic=10.0,
            freshness_policy=self.policy,
            availability_policy=availability_policy,
        )
        second = reconcile_supervised_availability(
            first.next_state,
            (self.identity,),
            {
                self.identity: TimedProbeSample(
                    ProbeOutcome.FAILURE,
                    monotonic_time=10.0,
                )
            },
            now_monotonic=10.0,
            freshness_policy=self.policy,
            availability_policy=availability_policy,
        )

        self.assertEqual(
            first.availability[self.identity].value,
            "unknown",
        )
        self.assertEqual(
            second.availability[self.identity].value,
            "unavailable",
        )

    def test_supervised_reconcile_rejects_stale_before_hysteresis(self):
        availability_policy = AvailabilityPolicy(
            failure_threshold=1,
            recovery_threshold=1,
        )
        previous = AvailabilityTrackerState.empty()

        with self.assertRaises(DetectorEvidenceStale):
            reconcile_supervised_availability(
                previous,
                (self.identity,),
                {
                    self.identity: TimedProbeSample(
                        ProbeOutcome.FAILURE,
                        monotonic_time=0.0,
                    )
                },
                now_monotonic=10.0,
                freshness_policy=self.policy,
                availability_policy=availability_policy,
            )

        self.assertEqual(dict(previous.by_interface), {})

    def test_supervised_reconcile_requires_current_generation_sample(self):
        availability_policy = AvailabilityPolicy(
            failure_threshold=1,
            recovery_threshold=1,
        )
        fresh = InterfaceIdentity("vpns00", 11)

        with self.assertRaises(DetectorEvidenceMissing):
            reconcile_supervised_availability(
                AvailabilityTrackerState.empty(),
                (fresh,),
                {
                    self.identity: TimedProbeSample(
                        ProbeOutcome.SUCCESS,
                        monotonic_time=10.0,
                    )
                },
                now_monotonic=10.0,
                freshness_policy=self.policy,
                availability_policy=availability_policy,
            )

    def test_nonfinite_numeric_values_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(policy=value):
                with self.assertRaises(ValueError):
                    DetectorFreshnessPolicy(value)
            with self.subTest(sample=value):
                with self.assertRaises(ValueError):
                    TimedProbeSample(
                        ProbeOutcome.SUCCESS,
                        monotonic_time=value,
                    )
            with self.subTest(now=value):
                with self.assertRaises(ValueError):
                    require_fresh_evidence(
                        (),
                        {},
                        now_monotonic=value,
                        policy=self.policy,
                    )

    def test_boolean_numeric_values_are_rejected(self):
        with self.assertRaises(ValueError):
            DetectorFreshnessPolicy(True)
        with self.assertRaises(ValueError):
            TimedProbeSample(
                ProbeOutcome.SUCCESS,
                monotonic_time=False,
            )
        with self.assertRaises(ValueError):
            require_fresh_evidence(
                (),
                {},
                now_monotonic=True,
                policy=self.policy,
            )

    def test_probe_sample_requires_typed_outcome(self):
        with self.assertRaisesRegex(ValueError, "ProbeOutcome"):
            TimedProbeSample(
                "success",  # type: ignore[arg-type]
                monotonic_time=1.0,
            )

    def test_negative_monotonic_values_are_rejected(self):
        with self.assertRaises(ValueError):
            TimedProbeSample(
                ProbeOutcome.SUCCESS,
                monotonic_time=-1.0,
            )
        with self.assertRaises(ValueError):
            require_fresh_evidence(
                (),
                {},
                now_monotonic=-1.0,
                policy=self.policy,
            )


if __name__ == "__main__":
    unittest.main()
