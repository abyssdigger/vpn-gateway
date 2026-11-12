import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.config import ConfigError, parse_active_config
from rou.domain import (
    Direction,
    EnvelopeAction,
    EnvelopeDirection,
    EnvelopeProtocol,
    MatchKind,
    NatMode,
    TransportProtocol,
)


def parse(body: str):
    return parse_active_config("schema_version = 1\n" + body)


class ConfigTests(unittest.TestCase):
    def test_schema_version_is_mandatory(self):
        with self.assertRaisesRegex(ConfigError, "schema_version = 1"):
            parse_active_config("[device.future]\nenabled=false\n")

    def test_unknown_schema_version_rejected(self):
        with self.assertRaisesRegex(ConfigError, "schema_version = 1"):
            parse_active_config(
                "schema_version=2\n[device.future]\nenabled=false\n"
            )

    def test_minimal_disabled_placeholders(self):
        cfg = parse("""
[device.wg-future]
enabled = false
nonsense = "ignored while disabled"

[profile.future]
enabled = false
direction = 123
""")
        self.assertFalse(cfg.devices["wg-future"].enabled)
        self.assertFalse(cfg.profiles["future"].enabled)

    def test_enabled_device_exact_prefix_and_explicit_nat(self):
        cfg = parse("""
[device.oc-main]
enabled = true
expected_interfaces = ["wg0", "vpns*/5"]
nat = "masquerade"
""")
        dev = cfg.devices["oc-main"]
        self.assertEqual(dev.interface_quota, 6)
        self.assertEqual(dev.nat, NatMode.MASQUERADE)
        self.assertEqual(
            dev.expected_interfaces[0].match.kind,
            MatchKind.EXACT,
        )
        self.assertEqual(dev.expected_interfaces[1].match.kind, MatchKind.PREFIX)
        self.assertEqual(dev.expected_interfaces[1].match.value, "vpns")

    def test_enabled_device_requires_explicit_nat(self):
        with self.assertRaisesRegex(ConfigError, "nat must be"):
            parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
""")

    def test_prefix_without_quota_rejected(self):
        with self.assertRaisesRegex(ConfigError, "positive-quota"):
            parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*"]
nat = "none"
""")

    def test_exact_with_quota_rejected(self):
        with self.assertRaises(ConfigError):
            parse("""
[device.wg]
enabled = true
expected_interfaces = ["wg0/1"]
nat = "none"
""")

    def test_enabled_device_requires_nonempty_expected_interfaces(self):
        with self.assertRaisesRegex(ConfigError, "non-empty"):
            parse("""
[device.oc]
enabled = true
expected_interfaces = []
nat = "none"
""")

    def test_enabled_is_mandatory(self):
        with self.assertRaisesRegex(ConfigError, "enabled is required"):
            parse("""
[device.oc]
expected_interfaces = ["vpns*/2"]
nat = "none"
""")

    def test_id_grammar(self):
        with self.assertRaisesRegex(ConfigError, "invalid Device id"):
            parse("""
[device.oc_main]
enabled = false
""")

    def test_enabled_profile_full_model(self):
        cfg = parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8", "192.168.100.1/32"]
device_order = ["oc"]
""")
        profile = cfg.profiles["corp"]
        self.assertEqual(profile.direction, Direction.OUTBOUND)
        self.assertEqual(
            profile.destinations,
            (
                ipaddress.IPv4Network("10.0.0.0/8"),
                ipaddress.IPv4Network("192.168.100.1/32"),
            ),
        )
        self.assertEqual(cfg.active_device_names, frozenset({"oc"}))

    def test_host_bits_and_ipv6_rejected(self):
        for bad in ("10.0.0.1/8", "2001:db8::/32"):
            with self.subTest(bad=bad):
                with self.assertRaises(ConfigError):
                    parse(f"""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["{bad}"]
device_order = ["oc"]
""")

    def test_duplicate_destination_across_profiles_rejected(self):
        with self.assertRaisesRegex(ConfigError, "duplicated by enabled Profiles"):
            parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"

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
""")

    def test_overlapping_different_prefixes_are_allowed(self):
        cfg = parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"

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
""")
        self.assertEqual(set(cfg.profiles), {"a", "b"})

    def test_unknown_and_disabled_device_references(self):
        with self.assertRaisesRegex(ConfigError, "unknown Device"):
            parse("""
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["missing"]
""")

        cfg = parse("""
[device.wg-future]
enabled = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg-future"]
""")
        self.assertEqual(cfg.active_device_names, frozenset())

    def test_selector_overlap_validation(self):
        with self.assertRaisesRegex(ConfigError, "overlaps"):
            parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2", "vpns00"]
nat = "none"
""")

        with self.assertRaisesRegex(
            ConfigError,
            "active ExpectedInterface selectors overlap",
        ):
            parse("""
[device.a]
enabled = true
expected_interfaces = ["vpn*/2"]
nat = "none"

[device.b]
enabled = true
expected_interfaces = ["vpn0"]
nat = "none"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["a", "b"]
""")

    def test_publication_shorthand_range_and_protocol(self):
        cfg = parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"
