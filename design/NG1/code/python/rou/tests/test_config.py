import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.config import ConfigError, parse_active_config
from rou.domain import Direction, MatchKind


class ConfigTests(unittest.TestCase):
    def test_minimal_disabled_placeholders(self):
        cfg = parse_active_config('''
[device.wg-future]
enabled = false
nonsense = "ignored while disabled"

[profile.future]
enabled = false
direction = 123
''')
        self.assertFalse(cfg.devices['wg-future'].enabled)
        self.assertFalse(cfg.profiles['future'].enabled)

    def test_enabled_device_exact_and_prefix(self):
        cfg = parse_active_config('''
[device.oc-main]
enabled = true
expected_interfaces = ["wg0", "vpns*/5"]
''')
        dev = cfg.devices['oc-main']
        self.assertEqual(dev.interface_quota, 6)
        self.assertEqual(dev.expected_interfaces[0].match.kind, MatchKind.EXACT)
        self.assertEqual(dev.expected_interfaces[0].interface_quota, 1)
        self.assertEqual(dev.expected_interfaces[1].match.kind, MatchKind.PREFIX)
        self.assertEqual(dev.expected_interfaces[1].match.value, 'vpns')
        self.assertEqual(dev.expected_interfaces[1].interface_quota, 5)

    def test_prefix_without_quota_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'positive-quota'):
            parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*"]
''')

    def test_exact_with_quota_rejected(self):
        with self.assertRaises(ConfigError):
            parse_active_config('''
[device.wg]
enabled = true
expected_interfaces = ["wg0/1"]
''')

    def test_enabled_device_requires_nonempty_expected_interfaces(self):
        with self.assertRaisesRegex(ConfigError, 'non-empty'):
            parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = []
''')

    def test_enabled_is_mandatory(self):
        with self.assertRaisesRegex(ConfigError, 'enabled is required'):
            parse_active_config('''
[device.oc]
expected_interfaces = ["vpns*/2"]
''')

    def test_enabled_must_be_bool_not_integer(self):
        with self.assertRaisesRegex(ConfigError, 'must be boolean'):
            parse_active_config('''
[device.oc]
enabled = 1
''')

    def test_id_grammar(self):
        with self.assertRaisesRegex(ConfigError, 'invalid Device id'):
            parse_active_config('''
[device.oc_main]
enabled = false
''')

    def test_enabled_profile_full_model(self):
        cfg = parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8", "192.168.100.1/32"]
device_order = ["oc"]
''')
        p = cfg.profiles['corp']
        self.assertEqual(p.direction, Direction.OUTBOUND)
        self.assertEqual(p.destinations, (
            ipaddress.IPv4Network('10.0.0.0/8'),
            ipaddress.IPv4Network('192.168.100.1/32'),
        ))
        self.assertEqual(p.device_order, ('oc',))
        self.assertEqual(cfg.active_device_names, frozenset({'oc'}))

    def test_host_bits_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'strict IPv4 CIDR'):
            parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.1/8"]
device_order = ["oc"]
''')

    def test_ipv6_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'must be IPv4'):
            parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["2001:db8::/32"]
device_order = ["oc"]
''')

    def test_duplicate_destination_across_profiles_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'duplicated by enabled Profiles'):
            parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]

[profile.a]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]

[profile.b]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
''')

    def test_overlapping_different_prefixes_are_allowed(self):
        cfg = parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]

[profile.a]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]

[profile.b]
enabled = true
direction = "inbound"
destinations = ["10.1.0.0/16"]
device_order = ["oc"]
''')
        self.assertEqual(set(cfg.profiles), {'a', 'b'})

    def test_unknown_device_reference_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'unknown Device'):
            parse_active_config('''
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["missing"]
''')

    def test_known_disabled_device_reference_is_valid_and_inactive(self):
        cfg = parse_active_config('''
[device.wg-future]
enabled = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg-future"]
''')
        self.assertEqual(cfg.active_device_names, frozenset())

    def test_duplicate_device_order_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'duplicate Device id'):
            parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc", "oc"]
''')

    def test_overlap_inside_device_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'overlaps'):
            parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2", "vpns00"]
''')

    def test_overlap_across_active_devices_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'active ExpectedInterface selectors overlap'):
            parse_active_config('''
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
''')

    def test_overlap_with_enabled_but_unused_device_is_allowed(self):
        cfg = parse_active_config('''
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
''')
        self.assertEqual(cfg.active_device_names, frozenset({'a'}))

    def test_unsupported_enabled_field_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'unsupported field'):
            parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
publication = ["44443/udp>44443"]
''')

    def test_bad_direction_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'direction must be one of'):
            parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]

[profile.corp]
enabled = true
direction = "both"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
''')


if __name__ == '__main__':
    unittest.main()
