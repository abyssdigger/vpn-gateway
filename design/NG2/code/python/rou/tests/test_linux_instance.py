from ipaddress import IPv4Interface
import unittest

from rou.linux_instance import LinuxInstanceSpec


class LinuxInstanceSpecTests(unittest.TestCase):
    def test_accepts_explicit_slash31_link(self):
        spec = LinuxInstanceSpec(
            namespace="vpn-gate-rou0",
            host_interface="rouvpn0",
            host_address=IPv4Interface("192.0.2.0/31"),
            inner_address=IPv4Interface("192.0.2.1/31"),
        )

        self.assertEqual(spec.namespace, "vpn-gate-rou0")

    def test_rejects_different_link_networks(self):
        with self.assertRaisesRegex(
            ValueError,
            "same IPv4 network",
        ):
            LinuxInstanceSpec(
                namespace="rou0",
                host_interface="rouvpn0",
                host_address=IPv4Interface("192.0.2.1/30"),
                inner_address=IPv4Interface("192.0.2.6/30"),
            )

    def test_rejects_network_address_for_prefix_with_broadcast_semantics(self):
        with self.assertRaisesRegex(ValueError, "not usable"):
            LinuxInstanceSpec(
                namespace="rou0",
                host_interface="rouvpn0",
                host_address=IPv4Interface("192.0.2.0/30"),
                inner_address=IPv4Interface("192.0.2.1/30"),
            )

    def test_rejects_unsafe_namespace_and_interface_names(self):
        with self.assertRaisesRegex(ValueError, "namespace"):
            LinuxInstanceSpec(
                namespace="../rou0",
                host_interface="rouvpn0",
                host_address=IPv4Interface("192.0.2.1/30"),
                inner_address=IPv4Interface("192.0.2.2/30"),
            )

        with self.assertRaisesRegex(ValueError, "host interface"):
            LinuxInstanceSpec(
                namespace="rou0",
                host_interface="bad/interface",
                host_address=IPv4Interface("192.0.2.1/30"),
                inner_address=IPv4Interface("192.0.2.2/30"),
            )


if __name__ == "__main__":
    unittest.main()