publications = [
  "44443/tcp",
  "5678/udp>7890",
  "4700:4900/udp>55200:55400",
]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")
        pubs = cfg.devices["oc"].publications
        self.assertEqual(pubs[0].protocol, TransportProtocol.TCP)
        self.assertEqual((pubs[0].external.start, pubs[0].internal.start), (44443, 44443))
        self.assertEqual((pubs[1].external.start, pubs[1].internal.start), (5678, 7890))
        self.assertEqual(pubs[2].external.size, 201)
        self.assertEqual(pubs[2].internal.size, 201)

    def test_publication_bad_cardinality_and_port_rejected(self):
        for publication in (
            "4700:4900/udp>55200:55300",
            "0/tcp",
            "70000/udp",
        ):
            with self.subTest(publication=publication):
                with self.assertRaises(ConfigError):
                    parse(f"""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"
publications = ["{publication}"]
""")

    def test_active_publication_external_collision_rejected(self):
        with self.assertRaisesRegex(ConfigError, "external.*overlap"):
            parse("""
[device.a]
enabled = true
expected_interfaces = ["a0"]
nat = "none"
publications = ["4000:4010/tcp>5000:5010"]

[device.b]
enabled = true
expected_interfaces = ["b0"]
nat = "none"
publications = ["4005/tcp>6000"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["a", "b"]
""")

    def test_cross_device_internal_publication_collision_rejected(self):
        with self.assertRaisesRegex(ConfigError, "internal.*overlap"):
            parse("""
[device.a]
enabled = true
expected_interfaces = ["a0"]
nat = "none"
publications = ["4000/tcp>5000"]

[device.b]
enabled = true
expected_interfaces = ["b0"]
nat = "none"
publications = ["6000/tcp>5000"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["a", "b"]
""")

    def test_same_device_internal_alias_is_allowed(self):
        cfg = parse("""
[device.a]
enabled = true
expected_interfaces = ["a0"]
nat = "none"
publications = ["4000/tcp>5000", "4001/tcp>5000"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["a"]
""")
        self.assertEqual(len(cfg.devices["a"].publications), 2)

    def test_envelope_parses_ordered_rules_and_ports(self):
        cfg = parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"

[device.oc.traffic_envelope]
default = "drop"

[[device.oc.traffic_envelope.rules]]
direction = "from-device"
action = "drop"
source = "10.20.0.0/16"
protocol = "tcp"
destination_ports = ["8007", "9000-9010"]

[[device.oc.traffic_envelope.rules]]
direction = "to-device"
action = "allow"
destination = "192.168.50.0/24"
protocol = "udp"
destination_ports = ["53"]
""")
        envelope = cfg.devices["oc"].traffic_envelope
        self.assertIsNotNone(envelope)
        assert envelope is not None
        self.assertEqual(envelope.default_action, EnvelopeAction.DROP)
        self.assertEqual(envelope.rules[0].direction, EnvelopeDirection.FROM_DEVICE)
        self.assertEqual(envelope.rules[0].protocol, EnvelopeProtocol.TCP)
        self.assertEqual(envelope.rules[0].destination_ports[1].start, 9000)
        self.assertEqual(envelope.rules[1].action, EnvelopeAction.ALLOW)

    def test_envelope_ports_require_tcp_or_udp(self):
        with self.assertRaisesRegex(ConfigError, "ports require tcp or udp"):
            parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"

[device.oc.traffic_envelope]
default = "allow"

[[device.oc.traffic_envelope.rules]]
direction = "from-device"
action = "drop"
protocol = "icmp"
destination_ports = ["80"]
""")

    def test_envelope_overlapping_port_ranges_rejected(self):
        with self.assertRaisesRegex(ConfigError, "overlapping ranges"):
            parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"

[device.oc.traffic_envelope]
default = "allow"

[[device.oc.traffic_envelope.rules]]
direction = "to-device"
action = "drop"
protocol = "tcp"
destination_ports = ["80-90", "90-100"]
""")

    def test_remote_initiated_capacity_two_is_rejected(self):
        with self.assertRaisesRegex(
            ConfigError,
            "requires active interface capacity exactly 1",
        ):
            parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"

[device.oc.traffic_envelope]
default = "drop"

[profile.support]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")

    def test_remote_initiated_capacity_one_with_restrictive_envelope_is_allowed(self):
        cfg = parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]
nat = "none"

[device.oc.traffic_envelope]
default = "drop"

[[device.oc.traffic_envelope.rules]]
direction = "from-device"
action = "allow"
source = "10.0.0.0/8"
destination = "192.168.50.10/32"
protocol = "tcp"
destination_ports = ["22"]

[profile.support]
enabled = true
direction = "bidirectional"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")
        self.assertEqual(
            cfg.profiles["support"].direction,
            Direction.BIDIRECTIONAL,
        )

    def test_remote_initiated_requires_restrictive_envelope(self):
        with self.assertRaisesRegex(
            ConfigError,
            "traffic_envelope default='drop'",
        ):
            parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]
nat = "none"

[profile.support]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")

        with self.assertRaisesRegex(
            ConfigError,
            "traffic_envelope default='drop'",
        ):
            parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]
nat = "none"

[device.oc.traffic_envelope]
default = "allow"

[profile.support]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")

    def test_disabled_device_does_not_count_toward_remote_initiated_capacity(self):
        cfg = parse("""
[device.oc]
enabled = true
expected_interfaces = ["vpns0"]
nat = "none"

[device.oc.traffic_envelope]
default = "drop"

[device.wg-future]
enabled = false

[profile.support]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc", "wg-future"]
""")
        self.assertEqual(
            cfg.profiles["support"].direction,
            Direction.INBOUND,
        )

    def test_disabled_device_does_not_deep_validate_new_fields(self):
        cfg = parse("""
[device.future]
enabled = false
nat = 123
publications = ["not a publication"]
traffic_envelope = "not a table"
""")
        self.assertFalse(cfg.devices["future"].enabled)


if __name__ == "__main__":
    unittest.main()
