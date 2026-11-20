import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.domain import Direction
from rou.host_managed_routing import (
    HostManagedRoutingProfile,
    build_host_managed_routing_plan,
)
from rou.linux_host_managed_routing import (
    HostManagedRoutingLinuxAllocation,
    build_linux_host_managed_routing_desired,
    build_linux_peaceful_host_routing_desired,
)
from rou.network_policy_layout import NumericResourcePool


class LinuxHostManagedRoutingTests(unittest.TestCase):
    def allocation(self):
        return HostManagedRoutingLinuxAllocation(
            table=0x7FFF0003,
            bypass_priority=0x6000,
            dispatch_priority=0x6001,
            owned_rule_priorities=NumericResourcePool(0x6001, 0x6002),
            rule_protocol=203,
            route_protocol=203,
        )

    def plan(self, *profiles):
        return build_host_managed_routing_plan(profiles)

    def profile(self, pid, direction, *destinations, snat=None):
        return HostManagedRoutingProfile(
            profile_id=pid,
            direction=direction,
            destinations=tuple(IPv4Network(item) for item in destinations),
            effective_snat_address=(
                None if snat is None else IPv4Address(snat)
            ),
        )

    def peaceful_allocation(self):
        return HostManagedRoutingLinuxAllocation(
            table=0x7FFF0004,
            bypass_priority=0x6002,
            preserve_priority=0x6003,
            dispatch_priority=0x6004,
            owned_rule_priorities=NumericResourcePool(0x6003, 0x6005),
            rule_protocol=204,
            route_protocol=204,
        )

    def test_peaceful_helper_checks_non_default_main_before_dispatch(self):
        desired = build_linux_peaceful_host_routing_desired(
            self.plan(self.profile("full", Direction.OUTBOUND, "0.0.0.0/0")),
            host_interface="vpng0",
            allocation=self.peaceful_allocation(),
        )
        self.assertEqual(desired.bypass.priority, 0x6002)
        self.assertEqual(desired.preserve_main.priority, 0x6003)
        self.assertEqual(desired.preserve_main.suppress_prefixlength, 0)
        self.assertEqual(desired.dispatch.priority, 0x6004)
        self.assertEqual(desired.routes[0].table, 0x7FFF0004)
        self.assertEqual(desired.routes[0].protocol, 204)

    def test_one_dispatch_rule_serves_all_prefixes(self):
        desired = build_linux_host_managed_routing_desired(
            self.plan(
                self.profile("full", Direction.OUTBOUND, "0.0.0.0/0"),
                self.profile("nested", Direction.INBOUND, "10.0.0.0/8"),
                self.profile(
                    "snat",
                    Direction.INBOUND,
                    "10.20.0.0/16",
                    snat="198.19.255.10",
                ),
            ),
            host_interface="vpng0",
            allocation=self.allocation(),
            stack_service_address=IPv4Address("198.19.255.2"),
        )
        self.assertEqual(
            [item.destination.with_prefixlen for item in desired.routes],
            ["198.19.255.10/32", "10.20.0.0/16", "10.0.0.0/8", "0.0.0.0/0"],
        )
        snat_route = desired.routes[0]
        self.assertEqual(snat_route.gateway, IPv4Address("198.19.255.2"))
        self.assertTrue(snat_route.onlink)
        self.assertEqual(desired.bypass.priority, 0x6000)
        self.assertEqual(desired.bypass.interface, "vpng0")
        self.assertEqual(desired.dispatch.priority, 0x6001)
        self.assertEqual(desired.dispatch.table, 0x7FFF0003)

    def test_remote_routes_remain_device_only(self):
        desired = build_linux_host_managed_routing_desired(
            self.plan(self.profile("p", Direction.INBOUND, "10.0.0.0/8")),
            host_interface="vpng0",
            allocation=self.allocation(),
        )
        self.assertEqual(desired.routes[0].interface, "vpng0")
        self.assertEqual(desired.routes[0].table, 0x7FFF0003)
        self.assertIsNone(desired.routes[0].gateway)
        self.assertFalse(desired.routes[0].onlink)

    def test_snat_identity_requires_stack_service_address(self):
        with self.assertRaisesRegex(ValueError, "stack_service_address"):
            build_linux_host_managed_routing_desired(
                self.plan(
                    self.profile(
                        "snat",
                        Direction.INBOUND,
                        "10.20.0.0/16",
                        snat="198.19.255.10",
                    )
                ),
                host_interface="vpng0",
                allocation=self.allocation(),
            )

    def test_empty_plan_has_no_active_rules(self):
        desired = build_linux_host_managed_routing_desired(
            self.plan(),
            host_interface="vpng0",
            allocation=self.allocation(),
        )
        self.assertEqual(desired.routes, ())
        self.assertIsNone(desired.bypass)
        self.assertIsNone(desired.dispatch)

    def test_allocation_requires_bypass_before_dispatch(self):
        with self.assertRaisesRegex(ValueError, "before managed dispatch"):
            HostManagedRoutingLinuxAllocation(
                table=100,
                bypass_priority=5000,
                dispatch_priority=2000,
                owned_rule_priorities=NumericResourcePool(2000, 4000),
                rule_protocol=203,
                route_protocol=203,
            )


if __name__ == "__main__":
    unittest.main()
