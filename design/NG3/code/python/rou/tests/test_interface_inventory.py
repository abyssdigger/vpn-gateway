from __future__ import annotations

import unittest

from rou.interface_identity import InterfaceIdentity
from rou.interface_inventory import InterfaceInventoryError, parse_ip_link_inventory


class InterfaceInventoryTests(unittest.TestCase):
    def test_preserves_authoritative_snapshot_order(self):
        out = parse_ip_link_inventory(
            '[{"ifindex":7,"ifname":"vpns01"},{"ifindex":3,"ifname":"lo"}]'
        )
        self.assertEqual(
            out,
            (InterfaceIdentity("vpns01", 7), InterfaceIdentity("lo", 3)),
        )

    def test_empty_array_is_valid_empty_inventory(self):
        self.assertEqual(parse_ip_link_inventory("[]"), ())

    def test_duplicate_ifname_and_ifindex_are_rejected(self):
        with self.assertRaisesRegex(InterfaceInventoryError, "duplicate interface name"):
            parse_ip_link_inventory(
                '[{"ifindex":7,"ifname":"a"},{"ifindex":8,"ifname":"a"}]'
            )
        with self.assertRaisesRegex(InterfaceInventoryError, "duplicate ifindex"):
            parse_ip_link_inventory(
                '[{"ifindex":7,"ifname":"a"},{"ifindex":7,"ifname":"b"}]'
            )

    def test_invalid_ifindex_is_rejected(self):
        for value in ("true", "0", "-1", '"7"'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(InterfaceInventoryError, "positive integer"):
                    parse_ip_link_inventory(
                        f'[{{"ifindex":{value},"ifname":"a"}}]'
                    )

    def test_invalid_ifname_is_rejected(self):
        with self.assertRaisesRegex(InterfaceInventoryError, "non-empty string"):
            parse_ip_link_inventory('[{"ifindex":7,"ifname":""}]')
        with self.assertRaisesRegex(InterfaceInventoryError, "IFNAMSIZ"):
            parse_ip_link_inventory(
                '[{"ifindex":7,"ifname":"abcdefghijklmnop"}]'
            )

    def test_invalid_json_shape_is_rejected_not_treated_as_empty(self):
        for text in ("{", "{}", '["not-object"]'):
            with self.subTest(text=text):
                with self.assertRaises(InterfaceInventoryError):
                    parse_ip_link_inventory(text)

    def test_same_name_new_ifindex_is_valid_across_separate_snapshots(self):
        first = parse_ip_link_inventory('[{"ifindex":7,"ifname":"vpn0"}]')
        second = parse_ip_link_inventory('[{"ifindex":8,"ifname":"vpn0"}]')
        self.assertNotEqual(first, second)
        self.assertEqual(first[0].ifname, second[0].ifname)


if __name__ == "__main__":
    unittest.main()
