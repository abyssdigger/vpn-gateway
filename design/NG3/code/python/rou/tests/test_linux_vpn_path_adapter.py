from __future__ import annotations

import json
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_vpn_path_adapter import (
    LinuxVpnPathAdapter,
    VpnPathObservationError,
)


class Runner:
    def __init__(self, payload=None, *, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    def run(self, argv):
        self.calls.append(tuple(argv))
        if self.error is not None:
            raise self.error
        return self.payload


class LinuxVpnPathAdapterTests(unittest.TestCase):
    def test_observes_one_full_current_inventory(self):
        runner = Runner(
            json.dumps(
                [
                    {"ifname": "lo", "ifindex": 1},
                    {"ifname": "host0", "ifindex": 2},
                    {"ifname": "vpn0", "ifindex": 11},
                ]
            )
        )
        adapter = LinuxVpnPathAdapter(runner, "managed")
        result = adapter.observe_interfaces(
            required_host_boundary=InterfaceIdentity("host0", 2)
        )

        self.assertEqual(
            result.interfaces,
            (
                InterfaceIdentity("lo", 1),
                InterfaceIdentity("host0", 2),
                InterfaceIdentity("vpn0", 11),
            ),
        )
        self.assertEqual(
            runner.calls,
            [("ip", "-n", "managed", "-j", "link", "show")],
        )

    def test_same_name_new_ifindex_does_not_confirm_old_host_boundary(self):
        runner = Runner(
            json.dumps(
                [
                    {"ifname": "lo", "ifindex": 1},
                    {"ifname": "host0", "ifindex": 99},
                ]
            )
        )
        adapter = LinuxVpnPathAdapter(runner, "managed")

        with self.assertRaisesRegex(
            VpnPathObservationError,
            "same-name different generation",
        ):
            adapter.observe_interfaces(
                required_host_boundary=InterfaceIdentity("host0", 2)
            )

    def test_missing_host_boundary_is_observation_failure(self):
        runner = Runner(json.dumps([{"ifname": "lo", "ifindex": 1}]))
        adapter = LinuxVpnPathAdapter(runner, "managed")

        with self.assertRaisesRegex(
            VpnPathObservationError,
            "interface is absent",
        ):
            adapter.observe_interfaces(
                required_host_boundary=InterfaceIdentity("host0", 2)
            )

    def test_invalid_inventory_is_not_converted_to_empty(self):
        adapter = LinuxVpnPathAdapter(Runner("{"), "managed")
        with self.assertRaisesRegex(
            VpnPathObservationError,
            "inventory is invalid",
        ):
            adapter.observe_interfaces()

    def test_lower_observation_failure_is_not_converted_to_empty(self):
        adapter = LinuxVpnPathAdapter(
            Runner(error=RuntimeError("synthetic command failure")),
            "managed",
        )
        with self.assertRaisesRegex(
            VpnPathObservationError,
            "observation command failed",
        ):
            adapter.observe_interfaces()

    def test_adapter_retains_no_current_inventory(self):
        runner = Runner(
            json.dumps([{"ifname": "vpn0", "ifindex": 10}])
        )
        adapter = LinuxVpnPathAdapter(runner, "managed")
        first = adapter.observe_interfaces()

        runner.payload = json.dumps([{"ifname": "vpn0", "ifindex": 11}])
        second = adapter.observe_interfaces()

        self.assertEqual(
            first.interfaces,
            (InterfaceIdentity("vpn0", 10),),
        )
        self.assertEqual(
            second.interfaces,
            (InterfaceIdentity("vpn0", 11),),
        )
        self.assertEqual(len(runner.calls), 2)


if __name__ == "__main__":
    unittest.main()
