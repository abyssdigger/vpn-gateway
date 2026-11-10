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


def profile_config(*, mixed=False):
    bindings = (
        (
            vpng.BindingSpec(
                vpng.InterfaceSelector.parse("wg0"),
                IPv4Network("172.20.126.0/29"),
                0,
                0,
            ),
            vpng.BindingSpec(
                vpng.InterfaceSelector.parse("vpns+"),
                IPv4Network("172.20.130.0/29"),
                1,
                None,
            ),
        )
        if mixed
        else (
            vpng.BindingSpec(
                vpng.InterfaceSelector.parse("vpns+"),
                IPv4Network("172.20.130.0/29"),
                0,
                None,
            ),
        )
    )
    return vpng.VpnProfileConfig(
        profile_id="primary",
        routes=(
            IPv4Network("10.0.0.0/8"),
            IPv4Network("192.168.0.0/16"),
        ),
        bindings=bindings,
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

    def test_profile_dynamic_metric_min_follows_exact_count(self):
        self.assertEqual(profile_config().dynamic_metric_min, 10)
        self.assertEqual(profile_config(mixed=True).dynamic_metric_min, 20)

    def test_profile_verified_state_starts_empty(self):
        profile = vpng.VpnProfile(profile_config())
        self.assertEqual(profile.owned_routes, frozenset())
        self.assertIsNone(profile.committed_active_bindings)
        self.assertEqual(dict(profile.committed_prefix_metrics), {})
        self.assertEqual(profile.committed_prefix_metric_cursor, 10)

    def test_commit_verified_state_allows_verified_zero_path(self):
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
        profile.commit_verified_state(
            routes=source,
            active_bindings=(),
            prefix_bindings=(),
            prefix_metrics={},
            prefix_metric_cursor=10,
        )
        source.clear()
        self.assertEqual(profile.owned_routes, frozenset({route}))
        self.assertEqual(profile.committed_active_bindings, ())

    def test_prepare_then_commit_is_non_partial_boundary(self):
        profile = vpng.VpnProfile(profile_config(mixed=True))
        exact = vpng.InterfaceBinding("wg0", 7)
        prefix = vpng.InterfaceBinding("vpns0", 8)
        prepared = profile.prepare_verified_state(
            routes=frozenset(),
            active_bindings=(exact, prefix),
            prefix_bindings=(prefix,),
            prefix_metrics={prefix: 20},
            prefix_metric_cursor=30,
        )
        self.assertIsNone(profile.committed_active_bindings)
        profile.commit_prepared_state(prepared)
        self.assertEqual(profile.committed_active_bindings, (exact, prefix))
        self.assertEqual(dict(profile.committed_prefix_metrics), {prefix: 20})

    def test_prefix_metric_below_dynamic_floor_is_rejected(self):
        profile = vpng.VpnProfile(profile_config(mixed=True))
        prefix = vpng.InterfaceBinding("vpns0", 8)
        with self.assertRaises(ValueError):
            profile.prepare_verified_state(
                routes=frozenset(),
                active_bindings=(prefix,),
                prefix_bindings=(prefix,),
                prefix_metrics={prefix: 10},
                prefix_metric_cursor=20,
            )

    def test_duplicate_prefix_metrics_are_rejected(self):
        profile = vpng.VpnProfile(profile_config())
        first = vpng.InterfaceBinding("vpns0", 7)
        second = vpng.InterfaceBinding("vpns1", 8)
        with self.assertRaises(ValueError):
            profile.prepare_verified_state(
                routes=frozenset(),
                active_bindings=(first, second),
                prefix_bindings=(first, second),
                prefix_metrics={first: 10, second: 10},
                prefix_metric_cursor=20,
            )


if __name__ == "__main__":
    unittest.main()
