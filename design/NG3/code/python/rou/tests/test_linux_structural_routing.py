from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.linux_structural_routing import (
    LinuxStructuralRoutingBackend,
    LinuxStructuralRoutingError,
)
from rou.payload_routing_desired import (
    ManagedRouteSpec,
    ManagedRouteType,
    ManagedRuleSpec,
)
from rou.structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
)


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)
PATH = LogicalPathId("device", 0, 0)


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, argv):
        self.commands.append(tuple(argv))
        return ""


class LinuxStructuralRoutingBackendTests(unittest.TestCase):
    def test_add_guard_uses_exp048_shape(self):
        runner = FakeRunner()
        backend = LinuxStructuralRoutingBackend(runner, "managed")
        backend.add_route(
            ManagedRouteSpec(
                table=0x80000000,
                destination=IPv4Network("0.0.0.0/0"),
                route_type=ManagedRouteType.BLACKHOLE,
                protocol=201,
                metric=0xFFFFFFFF,
            )
        )
        self.assertEqual(
            runner.commands[-1],
            (
                "ip", "-n", "managed", "-4", "route", "add",
                "blackhole", "default",
                "table", str(0x80000000),
                "proto", "201",
                "metric", str(0xFFFFFFFF),
            ),
        )

    def test_add_gateway_path_preserves_gateway_device_and_onlink(self):
        runner = FakeRunner()
        backend = LinuxStructuralRoutingBackend(runner, "managed")
        backend.add_route(
            ManagedRouteSpec(
                table=0x80000000,
                destination=IPv4Network("10.0.0.0/8"),
                route_type=ManagedRouteType.UNICAST,
                protocol=202,
                metric=3,
                path_id=PATH,
                endpoint=VPN,
                gateway=IPv4Address("192.0.2.1"),
                onlink=True,
            )
        )
        self.assertEqual(
            runner.commands[-1],
            (
                "ip", "-n", "managed", "-4", "route", "add",
                "unicast", "10.0.0.0/8",
                "table", str(0x80000000),
                "proto", "202",
                "metric", "3",
                "via", "192.0.2.1",
                "dev", "vpn0",
                "onlink",
            ),
        )


    def test_delete_stale_route_uses_observed_physical_shape(self):
        runner = FakeRunner()
        backend = LinuxStructuralRoutingBackend(runner, "managed")
        backend.delete_route(
            ObservedManagedRoute(
                table=0x80000001,
                destination=IPv4Network("203.0.113.48/32"),
                route_type=ManagedRouteType.UNICAST,
                protocol=202,
                metric=7,
                scope=0,
                endpoint=VPN,
                gateway=IPv4Address("192.0.2.1"),
                onlink=True,
            )
        )
        self.assertEqual(
            runner.commands[-1],
            (
                "ip", "-n", "managed", "-4", "route", "del",
                "unicast", "203.0.113.48/32",
                "table", str(0x80000001),
                "proto", "202",
                "metric", "7",
                "via", "192.0.2.1",
                "dev", "vpn0",
                "onlink",
            ),
        )

    def test_add_and_delete_payload_rule_use_exact_dispatch_shape(self):
        runner = FakeRunner()
        backend = LinuxStructuralRoutingBackend(runner, "managed")
        desired = ManagedRuleSpec(
            priority=0x4000,
            ingress=HOST,
            destination=IPv4Network("203.0.113.48/32"),
            table=0x80000000,
        )
        backend.add_rule(desired)
        backend.delete_rule(
            ObservedManagedRule(
                priority=desired.priority,
                table=desired.table,
                ingress=HOST,
                destination=desired.destination,
                fwmark=None,
                fwmask=None,
            )
        )
        suffix = (
            "priority", str(0x4000),
            "iif", "host0",
            "to", "203.0.113.48/32",
            "lookup", str(0x80000000),
        )
        self.assertEqual(
            runner.commands[0],
            ("ip", "-n", "managed", "-4", "rule", "add") + suffix,
        )
        self.assertEqual(
            runner.commands[1],
            ("ip", "-n", "managed", "-4", "rule", "del") + suffix,
        )

    def test_delete_rejects_non_payload_rule_shape(self):
        runner = FakeRunner()
        backend = LinuxStructuralRoutingBackend(runner, "managed")
        with self.assertRaisesRegex(
            LinuxStructuralRoutingError,
            "not an exact payload dispatch rule",
        ):
            backend.delete_rule(
                ObservedManagedRule(
                    priority=0x4000,
                    table=0x80000000,
                    ingress=None,
                    destination=None,
                    fwmark=0x48,
                    fwmask=0xFFFF,
                )
            )
        self.assertEqual(runner.commands, [])


if __name__ == "__main__":
    unittest.main()
