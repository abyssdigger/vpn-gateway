#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


def make_profile(
    *,
    profile_id: str = "primary",
    interface: str = "vpns0",
    network: str = "172.20.130.0/29",
    local_address: str = "172.20.130.1",
    peers: tuple[str, ...] = ("172.20.130.6",),
    routes: tuple[str, ...] = ("10.0.0.0/8",),
) -> object:
    return vpng.VpnProfile(
        vpng.VpnProfileConfig(
            profile_id=profile_id,
            interface=interface,
            network=IPv4Network(network),
            local_address=IPv4Address(local_address),
            peers=tuple(IPv4Address(item) for item in peers),
            routes=tuple(IPv4Network(item) for item in routes),
            allowed_sources=(),
        )
    )


def make_daemon(*profiles) -> object:
    daemon = object.__new__(vpng.VpnGatewayDaemon)
    daemon.profiles = MappingProxyType(
        {
            profile.config.profile_id: profile
            for profile in profiles
        }
    )
    return daemon


def configured_by_type(profile, route_type):
    return frozenset(
        route
        for route in profile._list_routes(vpng.ProfileResourceSet.CONFIGURED)
        if route.route_type is route_type
    )


def foreign_route(
    destination: str,
    *,
    proto: int | None = 4,
    interface: str = "ens18",
    via: str | None = "10.200.200.1",
    metric: int | None = 100,
) -> object:
    return vpng.RouteSpec(
        destination=IPv4Network(destination),
        route_type=vpng.RouteType.UNICAST,
        via=None if via is None else IPv4Address(via),
        interface=interface,
        metric=metric,
        proto=proto,
        onlink=False,
    )


