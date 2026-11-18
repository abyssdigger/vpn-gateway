import json
import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.host_underlay_route import (
    HostUnderlayRouteError,
    classify_existing_exact_route,
    parse_ordinary_route_get,
    render_pin_argv,
)


class HostUnderlayRouteTests(unittest.TestCase):
    def parse(self, row):
        return parse_ordinary_route_get(
            json.dumps([row]),
            endpoint=IPv4Address("198.51.100.10"),
            managed_interface="vnga-host0",
            owner_protocol=203,
        )

    def test_main_gateway_route_becomes_exact_pin(self):
        pin = self.parse(
            {
                "dst": "198.51.100.10",
                "gateway": "192.0.2.1",
                "dev": "eth0",
                "prefsrc": "192.0.2.20",
            }
        )
        self.assertEqual(pin.destination, IPv4Network("198.51.100.10/32"))
        self.assertEqual(pin.gateway, IPv4Address("192.0.2.1"))
        self.assertEqual(pin.source, IPv4Address("192.0.2.20"))
        self.assertEqual(
            render_pin_argv(pin),
            (
                "ip", "-4", "route", "add", "198.51.100.10/32",
                "via", "192.0.2.1", "dev", "eth0",
                "src", "192.0.2.20", "proto", "203",
            ),
        )

    def test_existing_host_route_without_slash_is_normalized_as_32(self):
        pin = self.parse(
            {
                "dst": "198.51.100.10",
                "gateway": "192.0.2.1",
                "dev": "eth0",
                "prefsrc": "192.0.2.20",
            }
        )
        existing = classify_existing_exact_route(
            pin,
            json.dumps([
                {
                    "dst": "198.51.100.10",
                    "gateway": "192.0.2.1",
                    "dev": "eth0",
                    "prefsrc": "192.0.2.20",
                    "protocol": 203,
                }
            ]),
        )
        self.assertTrue(existing.owned)
        self.assertTrue(existing.present)

    def test_existing_owner_protocol_exact_route_is_owned_present(self):
        pin = self.parse(
            {
                "dst": "198.51.100.10",
                "gateway": "192.0.2.1",
                "dev": "eth0",
                "prefsrc": "192.0.2.20",
            }
        )
        existing = classify_existing_exact_route(
            pin,
            json.dumps([
                {
                    "dst": "198.51.100.10/32",
                    "gateway": "192.0.2.1",
                    "dev": "eth0",
                    "prefsrc": "192.0.2.20",
                    "protocol": 203,
                }
            ]),
        )
        self.assertTrue(existing.owned)
        self.assertTrue(existing.present)

    def test_existing_foreign_exact_route_is_external_present(self):
        pin = self.parse(
            {
                "dst": "198.51.100.10",
                "gateway": "192.0.2.1",
                "dev": "eth0",
                "prefsrc": "192.0.2.20",
            }
        )
        existing = classify_existing_exact_route(
            pin,
            json.dumps([
                {
                    "dst": "198.51.100.10/32",
                    "gateway": "192.0.2.1",
                    "dev": "eth0",
                    "prefsrc": "192.0.2.20",
                    "protocol": "static",
                }
            ]),
        )
        self.assertFalse(existing.owned)
        self.assertTrue(existing.present)

    def test_direct_main_route_is_supported_without_gateway(self):
        pin = self.parse(
            {
                "dst": "198.51.100.10",
                "dev": "eth0",
                "src": "192.0.2.20",
            }
        )
        self.assertIsNone(pin.gateway)
        self.assertIn("dev", render_pin_argv(pin))

    def test_custom_policy_table_is_rejected(self):
        with self.assertRaisesRegex(HostUnderlayRouteError, "main table"):
            self.parse(
                {
                    "dst": "198.51.100.10",
                    "gateway": "192.0.2.1",
                    "dev": "eth0",
                    "table": 100,
                }
            )

    def test_managed_boundary_route_is_rejected(self):
        with self.assertRaisesRegex(HostUnderlayRouteError, "managed boundary"):
            self.parse(
                {
                    "dst": "198.51.100.10",
                    "gateway": "198.19.255.2",
                    "dev": "vnga-host0",
                }
            )

    def test_non_unicast_route_is_rejected(self):
        with self.assertRaisesRegex(HostUnderlayRouteError, "unicast"):
            self.parse(
                {
                    "dst": "198.51.100.10",
                    "type": "blackhole",
                    "dev": "eth0",
                }
            )


if __name__ == "__main__":
    unittest.main()
