import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_driver import (
    CommandResult,
    LinuxDriverResult,
    LinuxNetworkVerification,
)
from rou.runtime_bootstrap import (
    LinuxRuntimeBootstrapResult,
    bootstrap_linux_network_rules_adapter,
    bootstrap_linux_network_rules_adapter_in_namespace,
)


class FakeBootstrapBackend:
    def __init__(self, close_result):
        self.close_result = close_result
        self.close_calls = 0

    def close_forwarding_verified(self):
        self.close_calls += 1
        return self.close_result

    def observe_interfaces(self):
        return ()

    def materialize_structural(self, desired):
        raise AssertionError("bootstrap must not materialize owner policy")

    def verify_current(self, desired):
        return LinuxNetworkVerification(True, ())


class NamespaceBootstrapHostRunner:
    def __init__(self):
        self.calls = []
        self.forwarding = True

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append((argv, input_text, check))
        prefix = ("ip", "netns", "exec", "rou0")
        if argv == (*prefix, "sysctl", "-q", "-w", "net.ipv4.ip_forward=0"):
            self.forwarding = False
            return CommandResult(0, "", "")
        if argv in {
            (*prefix, "sysctl", "-q", "-w", "net/ipv6/conf/all/forwarding=0"),
            (
                *prefix,
                "sysctl",
                "-q",
                "-w",
                "net/ipv6/conf/default/forwarding=0",
            ),
        }:
            return CommandResult(0, "", "")
        if argv == (*prefix, "sysctl", "-n", "net.ipv4.ip_forward"):
            return CommandResult(0, "1\n" if self.forwarding else "0\n", "")
        if argv in {
            (*prefix, "sysctl", "-n", "net/ipv6/conf/all/forwarding"),
            (
                *prefix,
                "sysctl",
                "-n",
                "net/ipv6/conf/default/forwarding",
            ),
        }:
            return CommandResult(0, "0\n", "")
        raise AssertionError(f"unexpected host command: {argv!r}")


class RuntimeBootstrapTests(unittest.TestCase):
    def test_success_exposes_adapter_only_after_verified_close(self):
        backend = FakeBootstrapBackend(LinuxDriverResult(True))

        result = bootstrap_linux_network_rules_adapter(
            backend,
            local_interface="host0",
        )

        self.assertTrue(result.success)
        self.assertIsNotNone(result.adapter)
        self.assertEqual(backend.close_calls, 1)

    def test_failed_close_does_not_expose_adapter(self):
        backend = FakeBootstrapBackend(
            LinuxDriverResult(False, "cannot verify close")
        )

        result = bootstrap_linux_network_rules_adapter(
            backend,
            local_interface="host0",
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.adapter)
        self.assertEqual(result.diagnostic, "cannot verify close")
        self.assertEqual(backend.close_calls, 1)

    def test_namespace_factory_closes_forwarding_inside_requested_namespace(self):
        host = NamespaceBootstrapHostRunner()

        result = bootstrap_linux_network_rules_adapter_in_namespace(
            "rou0",
            local_interface="host0",
            host_runner=host,
        )

        self.assertTrue(result.success, result.diagnostic)
        self.assertIsNotNone(result.adapter)
        self.assertFalse(host.forwarding)
        self.assertEqual(
            host.calls[0][0][:4],
            ("ip", "netns", "exec", "rou0"),
        )
        self.assertEqual(
            host.calls[1][0][:4],
            ("ip", "netns", "exec", "rou0"),
        )

    def test_result_rejects_inconsistent_adapter_exposure(self):
        with self.assertRaisesRegex(
            ValueError,
            "successful bootstrap requires an Adapter",
        ):
            LinuxRuntimeBootstrapResult(True)

        backend = FakeBootstrapBackend(LinuxDriverResult(True))
        adapter = bootstrap_linux_network_rules_adapter(
            backend,
            local_interface="host0",
        ).adapter
        assert adapter is not None

        with self.assertRaisesRegex(
            ValueError,
            "failed bootstrap must not expose an Adapter",
        ):
            LinuxRuntimeBootstrapResult(False, adapter=adapter)


if __name__ == "__main__":
    unittest.main()