class RoutePlanningTests(unittest.TestCase):
    def test_desired_ready_profile_contains_configured_routes(self):
        profile = make_profile(
            peers=("172.20.130.6", "172.20.130.5"),
            routes=("10.0.0.0/8", "192.168.0.0/16"),
        )
        daemon = make_daemon(profile)

        desired = daemon._derive_desired_routes(
            interface_ipv4={
                "vpns0": frozenset({IPv4Address("172.20.130.1")}),
            }
        )

        self.assertEqual(
            desired["primary"],
            profile._list_routes(vpng.ProfileResourceSet.CONFIGURED),
        )
        self.assertIsInstance(desired, MappingProxyType)
        self.assertIsInstance(desired["primary"], frozenset)
        with self.assertRaises(TypeError):
            desired["primary"] = frozenset()

    def test_desired_not_ready_keeps_blackholes_only(self):
        profile = make_profile(peers=("172.20.130.6", "172.20.130.5"))
        daemon = make_daemon(profile)

        for interfaces in (
            {},
            {"vpns0": frozenset()},
            {"vpns0": frozenset({IPv4Address("172.20.130.2")})},
        ):
            with self.subTest(interfaces=interfaces):
                desired = daemon._derive_desired_routes(
                    interface_ipv4=interfaces
                )
                self.assertEqual(
                    desired["primary"],
                    configured_by_type(
                        profile,
                        vpng.RouteType.BLACKHOLE,
                    ),
                )

    def test_missing_desired_routes_become_adds(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        desired = daemon._derive_desired_routes(
            interface_ipv4={
                "vpns0": frozenset({IPv4Address("172.20.130.1")}),
            }
        )

        plan = daemon._build_plan(
            all_kernel_routes=frozenset(),
            desired_routes_by_profile=desired,
        )
        daemon._validate_plan(
            plan,
            all_kernel_routes=frozenset(),
            desired_routes_by_profile=desired,
        )

        self.assertEqual(plan.route_adds, desired["primary"])
        self.assertFalse(plan.route_deletes)
        self.assertFalse(plan.route_replaces)

    def test_owned_desired_actual_route_is_kept(self):
        profile = make_profile(peers=())
        daemon = make_daemon(profile)
        desired = daemon._derive_desired_routes(interface_ipv4={})
        route = next(iter(desired["primary"]))
        profile.update_owned_state(routes={route})

        plan = daemon._build_plan(
            all_kernel_routes=frozenset({route}),
            desired_routes_by_profile=desired,
        )
        daemon._validate_plan(
            plan,
            all_kernel_routes=frozenset({route}),
            desired_routes_by_profile=desired,
        )

        self.assertFalse(plan.route_adds)
        self.assertFalse(plan.route_deletes)
        self.assertFalse(plan.route_replaces)

    def test_actual_desired_not_owned_becomes_replace(self):
        profile = make_profile(peers=())
        daemon = make_daemon(profile)
        desired = daemon._derive_desired_routes(interface_ipv4={})
        route = next(iter(desired["primary"]))

        plan = daemon._build_plan(
            all_kernel_routes=frozenset({route}),
            desired_routes_by_profile=desired,
        )
        daemon._validate_plan(
            plan,
            all_kernel_routes=frozenset({route}),
            desired_routes_by_profile=desired,
        )

        self.assertFalse(plan.route_adds)
        self.assertFalse(plan.route_deletes)
        self.assertEqual(plan.route_replaces, frozenset({route}))

    def test_owned_unicast_not_desired_when_profile_down_is_deleted(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        unicast = next(iter(configured_by_type(
            profile,
            vpng.RouteType.UNICAST,
        )))
        profile.update_owned_state(routes={unicast})

        desired = daemon._derive_desired_routes(interface_ipv4={})
        plan = daemon._build_plan(
            all_kernel_routes=frozenset({unicast}),
            desired_routes_by_profile=desired,
        )
        daemon._validate_plan(
            plan,
            all_kernel_routes=frozenset({unicast}),
            desired_routes_by_profile=desired,
        )

        self.assertIn(unicast, plan.route_deletes)
        self.assertEqual(
            plan.route_adds,
            configured_by_type(profile, vpng.RouteType.BLACKHOLE),
        )

    def test_foreign_competing_exact_route_is_deleted(self):
        profile = make_profile(peers=())
        daemon = make_daemon(profile)
        foreign = foreign_route("10.0.0.0/8")
        desired = daemon._derive_desired_routes(interface_ipv4={})

        plan = daemon._build_plan(
            all_kernel_routes=frozenset({foreign}),
            desired_routes_by_profile=desired,
        )
        daemon._validate_plan(
            plan,
            all_kernel_routes=frozenset({foreign}),
            desired_routes_by_profile=desired,
        )

        self.assertEqual(plan.route_deletes, frozenset({foreign}))
        self.assertEqual(plan.route_adds, desired["primary"])

    def test_more_and_less_specific_overlaps_are_not_modified(self):
        profile = make_profile(routes=("10.20.0.0/16",))
        daemon = make_daemon(profile)
        more_specific = foreign_route("10.20.30.0/24")
        less_specific = foreign_route("10.0.0.0/8")
        default = foreign_route("0.0.0.0/0")
        actual = frozenset({more_specific, less_specific, default})

        desired = daemon._derive_desired_routes(interface_ipv4={})
        plan = daemon._build_plan(
            all_kernel_routes=actual,
            desired_routes_by_profile=desired,
        )
        daemon._validate_plan(
            plan,
            all_kernel_routes=actual,
            desired_routes_by_profile=desired,
        )

        self.assertFalse(plan.route_deletes)
        self.assertFalse(plan.route_replaces)
        self.assertEqual(plan.route_adds, desired["primary"])

        related = daemon._routes_for_profile(profile, actual)
        self.assertEqual(
            related,
            frozenset({more_specific, less_specific}),
        )

    def test_exact_proto_kernel_conflict_is_rejected_before_apply(self):
        profile = make_profile(peers=())
        daemon = make_daemon(profile)
        kernel = foreign_route(
            "10.0.0.0/8",
            proto=vpng.KERNEL_ROUTE_PROTO,
            interface="ens18",
            via=None,
            metric=None,
        )
        desired = daemon._derive_desired_routes(interface_ipv4={})

        plan = daemon._build_plan(
            all_kernel_routes=frozenset({kernel}),
            desired_routes_by_profile=desired,
        )
        self.assertIn(kernel, plan.route_deletes)

        with self.assertRaises(vpng.PlanValidationError):
            daemon._validate_plan(
                plan,
                all_kernel_routes=frozenset({kernel}),
                desired_routes_by_profile=desired,
            )

    def test_foreign_delete_outside_exact_scope_is_rejected(self):
        profile = make_profile(peers=())
        daemon = make_daemon(profile)
        foreign = foreign_route("192.168.0.0/16")
        desired = daemon._derive_desired_routes(interface_ipv4={})
        plan = vpng.ReconciliationPlan(
            route_adds=frozenset(),
            route_deletes=frozenset({foreign}),
            route_replaces=frozenset(),
        )

        with self.assertRaises(vpng.PlanValidationError):
            daemon._validate_plan(
                plan,
                all_kernel_routes=frozenset({foreign}),
                desired_routes_by_profile=desired,
            )

    def test_add_delete_replace_sets_must_be_disjoint(self):
        profile = make_profile(peers=())
        daemon = make_daemon(profile)
        desired = daemon._derive_desired_routes(interface_ipv4={})
        route = next(iter(desired["primary"]))
        plan = vpng.ReconciliationPlan(
            route_adds=frozenset({route}),
            route_deletes=frozenset(),
            route_replaces=frozenset({route}),
        )

        with self.assertRaises(vpng.PlanValidationError):
            daemon._validate_plan(
                plan,
                all_kernel_routes=frozenset({route}),
                desired_routes_by_profile=desired,
            )

    def test_replace_requires_actual_and_not_owned(self):
        profile = make_profile(peers=())
        daemon = make_daemon(profile)
        desired = daemon._derive_desired_routes(interface_ipv4={})
        route = next(iter(desired["primary"]))
        plan = vpng.ReconciliationPlan(
            route_adds=frozenset(),
            route_deletes=frozenset(),
            route_replaces=frozenset({route}),
        )

        with self.assertRaises(vpng.PlanValidationError):
            daemon._validate_plan(
                plan,
                all_kernel_routes=frozenset(),
                desired_routes_by_profile=desired,
            )

        profile.update_owned_state(routes={route})
        with self.assertRaises(vpng.PlanValidationError):
            daemon._validate_plan(
                plan,
                all_kernel_routes=frozenset({route}),
                desired_routes_by_profile=desired,
            )

    def test_incomplete_desired_snapshot_is_rejected(self):
        primary = make_profile(profile_id="primary")
        backup = make_profile(
            profile_id="backup",
            interface="wg0",
            network="172.20.126.0/29",
            local_address="172.20.126.1",
            peers=("172.20.126.2",),
            routes=("192.168.0.0/16",),
        )
        daemon = make_daemon(primary, backup)

        incomplete = MappingProxyType({
            "primary": primary._list_routes(
                vpng.ProfileResourceSet.CONFIGURED
            ),
        })

        with self.assertRaises(vpng.ReconciliationError):
            daemon._build_plan(
                all_kernel_routes=frozenset(),
                desired_routes_by_profile=incomplete,
            )

    def test_duplicate_exact_resource_claim_is_rejected_defensively(self):
        primary = make_profile(profile_id="primary", peers=())
        backup = make_profile(
            profile_id="backup",
            interface="wg0",
            network="172.20.126.0/29",
            local_address="172.20.126.1",
            peers=(),
            routes=("192.168.0.0/16",),
        )
        daemon = make_daemon(primary, backup)

        shared = next(iter(
            primary._list_routes(vpng.ProfileResourceSet.CONFIGURED)
        ))
        desired = MappingProxyType({
            "primary": frozenset({shared}),
            "backup": frozenset({shared}),
        })
        plan = vpng.ReconciliationPlan(
            route_adds=frozenset({shared}),
            route_deletes=frozenset(),
            route_replaces=frozenset(),
        )

        with self.assertRaises(vpng.PlanValidationError):
            daemon._validate_plan(
                plan,
                all_kernel_routes=frozenset(),
                desired_routes_by_profile=desired,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
