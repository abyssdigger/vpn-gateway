from __future__ import annotations

import unittest

from rou import parse_structural_config
from rou.binding import DeviceBindingState, LogicalPathId, PathBinding, project_device_bindings
from rou.interface_identity import InterfaceIdentity
from rou.payload_profile import build_payload_profile_requests


class PayloadProfileProjectionTests(unittest.TestCase):
    def test_profile_device_order_overrides_global_binding_order(self):
        cfg = parse_structural_config("""
[device.a]
enabled = true
expected_interfaces = ["fixed0", "a*/2"]

[device.b]
enabled = true
expected_interfaces = ["b*/2"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["b", "a"]
""")
        projection = project_device_bindings(
            cfg.device_binding_intents,
            DeviceBindingState.empty(),
            (
                InterfaceIdentity("a01", 11),
                InterfaceIdentity("b01", 21),
                InterfaceIdentity("fixed0", 10),
                InterfaceIdentity("b00", 20),
                InterfaceIdentity("a00", 12),
            ),
        )
        request = build_payload_profile_requests(
            cfg.profiles.values(), projection.bindings
        )[0]
        self.assertEqual(
            request.ordered_paths,
            (
                LogicalPathId("b", 0, 0),
                LogicalPathId("b", 0, 1),
                LogicalPathId("a", 0, 0),
                LogicalPathId("a", 1, 0),
                LogicalPathId("a", 1, 1),
            ),
        )

    def test_only_profile_devices_contribute(self):
        cfg = parse_structural_config("""
[device.a]
enabled = true
expected_interfaces = ["a0"]

[device.b]
enabled = true
expected_interfaces = ["b0"]

[profile.only-a]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["a"]

[profile.activate-b]
enabled = true
direction = "outbound"
destinations = ["192.0.2.0/24"]
device_order = ["b"]
""")
        projection = project_device_bindings(
            cfg.device_binding_intents,
            DeviceBindingState.empty(),
            (InterfaceIdentity("a0", 10), InterfaceIdentity("b0", 20)),
        )
        requests = {
            item.profile_id: item
            for item in build_payload_profile_requests(
                cfg.profiles.values(), projection.bindings
            )
        }
        self.assertEqual(
            requests["only-a"].ordered_paths,
            (LogicalPathId("a", 0, 0),),
        )

    def test_waiting_candidate_is_not_profile_member(self):
        cfg = parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/1"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")
        projection = project_device_bindings(
            cfg.device_binding_intents,
            DeviceBindingState.empty(),
            (InterfaceIdentity("vpns0", 10), InterfaceIdentity("vpns1", 11)),
        )
        request = build_payload_profile_requests(
            cfg.profiles.values(), projection.bindings
        )[0]
        self.assertEqual(request.ordered_paths, (LogicalPathId("oc", 0, 0),))
        self.assertEqual(len(projection.waiting), 1)

    def test_zero_path_enabled_profile_is_preserved(self):
        cfg = parse_structural_config("""
[device.future]
enabled = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["future"]
""")
        requests = build_payload_profile_requests(cfg.profiles.values(), ())
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].ordered_paths, ())

    def test_disabled_profile_is_omitted(self):
        cfg = parse_structural_config("""
[profile.future]
enabled = false
""")
        self.assertEqual(
            build_payload_profile_requests(cfg.profiles.values(), ()),
            (),
        )

    def test_concrete_endpoint_replacement_does_not_change_profile_membership_identity(self):
        cfg = parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")
        path = LogicalPathId("oc", 0, 0)
        first = build_payload_profile_requests(
            cfg.profiles.values(),
            (PathBinding(path, InterfaceIdentity("vpns0", 10)),),
        )
        second = build_payload_profile_requests(
            cfg.profiles.values(),
            (PathBinding(path, InterfaceIdentity("vpns0", 20)),),
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
