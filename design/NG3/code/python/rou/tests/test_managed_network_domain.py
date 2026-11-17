from __future__ import annotations

from ipaddress import IPv4Interface
import json
import unittest

from rou.forwarding_gate import ForwardingGateState
from rou.managed_network_domain import (
    ManagedNetworkDomainError,
    ManagedNetworkDomainSpec,
    destroy_managed_network_domain,
    ensure_managed_network_domain,
    verify_managed_network_domain,
)


SPEC = ManagedNetworkDomainSpec(
    namespace="vg-test",
    host_interface="vghost0",
    inner_interface="host0",
    host_address=IPv4Interface("192.0.2.1/30"),
    inner_address=IPv4Interface("192.0.2.2/30"),
)


class FakeRunner:
    def __init__(self):
        self.namespace = False
        self.host_link = False
        self.inner_link = False
        self.inner_temp = False
        self.host_up = False
        self.inner_up = False
        self.loopback_up = False
        self.host_addresses = []
        self.inner_addresses = []
        self.default_route = False
        self.forwarding = ForwardingGateState.ENABLED
        self.peer_mismatch = False
        self.commands = []
        self.fail_contains = None

    def install_exact(self):
        self.namespace = True
        self.host_link = True
        self.inner_link = True
        self.host_up = True
        self.inner_up = True
        self.loopback_up = True
        self.host_addresses = [SPEC.host_address]
        self.inner_addresses = [SPEC.inner_address]
        self.default_route = True

    def run(self, argv):
        command = tuple(argv)
        self.commands.append(command)
        if (
            self.fail_contains is not None
            and self.fail_contains in command
        ):
            raise RuntimeError(f"synthetic failure on {self.fail_contains}")

        if command == ("ip", "netns", "list"):
            return "vg-test\n" if self.namespace else ""

        if command == ("ip", "-j", "-d", "link", "show"):
            rows = []
            if self.host_link:
                rows.append({
                    "ifname": SPEC.host_interface,
                    "ifindex": 11,
                    "link_index": 99 if self.peer_mismatch else 12,
                    "flags": ["BROADCAST", "UP"] if self.host_up else ["BROADCAST"],
                    "linkinfo": {"info_kind": "veth"},
                })
            if self.inner_temp:
                rows.append({
                    "ifname": SPEC.inner_interface,
                    "ifindex": 12,
                    "link_index": 11,
                    "flags": ["BROADCAST"],
                    "linkinfo": {"info_kind": "veth"},
                })
            return json.dumps(rows)

        if command == (
            "ip", "-n", SPEC.namespace,
            "-j", "-d", "link", "show",
        ):
            if not self.namespace:
                raise RuntimeError("namespace missing")
            rows = [{
                "ifname": "lo",
                "ifindex": 1,
                "flags": ["LOOPBACK", "UP"] if self.loopback_up else ["LOOPBACK"],
                "linkinfo": {"info_kind": "loopback"},
            }]
            if self.inner_link:
                rows.append({
                    "ifname": SPEC.inner_interface,
                    "ifindex": 12,
                    "link_index": 98 if self.peer_mismatch else 11,
                    "flags": ["BROADCAST", "UP"] if self.inner_up else ["BROADCAST"],
                    "linkinfo": {"info_kind": "veth"},
                })
            return json.dumps(rows)

        if command == (
            "ip", "-j", "-4", "addr", "show",
            "dev", SPEC.host_interface,
        ):
            return self._address_json(SPEC.host_interface, self.host_addresses)

        if command == (
            "ip", "-n", SPEC.namespace,
            "-j", "-4", "addr", "show",
            "dev", SPEC.inner_interface,
        ):
            return self._address_json(SPEC.inner_interface, self.inner_addresses)

        if command == (
            "ip", "-n", SPEC.namespace,
            "-j", "-4", "route", "show", "table", "main",
        ):
            rows = []
            if self.inner_addresses:
                rows.append({
                    "dst": str(SPEC.inner_address.network),
                    "dev": SPEC.inner_interface,
                    "scope": "link",
                })
            if self.default_route:
                rows.append({
                    "dst": "default",
                    "gateway": str(SPEC.host_address.ip),
                    "dev": SPEC.inner_interface,
                })
            return json.dumps(rows)

        if command == (
            "ip", "netns", "exec", SPEC.namespace,
            "sysctl", "-n", "net.ipv4.ip_forward",
        ):
            if not self.namespace:
                raise RuntimeError("namespace missing")
            return (
                "1\n"
                if self.forwarding is ForwardingGateState.ENABLED
                else "0\n"
            )

        if command[:6] == (
            "ip", "netns", "exec", SPEC.namespace,
            "sysctl", "-w",
        ):
            value = command[6]
            if value == "net.ipv4.ip_forward=0":
                self.forwarding = ForwardingGateState.DISABLED
            elif value == "net.ipv4.ip_forward=1":
                self.forwarding = ForwardingGateState.ENABLED
            else:
                raise AssertionError(command)
            return value + "\n"

        if command == ("ip", "netns", "add", SPEC.namespace):
            if self.namespace:
                raise RuntimeError("namespace exists")
            self.namespace = True
            self.loopback_up = False
            self.forwarding = ForwardingGateState.ENABLED
            return ""

        if command == (
            "ip", "link", "add", SPEC.host_interface,
            "type", "veth", "peer", "name", SPEC.inner_interface,
        ):
            self.host_link = True
            self.inner_temp = True
            return ""

        if command == (
            "ip", "link", "set", SPEC.inner_interface,
            "netns", SPEC.namespace,
        ):
            self.inner_temp = False
            self.inner_link = True
            return ""

        if command == (
            "ip", "addr", "add", SPEC.host_address.with_prefixlen,
            "dev", SPEC.host_interface,
        ):
            self.host_addresses = [SPEC.host_address]
            return ""

        if command == (
            "ip", "link", "set", SPEC.host_interface, "up",
        ):
            self.host_up = True
            return ""

        if command == (
            "ip", "-n", SPEC.namespace,
            "link", "set", "lo", "up",
        ):
            self.loopback_up = True
            return ""

        if command == (
            "ip", "-n", SPEC.namespace,
            "addr", "add", SPEC.inner_address.with_prefixlen,
            "dev", SPEC.inner_interface,
        ):
            self.inner_addresses = [SPEC.inner_address]
            return ""

        if command == (
            "ip", "-n", SPEC.namespace,
            "link", "set", SPEC.inner_interface, "up",
        ):
            self.inner_up = True
            return ""

        if command == (
            "ip", "-n", SPEC.namespace,
            "-4", "route", "replace", "default",
            "via", str(SPEC.host_address.ip),
            "dev", SPEC.inner_interface,
        ):
            self.default_route = True
            return ""

        if command == ("ip", "netns", "del", SPEC.namespace):
            self.namespace = False
            self.loopback_up = False
            self.inner_link = False
            self.inner_temp = False
            self.inner_addresses = []
            self.default_route = False
            # Deleting a namespace containing one veth endpoint destroys
            # the pair, including the host-side peer.
            self.host_link = False
            self.host_up = False
            self.host_addresses = []
            return ""

        if command == ("ip", "link", "del", SPEC.host_interface):
            self.host_link = False
            self.host_up = False
            self.host_addresses = []
            self.inner_link = False
            self.inner_temp = False
            return ""

        raise AssertionError(f"unexpected command {command!r}")

    @staticmethod
    def _address_json(ifname, addresses):
        return json.dumps([{
            "ifname": ifname,
            "addr_info": [
                {
                    "family": "inet",
                    "local": str(address.ip),
                    "prefixlen": address.network.prefixlen,
                }
                for address in addresses
            ],
        }])


