#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import sys
import unittest
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


class InterfaceSelectorTests(unittest.TestCase):
    def test_exact_prefix_and_explicit_list_parse(self):
        exact = vpng.InterfaceSelector.parse("wg0")
        prefix = vpng.InterfaceSelector.parse("vpns+")
        explicit = vpng.InterfaceSelector.parse(["vpnA", "vpnB", "vpnC"])

        self.assertIs(exact.kind, vpng.InterfaceSelectorKind.EXACT)
        self.assertEqual(exact.values, ("wg0",))
        self.assertIs(prefix.kind, vpng.InterfaceSelectorKind.PREFIX)
        self.assertEqual(prefix.values, ("vpns",))
        self.assertIs(explicit.kind, vpng.InterfaceSelectorKind.EXACT_LIST)
        self.assertEqual(explicit.values, ("vpnA", "vpnB", "vpnC"))
        self.assertEqual(prefix.guard_interfaces(), ("vpns+",))
        self.assertEqual(explicit.guard_interfaces(), explicit.values)

    def test_selector_validation_rejects_legacy_percent_and_bad_lists(self):
        for value in ("", "+", "1tun", "vpns++", "vpns%", "abcdefghijklmnop"):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    vpng.InterfaceSelector.parse(value)

        for value in ([], ["vpnA", "vpnA"], ["vpnA", 3], ["lo"]):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    vpng.InterfaceSelector.parse(value)

    def test_selector_overlap_covers_prefix_and_explicit_list(self):
        cases = (
            ("vpns+", "vpns0", True),
            ("vpns+", "vpns1+", True),
            ("vpns1+", "vpns2+", False),
            (["tunA", "tunB"], "tunA", True),
            (["tunA", "tunB"], ["tunB", "tunC"], True),
            (["tunA", "tunB"], "wg0", False),
            (["vpns9", "tun0"], "vpns+", True),
        )
        for left, right, expected in cases:
            with self.subTest(left=left, right=right):
                first = vpng.InterfaceSelector.parse(left)
                second = vpng.InterfaceSelector.parse(right)
                self.assertEqual(first.overlaps(second), expected)
                self.assertEqual(second.overlaps(first), expected)


class InterfaceStateTests(unittest.TestCase):
    def record(self, name, ifindex, *addresses):
        return vpng.InterfaceRecord(
            name,
            ifindex,
            frozenset(IPv4Address(item) for item in addresses),
        )

    def test_record_is_frozen_and_defensively_freezes_ipv4(self):
        addresses = {IPv4Address("172.20.130.1")}
        record = vpng.InterfaceRecord("vpns0", 7, addresses)
        addresses.clear()
        self.assertEqual(
            record.ipv4,
            frozenset({IPv4Address("172.20.130.1")}),
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.ifindex = 8

    def test_prefix_initial_snapshot_uses_bytewise_tiebreak_order(self):
        state = vpng.resolve_profile_interface_state(
            vpng.InterfaceSelector.parse("vpns+"),
            (
                self.record("vpns9", 9, "172.20.130.1"),
                self.record("vpns10", 10, "172.20.130.1"),
                self.record("other0", 11, "172.20.130.1"),
            ),
            IPv4Network("172.20.130.0/29"),
        )
        self.assertEqual(
            tuple(record.name for record in state.candidates),
            ("vpns10", "vpns9"),
        )
        self.assertEqual(
            state.active_bindings,
            (
                vpng.InterfaceBinding("vpns10", 10),
                vpng.InterfaceBinding("vpns9", 9),
            ),
        )

    def test_prefix_preserves_survivor_order_and_appends_new_bindings(self):
        previous = (
            vpng.InterfaceBinding("vpns2", 2),
            vpng.InterfaceBinding("vpns9", 9),
        )
        state = vpng.resolve_profile_interface_state(
            vpng.InterfaceSelector.parse("vpns+"),
            (
                self.record("vpns10", 10, "172.20.130.1"),
                self.record("vpns9", 9, "172.20.130.1"),
                self.record("vpns2", 2, "172.20.130.1"),
                self.record("vpns1", 1, "172.20.130.1"),
            ),
            IPv4Network("172.20.130.0/29"),
            previous_active_bindings=previous,
        )
        self.assertEqual(
            state.active_bindings,
            (
                vpng.InterfaceBinding("vpns2", 2),
                vpng.InterfaceBinding("vpns9", 9),
                vpng.InterfaceBinding("vpns1", 1),
                vpng.InterfaceBinding("vpns10", 10),
            ),
        )

    def test_prefix_same_name_new_ifindex_is_fresh_binding(self):
        previous = (
            vpng.InterfaceBinding("vpns2", 2),
            vpng.InterfaceBinding("vpns9", 9),
        )
        state = vpng.resolve_profile_interface_state(
            vpng.InterfaceSelector.parse("vpns+"),
            (
                self.record("vpns2", 22, "172.20.130.1"),
                self.record("vpns9", 9, "172.20.130.1"),
            ),
            IPv4Network("172.20.130.0/29"),
            previous_active_bindings=previous,
        )
        self.assertEqual(
            state.active_bindings,
            (
                vpng.InterfaceBinding("vpns9", 9),
                vpng.InterfaceBinding("vpns2", 22),
            ),
        )

    def test_matching_candidates_with_different_addresses_inside_network_are_active(self):
        state = vpng.resolve_profile_interface_state(
            vpng.InterfaceSelector.parse("vpns+"),
            (
                self.record("vpns0", 7, "172.20.130.1"),
                self.record("vpns1", 8, "172.20.130.2"),
            ),
            IPv4Network("172.20.130.0/29"),
        )
        self.assertEqual(
            state.active_bindings,
            (
                vpng.InterfaceBinding("vpns0", 7),
                vpng.InterfaceBinding("vpns1", 8),
            ),
        )

    def test_matching_candidate_without_address_in_network_remains_inactive(self):
        state = vpng.resolve_profile_interface_state(
            vpng.InterfaceSelector.parse("vpns+"),
            (
                self.record("vpns0", 7, "172.20.130.1"),
                self.record("vpns1", 8, "172.20.131.2"),
            ),
            IPv4Network("172.20.130.0/29"),
        )
        self.assertEqual(
            tuple(record.name for record in state.candidates),
            ("vpns0", "vpns1"),
        )
        self.assertEqual(
            state.active_bindings,
            (vpng.InterfaceBinding("vpns0", 7),),
        )

    def test_explicit_list_preserves_config_order_and_missing_holes(self):
        state = vpng.resolve_profile_interface_state(
            vpng.InterfaceSelector.parse(["vpnB", "vpnA", "vpnC"]),
            (
                self.record("vpnA", 1, "172.20.140.1"),
                self.record("vpnC", 3, "172.20.140.1"),
            ),
            IPv4Network("172.20.140.0/29"),
        )
        self.assertEqual(
            tuple(record.name for record in state.candidates),
            ("vpnA", "vpnC"),
        )
        self.assertEqual(
            state.active_bindings,
            (
                vpng.InterfaceBinding("vpnA", 1),
                vpng.InterfaceBinding("vpnC", 3),
            ),
        )

    def test_duplicate_name_with_conflicting_ifindex_is_rejected(self):
        with self.assertRaises(ValueError):
            vpng.resolve_profile_interface_state(
                vpng.InterfaceSelector.parse("vpns+"),
                (self.record("vpns0", 7), self.record("vpns0", 8)),
                IPv4Network("172.20.130.0/29"),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
