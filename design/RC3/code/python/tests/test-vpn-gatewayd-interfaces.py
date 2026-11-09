#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import sys
import unittest
from ipaddress import IPv4Address
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


class InterfaceSelectorTests(unittest.TestCase):
    def test_exact_selector_parse_and_match(self):
        selector = vpng.InterfaceSelector.parse("wg0")

        self.assertIs(selector.kind, vpng.InterfaceSelectorKind.EXACT)
        self.assertEqual(str(selector), "wg0")
        self.assertTrue(selector.matches("wg0"))
        self.assertFalse(selector.matches("wg01"))

    def test_prefix_selector_matches_bare_prefix_and_suffixes(self):
        selector = vpng.InterfaceSelector.parse("vpns+")

        self.assertIs(
            selector.kind,
            vpng.InterfaceSelectorKind.PREFIX_FAMILY,
        )
        self.assertEqual(selector.value, "vpns")
        self.assertEqual(str(selector), "vpns+")
        self.assertTrue(selector.matches("vpns"))
        self.assertTrue(selector.matches("vpns0"))
        self.assertTrue(selector.matches("vpnsX"))
        self.assertFalse(selector.matches("other0"))

    def test_selector_validation(self):
        for value in ("", "+", "1tun", "vpns++", "abcdefghijklmnop"):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    vpng.InterfaceSelector.parse(value)

        for value in ("lo", "ANY", "Default", "all"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    vpng.InterfaceSelector.parse(value)

    def test_prefix_max_length_is_fourteen(self):
        value = "a" * 14 + "+"
        self.assertEqual(str(vpng.InterfaceSelector.parse(value)), value)

        with self.assertRaises(ValueError):
            vpng.InterfaceSelector.parse("a" * 15 + "+")

    def test_selector_overlap(self):
        cases = (
            ("vpns+", "vpns0", True),
            ("vpns+", "vpns1+", True),
            ("vpns1+", "vpns12+", True),
            ("vpns1+", "vpns2+", False),
            ("wg0", "wg0", True),
            ("wg0", "wg1", False),
        )

        for left, right, expected in cases:
            with self.subTest(left=left, right=right):
                first = vpng.InterfaceSelector.parse(left)
                second = vpng.InterfaceSelector.parse(right)
                self.assertEqual(first.overlaps(second), expected)
                self.assertEqual(second.overlaps(first), expected)


class InterfaceRecordTests(unittest.TestCase):
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

    def test_resolution_cardinality_and_binding(self):
        one = vpng.InterfaceRecord("vpns0", 7, frozenset())
        two = vpng.InterfaceRecord("vpns1", 8, frozenset())

        absent = vpng.InterfaceResolution.absent()
        self.assertIs(
            absent.state,
            vpng.InterfaceResolutionState.ABSENT,
        )
        self.assertIsNone(absent.binding)

        bound = vpng.InterfaceResolution.bound(one)
        self.assertIs(
            bound.state,
            vpng.InterfaceResolutionState.BOUND,
        )
        self.assertEqual(
            bound.binding,
            vpng.InterfaceBinding("vpns0", 7),
        )
        self.assertEqual(bound.bound_record, one)

        ambiguous = vpng.InterfaceResolution.ambiguous((one, two))
        self.assertIs(
            ambiguous.state,
            vpng.InterfaceResolutionState.AMBIGUOUS,
        )
        self.assertIsNone(ambiguous.binding)

        with self.assertRaises(ValueError):
            vpng.InterfaceResolution(
                vpng.InterfaceResolutionState.BOUND,
                (),
            )

        with self.assertRaises(ValueError):
            vpng.InterfaceResolution.ambiguous((one,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
