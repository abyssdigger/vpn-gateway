import ipaddress
import unittest

from rou.domain import Direction
from rou.port_bundle import PortBundle, PortSpan
from rou.release1_config import Release1ConfigError, parse_release1_config


class Release1ConfigTests(unittest.TestCase):
    def test_complete_canonical_surface_normalizes(self):
        cfg = parse_release1_config("""
default_snat_address = "198.19.255.10"

[device.wg-main]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = true
allow_vpn_client = "udp:51820>198.51.100.10:51820"
firewall = [
    "out allow tcp to 10.20.0.0/16:443 # HTTPS to corp",
    "out allow icmp to 10.20.0.0/16",
]

[device.wg-main.availability_check]
mechanism = "icmp"
target = "198.51.100.11"

[device.oc-backup]
enabled = true
expected_interfaces = ["vpn*/2"]
use_outbound_nat = false
allow_vpn_client = [
    "tcp>198.51.100.20:443",
    "udp>198.51.100.20:443",
]

[device.oc-backup.availability_check]
mechanism = "icmp"
target = "198.51.100.12"

[device.oc-server]
enabled = true
expected_interfaces = ["ocsvr0"]
publish_vpn_server = [
    "tcp/eth0:44443>443",
    "udp/192.0.2.10:44443>443",
]
firewall = [
    "in allow tcp from 10.30.0.0/16 to 10.0.0.20/32:22",
]

[profile.corporate]
enabled = true
direction = "outbound"
destinations = ["10.20.0.0/16"]
device_order = ["wg-main", "oc-backup"]
availability_check = "default"

[profile.remote-admin]
enabled = true
direction = "inbound+snat"
destinations = ["10.30.0.0/16"]
device_order = ["oc-server"]
[profile.remote-admin.availability_check]
mechanism = "icmp"
target = "10.30.0.1"
""")
        self.assertEqual(
            cfg.structural.profiles["remote-admin"].direction,
            Direction.INBOUND,
        )
        self.assertEqual(
            cfg.profiles["remote-admin"].effective_snat_address,
            ipaddress.IPv4Address("198.19.255.10"),
        )
        self.assertEqual(
            cfg.default_snat_address,
            ipaddress.IPv4Address("198.19.255.10"),
        )
        self.assertEqual(
            str(cfg.profiles["remote-admin"].availability_check.target),
            "10.30.0.1",
        )
        self.assertTrue(
            cfg.profiles["corporate"].availability_uses_device_default
        )
        self.assertIsNone(cfg.profiles["corporate"].availability_check)
        self.assertEqual(
            str(cfg.devices["wg-main"].availability_check.target),
            "198.51.100.11",
        )

        wg = cfg.devices["wg-main"]
        self.assertTrue(wg.use_outbound_nat)
        self.assertEqual(len(wg.allow_vpn_client), 1)
        self.assertEqual(wg.allow_vpn_client[0].local_port, 51820)
        self.assertEqual(wg.allow_vpn_client[0].remote_port, 51820)
        self.assertEqual(wg.firewall[0].destination_ports, PortBundle.single(443))
        self.assertEqual(wg.firewall[0].comment, "HTTPS to corp")

        backup = cfg.devices["oc-backup"]
        self.assertFalse(backup.use_outbound_nat)
        self.assertIsNone(backup.allow_vpn_client[0].local_port)

        server = cfg.devices["oc-server"]
        self.assertIsNone(server.use_outbound_nat)
        self.assertEqual(server.publish_vpn_server[0].host_selector.kind, "interface")
        self.assertEqual(server.publish_vpn_server[0].host_selector.value, "eth0")
        self.assertEqual(server.publish_vpn_server[0].internal_ports, PortBundle.single(443))
        self.assertEqual(server.publish_vpn_server[1].host_selector.kind, "ipv4")
        self.assertEqual(
            server.publish_vpn_server[1].host_selector.value,
            ipaddress.IPv4Address("192.0.2.10"),
        )

    def test_outbound_nat_is_required_only_for_ordinary_to_vpn_role(self):
        with self.assertRaisesRegex(
            Release1ConfigError, "use_outbound_nat is required"
        ):
            parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")

        cfg = parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]

