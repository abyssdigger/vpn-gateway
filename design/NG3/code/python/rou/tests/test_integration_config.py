import unittest

from rou.integration_config import (
    IntegrationConfigError,
    parse_integration_transport_config,
)
from rou.local_integration_policy import IntegrationTransportProtocol


class IntegrationConfigTests(unittest.TestCase):
    def test_parses_bounded_transport_facts(self):
        parsed = parse_integration_transport_config(
            """
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]

[integration.corp]
device = "oc"
protocol = "udp"
remote_ipv4 = "198.51.100.7"
remote_port = 1194
local_port = 1195
"""
        )
        self.assertEqual(len(parsed), 1)
        item = parsed[0]
        self.assertEqual(item.integration_id, "corp")
        self.assertEqual(item.device_id, "oc")
        self.assertIs(item.protocol, IntegrationTransportProtocol.UDP)
        self.assertEqual(str(item.remote_address), "198.51.100.7")
        self.assertEqual(item.remote_port, 1194)
        self.assertEqual(item.local_port, 1195)

    def test_dynamic_local_port_is_explicitly_absent(self):
        item = parse_integration_transport_config(
            """
[integration.corp]
device = "oc"
protocol = "tcp"
remote_ipv4 = "203.0.113.10"
remote_port = 443
"""
        )[0]
        self.assertIsNone(item.local_port)

    def test_rejects_hostname_as_unbounded_remote_fact(self):
        with self.assertRaises(IntegrationConfigError):
            parse_integration_transport_config(
                """
[integration.corp]
device = "oc"
protocol = "tcp"
remote_ipv4 = "vpn.example.test"
remote_port = 443
"""
            )


if __name__ == "__main__":
    unittest.main()
