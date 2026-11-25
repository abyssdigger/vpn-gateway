import ipaddress
import unittest

from rou.release1_config import CurrentConfigError, parse_current_config


PEER_A_KEY = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
PEER_B_KEY = "ISIjJCUmJygpKissLS4vMDEyMzQ1Njc4OTo7PD0+P0A="


def _config(profile_tail: str = "") -> str:
    return f"""
[device.wg]
enabled = true
use_outbound_nat = true

[device.wg.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "/etc/wg.key"

[[device.wg.managed_vpn.peers]]
id = "edge-a"
public_key = "{PEER_A_KEY}"
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"

[[device.wg.managed_vpn.peers]]
id = "edge-b"
public_key = "{PEER_B_KEY}"
endpoint = "198.51.100.11:51820"
probe_target = "10.201.0.2"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.20.0.0/16", "10.30.0.0/16"]
device_order = ["wg"]
{profile_tail}
"""


class WireGuardGroupConfigTests(unittest.TestCase):
    def test_profile_membership_normalizes_default_group(self):
        cfg = parse_current_config(_config())
        group = cfg.wireguard_groups[("corp", "wg")]

        self.assertEqual(group.profile_id, "corp")
        self.assertEqual(group.device_id, "wg")
        self.assertEqual(
            group.prefixes,
            (
                ipaddress.IPv4Network("10.20.0.0/16"),
                ipaddress.IPv4Network("10.30.0.0/16"),
            ),
        )
        self.assertEqual(
            tuple((item.peer_id, item.reserve) for item in group.peer_memberships),
            (("edge-a", False), ("edge-b", False)),
        )
        self.assertIsNone(group.availability_check)

    def test_profile_membership_can_select_ordered_reserve_peer_subset(self):
        cfg = parse_current_config(
            _config(
                """
[profile.corp.device_membership.wg]
peer_order = ["edge-b", "edge-a:reserve"]
"""
            )
        )
        group = cfg.wireguard_groups[("corp", "wg")]
        self.assertEqual(
            tuple((item.peer_id, item.reserve) for item in group.peer_memberships),
            (("edge-b", False), ("edge-a", True)),
        )

    def test_qualified_profile_check_is_reused_as_group_description(self):
        cfg = parse_current_config(
            _config(
                """
[profile.corp.availability_check]
mechanism = "icmp"
target = "10.20.0.10"
"""
            )
        )
        group = cfg.wireguard_groups[("corp", "wg")]
        self.assertIsNotNone(group.availability_check)
        self.assertEqual(
            group.availability_check.target,
            ipaddress.IPv4Address("10.20.0.10"),
        )

        outside = parse_current_config(
            _config(
                """
[profile.corp.availability_check]
mechanism = "icmp"
target = "192.0.2.10"
"""
            )
        )
        self.assertIsNone(outside.wireguard_groups[("corp", "wg")].availability_check)

    def test_membership_detail_rejects_nonmember_and_invalid_peer_order(self):
        cases = (
            (
                """
[profile.corp.device_membership.other]
peer_order = ["edge-a"]
""",
                "absent from device_order",
            ),
            (
                """
[profile.corp.device_membership.wg]
peer_order = ["missing"]
""",
                "unknown WireGuard peer",
            ),
            (
                """
[profile.corp.device_membership.wg]
peer_order = ["edge-a", "edge-a:reserve"]
""",
                "duplicate peer",
            ),
            (
                """
[profile.corp.device_membership.wg]
peer_order = ["edge-a:future"]
""",
                "unsupported membership suffix",
            ),
        )
        for tail, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(CurrentConfigError, expected):
                    parse_current_config(_config(tail))


if __name__ == "__main__":
    unittest.main()
