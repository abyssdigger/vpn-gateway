import unittest
from ipaddress import IPv4Network

from rou.release1_config import parse_release1_config
from rou.release1_host_boundary import build_release1_host_boundary_intent


class Release1HostBoundaryTests(unittest.TestCase):
    def test_all_enabled_profile_destinations_are_managed_routes(self):
        cfg = parse_release1_config("""
[device.vpn]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.out]
enabled = true
direction = "outbound"
destinations = ["10.1.0.0/16"]
device_order = ["vpn"]

[profile.in]
enabled = true
direction = "inbound"
destinations = ["10.2.0.0/16"]
device_order = ["vpn"]

[profile.both]
enabled = true
direction = "bidirectional"
destinations = ["10.3.0.0/16"]
device_order = ["vpn"]
""")
        intent = build_release1_host_boundary_intent(cfg)
        self.assertEqual(
            tuple(item.destination.with_prefixlen for item in intent.plan.routes),
            ("10.1.0.0/16", "10.2.0.0/16", "10.3.0.0/16"),
        )

    def test_full_tunnel_is_one_authoritative_managed_route(self):
        cfg = parse_release1_config("""
[device.vpn]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.full]
enabled = true
direction = "outbound"
destinations = ["0.0.0.0/0"]
device_order = ["vpn"]
""")
        intent = build_release1_host_boundary_intent(cfg)
        self.assertTrue(intent.plan.full_tunnel)
        self.assertEqual(
            intent.plan.routes[0].destination,
            IPv4Network("0.0.0.0/0"),
        )

    def test_effective_snat_identity_adds_managed_32(self):
        cfg = parse_release1_config("""
default_snat_address = "198.19.255.10"

[device.server]
enabled = true
expected_interfaces = ["vpn0"]

[profile.a]
enabled = true
direction = "inbound+snat"
destinations = ["10.10.0.0/16"]
device_order = ["server"]

[profile.b]
enabled = true
direction = "inbound+snat>198.19.255.10"
destinations = ["10.20.0.0/16"]
device_order = ["server"]
""")
        intent = build_release1_host_boundary_intent(cfg)
        by_destination = {
            item.destination: item.profile_ids
            for item in intent.plan.routes
        }
        self.assertEqual(
            by_destination[IPv4Network("198.19.255.10/32")],
            ("a", "b"),
        )

    def test_transport_endpoint_may_equal_managed_destination(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false
allow_vpn_client = "udp>198.51.100.10:51820"

[profile.full]
enabled = true
direction = "outbound"
destinations = ["198.51.100.10/32"]
device_order = ["wg"]
""")
        intent = build_release1_host_boundary_intent(cfg)
        self.assertEqual(
            intent.plan.routes[0].destination,
            IPv4Network("198.51.100.10/32"),
        )

    def test_disabled_profile_contributes_nothing(self):
        cfg = parse_release1_config("""
[device.vpn]
enabled = true
expected_interfaces = ["vpn0"]

[profile.off]
enabled = false
direction = "future"
destinations = ["0.0.0.0/0"]
device_order = ["vpn"]
""")
        intent = build_release1_host_boundary_intent(cfg)
        self.assertEqual(intent.plan.routes, ())
        self.assertFalse(intent.plan.full_tunnel)


if __name__ == "__main__":
    unittest.main()
