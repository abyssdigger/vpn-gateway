from __future__ import annotations

import ipaddress
import unittest

from rou import ConfigError, Direction, SelectorKind, parse_structural_config


class StructuralConfigTests(unittest.TestCase):
    def test_valid_core_normalizes_order_and_active_devices(self):
        cfg = parse_structural_config("""
[device.oc-main]
enabled = true
expected_interfaces = ["wg0", "vpns*/2"]

[device.wg-future]
enabled = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8", "192.168.100.1/32"]
device_order = ["oc-main", "wg-future"]
""")
        self.assertEqual(cfg.active_device_ids, frozenset({"oc-main"}))
        self.assertEqual(
            tuple(intent.device_id for intent in cfg.device_binding_intents),
            ("oc-main",),
        )
        selectors = cfg.devices["oc-main"].expected_interfaces
        self.assertEqual(selectors[0].kind, SelectorKind.EXACT)
        self.assertEqual(selectors[0].quota, 1)
        self.assertEqual(selectors[1].kind, SelectorKind.PREFIX)
        self.assertEqual(selectors[1].quota, 2)
        self.assertEqual(
            cfg.profiles["corp"].destinations,
            (
                ipaddress.IPv4Network("10.0.0.0/8"),
                ipaddress.IPv4Network("192.168.100.1/32"),
            ),
        )

    def test_ids_and_enabled_are_strict(self):
        with self.assertRaisesRegex(ConfigError, "invalid Device id"):
            parse_structural_config("""
[device.Bad_ID]
enabled = false
""")
        with self.assertRaisesRegex(ConfigError, "enabled is required"):
            parse_structural_config("""
[device.ok]
expected_interfaces = ["wg0"]
""")
        with self.assertRaisesRegex(ConfigError, "enabled must be boolean"):
            parse_structural_config("""
[device.ok]
enabled = 1
""")

    def test_disabled_placeholder_skips_deep_validation(self):
        cfg = parse_structural_config("""
[device.future]
enabled = false
expected_interfaces = "not-an-array"
unknown_future_field = { anything = true }

[profile.future]
enabled = false
direction = 123
device_order = "not-an-array"
""")
        self.assertFalse(cfg.devices["future"].enabled)
        self.assertFalse(cfg.profiles["future"].enabled)

    def test_enabled_device_requires_nonempty_expected_interfaces(self):
        for body in ("", "expected_interfaces = []"):
            with self.subTest(body=body):
                with self.assertRaisesRegex(ConfigError, "non-empty array"):
                    parse_structural_config(f"""
[device.oc]
enabled = true
{body}
""")

    def test_selector_forms_and_quota_are_strict(self):
        for selector in ("vpns*", "vpns*/0", "vpns*/-1", "vpns*/1.5", "vpns/2"):
            with self.subTest(selector=selector):
                with self.assertRaisesRegex(ConfigError, "<ifname> or <prefix>"):
                    parse_structural_config(f"""
[device.oc]
enabled = true
expected_interfaces = ["{selector}"]
""")

    def test_selector_overlap_within_enabled_device_rejected(self):
        with self.assertRaisesRegex(ConfigError, "overlaps"):
            parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2", "vpns00"]
""")

    def test_active_cross_device_overlap_rejected(self):
        with self.assertRaisesRegex(ConfigError, "active ExpectedInterface selectors overlap"):
            parse_structural_config("""
[device.a]
enabled = true
expected_interfaces = ["vpn*/2"]

[device.b]
enabled = true
expected_interfaces = ["vpn0"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["a", "b"]
""")

    def test_unreferenced_device_does_not_participate_in_cross_device_overlap(self):
        cfg = parse_structural_config("""
[device.a]
enabled = true
expected_interfaces = ["vpn*/2"]

[device.b]
enabled = true
expected_interfaces = ["vpn0"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["a"]
""")
        self.assertEqual(cfg.active_device_ids, frozenset({"a"}))

    def test_profile_strict_ipv4_and_duplicates(self):
        for bad in ("10.1.2.3/8", "2001:db8::/32"):
            with self.subTest(bad=bad):
                with self.assertRaises(ConfigError):
                    parse_structural_config(f"""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["{bad}"]
device_order = ["oc"]
""")
        with self.assertRaisesRegex(ConfigError, "destinations contains duplicates"):
            parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8", "10.0.0.0/8"]
device_order = ["oc"]
""")

    def test_duplicate_exact_destination_across_profiles_rejected(self):
        with self.assertRaisesRegex(ConfigError, "duplicated by enabled Profiles"):
            parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]

[profile.a]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]

[profile.b]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")

    def test_different_length_destination_overlap_allowed(self):
        cfg = parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]

[profile.a]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]

[profile.b]
enabled = true
direction = "outbound"
destinations = ["10.1.0.0/16"]
device_order = ["oc"]
""")
        self.assertEqual(set(cfg.profiles), {"a", "b"})

    def test_device_references_unknown_disabled_and_duplicates(self):
        with self.assertRaisesRegex(ConfigError, "unknown Device"):
            parse_structural_config("""
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["missing"]
""")
        with self.assertRaisesRegex(ConfigError, "device_order contains duplicates"):
            parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc", "oc"]
""")
        cfg = parse_structural_config("""
[device.future]
enabled = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["future"]
""")
        self.assertEqual(cfg.active_device_ids, frozenset())

    def test_release1_inbound_capacity_validation(self):
        for direction in ("inbound", "bidirectional"):
            with self.subTest(direction=direction):
                with self.assertRaisesRegex(ConfigError, "capacity is 2"):
                    parse_structural_config(f"""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]

[profile.support]
enabled = true
direction = "{direction}"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")

    def test_release1_inbound_capacity_zero_and_one_allowed(self):
        zero = parse_structural_config("""
[device.future]
enabled = false

[profile.support]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/8"]
device_order = ["future"]
""")
        self.assertEqual(zero.profiles["support"].direction, Direction.INBOUND)

        one = parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]

[profile.support]
enabled = true
direction = "bidirectional"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")
        self.assertEqual(one.devices["oc"].path_capacity, 1)

    def test_outbound_capacity_greater_than_one_allowed(self):
        cfg = parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/3"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")
        self.assertEqual(cfg.devices["oc"].path_capacity, 3)

    def test_active_transport_policy_fields_are_not_guessed(self):
        for field in ('nat = "none"', 'publications = ["44443/tcp"]'):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ConfigError, "unsupported field"):
                    parse_structural_config(f"""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]
{field}
""")


if __name__ == "__main__":
    unittest.main()