[profile.support]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")
        self.assertIsNone(cfg.devices["oc"].use_outbound_nat)

    def test_direction_snat_suffix_is_bounded(self):
        cfg = parse_release1_config("""
default_snat_address = "198.19.255.10"

[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.support]
enabled = true
direction = "bidirectional+snat"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")
        self.assertEqual(
            cfg.structural.profiles["support"].direction,
            Direction.BIDIRECTIONAL,
        )
        self.assertEqual(
            cfg.profiles["support"].effective_snat_address,
            ipaddress.IPv4Address("198.19.255.10"),
        )

        with self.assertRaisesRegex(Release1ConfigError, "VPN-to-ordinary"):
            parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.bad]
enabled = true
direction = "outbound+snat"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")

    def test_direction_snat_default_override_and_shared_identity(self):
        cfg = parse_release1_config("""
default_snat_address = "198.19.255.10"

[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.a]
enabled = true
direction = "bidirectional+snat"
destinations = ["10.0.0.0/16"]
device_order = ["oc"]

[profile.b]
enabled = true
direction = "inbound+snat>198.19.255.10"
destinations = ["10.1.0.0/16"]
device_order = ["oc"]

[profile.c]
enabled = true
direction = "inbound+snat>198.19.255.11"
destinations = ["10.2.0.0/16"]
device_order = ["oc"]
""")
        self.assertEqual(
            cfg.profiles["a"].effective_snat_address,
            ipaddress.IPv4Address("198.19.255.10"),
        )
        self.assertEqual(
            cfg.profiles["b"].effective_snat_address,
            ipaddress.IPv4Address("198.19.255.10"),
        )
        self.assertEqual(
            cfg.profiles["c"].effective_snat_address,
            ipaddress.IPv4Address("198.19.255.11"),
        )

        explicit = parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]

[profile.support]
enabled = true
direction = "inbound+snat>198.19.255.12"
destinations = ["10.3.0.0/16"]
device_order = ["oc"]
""")
        self.assertIsNone(explicit.default_snat_address)
        self.assertEqual(
            explicit.profiles["support"].effective_snat_address,
            ipaddress.IPv4Address("198.19.255.12"),
        )

    def test_bare_snat_requires_default(self):
        with self.assertRaisesRegex(
            Release1ConfigError, "requires top-level default_snat_address"
        ):
            parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]

