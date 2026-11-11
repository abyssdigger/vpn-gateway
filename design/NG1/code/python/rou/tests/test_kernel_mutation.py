import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.environment import EnvironmentSnapshot, KernelRoute, KernelRule, RouteNexthop
from rou.kernel_mutation import (
    KernelMutationPlanError,
    compile_kernel_mutation_plan,
)
from rou.kernel_state import KernelDesiredState, KernelRouteSpec, KernelRuleSpec


class KernelMutationTests(unittest.TestCase):
    def test_full_rebuild_closes_barrier_and_never_reopens_it(self):
        desired = KernelDesiredState(
            routes=(
                KernelRouteSpec(
                    table=1,
                    destination=ipaddress.IPv4Network("10.0.0.0/8"),
                    route_type="unicast",
                    protocol=202,
                    metric=1,
                    ifname="vpns00",
                ),
                KernelRouteSpec(
                    table=1,
                    destination=ipaddress.IPv4Network("10.0.0.0/8"),
                    route_type="unicast",
                    protocol=202,
                    metric=65535,
                    nexthops=(
                        RouteNexthop("vpns00", 1),
                        RouteNexthop("vpns01", 1),
                    ),
                ),
                KernelRouteSpec(
                    table=1,
                    destination=ipaddress.IPv4Network("0.0.0.0/0"),
                    route_type="blackhole",
                    protocol=201,
                    metric=65536,
                ),
            ),
            rules=(
                KernelRuleSpec(
                    priority=1,
                    iif="host0",
                    destination=ipaddress.IPv4Network("10.0.0.0/8"),
                    table=1,
                    action="to_tbl",
                ),
                KernelRuleSpec(
                    priority=2,
                    iif="host0",
                    destination=None,
                    table=None,
                    action="unreachable",
                ),
            ),
            owned_tables=(1,),
        )
        observed = EnvironmentSnapshot(
            (),
            routes=(
                KernelRoute(
                    table=1,
                    destination=ipaddress.IPv4Network("192.0.2.0/24"),
                    route_type="unicast",
                    protocol=99,
                    metric=5,
                    ifname="vpns00",
                    nexthops=(),
                ),
            ),
            rules=(
                KernelRule(1, 1, "to_tbl", destination=ipaddress.IPv4Network("192.0.2.0/24"), iif="host0"),
                KernelRule(32766, 254, "to_tbl"),
            ),
        )

        plan = compile_kernel_mutation_plan(desired, observed)
        argv = [item.argv for item in plan.commands]

        self.assertEqual(
            argv[0],
            ("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"),
        )
        self.assertIn(("ip", "route", "flush", "table", "1"), argv)
        self.assertIn(("ip", "rule", "del", "priority", "1"), argv)
        self.assertIn(
            (
                "ip", "route", "add", "table", "1", "10.0.0.0/8",
                "dev", "vpns00", "proto", "202", "metric", "1",
            ),
            argv,
        )
        self.assertIn(
            (
                "ip", "route", "add", "table", "1", "10.0.0.0/8",
                "proto", "202", "metric", "65535",
                "nexthop", "dev", "vpns00", "weight", "1",
                "nexthop", "dev", "vpns01", "weight", "1",
            ),
            argv,
        )
        self.assertIn(
            (
                "ip", "rule", "add", "priority", "2", "iif", "host0",
                "type", "unreachable",
            ),
            argv,
        )
        self.assertFalse(
            any(
                command[:3] == ("sysctl", "-q", "-w")
                and command[-1] == "net.ipv4.ip_forward=1"
                for command in argv
            )
        )

    def test_stale_tagged_old_profile_table_is_flushed(self):
        desired = KernelDesiredState((), (), (1,))
        observed = EnvironmentSnapshot(
            (),
            routes=(
                KernelRoute(
                    table=77,
                    destination=ipaddress.IPv4Network("10.0.0.0/8"),
                    route_type="unicast",
                    protocol=202,
                    metric=1,
                    ifname="vpns00",
                    nexthops=(),
                ),
            ),
        )
        plan = compile_kernel_mutation_plan(desired, observed)
        self.assertIn(
            ("ip", "route", "flush", "table", "77"),
            [item.argv for item in plan.commands],
        )

    def test_tagged_route_in_reserved_table_is_structural_error(self):
        desired = KernelDesiredState((), (), ())
        observed = EnvironmentSnapshot(
            (),
            routes=(
                KernelRoute(
                    table=254,
                    destination=ipaddress.IPv4Network("10.0.0.0/8"),
                    route_type="unicast",
                    protocol=202,
                    metric=1,
                    ifname="host0",
                    nexthops=(),
                ),
            ),
        )
        with self.assertRaisesRegex(KernelMutationPlanError, "reserved table"):
            compile_kernel_mutation_plan(desired, observed)

    def test_all_custom_rules_before_main_are_removed_even_if_stale(self):
        desired = KernelDesiredState((), (), ())
        observed = EnvironmentSnapshot(
            (),
            rules=(
                KernelRule(1, 10, "to_tbl"),
                KernelRule(17, None, "unreachable", iif="host0"),
                KernelRule(32766, 254, "to_tbl"),
            ),
        )
        plan = compile_kernel_mutation_plan(desired, observed)
        deletes = [
            item.argv
            for item in plan.commands
            if item.phase == "rule-clear"
        ]
        self.assertEqual(
            deletes,
            [
                ("ip", "rule", "del", "priority", "1"),
                ("ip", "rule", "del", "priority", "17"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
