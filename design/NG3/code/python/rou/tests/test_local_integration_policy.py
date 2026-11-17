from ipaddress import IPv4Address
import unittest

from rou import (
    IntegrationLocalHook,
    IntegrationLocalTransportIntent,
    IntegrationTransportProtocol,
    InterfaceIdentity,
    build_integration_local_desired,
)


class IntegrationLocalPolicyTests(unittest.TestCase):
    def test_exact_local_port_produces_two_exact_rules(self):
        boundary = InterfaceIdentity("host0", 7)
        desired = build_integration_local_desired(
            (
                IntegrationLocalTransportIntent(
                    integration_id="wg",
                    protocol=IntegrationTransportProtocol.UDP,
                    host_boundary=boundary,
                    local_address=IPv4Address("192.0.2.2"),
                    remote_address=IPv4Address("198.51.100.9"),
                    remote_port=51820,
                    local_port=51821,
                ),
            )
        )
        self.assertEqual(len(desired.rules), 2)
        self.assertEqual(
            {item.hook for item in desired.rules},
            {IntegrationLocalHook.INPUT, IntegrationLocalHook.OUTPUT},
        )
        self.assertTrue(all(item.local_port == 51821 for item in desired.rules))

    def test_dynamic_local_port_keeps_remote_endpoint_exact(self):
        boundary = InterfaceIdentity("host0", 9)
        desired = build_integration_local_desired(
            (
                IntegrationLocalTransportIntent(
                    integration_id="openconnect",
                    protocol=IntegrationTransportProtocol.TCP,
                    host_boundary=boundary,
                    local_address=IPv4Address("192.0.2.2"),
                    remote_address=IPv4Address("203.0.113.8"),
                    remote_port=443,
                ),
            )
        )
        self.assertEqual(len(desired.rules), 2)
        self.assertTrue(all(item.local_port is None for item in desired.rules))
        self.assertTrue(
            all(item.remote_address == IPv4Address("203.0.113.8") for item in desired.rules)
        )
        self.assertTrue(all(item.remote_port == 443 for item in desired.rules))

    def test_duplicate_integration_physical_allow_deduplicates(self):
        boundary = InterfaceIdentity("host0", 11)
        left = IntegrationLocalTransportIntent(
            integration_id="one",
            protocol=IntegrationTransportProtocol.UDP,
            host_boundary=boundary,
            local_address=IPv4Address("192.0.2.2"),
            remote_address=IPv4Address("198.51.100.10"),
            remote_port=1194,
        )
        right = IntegrationLocalTransportIntent(
            integration_id="two",
            protocol=IntegrationTransportProtocol.UDP,
            host_boundary=boundary,
            local_address=IPv4Address("192.0.2.2"),
            remote_address=IPv4Address("198.51.100.10"),
            remote_port=1194,
        )
        desired = build_integration_local_desired((left, right))
        self.assertEqual(len(desired.rules), 2)


if __name__ == "__main__":
    unittest.main()
