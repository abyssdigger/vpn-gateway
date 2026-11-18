import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.domain import Direction
from rou.host_boundary_policy import HostBoundaryProfileIntent, build_host_boundary_policy
from rou.host_underlay_route import HostUnderlayPin
from rou.linux_host_boundary_policy import (
    HostBoundaryLinuxAllocation,
    UnderlayPinningIncomplete,
    build_linux_host_boundary_desired,
)


class LinuxHostBoundaryPolicyTests(unittest.TestCase):
    def allocation(self):
        return HostBoundaryLinuxAllocation(
            mark=0x53,
            return_table=1053,
            return_rule_priority=1053,
            route_protocol=203,
        )

    def intent(self, profile_id, direction, network, *, route_return=False):
        return HostBoundaryProfileIntent(
            profile_id=profile_id,
            direction=direction,
            destinations=(IPv4Network(network),),
            route_return=route_return,
        )

    def test_stateful_inbound_compiles_return_nft_and_rpdb_without_bootstrap_route(self):
        plan = build_host_boundary_policy(
            (self.intent("in", Direction.INBOUND, "10.0.0.0/8"),)
        )
        desired = build_linux_host_boundary_desired(
            plan,
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("192.0.2.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(desired.bootstrap_routes, ())
        self.assertEqual(desired.return_rule.mark, 0x53)
        self.assertEqual(desired.return_route.table, 1053)
        self.assertIn(
            "ip saddr 10.0.0.0/8 ct state new ct mark set 0x53 return",
            desired.nft_script,
        )
        self.assertIn("type route hook output", desired.nft_script)

    def test_route_return_inbound_compiles_bootstrap_route_and_no_stateful_owner(self):
        plan = build_host_boundary_policy(
            (
                self.intent(
                    "in",
                    Direction.INBOUND,
                    "10.0.0.0/8",
                    route_return=True,
                ),
            )
        )
        desired = build_linux_host_boundary_desired(
            plan,
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("192.0.2.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(
            desired.bootstrap_routes[0].destination,
            IPv4Network("10.0.0.0/8"),
        )
        self.assertIsNone(desired.return_rule)
        self.assertIsNone(desired.return_route)
        self.assertIsNone(desired.nft_script)

    def test_mixed_classifier_keeps_explicit_more_specific_route_verdict(self):
        plan = build_host_boundary_policy(
            (
                self.intent("broad", Direction.INBOUND, "10.0.0.0/8"),
                self.intent(
                    "route",
                    Direction.INBOUND,
                    "10.20.0.0/16",
                    route_return=True,
                ),
            )
        )
        desired = build_linux_host_boundary_desired(
            plan,
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("192.0.2.2"),
            allocation=self.allocation(),
        )
        script = desired.nft_script
        specific = script.index("ip saddr 10.20.0.0/16 return")
        broad = script.index(
            "ip saddr 10.0.0.0/8 ct state new ct mark set 0x53 return"
        )
        self.assertLess(specific, broad)

    def test_outbound_compiles_only_bootstrap_route(self):
        plan = build_host_boundary_policy(
            (self.intent("out", Direction.OUTBOUND, "10.0.0.0/8"),)
        )
        desired = build_linux_host_boundary_desired(
            plan,
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("192.0.2.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(len(desired.bootstrap_routes), 1)
        self.assertIsNone(desired.nft_script)

    def test_captured_underlay_endpoint_requires_exact_observed_pin_set(self):
        plan = build_host_boundary_policy(
            (self.intent("full", Direction.OUTBOUND, "0.0.0.0/0"),)
        )
        endpoint = IPv4Address("198.51.100.10")
        with self.assertRaises(UnderlayPinningIncomplete):
            build_linux_host_boundary_desired(
                plan,
                host_interface="vnga-host0",
                inner_gateway=IPv4Address("192.0.2.2"),
                allocation=self.allocation(),
                required_underlay_endpoints=(endpoint,),
            )

        pin = HostUnderlayPin(
            endpoint=endpoint,
            interface="eth0",
            gateway=IPv4Address("192.0.2.1"),
            source=IPv4Address("192.0.2.20"),
            protocol=203,
        )
        desired = build_linux_host_boundary_desired(
            plan,
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("192.0.2.2"),
            allocation=self.allocation(),
            required_underlay_endpoints=(endpoint,),
            underlay_pins=(pin,),
        )
        self.assertEqual(desired.underlay_pins, (pin,))
        self.assertEqual(
            [item.destination for item in desired.bootstrap_routes],
            [IPv4Network("0.0.0.0/1"), IPv4Network("128.0.0.0/1")],
        )

    def test_full_tunnel_lowering_preserves_ordinary_default(self):
        plan = build_host_boundary_policy(
            (self.intent("full", Direction.OUTBOUND, "0.0.0.0/0"),)
        )
        desired = build_linux_host_boundary_desired(
            plan,
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("192.0.2.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(
            [item.destination.with_prefixlen for item in desired.bootstrap_routes],
            ["0.0.0.0/1", "128.0.0.0/1"],
        )

    def test_full_tunnel_lowering_deduplicates_explicit_split_prefix(self):
        plan = build_host_boundary_policy(
            (
                self.intent("full", Direction.OUTBOUND, "0.0.0.0/0"),
                self.intent("half", Direction.OUTBOUND, "0.0.0.0/1"),
            )
        )
        desired = build_linux_host_boundary_desired(
            plan,
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("192.0.2.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(
            [item.destination.with_prefixlen for item in desired.bootstrap_routes],
            ["0.0.0.0/1", "128.0.0.0/1"],
        )

    def test_extra_underlay_pin_is_rejected(self):
        plan = build_host_boundary_policy(
            (self.intent("out", Direction.OUTBOUND, "10.0.0.0/8"),)
        )
        extra = HostUnderlayPin(
            endpoint=IPv4Address("198.51.100.10"),
            interface="eth0",
            gateway=IPv4Address("192.0.2.1"),
            source=None,
            protocol=203,
        )
        with self.assertRaises(UnderlayPinningIncomplete):
            build_linux_host_boundary_desired(
                plan,
                host_interface="vnga-host0",
                inner_gateway=IPv4Address("192.0.2.2"),
                allocation=self.allocation(),
                underlay_pins=(extra,),
            )


if __name__ == "__main__":
    unittest.main()
