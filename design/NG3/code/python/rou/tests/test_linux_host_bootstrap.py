import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.domain import Direction
from rou.host_boundary_policy import HostBoundaryProfileIntent, build_host_boundary_policy
from rou.linux_host_bootstrap import (
    HostBootstrapLinuxAllocation,
    build_linux_host_bootstrap_desired,
)
from rou.network_policy_layout import NumericResourcePool


class LinuxHostBootstrapTests(unittest.TestCase):
    def allocation(self):
        return HostBootstrapLinuxAllocation(
            table=0x7FFF0002,
            bypass_priority=0x1900,
            pair_priorities=NumericResourcePool(0x2000,0x3000),
            rule_protocol=203,
            route_protocol=203,
        )

    def plan(self,*items):
        return build_host_boundary_policy(tuple(items))

    def profile(self,pid,direction,*destinations,route_return=False):
        return HostBoundaryProfileIntent(
            profile_id=pid,
            direction=direction,
            destinations=tuple(IPv4Network(x) for x in destinations),
            route_return=route_return,
        )

    def test_no_bootstrap_need_produces_no_host_owner(self):
        desired=build_linux_host_bootstrap_desired(
            self.plan(self.profile("in",Direction.INBOUND,"10.0.0.0/8")),
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("198.19.255.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(desired.routes,())
        self.assertIsNone(desired.bypass)
        self.assertEqual(desired.pairs,())

    def test_destinations_are_longest_prefix_first_with_consecutive_pairs(self):
        desired=build_linux_host_bootstrap_desired(
            self.plan(
                self.profile("full",Direction.OUTBOUND,"0.0.0.0/0"),
                self.profile("nested",Direction.OUTBOUND,"203.0.113.128/25"),
                self.profile("exact",Direction.OUTBOUND,"198.51.100.10/32"),
            ),
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("198.19.255.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(
            [x.destination.with_prefixlen for x in desired.routes],
            ["198.51.100.10/32","203.0.113.128/25","0.0.0.0/0"],
        )
        self.assertEqual(
            [(x.preserve.priority,x.dispatch.priority) for x in desired.pairs],
            [(0x2000,0x2001),(0x2002,0x2003),(0x2004,0x2005)],
        )
        self.assertEqual(
            [x.preserve.suppress_prefixlen for x in desired.pairs],
            [32,25,0],
        )
        self.assertEqual(desired.routes[-1].destination,IPv4Network("0.0.0.0/0"))
        self.assertEqual(desired.bypass.interface,"vnga-host0")

    def test_route_return_inbound_gets_bootstrap_pair(self):
        desired=build_linux_host_bootstrap_desired(
            self.plan(
                self.profile(
                    "in-route",Direction.INBOUND,"10.0.0.0/8",route_return=True
                )
            ),
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("198.19.255.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(len(desired.routes),1)
        self.assertEqual(desired.routes[0].destination,IPv4Network("10.0.0.0/8"))

    def test_exact_transport_address_is_just_an_ordinary_managed_32(self):
        desired=build_linux_host_bootstrap_desired(
            self.plan(self.profile("p",Direction.OUTBOUND,"198.51.100.10/32")),
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("198.19.255.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(desired.routes[0].destination,IPv4Network("198.51.100.10/32"))
        self.assertEqual(desired.pairs[0].preserve.suppress_prefixlen,32)

    def test_priority_pool_capacity_is_bounded(self):
        small=HostBootstrapLinuxAllocation(
            table=100,
            bypass_priority=900,
            pair_priorities=NumericResourcePool(1000,1002),
            rule_protocol=203,
            route_protocol=203,
        )
        with self.assertRaises(ValueError):
            build_linux_host_bootstrap_desired(
                self.plan(
                    self.profile("a",Direction.OUTBOUND,"10.0.0.0/8"),
                    self.profile("b",Direction.OUTBOUND,"20.0.0.0/8"),
                ),
                host_interface="vnga-host0",
                inner_gateway=IPv4Address("198.19.255.2"),
                allocation=small,
            )


if __name__=="__main__":
    unittest.main()
