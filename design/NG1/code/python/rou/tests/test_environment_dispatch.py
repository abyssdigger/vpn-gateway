import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.dispatch import compile_profile_dispatch
from rou.domain import ActiveConfig, Direction, Profile
from rou.environment import EnvironmentParseError, parse_ip_link_json


class EnvironmentTests(unittest.TestCase):
    def test_preserves_kernel_json_order(self):
        snapshot = parse_ip_link_json(
            '[{"ifindex":7,"ifname":"vpns01"},{"ifindex":3,"ifname":"lo"}]'
        )
        self.assertEqual(
            [
                (item.identity.ifname, item.identity.ifindex)
                for item in snapshot.interfaces
            ],
            [("vpns01", 7), ("lo", 3)],
        )

    def test_rejects_duplicate_ifindex(self):
        with self.assertRaisesRegex(EnvironmentParseError, "duplicate ifindex"):
            parse_ip_link_json(
                '[{"ifindex":7,"ifname":"a"},{"ifindex":7,"ifname":"b"}]'
            )

    def test_rejects_duplicate_ifname(self):
        with self.assertRaisesRegex(
            EnvironmentParseError,
            "duplicate interface name",
        ):
            parse_ip_link_json(
                '[{"ifindex":7,"ifname":"a"},{"ifindex":8,"ifname":"a"}]'
            )

    def test_bool_is_not_valid_ifindex(self):
        with self.assertRaisesRegex(EnvironmentParseError, "positive integer"):
            parse_ip_link_json('[{"ifindex":true,"ifname":"a"}]')


class DispatchTests(unittest.TestCase):
    def test_longest_prefix_then_network_address(self):
        profiles = {
            "default": Profile(
                "default",
                True,
                Direction.OUTBOUND,
                (ipaddress.IPv4Network("0.0.0.0/0"),),
                (),
            ),
            "b": Profile(
                "b",
                True,
                Direction.OUTBOUND,
                (ipaddress.IPv4Network("10.2.0.0/16"),),
                (),
            ),
            "a": Profile(
                "a",
                True,
                Direction.OUTBOUND,
                (
                    ipaddress.IPv4Network("10.1.0.0/16"),
                    ipaddress.IPv4Network("10.1.2.3/32"),
                ),
                (),
            ),
        }
        out = compile_profile_dispatch(ActiveConfig({}, profiles))
        self.assertEqual(
            [(str(item.destination), item.profile_name) for item in out],
            [
                ("10.1.2.3/32", "a"),
                ("10.1.0.0/16", "a"),
                ("10.2.0.0/16", "b"),
                ("0.0.0.0/0", "default"),
            ],
        )

    def test_disabled_profile_is_not_materialized(self):
        profiles = {
            "off": Profile(
                "off",
                False,
                None,
                (ipaddress.IPv4Network("10.0.0.0/8"),),
                (),
            )
        }
        self.assertEqual(
            compile_profile_dispatch(ActiveConfig({}, profiles)),
            (),
        )


if __name__ == "__main__":
    unittest.main()
