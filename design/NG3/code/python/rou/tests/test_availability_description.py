from __future__ import annotations

from ipaddress import IPv4Address
import unittest

from rou.availability_description import (
    AvailabilityDescriptionResolutionError,
    resolve_availability_probe_intents,
)
from rou.binding import LogicalPathId
from rou.release1_config import parse_release1_config


WG0 = LogicalPathId("wg", 0, 0)
WG1 = LogicalPathId("wg", 0, 1)
OC0 = LogicalPathId("oc", 0, 0)


class AvailabilityDescriptionResolverTests(unittest.TestCase):
    def test_profile_default_is_copied_per_subject(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg*/2"]
use_outbound_nat = false

[device.wg.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg"]
availability_check = "default"
""")
        intents = resolve_availability_probe_intents(cfg, (WG1, WG0))
        self.assertEqual(
            [(item.owner.profile_id, item.owner.path_id) for item in intents],
            [("corp", WG0), ("corp", WG1)],
        )
        self.assertEqual(
            {item.target for item in intents},
            {IPv4Address("198.51.100.10")},
        )

    def test_profile_override_wins_over_device_default(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false

[device.wg.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[profile.accounting]
enabled = true
direction = "outbound"
destinations = ["10.20.0.0/16"]
device_order = ["wg"]

[profile.accounting.availability_check]
mechanism = "icmp"
target = "10.20.30.10"
""")
        intents = resolve_availability_probe_intents(cfg, (WG0,))
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].target, IPv4Address("10.20.30.10"))

    def test_same_path_can_have_different_profile_criteria(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false

[device.wg.availability_check]
mechanism = "icmp"
target = "1.1.1.1"

[profile.internet]
enabled = true
direction = "outbound"
destinations = ["0.0.0.0/0"]
device_order = ["wg"]
availability_check = "default"

[profile.accounting]
enabled = true
direction = "outbound"
destinations = ["10.20.0.0/16"]
device_order = ["wg"]

[profile.accounting.availability_check]
mechanism = "icmp"
target = "10.20.30.10"
""")
        intents = resolve_availability_probe_intents(cfg, (WG0,))
        by_profile = {
            item.owner.profile_id: item.target
            for item in intents
        }
        self.assertEqual(
            by_profile,
            {
                "accounting": IPv4Address("10.20.30.10"),
                "internet": IPv4Address("1.1.1.1"),
            },
        )

    def test_disabled_profile_creates_no_probe_intent(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false

[device.wg.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[profile.future]
enabled = false
availability_check = "default"
""")
        self.assertEqual(
            resolve_availability_probe_intents(cfg, (WG0,)),
            (),
        )

    def test_paths_outside_profile_device_order_are_ignored(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false

[device.wg.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[device.oc]
enabled = true
expected_interfaces = ["oc0"]
use_outbound_nat = false

[device.oc.availability_check]
mechanism = "icmp"
target = "198.51.100.20"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg"]
availability_check = "default"
""")
        intents = resolve_availability_probe_intents(cfg, (OC0, WG0))
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].owner.path_id, WG0)

    def test_duplicate_current_path_is_rejected(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false
""")
        with self.assertRaisesRegex(
            AvailabilityDescriptionResolutionError,
            "duplicates",
        ):
            resolve_availability_probe_intents(cfg, (WG0, WG0))


if __name__ == "__main__":
    unittest.main()
