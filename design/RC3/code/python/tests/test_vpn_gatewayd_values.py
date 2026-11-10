#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import sys
import unittest
from ipaddress import IPv4Network
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


def profile_config():
    return vpng.VpnProfileConfig(
        profile_id="primary",
        interface=vpng.InterfaceSelector.parse("vpns+"),
        network=IPv4Network("172.20.130.0/29"),
        routes=(
            IPv4Network("10.0.0.0/8"),
            IPv4Network("192.168.0.0/16"),
        ),
        allowed_sources=(),
    )


class ValueObjectTests(unittest.TestCase):
    def test_route_spec_value_hash_and_frozen_semantics(self):
        left = vpng.RouteSpec(
            IPv4Network("10.0.0.0/8"),
            vpng.RouteType.UNICAST,
            None,
            "vpns0",
            10,
            vpng.VPN_ROUTE_PROTO,
            False,
        )
        right = vpng.RouteSpec(
            IPv4Network("10.0.0.0/8"),
            vpng.RouteType.UNICAST,
            None,
            "vpns0",
            10,
            vpng.VPN_ROUTE_PROTO,
            False,
        )
        self.assertEqual(left, right)
        self.assertEqual(hash(left), hash(right))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            left.metric = 20

    def test_reconciliation_plan_uses_frozensets(self):
        route = vpng.RouteSpec(
            IPv4Network("10.0.0.0/8"),
            vpng.RouteType.BLACKHOLE,
            None,
            None,
            vpng.BLACKHOLE_METRIC,
            vpng.BLACKHOLE_ROUTE_PROTO,
            False,
        )
        plan = vpng.ReconciliationPlan(
            frozenset({route}),
            frozenset(),
            frozenset(),
        )
        self.assertIsInstance(plan.route_adds, frozenset)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.route_adds = frozenset()

    def test_profile_verified_state_starts_empty(self):
        profile = vpng.VpnProfile(profile_config())
        self.assertEqual(profile.owned_routes, frozenset())
        self.assertIsNone(profile.committed_active_bindings)
        self.assertEqual(dict(profile.committed_prefix_metrics), {})
        self.assertEqual(
            profile.committed_prefix_metric_cursor,
            vpng.FIRST_UNICAST_METRIC,
        )

    def test_commit_verified_state_is_defensive_and_allows_zero_path(self):
        profile = vpng.VpnProfile(profile_config())
        route = vpng.RouteSpec(
            IPv4Network("10.0.0.0/8"),
            vpng.RouteType.BLACKHOLE,
            None,
            None,
            vpng.BLACKHOLE_METRIC,
            vpng.BLACKHOLE_ROUTE_PROTO,
            False,
        )
        source = {route}
        candidates = (vpng.InterfaceBinding("vpns0", 7),)
        profile.commit_verified_state(
            routes=source,
            active_bindings=(),
            prefix_metrics={},
            prefix_metric_cursor=vpng.FIRST_UNICAST_METRIC,
        )
        source.clear()

        self.assertEqual(profile.owned_routes, frozenset({route}))
        self.assertEqual(profile.committed_active_bindings, ())

    def test_commit_replaces_active_binding_set(self):
        profile = vpng.VpnProfile(profile_config())
        first = (vpng.InterfaceBinding("vpns0", 7),)
        second = (
            vpng.InterfaceBinding("vpns0", 7),
            vpng.InterfaceBinding("vpns1", 8),
        )
        profile.commit_verified_state(
            routes=frozenset(),
            active_bindings=first,
            prefix_metrics={first[0]: 10},
            prefix_metric_cursor=20,
        )
        self.assertEqual(profile.committed_active_bindings, first)
        self.assertEqual(dict(profile.committed_prefix_metrics), {first[0]: 10})

        profile.commit_verified_state(
            routes=frozenset(),
            active_bindings=second,
            prefix_metrics={second[0]: 10, second[1]: 20},
            prefix_metric_cursor=30,
        )
        self.assertEqual(profile.committed_active_bindings, second)
        self.assertEqual(
            dict(profile.committed_prefix_metrics),
            {second[0]: 10, second[1]: 20},
        )
        self.assertEqual(profile.committed_prefix_metric_cursor, 30)

    def test_prefix_commit_rejects_incomplete_or_duplicate_allocator_state(self):
        profile = vpng.VpnProfile(profile_config())
        first = vpng.InterfaceBinding("vpns0", 7)
        second = vpng.InterfaceBinding("vpns1", 8)

        with self.assertRaises(ValueError):
            profile.commit_verified_state(
                routes=frozenset(),
                active_bindings=(first,),
                prefix_metrics={},
                prefix_metric_cursor=10,
            )

        with self.assertRaises(ValueError):
            profile.commit_verified_state(
                routes=frozenset(),
                active_bindings=(first, second),
                prefix_metrics={first: 10, second: 10},
                prefix_metric_cursor=20,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
