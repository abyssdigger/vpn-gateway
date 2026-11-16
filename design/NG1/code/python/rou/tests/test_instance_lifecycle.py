from ipaddress import IPv4Interface
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.instance_lifecycle import InstanceConfig, InstanceConfigError


class InstanceConfigTests(unittest.TestCase):
    def test_rfc3021_slash31_link_is_valid(self):
        config = InstanceConfig(
            namespace="rou0",
            host_if="rouvpn0",
            inner_if="host0",
            host_address=IPv4Interface("192.0.2.0/31"),
            inner_address=IPv4Interface("192.0.2.1/31"),
        )
        self.assertEqual(config.link_network.prefixlen, 31)

    def test_network_address_rejected_for_normal_subnet(self):
        with self.assertRaisesRegex(InstanceConfigError, "host address"):
            InstanceConfig(
                namespace="rou0",
                host_if="rouvpn0",
                inner_if="host0",
                host_address=IPv4Interface("192.0.2.0/30"),
                inner_address=IPv4Interface("192.0.2.2/30"),
            )

    def test_current_model_requires_host0_inner_role(self):
        with self.assertRaisesRegex(InstanceConfigError, "inner_if='host0'"):
            InstanceConfig(
                namespace="rou0",
                host_if="rouvpn0",
                inner_if="inside0",
                host_address=IPv4Interface("192.0.2.1/30"),
                inner_address=IPv4Interface("192.0.2.2/30"),
            )

    def test_link_addresses_must_share_network(self):
        with self.assertRaisesRegex(InstanceConfigError, "same IPv4 network"):
            InstanceConfig(
                namespace="rou0",
                host_if="rouvpn0",
                inner_if="host0",
                host_address=IPv4Interface("192.0.2.1/30"),
                inner_address=IPv4Interface("192.0.2.6/30"),
            )

    def test_ifname_limit_is_enforced(self):
        with self.assertRaisesRegex(InstanceConfigError, "Linux interface"):
            InstanceConfig(
                namespace="rou0",
                host_if="this-interface-name-is-too-long",
                inner_if="host0",
                host_address=IPv4Interface("192.0.2.1/30"),
                inner_address=IPv4Interface("192.0.2.2/30"),
            )


if __name__ == "__main__":
    unittest.main()
