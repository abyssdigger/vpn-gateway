import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from rou.domain import ActiveConfig, Availability, Device, NatMode, Direction, ExpectedInterface, InterfaceMatch, MatchKind, Profile
from rou.environment import EnvironmentSnapshot, KernelRoute, KernelRule, RouteNexthop
from rou.kernel_allocation import compile_kernel_allocation
from rou.kernel_state import (
    BLACKHOLE_PROTOCOL,
    HOST_INTERFACE,
    ROUTE_PROTOCOL,
    compile_kernel_desired_state,
    verify_kernel_desired_state,
)
from rou.traffic_state import MetricAssignment, TrafficProjection


def make_config():
    return ActiveConfig(
        {
            "oc": Device(
                "oc",
                True,
                (ExpectedInterface(InterfaceMatch(MatchKind.PREFIX, "vpns"), 2),),
            )
        },
        {
            "corp": Profile(
                "corp",
                True,
                Direction.OUTBOUND,
                (ipaddress.IPv4Network("10.0.0.0/8"),),
                ("oc",),
            )
        },
    )


class KernelStateTests(unittest.TestCase):
    def test_compile_materializes_normal_shadow_blackhole_and_rules(self):
        config = make_config()
        first = InterfaceIdentity("vpns00", 10)
        second = InterfaceIdentity("vpns01", 11)
        bindings = DeviceBindingSnapshot(
            (
                BoundInterface("oc", 0, first, Availability.AVAILABLE),
                BoundInterface("oc", 0, second, Availability.UNAVAILABLE),
            ),
            (),
        )
        metrics = TrafficProjection(
            (
                MetricAssignment("corp", "oc", 0, first, 1),
                MetricAssignment("corp", "oc", 0, second, 2),
            ),
            (),
        )
        allocation = compile_kernel_allocation(config)
        desired = compile_kernel_desired_state(config, bindings, metrics, allocation)

        self.assertEqual(len(desired.routes), 3)
        normal = [r for r in desired.routes if r.metric == 1][0]
        fallback = [r for r in desired.routes if r.metric == 65535][0]
        blackhole = [r for r in desired.routes if r.route_type == "blackhole"][0]

        self.assertEqual(normal.ifname, "vpns00")
        self.assertEqual(normal.protocol, ROUTE_PROTOCOL)
        self.assertEqual(
            [(n.ifname, n.weight) for n in fallback.nexthops],
            [("vpns00", 1), ("vpns01", 1)],
        )
        self.assertEqual(blackhole.protocol, BLACKHOLE_PROTOCOL)
        self.assertEqual(str(blackhole.destination), "0.0.0.0/0")

        self.assertEqual(desired.rules[0].iif, HOST_INTERFACE)
        self.assertEqual(str(desired.rules[0].destination), "10.0.0.0/8")
        self.assertEqual(desired.rules[-1].action, "unreachable")
        self.assertIsNone(desired.rules[-1].table)

    def test_single_member_shadow_is_direct_route(self):
        config = make_config()
        identity = InterfaceIdentity("vpns00", 10)
        bindings = DeviceBindingSnapshot(
            (BoundInterface("oc", 0, identity, Availability.UNAVAILABLE),),
            (),
        )
        metrics = TrafficProjection(
            (MetricAssignment("corp", "oc", 0, identity, 1),),
            (),
        )
        desired = compile_kernel_desired_state(
            config,
            bindings,
            metrics,
            compile_kernel_allocation(config),
        )
        fallback = [r for r in desired.routes if r.metric == 65535][0]
        self.assertEqual(fallback.ifname, "vpns00")
        self.assertEqual(fallback.nexthops, ())
        self.assertFalse(any(r.metric == 1 for r in desired.routes))

    def test_verify_requires_exact_owned_tables_and_priority_window(self):
        config = make_config()
        identity = InterfaceIdentity("vpns00", 10)
        bindings = DeviceBindingSnapshot(
            (BoundInterface("oc", 0, identity, Availability.AVAILABLE),),
            (),
        )
        metrics = TrafficProjection(
            (MetricAssignment("corp", "oc", 0, identity, 1),),
            (),
        )
        desired = compile_kernel_desired_state(
            config,
            bindings,
            metrics,
            compile_kernel_allocation(config),
        )

        observed_routes = tuple(
            KernelRoute(
                table=r.table,
                destination=r.destination,
                route_type=r.route_type,
                protocol=r.protocol,
                metric=r.metric,
                ifname=r.ifname,
                nexthops=r.nexthops,
            )
            for r in desired.routes
        )
        observed_rules = tuple(
            KernelRule(
                priority=r.priority,
                table=r.table,
                action=r.action,
                destination=r.destination,
                iif=r.iif,
            )
            for r in desired.rules
        )
        ok = verify_kernel_desired_state(
            desired,
            EnvironmentSnapshot((), routes=observed_routes, rules=observed_rules),
        )
        self.assertTrue(ok.ok, ok.errors)

        drifted = EnvironmentSnapshot(
            (),
            routes=observed_routes + (
                KernelRoute(
                    table=desired.owned_tables[0],
                    destination=ipaddress.IPv4Network("192.0.2.0/24"),
                    route_type="unicast",
                    protocol=99,
                    metric=5,
                    ifname="vpns00",
                    nexthops=(),
                ),
            ),
            rules=observed_rules,
        )
        result = verify_kernel_desired_state(desired, drifted)
        self.assertFalse(result.ok)
        self.assertRegex(result.errors[0], "unexpected routes")

    def test_verify_ignores_unrelated_main_table_and_default_rules(self):
        config = make_config()
        identity = InterfaceIdentity("vpns00", 10)
        desired = compile_kernel_desired_state(
            config,
            DeviceBindingSnapshot(
                (BoundInterface("oc", 0, identity, Availability.AVAILABLE),),
                (),
            ),
            TrafficProjection(
                (MetricAssignment("corp", "oc", 0, identity, 1),),
                (),
            ),
            compile_kernel_allocation(config),
        )
        observed_routes = [
            KernelRoute(
                r.table, r.destination, r.route_type, r.protocol,
                r.metric, r.ifname, r.nexthops
            )
            for r in desired.routes
        ]
        observed_routes.append(
            KernelRoute(
                254,
                ipaddress.IPv4Network("0.0.0.0/0"),
                "unicast",
                "dhcp",
                None,
                "host0",
                (),
            )
        )
        observed_rules = [
            KernelRule(r.priority, r.table, r.action, destination=r.destination, iif=r.iif)
            for r in desired.rules
        ]
        observed_rules.extend(
            (
                KernelRule(0, 255, "to_tbl"),
                KernelRule(32766, 254, "to_tbl"),
                KernelRule(32767, 253, "to_tbl"),
            )
        )
        result = verify_kernel_desired_state(
            desired,
            EnvironmentSnapshot((), routes=tuple(observed_routes), rules=tuple(observed_rules)),
        )
        self.assertTrue(result.ok, result.errors)


    def test_verify_rejects_foreign_rule_anywhere_in_owned_priority_window(self):
        config = make_config()
        identity = InterfaceIdentity("vpns00", 10)
        desired = compile_kernel_desired_state(
            config,
            DeviceBindingSnapshot(
                (BoundInterface("oc", 0, identity, Availability.AVAILABLE),),
                (),
            ),
            TrafficProjection(
                (MetricAssignment("corp", "oc", 0, identity, 1),),
                (),
            ),
            compile_kernel_allocation(config),
        )
        observed_routes = tuple(
            KernelRoute(
                r.table,
                r.destination,
                r.route_type,
                r.protocol,
                r.metric,
                r.ifname,
                r.nexthops,
            )
            for r in desired.routes
        )
        observed_rules = [
            KernelRule(
                r.priority,
                r.table,
                r.action,
                destination=r.destination,
                iif=r.iif,
            )
            for r in desired.rules
        ]
        observed_rules.append(
            KernelRule(
                1000,
                254,
                "to_tbl",
                destination=ipaddress.IPv4Network("203.0.113.0/24"),
                iif="host0",
            )
        )

        result = verify_kernel_desired_state(
            desired,
            EnvironmentSnapshot(
                (),
                routes=observed_routes,
                rules=tuple(observed_rules),
            ),
        )
        self.assertFalse(result.ok)
        self.assertTrue(
            any("unexpected rules" in error for error in result.errors)
        )


if __name__ == "__main__":
    unittest.main()