class ManagedNetworkDomainTests(unittest.TestCase):
    def test_spec_accepts_slash31_and_rejects_unsafe_shapes(self):
        value = ManagedNetworkDomainSpec(
            namespace="vg31",
            host_interface="vgh31",
            inner_interface="vgi31",
            host_address=IPv4Interface("198.51.100.10/31"),
            inner_address=IPv4Interface("198.51.100.11/31"),
        )
        self.assertEqual(value.host_address.network.prefixlen, 31)

        with self.assertRaisesRegex(ValueError, "same IPv4 network"):
            ManagedNetworkDomainSpec(
                namespace="vg",
                host_interface="vgh",
                inner_interface="vgi",
                host_address=IPv4Interface("192.0.2.1/30"),
                inner_address=IPv4Interface("192.0.2.6/30"),
            )
        with self.assertRaisesRegex(ValueError, "must differ"):
            ManagedNetworkDomainSpec(
                namespace="vg",
                host_interface="veth0",
                inner_interface="veth0",
                host_address=IPv4Interface("192.0.2.1/30"),
                inner_address=IPv4Interface("192.0.2.2/30"),
            )

    def test_exact_existing_domain_is_contained_then_confirmed(self):
        runner = FakeRunner()
        runner.install_exact()
        result = ensure_managed_network_domain(SPEC, runner)

        self.assertTrue(result.confirmed)
        self.assertFalse(result.created)
        self.assertEqual(
            result.verification.host_boundary.ifname,
            SPEC.inner_interface,
        )
        self.assertEqual(result.verification.host_boundary.ifindex, 12)
        self.assertEqual(runner.forwarding, ForwardingGateState.DISABLED)
        self.assertIn(
            (
                "ip", "netns", "exec", SPEC.namespace,
                "sysctl", "-w", "net.ipv4.ip_forward=0",
            ),
            runner.commands,
        )

    def test_partial_namespace_state_is_contained_then_rejected(self):
        runner = FakeRunner()
        runner.namespace = True
        runner.forwarding = ForwardingGateState.ENABLED

        with self.assertRaisesRegex(
            ManagedNetworkDomainError,
            "partially present",
        ):
            ensure_managed_network_domain(SPEC, runner)

        self.assertEqual(runner.forwarding, ForwardingGateState.DISABLED)

    def test_partial_host_only_state_is_rejected_without_adoption(self):
        runner = FakeRunner()
        runner.host_link = True

        with self.assertRaisesRegex(
            ManagedNetworkDomainError,
            "partially present",
        ):
            ensure_managed_network_domain(SPEC, runner)

        self.assertTrue(runner.host_link)
        self.assertFalse(runner.namespace)

    def test_existing_peer_mismatch_is_not_repaired(self):
        runner = FakeRunner()
        runner.install_exact()
        runner.peer_mismatch = True

        with self.assertRaisesRegex(
            ManagedNetworkDomainError,
            "not reciprocal veth peers",
        ):
            ensure_managed_network_domain(SPEC, runner)

        self.assertEqual(runner.forwarding, ForwardingGateState.DISABLED)
        self.assertTrue(runner.namespace)
        self.assertTrue(runner.host_link)

    def test_extra_owned_boundary_address_is_exact_verification_failure(self):
        runner = FakeRunner()
        runner.install_exact()
        runner.host_addresses.append(IPv4Interface("192.0.2.3/30"))

        verification = verify_managed_network_domain(SPEC, runner)

        self.assertFalse(verification.confirmed)
        self.assertIn(
            "host boundary IPv4 address set does not exactly match "
            + SPEC.host_address.with_prefixlen,
            verification.errors,
        )

    def test_absent_domain_is_created_contained_and_exactly_verified(self):
        runner = FakeRunner()

        result = ensure_managed_network_domain(SPEC, runner)

        self.assertTrue(result.confirmed)
        self.assertTrue(result.created)
        self.assertEqual(runner.forwarding, ForwardingGateState.DISABLED)
        self.assertTrue(runner.namespace)
        self.assertTrue(runner.host_link)
        self.assertTrue(runner.inner_link)
        self.assertTrue(runner.loopback_up)
        self.assertEqual(runner.host_addresses, [SPEC.host_address])
        self.assertEqual(runner.inner_addresses, [SPEC.inner_address])
        self.assertTrue(runner.default_route)

        add_ns = runner.commands.index(
            ("ip", "netns", "add", SPEC.namespace)
        )
        close = runner.commands.index(
            (
                "ip", "netns", "exec", SPEC.namespace,
                "sysctl", "-w", "net.ipv4.ip_forward=0",
            )
        )
        create_veth = runner.commands.index(
            (
                "ip", "link", "add", SPEC.host_interface,
                "type", "veth", "peer", "name", SPEC.inner_interface,
            )
        )
        self.assertLess(add_ns, close)
        self.assertLess(close, create_veth)

    def test_create_failure_rolls_back_created_namespace_and_veth(self):
        runner = FakeRunner()
        runner.fail_contains = "192.0.2.1/30"

        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            ensure_managed_network_domain(SPEC, runner)

        self.assertFalse(runner.namespace)
        self.assertFalse(runner.host_link)

    def test_destroy_contains_then_removes_owned_infrastructure(self):
        runner = FakeRunner()
        runner.install_exact()
        runner.forwarding = ForwardingGateState.ENABLED

        destroy_managed_network_domain(SPEC, runner)

        self.assertFalse(runner.namespace)
        self.assertFalse(runner.host_link)


if __name__ == "__main__":
    unittest.main()
