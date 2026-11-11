import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.domain import ActiveConfig, Direction, Profile
from rou.kernel_allocation import (
    MAIN_RULE_PRIORITY,
    RT_TABLE_COMPAT,
    RT_TABLE_DEFAULT,
    RT_TABLE_LOCAL,
    RT_TABLE_MAIN,
    KernelAllocationError,
    compile_kernel_allocation,
)


class KernelAllocationTests(unittest.TestCase):
    def test_tables_are_canonical_by_profile_id_and_skip_reserved_ids(self):
        profiles = {
            f"p{i:03d}": Profile(
                f"p{i:03d}",
                True,
                Direction.OUTBOUND,
                (ipaddress.IPv4Network(f"10.{i % 250}.0.0/16"),),
                (),
            )
            for i in range(1, 260)
        }
        allocation = compile_kernel_allocation(ActiveConfig({}, profiles))
        table_ids = [item.table_id for item in allocation.profile_tables]

        self.assertEqual(
            set(table_ids).intersection(
                {RT_TABLE_COMPAT, RT_TABLE_DEFAULT, RT_TABLE_MAIN, RT_TABLE_LOCAL}
            ),
            set(),
        )
        self.assertIn(251, table_ids)
        self.assertIn(256, table_ids)

    def test_dispatch_priority_matches_longest_prefix_order(self):
        profiles = {
            "default": Profile(
                "default",
                True,
                Direction.OUTBOUND,
                (ipaddress.IPv4Network("0.0.0.0/0"),),
                (),
            ),
            "corp": Profile(
                "corp",
                True,
                Direction.OUTBOUND,
                (
                    ipaddress.IPv4Network("10.0.0.0/8"),
                    ipaddress.IPv4Network("10.20.0.0/16"),
                ),
                (),
            ),
        }
        allocation = compile_kernel_allocation(ActiveConfig({}, profiles))
        self.assertEqual(
            [
                (rule.priority, str(rule.destination), rule.profile_name)
                for rule in allocation.dispatch_rules
            ],
            [
                (1, "10.20.0.0/16", "corp"),
                (2, "10.0.0.0/8", "corp"),
                (3, "0.0.0.0/0", "default"),
            ],
        )
        self.assertEqual(allocation.terminal_host0_priority, 4)
        self.assertLess(allocation.terminal_host0_priority, MAIN_RULE_PRIORITY)

    def test_table_allocation_is_independent_of_mapping_insertion_order(self):
        a = Profile(
            "a",
            True,
            Direction.OUTBOUND,
            (ipaddress.IPv4Network("10.0.0.0/8"),),
            (),
        )
        z = Profile(
            "z",
            True,
            Direction.OUTBOUND,
            (ipaddress.IPv4Network("192.168.0.0/16"),),
            (),
        )
        left = compile_kernel_allocation(ActiveConfig({}, {"z": z, "a": a}))
        right = compile_kernel_allocation(ActiveConfig({}, {"a": a, "z": z}))
        self.assertEqual(left.profile_tables, right.profile_tables)

    def test_duplicate_destination_in_manual_active_config_is_rejected(self):
        profiles = {
            "a": Profile(
                "a",
                True,
                Direction.OUTBOUND,
                (ipaddress.IPv4Network("10.0.0.0/8"),),
                (),
            ),
            "b": Profile(
                "b",
                True,
                Direction.OUTBOUND,
                (ipaddress.IPv4Network("10.0.0.0/8"),),
                (),
            ),
        }
        with self.assertRaisesRegex(KernelAllocationError, "duplicate"):
            compile_kernel_allocation(ActiveConfig({}, profiles))

    def test_rule_space_exhaustion_is_rejected(self):
        destinations = tuple(
            ipaddress.IPv4Network((index, 32))
            for index in range(1, MAIN_RULE_PRIORITY)
        )
        config = ActiveConfig(
            {},
            {
                "huge": Profile(
                    "huge",
                    True,
                    Direction.OUTBOUND,
                    destinations,
                    (),
                )
            },
        )
        with self.assertRaisesRegex(KernelAllocationError, "RPDB priorities"):
            compile_kernel_allocation(config)


if __name__ == "__main__":
    unittest.main()