[profile.support]
enabled = true
direction = "inbound+snat"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")


    def test_snat_identity_must_not_overlap_untranslated_remote_source_space(self):
        with self.assertRaisesRegex(
            Release1ConfigError, "overlaps untranslated remote source range"
        ):
            parse_release1_config("""
default_snat_address = "10.20.0.10"

[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.translated]
enabled = true
direction = "bidirectional+snat"
destinations = ["10.30.0.0/16"]
device_order = ["oc"]

[profile.direct]
enabled = true
direction = "outbound"
destinations = ["10.20.0.0/16"]
device_order = ["oc"]
""")

    def test_snat_identity_rejects_non_boundary_unicast_addresses(self):
        for address in ("0.0.0.0", "127.0.0.1", "169.254.1.1", "224.0.0.1", "255.255.255.255"):
            with self.subTest(address=address):
                with self.assertRaisesRegex(Release1ConfigError, "IPv4 unicast"):
                    parse_release1_config(f"""
default_snat_address = "{address}"

[device.oc]
enabled = true
expected_interfaces = ["vpn0"]

[profile.support]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")

    def test_direction_non_string_still_reports_config_error(self):
        with self.assertRaises(Release1ConfigError):
            parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]

[profile.bad]
enabled = true
direction = ["inbound"]
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")

    def test_firewall_port_bundles_are_ordered_strict_and_non_overlapping(self):
        cfg = parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
firewall = [
    "out deny udp from 10.0.0.0/8:53,1000-1003,8080 to 192.0.2.0/24:5353 # first",
    "out allow tcp to 192.0.2.10/32:80,443,8000-8007",
]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["192.0.2.0/24"]
device_order = ["oc"]
""")
        rules = cfg.devices["oc"].firewall
        self.assertEqual([rule.action for rule in rules], ["deny", "allow"])
        self.assertEqual(
            rules[0].source_ports,
            PortBundle(
                (
                    PortSpan(53, 53),
                    PortSpan(1000, 1003),
                    PortSpan(8080, 8080),
                )
            ),
        )
        self.assertEqual(rules[0].destination_ports, PortBundle.single(5353))
        self.assertEqual(rules[0].comment, "first")
        self.assertEqual(
            rules[1].destination_ports.cardinality,
            10,
        )

        for invalid in (
            "80,,443",
            "80, 443",
            "8007-8000",
            "80,80",
            "8000-8010,8005",
            "9000-9010,9005-9020",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(Release1ConfigError):
                    parse_release1_config(f"""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
firewall = ["out allow tcp to 192.0.2.0/24:{invalid}"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["192.0.2.0/24"]
device_order = ["oc"]
""")

        with self.assertRaisesRegex(Release1ConfigError, "explicit tcp or udp"):
            parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
firewall = ["out allow icmp to 192.0.2.0/24:8,9"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["192.0.2.0/24"]
device_order = ["oc"]
""")

    def test_client_allow_and_publication_forms_are_strict(self):
        cfg = parse_release1_config("""
[device.client]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
allow_vpn_client = [
    "tcp>198.51.100.20:443",
    "udp:11941>198.51.100.20:11940",
]

[device.server]
enabled = true
expected_interfaces = ["ocsvr0"]
publish_vpn_server = [
    "udp:44443",
    "tcp/eth0:443>8443",
]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["client"]
""")
        self.assertEqual(
            cfg.devices["server"].publish_vpn_server[0].host_selector.kind,
            "any",
        )
        self.assertEqual(
            cfg.devices["server"].publish_vpn_server[0].internal_ports,
            PortBundle.single(44443),
        )

        bundles = parse_release1_config("""
[device.server]
enabled = true
expected_interfaces = ["ocsvr0"]
publish_vpn_server = [
    "udp/eth0:53,123,5000-5003",
    "tcp/eth0:443,8000-8002,9000>8443,18000-18002,19000",
]
""").devices["server"].publish_vpn_server
        self.assertEqual(bundles[0].host_ports, bundles[0].internal_ports)
        self.assertEqual(bundles[0].host_ports.cardinality, 6)
        self.assertEqual(bundles[1].host_ports.cardinality, 5)
        self.assertEqual(bundles[1].internal_ports.cardinality, 5)
        self.assertEqual(
            list(zip(bundles[1].host_ports.expanded(), bundles[1].internal_ports.expanded())),
            [
                (443, 8443),
                (8000, 18000),
                (8001, 18001),
                (8002, 18002),
                (9000, 19000),
            ],
        )

        with self.assertRaisesRegex(Release1ConfigError, "equal cardinality"):
            parse_release1_config("""
[device.server]
enabled = true
expected_interfaces = ["ocsvr0"]
publish_vpn_server = "tcp/eth0:8000-8002>9000-9001"
""")

        with self.assertRaises(Release1ConfigError):
            parse_release1_config("""
[device.server]
enabled = true
expected_interfaces = ["ocsvr0"]
publish_vpn_server = "udp/eth0:53,53"
""")

        with self.assertRaisesRegex(Release1ConfigError, "tcp\|udp"):
            parse_release1_config("""
[device.client]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
allow_vpn_client = "udp:11940-11941>198.51.100.20:11940"
""")

        with self.assertRaisesRegex(Release1ConfigError, "exact IPv4"):
            parse_release1_config("""
[device.client]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
allow_vpn_client = "tcp>vpn.example.test:443"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["client"]
""")

    def test_unknown_enabled_fields_and_top_level_tables_are_rejected(self):
        for extra in (
            'unsupported_string = "value"',
            'unsupported_list = ["value"]',
            'unsupported_table = { key = "value" }',
        ):
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(
                    Release1ConfigError, "unsupported field"
                ):
                    parse_release1_config(f"""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
{extra}

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")

        with self.assertRaisesRegex(
            Release1ConfigError, "top level has unsupported"
        ):
            parse_release1_config("""
[unsupported.example]
value = true
""")

    def test_availability_field_and_prefix_quota_are_strict(self):
        cfg = parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn*/2"]
use_outbound_nat = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
[profile.corp.availability_check]
mechanism = "icmp"
target = "192.0.2.1"
""")
        self.assertEqual(
            cfg.profiles["corp"].availability_check.target,
            ipaddress.IPv4Address("192.0.2.1"),
        )

        with self.assertRaises(Release1ConfigError):
            parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn*"]
use_outbound_nat = false
""")

        with self.assertRaisesRegex(
            Release1ConfigError, 'must be "icmp"'
        ):
            parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
[profile.corp.availability_check]
mechanism = "tcp"
target = "192.0.2.1"
""")

    def test_profile_default_requires_device_default_description(self):
        with self.assertRaisesRegex(
            Release1ConfigError,
            "device.oc.availability_check is required",
        ):
            parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
availability_check = "default"
""")

        cfg = parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[device.oc.availability_check]
