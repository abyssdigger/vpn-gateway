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
    def test_no_problems_preserves_configured_order(self):
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

    def test_all_problem_paths_preserve_configured_order(self):
        configured = (A, B, C)
        self.assertEqual(
            calculate_effective_path_order(configured, (C, A, B)),
            configured,
        )

    def test_recovery_restores_configured_position(self):
        configured = (A, B, C)
        degraded = calculate_effective_path_order(configured, (A,))
        recovered = calculate_effective_path_order(configured, ())
        self.assertEqual(degraded, (B, C, A))
        self.assertEqual(recovered, configured)

    def test_membership_is_unchanged(self):
        configured = (A, B, C, D)
        effective = calculate_effective_path_order(configured, (B, D))
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

    def test_problem_path_outside_membership_is_rejected(self):
        with self.assertRaisesRegex(AvailabilityPriorityError, "outside"):
            calculate_effective_path_order((A, B), (C,))


if __name__ == "__main__":
    unittest.main()
