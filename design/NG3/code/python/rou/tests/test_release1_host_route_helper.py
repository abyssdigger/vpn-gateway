import unittest
from ipaddress import IPv4Interface

from rou.linux_policy_platform import NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION
from rou.managed_network_domain import ManagedNetworkDomainSpec
from rou.release1_config import HostRoutingMode, parse_release1_config
from rou.release1_host_route_helper import (
    build_release1_peaceful_host_routing_desired,
)


DOMAIN = ManagedNetworkDomainSpec(
    namespace="vpng-stack",
    host_interface="vpng0",
    inner_interface="stack0",
    inner_address=IPv4Interface("198.19.255.2/32"),
)


class Release1HostRouteHelperTests(unittest.TestCase):
    def test_manual_mode_builds_no_host_contribution(self):
        cfg = parse_release1_config('host_routing = "manual"')
        self.assertIs(cfg.host_routing, HostRoutingMode.MANUAL)
        self.assertIsNone(
            build_release1_peaceful_host_routing_desired(cfg, DOMAIN)
        )

    def test_auto_mode_materializes_remote_and_snat_routes(self):
        cfg = parse_release1_config("""
host_routing = "auto"
default_snat_address = "198.19.255.10"

[device.vpn]
enabled = true
expected_interfaces = ["vpn0"]

[profile.remote]
enabled = true
direction = "inbound+snat"
destinations = ["10.30.0.0/16"]
device_order = ["vpn"]
""")
        desired = build_release1_peaceful_host_routing_desired(cfg, DOMAIN)
        self.assertIsNotNone(desired)
        self.assertEqual(
            [route.destination.with_prefixlen for route in desired.routes],
            ["198.19.255.10/32", "10.30.0.0/16"],
        )
        self.assertEqual(
            {route.table for route in desired.routes},
            {NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION.table},
        )
        self.assertEqual(
            {route.protocol for route in desired.routes},
            {NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION.route_protocol},
        )
        snat = desired.routes[0]
        self.assertEqual(str(snat.gateway), "198.19.255.2")
        self.assertTrue(snat.onlink)
        self.assertIsNotNone(desired.preserve_main)


if __name__ == "__main__":
    unittest.main()