mechanism = "icmp"
target = "192.0.2.9"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
availability_check = "default"
""")
        self.assertTrue(cfg.profiles["corp"].availability_uses_device_default)
        self.assertIsNone(cfg.profiles["corp"].availability_check)
        self.assertEqual(
            cfg.devices["oc"].availability_check.target,
            ipaddress.IPv4Address("192.0.2.9"),
        )

        explicit = parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]

[profile.corp.availability_check]
mechanism = "icmp"
target = "192.0.2.10"
""")
        self.assertFalse(explicit.profiles["corp"].availability_uses_device_default)
        self.assertEqual(
            explicit.profiles["corp"].availability_check.target,
            ipaddress.IPv4Address("192.0.2.10"),
        )
        self.assertIsNone(explicit.devices["oc"].availability_check)

    def test_device_order_reserve_suffix_is_profile_local_and_normalized(self):
        cfg = parse_release1_config("""
[device.primary]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[device.backup]
enabled = true
expected_interfaces = ["vpn1"]
use_outbound_nat = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["primary", "backup:reserve"]

[profile.bulk]
enabled = true
direction = "outbound"
destinations = ["192.0.2.0/24"]
device_order = ["backup", "primary"]
""")
        self.assertEqual(
            cfg.structural.profiles["corp"].device_order,
            ("primary", "backup"),
        )
        self.assertEqual(
            cfg.profiles["corp"].reserve_device_ids,
            frozenset({"backup"}),
        )
        self.assertEqual(
            cfg.structural.profiles["bulk"].device_order,
            ("backup", "primary"),
        )
        self.assertEqual(
            cfg.profiles["bulk"].reserve_device_ids,
            frozenset(),
        )

    def test_device_order_unknown_membership_suffix_is_rejected(self):
        with self.assertRaisesRegex(
            Release1ConfigError,
            "unsupported membership suffix",
        ):
            parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc:cheap"]
""")

    def test_device_order_duplicate_after_suffix_normalization_is_rejected(self):
        with self.assertRaisesRegex(
            Release1ConfigError,
            "duplicate Device membership",
        ):
            parse_release1_config("""
[device.oc]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc", "oc:reserve"]
""")

    def test_disabled_placeholders_remain_shallow(self):
        cfg = parse_release1_config("""
[device.future]
enabled = false
nat = "ignored-because-disabled"
anything = { future = true }

[profile.future]
enabled = false
direction = "future-mode"
availability_check = 123
""")
        self.assertFalse(cfg.structural.devices["future"].enabled)
        self.assertFalse(cfg.structural.profiles["future"].enabled)


if __name__ == "__main__":
    unittest.main()
