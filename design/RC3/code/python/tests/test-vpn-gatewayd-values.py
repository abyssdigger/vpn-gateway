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
        interface="vpns0",
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

    def test_configured_routes_with_empty_peers_are_blackholes_only(self):
        profile = vpng.VpnProfile(profile_config(peers=()))

        routes = profile._list_routes(vpng.ProfileResourceSet.CONFIGURED)

        self.assertEqual(len(routes), 2)
        self.assertEqual(
            {route.destination for route in routes},
            {
                IPv4Network("10.0.0.0/8"),
                IPv4Network("192.168.0.0/16"),
            },
        )
        for route in routes:
            self.assertIs(route.route_type, vpng.RouteType.BLACKHOLE)
            self.assertIsNone(route.via)
            self.assertIsNone(route.interface)
            self.assertEqual(route.metric, vpng.BLACKHOLE_METRIC)
            self.assertEqual(route.proto, vpng.BLACKHOLE_ROUTE_PROTO)
            self.assertFalse(route.onlink)

    def test_configured_routes_with_peers_have_ordered_metrics_per_destination(self):
        profile = vpng.VpnProfile(
            profile_config(
                peers=("172.20.130.6", "172.20.130.5"),
            )
        )

        routes = profile._list_routes(vpng.ProfileResourceSet.CONFIGURED)

        # 2 protected destinations × (1 blackhole + 2 peer routes)
        self.assertEqual(len(routes), 6)

        for destination in (
            IPv4Network("10.0.0.0/8"),
            IPv4Network("192.168.0.0/16"),
        ):
            per_destination = {
                route
                for route in routes
                if route.destination == destination
            }
            blackholes = {
                route
                for route in per_destination
                if route.route_type is vpng.RouteType.BLACKHOLE
            }
            unicast = sorted(
                (
                    route
                    for route in per_destination
                    if route.route_type is vpng.RouteType.UNICAST
                ),
                key=lambda route: route.metric,
            )

            self.assertEqual(len(blackholes), 1)
            self.assertEqual(
                [(str(route.via), route.metric) for route in unicast],
                [
                    ("172.20.130.6", 10),
                    ("172.20.130.5", 20),
                ],
            )
            for route in unicast:
                self.assertEqual(route.interface, "vpns0")
                self.assertEqual(route.proto, vpng.VPN_ROUTE_PROTO)
                self.assertTrue(route.onlink)

    def test_owned_state_replacement_is_defensive(self):
        profile = vpng.VpnProfile(profile_config(peers=()))
        route = next(
            iter(profile._list_routes(vpng.ProfileResourceSet.CONFIGURED))
        )
        source = {route}

        profile.update_owned_state(routes=source)
        source.clear()

        self.assertEqual(
            profile._list_routes(vpng.ProfileResourceSet.OWNED),
            frozenset({route}),
        )

    def test_owned_state_replacement_replaces_atomically(self):
        profile = vpng.VpnProfile(profile_config(peers=()))
        configured = list(
            profile._list_routes(vpng.ProfileResourceSet.CONFIGURED)
        )

        profile.update_owned_state(routes={configured[0]})
        self.assertEqual(
            profile._list_routes(vpng.ProfileResourceSet.OWNED),
            frozenset({configured[0]}),
        )

        profile.update_owned_state(routes={configured[1]})
        self.assertEqual(
            profile._list_routes(vpng.ProfileResourceSet.OWNED),
            frozenset({configured[1]}),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
