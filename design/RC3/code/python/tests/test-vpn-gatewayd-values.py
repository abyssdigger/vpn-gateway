#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import importlib.util
import sys
import unittest
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


def profile_config(*, peers: tuple[str, ...]) -> object:
    return vpng.VpnProfileConfig(
        profile_id="primary",
        interface=vpng.InterfaceSelector.parse("vpns0"),
        network=IPv4Network("172.20.130.0/29"),
        local_address=IPv4Address("172.20.130.1"),
        peers=tuple(IPv4Address(item) for item in peers),
        routes=(
            IPv4Network("10.0.0.0/8"),
            IPv4Network("192.168.0.0/16"),
        ),
        allowed_sources=(),
    )


class ValueObjectTests(unittest.TestCase):
    def test_route_spec_has_value_equality_and_hash_semantics(self):
        left = vpng.RouteSpec(
            destination=IPv4Network("10.0.0.0/8"),
            route_type=vpng.RouteType.UNICAST,
            via=IPv4Address("172.20.130.6"),
            interface="vpns0",
            metric=10,
            proto=vpng.VPN_ROUTE_PROTO,
            onlink=True,
        )
        right = vpng.RouteSpec(
            destination=IPv4Network("10.0.0.0/8"),
            route_type=vpng.RouteType.UNICAST,
            via=IPv4Address("172.20.130.6"),
            interface="vpns0",
            metric=10,
            proto=vpng.VPN_ROUTE_PROTO,
            onlink=True,
        )

        self.assertEqual(left, right)
        self.assertEqual(hash(left), hash(right))
        self.assertEqual(frozenset({left, right}), frozenset({left}))

    def test_route_spec_is_frozen(self):
        route = vpng.RouteSpec(
            destination=IPv4Network("10.0.0.0/8"),
            route_type=vpng.RouteType.BLACKHOLE,
            via=None,
            interface=None,
            metric=vpng.BLACKHOLE_METRIC,
            proto=vpng.BLACKHOLE_ROUTE_PROTO,
            onlink=False,
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            route.metric = 1

    def test_reconciliation_plan_is_frozen_and_uses_frozensets(self):
        route = vpng.RouteSpec(
            destination=IPv4Network("10.0.0.0/8"),
            route_type=vpng.RouteType.BLACKHOLE,
            via=None,
            interface=None,
            metric=vpng.BLACKHOLE_METRIC,
            proto=vpng.BLACKHOLE_ROUTE_PROTO,
            onlink=False,
        )
        plan = vpng.ReconciliationPlan(
            route_adds=frozenset({route}),
            route_deletes=frozenset(),
            route_replaces=frozenset(),
        )

        self.assertIsInstance(plan.route_adds, frozenset)
        self.assertIsInstance(plan.route_deletes, frozenset)
        self.assertIsInstance(plan.route_replaces, frozenset)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.route_adds = frozenset()

    def test_profile_process_state_starts_empty(self):
        profile = vpng.VpnProfile(profile_config(peers=()))

        self.assertEqual(profile.owned_routes, frozenset())
        self.assertIsNone(profile.committed_binding)
        self.assertFalse(profile.committed_ready)
        self.assertIsNone(profile.committed_resolution_state)
        self.assertIsNone(profile.committed_match_count)

    def test_commit_verified_state_is_defensive(self):
        profile = vpng.VpnProfile(profile_config(peers=()))
        route = vpng.RouteSpec(
            destination=IPv4Network("10.0.0.0/8"),
            route_type=vpng.RouteType.BLACKHOLE,
            via=None,
            interface=None,
            metric=vpng.BLACKHOLE_METRIC,
            proto=vpng.BLACKHOLE_ROUTE_PROTO,
            onlink=False,
        )
        source = {route}

        profile.commit_verified_state(
            routes=source,
            binding=None,
            ready=False,
        )
        source.clear()

        self.assertEqual(profile.owned_routes, frozenset({route}))
        self.assertIsNone(profile.committed_binding)
        self.assertFalse(profile.committed_ready)

    def test_commit_verified_state_replaces_binding_and_readiness(self):
        profile = vpng.VpnProfile(profile_config(peers=()))
        binding = vpng.InterfaceBinding("vpns0", 7)

        profile.commit_verified_state(
            routes=frozenset(),
            binding=binding,
            ready=True,
        )
        self.assertEqual(profile.committed_binding, binding)
        self.assertTrue(profile.committed_ready)
        self.assertIs(
            profile.committed_resolution_state,
            vpng.InterfaceResolutionState.BOUND,
        )
        self.assertEqual(profile.committed_match_count, 1)

        profile.commit_verified_state(
            routes=frozenset(),
            binding=None,
            ready=False,
        )
        self.assertIsNone(profile.committed_binding)
        self.assertFalse(profile.committed_ready)
        self.assertIs(
            profile.committed_resolution_state,
            vpng.InterfaceResolutionState.ABSENT,
        )
        self.assertEqual(profile.committed_match_count, 0)

    def test_ready_committed_state_requires_binding(self):
        profile = vpng.VpnProfile(profile_config(peers=()))

        with self.assertRaises(ValueError):
            profile.commit_verified_state(
                routes=frozenset(),
                binding=None,
                ready=True,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
