#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


def spec(interface: str, network: str, index: int, rank=None):
    return vpng.BindingSpec(
        vpng.InterfaceSelector.parse(interface),
        IPv4Network(network),
        index,
        rank,
    )


def record(name: str, ifindex: int, address: str | None):
    addresses = frozenset() if address is None else frozenset({IPv4Address(address)})
    return vpng.InterfaceRecord(name, ifindex, addresses)


class InterfaceSelectorTests(unittest.TestCase):
    def test_only_exact_and_prefix_forms_exist(self):
        exact = vpng.InterfaceSelector.parse("wg0")
        prefix = vpng.InterfaceSelector.parse("vpns+")
        self.assertIs(exact.kind, vpng.InterfaceSelectorKind.EXACT)
        self.assertIs(prefix.kind, vpng.InterfaceSelectorKind.PREFIX)
        self.assertEqual(str(exact), "wg0")
        self.assertEqual(str(prefix), "vpns+")
        with self.assertRaises(TypeError):
            vpng.InterfaceSelector.parse(["wg0", "wg1"])

    def test_selector_overlap_is_namespace_based(self):
        self.assertTrue(
            vpng.InterfaceSelector.parse("vpns+").overlaps(
                vpng.InterfaceSelector.parse("vpns0")
            )
        )
        self.assertTrue(
            vpng.InterfaceSelector.parse("vpn+").overlaps(
                vpng.InterfaceSelector.parse("vpns+")
            )
        )
        self.assertFalse(
            vpng.InterfaceSelector.parse("wg0").overlaps(
                vpng.InterfaceSelector.parse("wg1")
            )
        )

    def test_invalid_forms_are_rejected(self):
        for value in ("+bad", "lo", "any", "default", "all", "a" * 16):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    vpng.InterfaceSelector.parse(value)


class BindingResolutionTests(unittest.TestCase):
    def test_binding_specific_networks_qualify_independently(self):
        specs = (
            spec("wg0", "172.20.126.0/29", 0, 0),
            spec("wg1", "172.20.127.0/29", 1, 1),
            spec("oc+", "172.20.130.0/29", 2, None),
        )
        state = vpng.resolve_profile_interface_state(
            specs,
            (
                record("wg0", 7, "172.20.126.2"),
                record("wg1", 8, "172.20.127.2"),
                record("oc1", 9, "172.20.130.5"),
                record("oc2", 10, "172.20.127.3"),
            ),
        )
        self.assertEqual(
            tuple((b.name, b.ifindex) for b in state.active_bindings),
            (("wg0", 7), ("wg1", 8), ("oc1", 9)),
        )
        self.assertEqual(
            tuple(b.name for b in state.exact_bindings),
            ("wg0", "wg1"),
        )
        self.assertEqual(tuple(b.name for b in state.prefix_bindings), ("oc1",))
        self.assertEqual(
            state.owner_index_by_binding[vpng.InterfaceBinding("oc1", 9)],
            2,
        )
        self.assertEqual(
            tuple(r.name for r in state.candidates),
            ("wg0", "wg1", "oc1", "oc2"),
        )

    def test_exact_order_ignores_prefix_positions(self):
        specs = (
            spec("oc+", "172.20.130.0/29", 0, None),
            spec("wg1", "172.20.127.0/29", 1, 0),
            spec("tun0", "172.20.140.0/29", 2, 1),
        )
        state = vpng.resolve_profile_interface_state(
            specs,
            (
                record("oc0", 7, "172.20.130.2"),
                record("tun0", 8, "172.20.140.2"),
                record("wg1", 9, "172.20.127.2"),
            ),
        )
        self.assertEqual(
            tuple(b.name for b in state.active_bindings),
            ("wg1", "tun0", "oc0"),
        )

    def test_prefix_survivors_keep_process_local_order_and_new_append(self):
        specs = (spec("vpns+", "172.20.130.0/29", 0, None),)
        first = vpng.resolve_profile_interface_state(
            specs,
            (
                record("vpns9", 7, "172.20.130.2"),
                record("vpns1", 8, "172.20.130.3"),
            ),
        )
        second = vpng.resolve_profile_interface_state(
            specs,
            (
                record("vpns0", 9, "172.20.130.4"),
                record("vpns1", 8, "172.20.130.3"),
                record("vpns9", 7, "172.20.130.2"),
            ),
            previous_prefix_active_bindings=first.prefix_bindings,
        )
        self.assertEqual(
            tuple(b.name for b in second.prefix_bindings),
            ("vpns9", "vpns1", "vpns0"),
        )

    def test_same_name_new_ifindex_is_new_prefix_binding(self):
        specs = (spec("vpns+", "172.20.130.0/29", 0, None),)
        previous = (vpng.InterfaceBinding("vpns0", 7),)
        state = vpng.resolve_profile_interface_state(
            specs,
            (record("vpns0", 8, "172.20.130.2"),),
            previous_prefix_active_bindings=previous,
        )
        self.assertEqual(state.prefix_bindings, (vpng.InterfaceBinding("vpns0", 8),))

    def test_candidate_without_matching_network_is_not_active(self):
        specs = (spec("wg0", "172.20.126.0/29", 0, 0),)
        state = vpng.resolve_profile_interface_state(
            specs,
            (record("wg0", 7, "172.20.127.2"),),
        )
        self.assertEqual(tuple(r.name for r in state.candidates), ("wg0",))
        self.assertEqual(state.active_bindings, ())

    def test_duplicate_name_with_conflicting_ifindex_is_rejected(self):
        specs = (spec("vpns+", "172.20.130.0/29", 0, None),)
        with self.assertRaises(ValueError):
            vpng.resolve_profile_interface_state(
                specs,
                (
                    record("vpns0", 7, "172.20.130.2"),
                    record("vpns0", 8, "172.20.130.2"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
