"""F2: dependency mutation is independent of retirement completion."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from rou.alpha_runtime import (
    AlphaReconcileResult,
    AlphaReconcileStatus,
    ManagedDeviceReleaseOutcome,
    reconcile_alpha_after_managed_release,
)


class AlphaReleaseRecoveryTests(unittest.TestCase):
    def test_touched_without_stop_requires_reconvergence(self):
        self.assertFalse(ManagedDeviceReleaseOutcome(()).requires_reconvergence)
        self.assertTrue(ManagedDeviceReleaseOutcome(
            (), dependencies_touched=True
        ).requires_reconvergence)
        self.assertTrue(ManagedDeviceReleaseOutcome(
            (), retirement_attempted=True
        ).requires_reconvergence)

    def test_recovery_uses_fresh_presence_before_payload_and_peers(self):
        prepared = SimpleNamespace(confirmed_managed_interfaces={"old"})
        domain, runner, manager, coordinator, probe, ownership = (
            Mock() for _ in range(6)
        )
        fresh = SimpleNamespace(realizations=("retained-reserve",))
        payload = AlphaReconcileResult(AlphaReconcileStatus.EXACT, None)
        availability, peers = Mock(), Mock()
        calls = []

        def presence(*args):
            calls.append("presence")
            prepared.confirmed_managed_interfaces = {"reserve"}
            return fresh

        def policy(*args):
            calls.append("payload")
            self.assertEqual(prepared.confirmed_managed_interfaces, {"reserve"})
            return payload

        def wg(*args):
            calls.append("wireguard")
            self.assertEqual(args[1], fresh.realizations)
            return availability, peers, None

        with patch("rou.alpha_runtime.converge_alpha_managed_device_presence", side_effect=presence), \
             patch("rou.alpha_runtime.reconcile_alpha_payload_once", side_effect=policy), \
             patch("rou.alpha_runtime.reconcile_alpha_availability_wireguard_once", side_effect=wg), \
             patch("rou.alpha_runtime.release_alpha_undemanded_devices") as release:
            result = reconcile_alpha_after_managed_release(
                prepared, domain, runner, manager, coordinator, probe, ownership
            )
        self.assertEqual(calls, ["presence", "payload", "wireguard"])
        release.assert_not_called()
        self.assertEqual(result.realizations, fresh.realizations)
        self.assertIs(result.availability, availability)
        self.assertIs(result.wireguard, peers)

    def test_unconfirmed_payload_does_not_publish_stale_wireguard(self):
        args = [Mock() for _ in range(7)]
        payload = AlphaReconcileResult(
            AlphaReconcileStatus.FAILED, None, diagnostic="failed"
        )
        with patch("rou.alpha_runtime.converge_alpha_managed_device_presence",
                   return_value=SimpleNamespace(realizations=())), \
             patch("rou.alpha_runtime.reconcile_alpha_payload_once", return_value=payload), \
             patch("rou.alpha_runtime.reconcile_alpha_availability_wireguard_once") as wg:
            result = reconcile_alpha_after_managed_release(*args)
        wg.assert_not_called()
        self.assertFalse(result.payload.ready)
        self.assertIsNone(result.availability)
        self.assertIsNone(result.wireguard)

    def test_observation_exception_contains_and_invalidates(self):
        prepared = SimpleNamespace(confirmed_managed_interfaces={"old"})
        domain = SimpleNamespace(namespace="test")
        args = [prepared, domain] + [Mock() for _ in range(5)]
        with patch("rou.alpha_runtime.converge_alpha_managed_device_presence",
                   side_effect=RuntimeError("observation failed")), \
             patch("rou.alpha_runtime.LinuxForwardingGateDriver"), \
             patch("rou.alpha_runtime.converge_forwarding_gate_once",
                   return_value=SimpleNamespace(confirmed=True)) as gate, \
             patch("rou.alpha_runtime.reconcile_alpha_payload_once") as policy:
            result = reconcile_alpha_after_managed_release(*args)
        gate.assert_called_once()
        policy.assert_not_called()
        self.assertFalse(result.payload.ready)
        self.assertIn("containment confirmed=True", result.payload.diagnostic)
        self.assertEqual(prepared.confirmed_managed_interfaces, frozenset())
        self.assertEqual(result.realizations, ())
        self.assertIsNone(result.availability)
