import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_driver import LinuxDriverResult, LinuxNetworkVerification
from rou.runtime_bootstrap import (
    LinuxRuntimeBootstrapResult,
    bootstrap_linux_network_rules_adapter,
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
