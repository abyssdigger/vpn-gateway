import unittest
from ipaddress import IPv4Address

from rou.release1_config import parse_release1_config
from rou.host_boundary_behavior import HostBoundaryBehaviorLane
from rou.host_underlay_policy import UnderlayEndpointPayloadConflict
from rou.release1_host_boundary import build_release1_host_boundary_intent


class Release1HostBoundaryTests(unittest.TestCase):
    def test_full_tunnel_collects_all_enabled_client_transport_endpoints(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false
allow_vpn_client = [
    "udp:51820>198.51.100.10:51820",
    "udp>203.0.113.20:443",
]

[device.disabled]
enabled = false
allow_vpn_client = "tcp>192.0.2.99:443"

[profile.full]
enabled = true
direction = "outbound"
destinations = ["0.0.0.0/0"]
device_order = ["wg"]
""")
        intent = build_release1_host_boundary_intent(cfg)
        self.assertEqual(
            intent.transport_endpoints,
            (
                IPv4Address("198.51.100.10"),
                IPv4Address("203.0.113.20"),
            ),
        )
        self.assertEqual(
            intent.required_underlay_endpoints,
            intent.transport_endpoints,
        )

    def test_narrow_bootstrap_only_requires_captured_endpoint(self):
        cfg = parse_release1_config("""
[device.a]
enabled = true
expected_interfaces = ["a0"]
use_outbound_nat = false
allow_vpn_client = "tcp>10.1.2.3:443"

[device.b]
enabled = true
expected_interfaces = ["b0"]
allow_vpn_client = "tcp>198.51.100.10:443"

[profile.p]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["a"]
""")
        intent = build_release1_host_boundary_intent(cfg)
        self.assertEqual(
            intent.required_underlay_endpoints,
            (IPv4Address("10.1.2.3"),),
        )

    def test_exact_client_endpoint_payload_destination_is_rejected_pre_actuation(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false
allow_vpn_client = "udp>198.51.100.10:51820"

[profile.bad]
enabled = true
direction = "outbound"
destinations = ["198.51.100.10/32"]
device_order = ["wg"]
""")
        with self.assertRaises(UnderlayEndpointPayloadConflict):
            build_release1_host_boundary_intent(cfg)

    def test_inbound_default_stateful_requires_no_bootstrap_or_pin(self):
        cfg = parse_release1_config("""
[device.server]
enabled = true
expected_interfaces = ["vpn0"]
allow_vpn_client = "tcp>10.1.2.3:443"

[profile.in]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/8"]
device_order = ["server"]
""")
        intent = build_release1_host_boundary_intent(cfg)
        self.assertEqual(intent.plan.bootstrap_routes, ())
        self.assertEqual(intent.required_underlay_endpoints, ())

    def test_profile_suffixes_project_to_fixed_behavior_classes(self):
        cfg = parse_release1_config("""
[device.server]
enabled = true
expected_interfaces = ["vpn0"]

[profile.a]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/16"]
device_order = ["server"]

[profile.b]
enabled = true
direction = "inbound+snat"
destinations = ["10.1.0.0/16"]
device_order = ["server"]

[profile.c]
enabled = true
direction = "inbound+route-return"
destinations = ["10.2.0.0/16"]
device_order = ["server"]

[profile.d]
enabled = true
direction = "inbound+snat+route-return"
destinations = ["10.3.0.0/16"]
device_order = ["server"]
""")
        intent = build_release1_host_boundary_intent(cfg)
        self.assertEqual(
            tuple((item.profile_id, item.lane) for item in intent.behavior),
            (
                ("a", HostBoundaryBehaviorLane.STATEFUL_NO_NAT),
                ("b", HostBoundaryBehaviorLane.STATEFUL_NAT),
                ("c", HostBoundaryBehaviorLane.ROUTE_NO_NAT),
                ("d", HostBoundaryBehaviorLane.ROUTE_NAT),
            ),
        )

    def test_inbound_route_return_can_require_pin(self):
        cfg = parse_release1_config("""
[device.client]
enabled = true
expected_interfaces = ["vpn0"]
allow_vpn_client = "tcp>10.1.2.3:443"

[profile.in]
enabled = true
direction = "inbound+route-return"
destinations = ["10.0.0.0/8"]
device_order = ["client"]
""")
        intent = build_release1_host_boundary_intent(cfg)
        self.assertEqual(
            intent.required_underlay_endpoints,
            (IPv4Address("10.1.2.3"),),
        )


if __name__ == "__main__":
    unittest.main()
