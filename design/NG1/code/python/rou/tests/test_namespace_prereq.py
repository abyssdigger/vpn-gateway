from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import CommandResult, NamespaceBackend
from rou.device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from rou.domain import Availability
from rou.environment import EnvironmentSnapshot
from rou.namespace_prereq import (
    apply_namespace_prerequisites,
    prerequisite_commands,
    verify_namespace_prerequisites,
)


class FakeHostBackend:
    def __init__(self):
        self.calls = []

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append(argv)
        return CommandResult(argv, 0, "", "")


class NamespacePrereqTests(unittest.TestCase):
    def make_bindings(self):
        return DeviceBindingSnapshot(
            (
                BoundInterface(
                    "oc",
                    0,
                    InterfaceIdentity("vpns00", 10),
                    Availability.UNKNOWN,
                ),
            ),
            (),
        )

    def test_commands_cover_global_defaults_host0_and_bound_interfaces(self):
        commands = prerequisite_commands(self.make_bindings())

        self.assertIn(
            ("sysctl", "-q", "-w", "net/ipv4/conf/all/rp_filter=0"),
            commands,
        )
        self.assertIn(
            ("sysctl", "-q", "-w", "net/ipv4/conf/default/rp_filter=0"),
            commands,
        )
        self.assertIn(
            ("sysctl", "-q", "-w", "net/ipv6/conf/default/disable_ipv6=1"),
            commands,
        )
        self.assertIn(
            ("sysctl", "-q", "-w", "net/ipv4/conf/host0/rp_filter=0"),
            commands,
        )
        self.assertIn(
            ("sysctl", "-q", "-w", "net/ipv6/conf/vpns00/disable_ipv6=1"),
            commands,
        )

    def test_interface_name_with_dot_uses_slash_form_without_shell(self):
        bindings = DeviceBindingSnapshot(
            (
                BoundInterface(
                    "oc",
                    0,
                    InterfaceIdentity("eth0.100", 10),
                    Availability.UNKNOWN,
                ),
            ),
            (),
        )
        self.assertIn(
            ("sysctl", "-q", "-w", "net/ipv4/conf/eth0.100/rp_filter=0"),
            prerequisite_commands(bindings),
        )

    def test_apply_uses_namespace_backend(self):
        host = FakeHostBackend()
        ns = NamespaceBackend("rou0", host)
        apply_namespace_prerequisites(self.make_bindings(), ns)

        self.assertTrue(host.calls)
        self.assertTrue(
            all(call[:4] == ("ip", "netns", "exec", "rou0") for call in host.calls)
        )

    def test_verify_requires_closed_or_open_forwarding_as_requested(self):
        bindings = self.make_bindings()
        sysctls = (
            ("net.ipv4.ip_forward", "0"),
            ("net.ipv4.conf.all.rp_filter", "0"),
            ("net.ipv4.conf.default.rp_filter", "0"),
            ("net.ipv4.fib_multipath_hash_policy", "0"),
            ("net.ipv6.conf.all.forwarding", "0"),
            ("net.ipv6.conf.default.forwarding", "0"),
            ("net.ipv6.conf.default.disable_ipv6", "1"),
            ("net.ipv4.conf.host0.rp_filter", "0"),
            ("net.ipv6.conf.host0.disable_ipv6", "1"),
            ("net.ipv4.conf.vpns00.rp_filter", "0"),
            ("net.ipv6.conf.vpns00.disable_ipv6", "1"),
        )
        closed = verify_namespace_prerequisites(
            EnvironmentSnapshot((), sysctls=sysctls),
            bindings,
            forwarding=False,
        )
        self.assertTrue(closed.ok, closed.errors)

        open_result = verify_namespace_prerequisites(
            EnvironmentSnapshot((), sysctls=sysctls),
            bindings,
            forwarding=True,
        )
        self.assertFalse(open_result.ok)
        self.assertRegex(open_result.errors[0], "ip_forward")

    def test_verify_detects_global_rp_filter_even_when_per_interface_is_zero(self):
        bindings = self.make_bindings()
        sysctls = (
            ("net.ipv4.ip_forward", "0"),
            ("net.ipv4.conf.all.rp_filter", "1"),
            ("net.ipv4.conf.default.rp_filter", "0"),
            ("net.ipv4.fib_multipath_hash_policy", "0"),
            ("net.ipv6.conf.all.forwarding", "0"),
            ("net.ipv6.conf.default.forwarding", "0"),
            ("net.ipv6.conf.default.disable_ipv6", "1"),
            ("net.ipv4.conf.host0.rp_filter", "0"),
            ("net.ipv6.conf.host0.disable_ipv6", "1"),
            ("net.ipv4.conf.vpns00.rp_filter", "0"),
            ("net.ipv6.conf.vpns00.disable_ipv6", "1"),
        )
        result = verify_namespace_prerequisites(
            EnvironmentSnapshot((), sysctls=sysctls),
            bindings,
            forwarding=False,
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("all.rp_filter" in error for error in result.errors))


    def test_verify_requires_observable_ecmp_hash_policy(self):
        bindings = self.make_bindings()
        sysctls = (
            ("net.ipv4.ip_forward", "0"),
            ("net.ipv4.conf.all.rp_filter", "0"),
            ("net.ipv4.conf.default.rp_filter", "0"),
            ("net.ipv6.conf.all.forwarding", "0"),
            ("net.ipv6.conf.default.forwarding", "0"),
            ("net.ipv6.conf.default.disable_ipv6", "1"),
            ("net.ipv4.conf.host0.rp_filter", "0"),
            ("net.ipv6.conf.host0.disable_ipv6", "1"),
            ("net.ipv4.conf.vpns00.rp_filter", "0"),
            ("net.ipv6.conf.vpns00.disable_ipv6", "1"),
        )
        result = verify_namespace_prerequisites(
            EnvironmentSnapshot((), sysctls=sysctls),
            bindings,
            forwarding=False,
        )
        self.assertFalse(result.ok)
        self.assertTrue(
            any("fib_multipath_hash_policy" in error for error in result.errors)
        )


if __name__ == "__main__":
    unittest.main()
