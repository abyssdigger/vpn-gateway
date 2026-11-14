import unittest

from rou.availability_probe_policy import AvailabilityProbePolicy


class AvailabilityProbePolicyTests(unittest.TestCase):
    def test_accepts_positive_normalized_values(self):
        policy = AvailabilityProbePolicy(
            interval_seconds=10,
            retry_interval_seconds=1.5,
            timeout_seconds=2,
            failure_threshold=3,
            recovery_threshold=2,
        )

        self.assertEqual(policy.interval_seconds, 10)
        self.assertEqual(policy.retry_interval_seconds, 1.5)
        self.assertEqual(policy.timeout_seconds, 2)
        self.assertEqual(policy.failure_threshold, 3)
        self.assertEqual(policy.recovery_threshold, 2)

    def test_threshold_defaults_preserve_single_attempt_baseline(self):
        policy = AvailabilityProbePolicy(
            interval_seconds=10,
            retry_interval_seconds=1,
            timeout_seconds=1,
        )

        self.assertEqual(policy.failure_threshold, 1)
        self.assertEqual(policy.recovery_threshold, 1)

    def test_rejects_nonpositive_or_nonfinite_intervals(self):
        for value in (0, -1, float("inf"), float("nan"), True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AvailabilityProbePolicy(
                        interval_seconds=value,
                        retry_interval_seconds=1,
                        timeout_seconds=1,
                    )

    def test_rejects_invalid_timeout(self):
        for value in (0, -1, 1.5, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AvailabilityProbePolicy(
                        interval_seconds=10,
                        retry_interval_seconds=1,
                        timeout_seconds=value,
                    )

    def test_rejects_invalid_thresholds(self):
        for field in ("failure_threshold", "recovery_threshold"):
            for value in (0, -1, 1.5, True):
                kwargs = dict(
                    interval_seconds=10,
                    retry_interval_seconds=1,
                    timeout_seconds=1,
                )
                kwargs[field] = value
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        AvailabilityProbePolicy(**kwargs)


if __name__ == "__main__":
    unittest.main()
