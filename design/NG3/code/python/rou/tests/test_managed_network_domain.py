from __future__ import annotations

from ipaddress import IPv4Interface
import json
import unittest

from rou.managed_network_domain import (
    ManagedNetworkDomainSpec,
    preflight_managed_network_domain,
)


SPEC = ManagedNetworkDomainSpec(
    namespace="vg-test",
    host_interface="vghost0",
    inner_interface="host0",
    inner_address=IPv4Interface("198.19.255.2/32"),
)


class AbsentRunner:
    def __init__(self):
        self.commands = []

    def run(self, argv):
        command = tuple(argv)
        self.commands.append(command)
        if command == ("ip", "netns", "list"):
            return ""
        if command == ("ip", "-j", "-d", "link", "show"):
            return "[]"
        raise AssertionError(f"unexpected command {command!r}")


class ManagedNetworkDomainTests(unittest.TestCase):
    def test_spec_is_only_selected_routed_l3_shape(self):
        self.assertEqual(SPEC.inner_address.network.prefixlen, 32)

        with self.assertRaisesRegex(ValueError, "must be /32"):
            ManagedNetworkDomainSpec(
                namespace="vg",
                host_interface="vgh0",
                inner_interface="vgi0",
                inner_address=IPv4Interface("198.19.255.2/30"),
                        )


        with self.assertRaisesRegex(ValueError, "must differ"):
            ManagedNetworkDomainSpec(
                namespace="vg",
                host_interface="same0",
                inner_interface="same0",
                inner_address=IPv4Interface("198.19.255.2/32"),
                        )

    def test_absent_preflight_is_read_only(self):
        runner = AbsentRunner()
        value = preflight_managed_network_domain(SPEC, runner)
        self.assertTrue(value.confirmed)
        self.assertFalse(value.existing)
        self.assertIsNone(value.verification)
        self.assertEqual(
            runner.commands,
            [
                ("ip", "netns", "list"),
                ("ip", "netns", "list"),
                ("ip", "-j", "-d", "link", "show"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
