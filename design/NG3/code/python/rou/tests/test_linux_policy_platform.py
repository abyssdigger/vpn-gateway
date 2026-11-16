from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.network_policy_layout import allocate_network_policy_layout
from rou.payload_profile import PayloadProfileRequest


A = LogicalPathId("a", 0, 0)
B = LogicalPathId("b", 0, 0)


class LinuxPolicyPlatformTests(unittest.TestCase):
    def test_constants_match_exp028_accepted_space(self):
        value = NG3_LINUX_POLICY_PLATFORM

        self.assertEqual(
            (value.payload_tables.first, value.payload_tables.stop),
            (0x80000000, 0xC0000000),
        )
        self.assertEqual(
            (value.probe_tables.first, value.probe_tables.stop),
            (0xC0000000, 0x1_0000_0000),
        )
        self.assertEqual(
            (
                value.probe_rule_priorities.first,
                value.probe_rule_priorities.stop,
            ),
            (0x2000, 0x4000),
        )
        self.assertEqual(
            (
                value.payload_rule_priorities.first,
                value.payload_rule_priorities.stop,
            ),
            (0x4000, 0x6000),
        )
        self.assertEqual(value.ambient_main_rule_priority, 32766)
        self.assertEqual(value.guard_route_protocol, 201)
        self.assertEqual(value.path_route_protocol, 202)
        self.assertEqual(
            value.route_metrics.first_preference_metric,
            1,
        )
        self.assertEqual(
            value.route_metrics.terminal_guard_metric,
            0xFFFFFFFF,
        )
        self.assertEqual((value.nft_family, value.nft_table), ("ip", "vpn_gate"))

    def test_pool_capacities_and_boundaries_are_explicit(self):
        value = NG3_LINUX_POLICY_PLATFORM

        self.assertEqual(value.payload_tables.capacity, 0x40000000)
        self.assertEqual(value.probe_tables.capacity, 0x40000000)
        self.assertEqual(value.probe_rule_priorities.capacity, 0x2000)
        self.assertEqual(value.payload_rule_priorities.capacity, 0x2000)

        self.assertTrue(value.payload_tables.contains(0x80000000))
        self.assertTrue(value.payload_tables.contains(0xBFFFFFFF))
        self.assertFalse(value.payload_tables.contains(0xC0000000))

        self.assertTrue(value.probe_tables.contains(0xC0000000))
        self.assertTrue(value.probe_tables.contains(0xFFFFFFFF))

    def test_real_allocator_consumes_accepted_platform_space(self):
        layout = allocate_network_policy_layout(
            (
                PayloadProfileRequest(
                    profile_id="corp",
                    direction=Direction.OUTBOUND,
                    destinations=(
                        IPv4Network("10.0.0.0/8"),
                        IPv4Network("10.1.0.0/16"),
                    ),
                    ordered_paths=(A, B),
                ),
            ),
            (),
            NG3_LINUX_POLICY_PLATFORM,
        )

        allocation = layout.payload[0]
        self.assertEqual(allocation.table, 0x80000000)
        self.assertEqual(
            allocation.metric_space.preference_slots,
            (1, 2),
        )
        self.assertEqual(
            allocation.metric_space.scratch_metrics,
            (3,),
        )
        self.assertEqual(
            allocation.terminal_guard_metric,
            0xFFFFFFFF,
        )
        self.assertEqual(
            [rule.priority for rule in layout.dispatch_rules],
            [0x4000, 0x4001],
        )
        self.assertEqual(
            [str(rule.destination) for rule in layout.dispatch_rules],
            ["10.1.0.0/16", "10.0.0.0/8"],
        )


if __name__ == "__main__":
    unittest.main()
