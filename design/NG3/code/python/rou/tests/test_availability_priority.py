from __future__ import annotations

import unittest

from rou.availability_priority import (
    AvailabilityPriorityError,
    calculate_effective_path_order,
)
from rou.binding import LogicalPathId


A = LogicalPathId("oc", 0, 0)
B = LogicalPathId("oc", 0, 1)
C = LogicalPathId("wg", 0, 0)
D = LogicalPathId("wg", 1, 0)


class AvailabilityPriorityTests(unittest.TestCase):
    def test_no_state_preserves_configured_order(self):
        configured = (A, B, C)
        self.assertEqual(
            calculate_effective_path_order(configured, ()),
            configured,
        )

    def test_one_problem_moves_after_nonproblem_paths(self):
        self.assertEqual(
            calculate_effective_path_order((A, B, C), (A,)),
            (B, C, A),
        )

    def test_multiple_problems_preserve_relative_order_in_both_groups(self):
        self.assertEqual(
            calculate_effective_path_order((A, B, C, D), (D, B)),
            (A, C, B, D),
        )

    def test_recovery_does_not_preempt_healthy_ordinary_active_path(self):
        configured = (A, B, C)
        degraded = calculate_effective_path_order(
            configured,
            (A,),
            active_path=B,
        )
        recovered = calculate_effective_path_order(
            configured,
            (),
            active_path=B,
        )
        self.assertEqual(degraded, (B, C, A))
        self.assertEqual(recovered, (B, A, C))

    def test_ordinary_active_is_first_and_standby_keeps_baseline_order(self):
        self.assertEqual(
            calculate_effective_path_order(
                (A, B, C, D),
                (),
                active_path=C,
            ),
            (C, A, B, D),
        )

    def test_reserve_active_yields_to_higher_baseline_usable_path(self):
        self.assertEqual(
            calculate_effective_path_order(
                (A, B, C),
                (),
                active_path=B,
                reserve_device_ids=("oc",),
            ),
            (A, B, C),
        )

    def test_reserve_active_stays_first_when_all_higher_paths_have_problems(self):
        self.assertEqual(
            calculate_effective_path_order(
                (A, B, C),
                (A,),
                active_path=B,
                reserve_device_ids=("oc",),
            ),
            (B, C, A),
        )

    def test_problematic_active_loses_sticky_position(self):
        self.assertEqual(
            calculate_effective_path_order(
                (A, B, C),
                (B,),
                active_path=B,
            ),
            (A, C, B),
        )

    def test_all_problem_paths_preserve_configured_order(self):
        configured = (A, B, C)
        self.assertEqual(
            calculate_effective_path_order(
                configured,
                (C, A, B),
                active_path=B,
            ),
            configured,
        )

    def test_membership_is_unchanged(self):
        configured = (A, B, C, D)
        effective = calculate_effective_path_order(
            configured,
            (B, D),
            active_path=A,
            reserve_device_ids=("wg",),
        )
        self.assertEqual(set(effective), set(configured))
        self.assertEqual(len(effective), len(configured))

    def test_empty_membership_is_valid(self):
        self.assertEqual(calculate_effective_path_order((), ()), ())

    def test_duplicate_configured_path_is_rejected(self):
        with self.assertRaisesRegex(AvailabilityPriorityError, "duplicate"):
            calculate_effective_path_order((A, A), ())

    def test_duplicate_problem_path_is_rejected(self):
        with self.assertRaisesRegex(AvailabilityPriorityError, "duplicate"):
            calculate_effective_path_order((A, B), (A, A))

    def test_duplicate_reserve_device_is_rejected(self):
        with self.assertRaisesRegex(AvailabilityPriorityError, "duplicate"):
            calculate_effective_path_order(
                (A, B),
                (),
                reserve_device_ids=("oc", "oc"),
            )

    def test_problem_path_outside_membership_is_rejected(self):
        with self.assertRaisesRegex(AvailabilityPriorityError, "outside"):
            calculate_effective_path_order((A, B), (C,))

    def test_invalid_reserve_device_id_is_rejected(self):
        with self.assertRaisesRegex(AvailabilityPriorityError, "non-empty"):
            calculate_effective_path_order(
                (A, B),
                (),
                reserve_device_ids=("",),
            )

    def test_active_path_outside_membership_is_rejected(self):
        with self.assertRaisesRegex(AvailabilityPriorityError, "outside"):
            calculate_effective_path_order(
                (A, B),
                (),
                active_path=C,
            )


if __name__ == "__main__":
    unittest.main()
