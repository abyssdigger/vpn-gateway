from itertools import permutations
import unittest

from rou.linux_route_priority import (
    plan_route_slot_moves,
    route_slots,
)


class RouteSlotsTests(unittest.TestCase):
    def test_gap_is_implicit_before_first_nonconfirmed_path(self):
        self.assertEqual(
            route_slots(("A", "B", "C", "D"), 2),
            ("A", "B", None, "C", "D"),
        )

    def test_all_live_has_only_trailing_working_gap(self):
        self.assertEqual(
            route_slots(("A", "B", "C"), 3),
            ("A", "B", "C", None),
        )

    def test_all_nonconfirmed_begin_at_second_metric_position(self):
        self.assertEqual(
            route_slots(("A", "B", "C"), 0),
            (None, "A", "B", "C"),
        )


class RouteSlotPlannerTests(unittest.TestCase):
    def assert_plan(self, current, desired, expected=None):
        moves = plan_route_slot_moves(current, desired)
        work = list(current)
        original = set(item for item in current if item is not None)
        for move in moves:
            self.assertIsNone(work[move.target_slot])
            self.assertEqual(work[move.source_slot], move.path)

            work[move.target_slot] = move.path
            self.assertEqual(
                set(item for item in work if item is not None),
                original,
            )
            self.assertEqual(
                len([item for item in work if item is not None]),
                len(original) + 1,
            )

            work[move.source_slot] = None
            self.assertEqual(
                set(item for item in work if item is not None),
                original,
            )

        self.assertEqual(tuple(work), desired)
        if expected is not None:
            self.assertEqual(
                tuple(
                    (move.path, move.source_slot, move.target_slot)
                    for move in moves
                ),
                expected,
            )

    def test_recovery_moves_gap_right_without_special_case(self):
        self.assert_plan(
            ("A", "B", "G", "D", None, "V", "E", "J"),
            ("A", "B", "V", "G", "D", None, "E", "J"),
            (
                ("D", 3, 4),
                ("G", 2, 3),
                ("V", 5, 2),
            ),
        )

    def test_recovery_shifts_dead_path_left_of_recovered_path_down(self):
        self.assert_plan(
            ("A", "B", "G", "D", None, "E", "V", "J"),
            ("A", "B", "V", "G", "D", None, "E", "J"),
            (
                ("D", 3, 4),
                ("G", 2, 3),
                ("V", 6, 2),
                ("E", 5, 6),
            ),
        )

    def test_last_dead_path_recovery_uses_trailing_working_position(self):
        self.assert_plan(
            ("A", "B", "G", "D", "E", "J", None, "V"),
            ("A", "B", "V", "G", "D", "E", "J", None),
            (
                ("J", 5, 6),
                ("E", 4, 5),
                ("D", 3, 4),
                ("G", 2, 3),
                ("V", 7, 2),
            ),
        )

    def test_death_moves_gap_left(self):
        self.assert_plan(
            ("B", "V", "G", None, "A", "D"),
            ("B", "V", None, "G", "A", "D"),
            (("G", 2, 3),),
        )

    def test_all_live_reorder_opens_and_closes_cycle(self):
        self.assert_plan(
            ("A", "B", "C", "D", None),
            ("C", "A", "B", "D", None),
            (
                ("A", 0, 4),
                ("C", 2, 0),
                ("B", 1, 2),
                ("A", 4, 1),
            ),
        )

    def test_noop(self):
        self.assertEqual(
            plan_route_slot_moves(("A", None, "B"), ("A", None, "B")),
            (),
        )

    def test_rejects_membership_change(self):
        with self.assertRaisesRegex(ValueError, "different paths"):
            plan_route_slot_moves(
                ("A", None, "B"),
                ("A", None, "C"),
            )

    def test_exhaustive_small_permutations_preserve_full_path_set(self):
        for path_count in range(1, 5):
            items = tuple(range(path_count)) + (None,)
            layouts = tuple(permutations(items))
            expected_paths = set(range(path_count))

            for current in layouts:
                for desired in layouts:
                    work = list(current)
                    moves = plan_route_slot_moves(current, desired)

                    for move in moves:
                        self.assertIsNone(work[move.target_slot])
                        self.assertEqual(work[move.source_slot], move.path)

                        work[move.target_slot] = move.path
                        materialized = [
                            item for item in work
                            if item is not None
                        ]
                        self.assertEqual(set(materialized), expected_paths)
                        self.assertEqual(len(materialized), path_count + 1)
                        self.assertEqual(
                            sum(materialized.count(path) == 2 for path in expected_paths),
                            1,
                        )

                        work[move.source_slot] = None
                        self.assertEqual(
                            set(item for item in work if item is not None),
                            expected_paths,
                        )
                        self.assertEqual(work.count(None), 1)

                    self.assertEqual(tuple(work), desired)


if __name__ == "__main__":
    unittest.main()
