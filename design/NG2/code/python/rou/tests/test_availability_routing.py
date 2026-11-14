import unittest

from rou.availability_routing import (
    AvailabilityWindowPolicy,
    AvailabilityWindowState,
    calculate_effective_path_order,
)
from rou.interface_identity import InterfaceIdentity


A = InterfaceIdentity("vpns00", 10)
B = InterfaceIdentity("vpns01", 11)
C = InterfaceIdentity("wg0", 12)
D = InterfaceIdentity("oc0", 13)


class AvailabilityWindowPolicyTests(unittest.TestCase):
    def test_minimal_policy_accepts_interval_failure_count_and_disable(self):
        policy = AvailabilityWindowPolicy(
            interval_seconds=10,
            failure_intervals=3,
            enabled=False,
        )

        self.assertEqual(policy.interval_seconds, 10)
        self.assertEqual(policy.failure_intervals, 3)
        self.assertFalse(policy.enabled)

    def test_policy_rejects_invalid_values(self):
        for interval in (0, -1, float("inf"), float("nan"), True):
            with self.subTest(interval=interval):
                with self.assertRaises(ValueError):
                    AvailabilityWindowPolicy(interval, 1)

        for failures in (0, -1, 1.5, True):
            with self.subTest(failures=failures):
                with self.assertRaises(ValueError):
                    AvailabilityWindowPolicy(10, failures)

        with self.assertRaises(ValueError):
            AvailabilityWindowPolicy(10, 1, enabled=1)


class AvailabilityWindowStateTests(unittest.TestCase):
    def test_good_news_immediately_confirms_live_and_resets_sadness(self):
        state = AvailabilityWindowState(
            confirmed_live=False,
            missed_intervals=2,
        )

        state.note_good_news()

        self.assertTrue(state.confirmed_live)
        self.assertEqual(state.missed_intervals, 0)
        self.assertTrue(state.good_news_since_boundary)

    def test_missing_windows_use_integral_hysteresis(self):
        state = AvailabilityWindowState()
        policy = AvailabilityWindowPolicy(10, 3)

        state.note_good_news()
        state.close_interval(policy)
        self.assertTrue(state.confirmed_live)

        self.assertFalse(state.close_interval(policy))
        self.assertEqual(state.missed_intervals, 1)
        self.assertTrue(state.confirmed_live)

        self.assertFalse(state.close_interval(policy))
        self.assertEqual(state.missed_intervals, 2)
        self.assertTrue(state.confirmed_live)

        self.assertTrue(state.close_interval(policy))
        self.assertEqual(state.missed_intervals, 3)
        self.assertFalse(state.confirmed_live)

    def test_good_news_cancels_incomplete_negative_integral(self):
        state = AvailabilityWindowState(confirmed_live=True)
        policy = AvailabilityWindowPolicy(10, 3)

        state.close_interval(policy)
        state.close_interval(policy)
        self.assertEqual(state.missed_intervals, 2)

        state.note_good_news()
        self.assertEqual(state.missed_intervals, 0)
        self.assertTrue(state.confirmed_live)

        state.close_interval(policy)
        self.assertEqual(state.missed_intervals, 0)
        self.assertTrue(state.confirmed_live)


class EffectivePathOrderTests(unittest.TestCase):
    def test_no_confirmed_live_path_preserves_current_order(self):
        current = (C, B, A, D)

        self.assertEqual(
            calculate_effective_path_order(
                (A, B, C, D),
                current,
                frozenset(),
            ),
            current,
        )

    def test_live_paths_bubble_in_configured_priority(self):
        self.assertEqual(
            calculate_effective_path_order(
                (A, B, C, D),
                (A, B, C, D),
                frozenset((B, C)),
            ),
            (B, C, A, D),
        )

    def test_non_live_tail_preserves_current_relative_order(self):
        self.assertEqual(
            calculate_effective_path_order(
                (A, B, C, D),
                (C, B, A, D),
                frozenset((B,)),
            ),
            (B, C, A, D),
        )

    def test_recovered_higher_priority_live_path_returns_to_top(self):
        self.assertEqual(
            calculate_effective_path_order(
                (A, B, C, D),
                (B, C, A, D),
                frozenset((A, B, C)),
            ),
            (A, B, C, D),
        )

    def test_unknown_live_path_is_rejected(self):
        foreign = InterfaceIdentity("foreign0", 99)

        with self.assertRaises(ValueError):
            calculate_effective_path_order(
                (A, B),
                (A, B),
                frozenset((foreign,)),
            )


if __name__ == "__main__":
    unittest.main()
