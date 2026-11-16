from itertools import permutations
import unittest

from rou.linux_route_priority import (
    plan_route_slot_moves,
    route_slots,
)


class RouteSlotsTests(unittest.TestCase):
    def test_gap_precedes_first_nonconfirmed_path(self):
        self.assertEqual(
            route_slots(("A", "B", "G", "D", "V", "E", "J"), 4),
            ("A", "B", "G", "D", None, "V", "E", "J"),
        )

    def test_all_live_has_only_trailing_working_slot(self):
        self.assertEqual(
            route_slots(("A", "B", "C"), 3),
            ("A", "B", "C", None),
        )

    def test_all_nonconfirmed_start_at_second_metric_position(self):
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

            # add duplicate
            work[move.target_slot] = move.path
            present = [item for item in work if item is not None]
            self.assertEqual(set(present), original)
            self.assertEqual(len(present), len(original) + 1)

            # delete old copy: its old slot becomes free automatically
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

    def test_recovery_from_middle_dead_tail(self):
        self.assert_plan(
            ("A", "B", "G", "D", None, "V", "E", "J"),
            ("A", "B", "V", "G", "D", None, "E", "J"),
            (
                ("D", 3, 4),
                ("G", 2, 3),
                ("V", 5, 2),
            ),
        )

    def test_demotion_moves_live_paths_toward_lower_metrics(self):
        self.assert_plan(
            ("A", "B", "V", "G", "D", None, "E", "J"),
            ("A", "B", "G", "D", None, "V", "E", "J"),
            (
                ("V", 2, 5),
                ("G", 3, 2),
                ("D", 4, 3),
            ),
        )

    def test_recovery_of_last_dead_path_ends_all_live(self):
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

    def test_death_from_all_live_uses_next_free_metric_as_scratch(self):
        self.assert_plan(
            ("A", "B", "V", "G", "D", "E", "J", None),
            ("A", "B", "G", "D", "E", "J", None, "V"),
            (
                ("V", 2, 7),
                ("G", 3, 2),
                ("D", 4, 3),
                ("E", 5, 4),
                ("J", 6, 5),
            ),
        )

    def test_all_live_admin_reorder_opens_cycle_through_trailing_slot(self):
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

    def test_all_four_path_layouts_converge_without_membership_loss(self):
        paths = ("A", "B", "C", "D")
        layouts = []
        for order in permutations(paths):
            for free in range(len(paths) + 1):
                layouts.append(
                    order[:free] + (None,) + order[free:]
                )

        for current in layouts:
            for desired in layouts:
                moves = plan_route_slot_moves(current, desired)
                self.assertLessEqual(
                    len(moves),
                    2 * len(current),
                    (current, desired, moves),
                )

                work = list(current)
                for move in moves:
                    self.assertIsNone(work[move.target_slot])
                    self.assertEqual(work[move.source_slot], move.path)

                    work[move.target_slot] = move.path
                    present = [
                        item for item in work
                        if item is not None
                    ]
                    self.assertEqual(set(present), set(paths))
                    self.assertEqual(len(present), len(paths) + 1)

                    work[move.source_slot] = None
                    self.assertEqual(
                        set(
                            item for item in work
                            if item is not None
                        ),
                        set(paths),
                    )
                    self.assertEqual(work.count(None), 1)

                self.assertEqual(tuple(work), desired)

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


if __name__ == "__main__":
    unittest.main()
