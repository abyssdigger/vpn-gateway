from __future__ import annotations

import unittest

from rou.managed_device_manager import (
    ManagedDeviceDesiredState,
    ManagedDeviceManager,
)
from rou.managed_wireguard_adapter import (
    ManagedWireGuardObservation,
    ManagedWireGuardState,
)
from rou.release1_config import parse_current_config


KEY_A = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="


def managed_config(*, referenced: bool = True):
    profile = (
        """
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.77.0.0/24"]
device_order = ["wg-main"]
"""
        if referenced
        else ""
    )
    return parse_current_config(
        f"""
[device.wg-main]
enabled = true

[device.wg-main.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "/secret/private.key"

[[device.wg-main.managed_vpn.peers]]
id = "edge-a"
public_key = "{KEY_A}"
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"
{profile}
"""
    )


def external_config():
    return parse_current_config(
        """
[device.external]
enabled = true
expected_interfaces = ["vpn0"]
"""
    )


class FakeLifecycle:
    def __init__(self):
        self.calls = []
        self.state = {}
        self.fail_present = False
        self.generation = "gen-a"

    def desired_generation(self, device_id, desired):
        self.calls.append(("generation", device_id))
        return self.generation

    def observe(self, device_id):
        self.calls.append(("observe", device_id))
        return self.state.get(
            device_id,
            ManagedWireGuardObservation(
                device_id,
                ManagedWireGuardState.ABSENT,
            ),
        )

    def converge_present(self, device_id, desired):
        self.calls.append(("present", device_id))
        if self.fail_present:
            raise RuntimeError("present failed")
        observation = ManagedWireGuardObservation(
            device_id,
            ManagedWireGuardState.PRESENT,
            confirmed_generation=self.generation,
            interface=__import__(
                "rou.interface_identity",
                fromlist=["InterfaceIdentity"],
            ).InterfaceIdentity(desired.interface, 7),
        )
        self.state[device_id] = observation
        return observation

    def converge_absent(self, device_id):
        self.calls.append(("absent", device_id))
        observation = ManagedWireGuardObservation(
            device_id,
            ManagedWireGuardState.ABSENT,
        )
        self.state[device_id] = observation
        return observation


class ManagedDeviceManagerTests(unittest.TestCase):
    def test_external_device_is_outside_manager_scope(self):
        lifecycle = FakeLifecycle()
        manager = ManagedDeviceManager(lifecycle)
        self.assertEqual(manager.reconcile(external_config()), ())
        self.assertEqual(lifecycle.calls, [])

    def test_structurally_demanded_managed_device_is_confirmed_present(self):
        lifecycle = FakeLifecycle()
        manager = ManagedDeviceManager(lifecycle)
        result = manager.reconcile(managed_config())
        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertIs(item.desired_state, ManagedDeviceDesiredState.PRESENT)
        self.assertEqual(item.desired_generation, "gen-a")
        self.assertIs(item.confirmed_state, ManagedWireGuardState.PRESENT)
        self.assertEqual(item.confirmed_generation, "gen-a")
        self.assertIsNone(item.problem)
        self.assertEqual(
            lifecycle.calls,
            [("generation", "wg-main"), ("present", "wg-main")],
        )

    def test_undemanded_present_device_waits_for_dependency_release(self):
        lifecycle = FakeLifecycle()
        lifecycle.state["wg-main"] = ManagedWireGuardObservation(
            "wg-main",
            ManagedWireGuardState.PRESENT,
            interface=__import__(
                "rou.interface_identity",
                fromlist=["InterfaceIdentity"],
            ).InterfaceIdentity("wg0", 7),
        )
        manager = ManagedDeviceManager(lifecycle)
        item = manager.reconcile(managed_config(referenced=False))[0]
        self.assertIs(item.desired_state, ManagedDeviceDesiredState.ABSENT)
        self.assertTrue(item.waiting_for_dependencies)
        self.assertEqual(lifecycle.calls, [("observe", "wg-main")])

    def test_dependency_release_allows_confirmed_absence(self):
        lifecycle = FakeLifecycle()
        manager = ManagedDeviceManager(lifecycle)
        item = manager.reconcile(
            managed_config(referenced=False),
            dependency_free_device_ids=frozenset({"wg-main"}),
        )[0]
        self.assertIs(item.confirmed_state, ManagedWireGuardState.ABSENT)
        self.assertFalse(item.waiting_for_dependencies)
        self.assertEqual(lifecycle.calls, [("absent", "wg-main")])

    def test_removed_management_is_retained_until_owned_instance_is_absent(self):
        lifecycle = FakeLifecycle()
        manager = ManagedDeviceManager(lifecycle)
        manager.reconcile(managed_config())
        lifecycle.calls.clear()

        pending = manager.reconcile(external_config())
        self.assertEqual(len(pending), 1)
        self.assertTrue(pending[0].waiting_for_dependencies)
        self.assertEqual(lifecycle.calls, [("observe", "wg-main")])

        lifecycle.calls.clear()
        removed = manager.reconcile(
            external_config(),
            dependency_free_device_ids=frozenset({"wg-main"}),
        )
        self.assertIs(removed[0].confirmed_state, ManagedWireGuardState.ABSENT)
        self.assertEqual(lifecycle.calls, [("absent", "wg-main")])

        lifecycle.calls.clear()
        self.assertEqual(manager.reconcile(external_config()), ())
        self.assertEqual(lifecycle.calls, [])

    def test_lifecycle_failure_is_problem_not_false_confirmation(self):
        lifecycle = FakeLifecycle()
        lifecycle.fail_present = True
        item = ManagedDeviceManager(lifecycle).reconcile(managed_config())[0]
        self.assertIsNone(item.confirmed_state)
        self.assertEqual(item.desired_generation, "gen-a")
        self.assertIn("present failed", item.problem or "")

    def test_generation_mismatch_is_problem(self):
        lifecycle = FakeLifecycle()

        def mismatched(device_id, desired):
            lifecycle.calls.append(("present", device_id))
            return ManagedWireGuardObservation(
                device_id,
                ManagedWireGuardState.PRESENT,
                interface=__import__(
                    "rou.interface_identity",
                    fromlist=["InterfaceIdentity"],
                ).InterfaceIdentity("wg0", 7),
                confirmed_generation="gen-b",
            )

        lifecycle.converge_present = mismatched
        item = ManagedDeviceManager(lifecycle).reconcile(managed_config())[0]
        self.assertIsNone(item.confirmed_state)
        self.assertIn("differs from desired", item.problem or "")


if __name__ == "__main__":
    unittest.main()
