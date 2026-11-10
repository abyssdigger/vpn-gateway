#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from unittest import mock
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


def make_profile(
    *,
    profile_id="primary",
    interface="vpns+",
    network="172.20.130.0/29",
    routes=("10.0.0.0/8",),
):
    return vpng.VpnProfile(
        vpng.VpnProfileConfig(
            profile_id=profile_id,
            interface=vpng.InterfaceSelector.parse(interface),
            network=IPv4Network(network),
            routes=tuple(IPv4Network(item) for item in routes),
            allowed_sources=(),
        )
    )


def make_daemon(*profiles):
    daemon = object.__new__(vpng.VpnGatewayDaemon)
    profile_map = MappingProxyType(
        {profile.config.profile_id: profile for profile in profiles}
    )
    daemon.profiles = profile_map
    daemon.config = vpng.GatewayConfig(
        reconcile_interval=10.0,
        common_allowed_sources=(),
        vpns=MappingProxyType(
            {
                profile_id: profile.config
                for profile_id, profile in profile_map.items()
            }
        ),
    )
    return daemon


def records(items):
    return tuple(
        vpng.InterfaceRecord(
            name,
            ifindex,
            frozenset({IPv4Address(address)}),
        )
        for name, ifindex, address in items
    )


def derive(daemon, items=()):
    state = daemon._resolve_profile_interfaces(records(items))
    allocations, cursors = daemon._build_prefix_metric_state(state)
    desired = daemon._derive_desired_routes(
        interface_state_by_profile=state,
        prefix_metric_allocations_by_profile=allocations,
    )
    return state, desired


def commit_state(profile, daemon, state, routes):
    allocations, cursors = daemon._build_prefix_metric_state(state)
    if profile.config.interface.kind is vpng.InterfaceSelectorKind.PREFIX:
        profile.commit_verified_state(
            routes=routes,
            active_bindings=state[profile.config.profile_id].active_bindings,
            prefix_metrics=allocations[profile.config.profile_id],
            prefix_metric_cursor=cursors[profile.config.profile_id],
        )
    else:
        profile.commit_verified_state(
            routes=routes,
            active_bindings=state[profile.config.profile_id].active_bindings,
        )


def by_type(routes, route_type):
    return frozenset(
        route for route in routes if route.route_type is route_type
    )


def foreign_route(
    destination,
    *,
    proto=4,
    interface="ens18",
    via="10.200.200.1",
    metric=100,
):
    return vpng.RouteSpec(
        destination=IPv4Network(destination),
        route_type=vpng.RouteType.UNICAST,
        via=None if via is None else IPv4Address(via),
        interface=interface,
        metric=metric,
        proto=proto,
        onlink=False,
    )


class RouteDerivationTests(unittest.TestCase):
    def test_prefix_materializes_direct_routes_for_all_active_interfaces(self):
        profile = make_profile(
            routes=("10.0.0.0/8", "192.168.0.0/16")
        )
        daemon = make_daemon(profile)
        state, desired = derive(
            daemon,
            (
                ("vpns9", 9, "172.20.130.1"),
                ("vpns10", 10, "172.20.130.1"),
            ),
        )
        self.assertEqual(
            tuple(
                binding.name
                for binding in state["primary"].active_bindings
            ),
            ("vpns9", "vpns10"),
        )
        unicast = by_type(
            desired["primary"],
            vpng.RouteType.UNICAST,
        )
        self.assertEqual(
            {route.interface for route in unicast},
            {"vpns10", "vpns9"},
        )
        self.assertEqual(
            {
                route.metric
                for route in unicast
                if route.interface == "vpns9"
            },
            {10},
        )
        self.assertEqual(
            {
                route.metric
                for route in unicast
                if route.interface == "vpns10"
            },
            {20},
        )
        self.assertTrue(
            all(route.via is None and not route.onlink for route in unicast)
        )

    def test_prefix_new_binding_keeps_existing_order_and_metrics(self):
        profile = make_profile()
        daemon = make_daemon(profile)

        first = daemon._build_reconciliation_snapshot(
            records(
                (
                    ("vpns2", 2, "172.20.130.1"),
                    ("vpns9", 9, "172.20.130.1"),
                )
            )
        )
        first_state = first.interface_state_by_profile["primary"]
        profile.commit_verified_state(
            routes=first.desired_routes_by_profile["primary"],
            active_bindings=first_state.active_bindings,
            prefix_metrics=first.prefix_metric_allocations_by_profile["primary"],
            prefix_metric_cursor=first.prefix_metric_cursor_by_profile["primary"],
        )

        second = daemon._build_reconciliation_snapshot(
            records(
                (
                    ("vpns10", 10, "172.20.130.1"),
                    ("vpns2", 2, "172.20.130.1"),
                    ("vpns9", 9, "172.20.130.1"),
                )
            )
        )
        second_state = second.interface_state_by_profile["primary"]
        self.assertEqual(
            tuple(binding.name for binding in second_state.active_bindings),
            ("vpns2", "vpns9", "vpns10"),
        )
        metrics = second.prefix_metric_allocations_by_profile["primary"]
        self.assertEqual(metrics[vpng.InterfaceBinding("vpns2", 2)], 10)
        self.assertEqual(metrics[vpng.InterfaceBinding("vpns9", 9)], 20)
        self.assertEqual(metrics[vpng.InterfaceBinding("vpns10", 10)], 30)

        nat = second.desired_full_policy.nat.chain("VPNG-PRIMARY-NAT").rules
        interfaces = tuple(
            token
            for rule in nat
            for token in rule.split()
            if token.startswith("vpns")
        )
        self.assertEqual(interfaces, ("vpns2", "vpns9", "vpns10"))

    def test_prefix_freed_metric_is_not_reused_before_cursor_wrap(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        first = daemon._build_reconciliation_snapshot(
            records(
                (
                    ("vpns2", 2, "172.20.130.1"),
                    ("vpns9", 9, "172.20.130.1"),
                )
            )
        )
        state = first.interface_state_by_profile["primary"]
        profile.commit_verified_state(
            routes=first.desired_routes_by_profile["primary"],
            active_bindings=state.active_bindings,
            prefix_metrics=first.prefix_metric_allocations_by_profile["primary"],
            prefix_metric_cursor=first.prefix_metric_cursor_by_profile["primary"],
        )

        second = daemon._build_reconciliation_snapshot(
            records(
                (
                    ("vpns9", 9, "172.20.130.1"),
                    ("vpns10", 10, "172.20.130.1"),
                )
            )
        )
        metrics = second.prefix_metric_allocations_by_profile["primary"]
        self.assertEqual(metrics[vpng.InterfaceBinding("vpns9", 9)], 20)
        self.assertEqual(metrics[vpng.InterfaceBinding("vpns10", 10)], 30)

    def test_prefix_allocator_wraps_and_skips_occupied_slots(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        first = vpng.InterfaceBinding("vpns1", 1)
        second = vpng.InterfaceBinding("vpns2", 2)
        profile.commit_verified_state(
            routes=frozenset(),
            active_bindings=(first, second),
            prefix_metrics={first: 10, second: 30},
            prefix_metric_cursor=30,
        )

        with mock.patch("vpn_gatewayd.daemon.BLACKHOLE_METRIC", 40):
            snapshot = daemon._build_reconciliation_snapshot(
                records(
                    (
                        ("vpns1", 1, "172.20.130.1"),
                        ("vpns2", 2, "172.20.130.1"),
                        ("vpns3", 3, "172.20.130.1"),
                    )
                )
            )

        metrics = snapshot.prefix_metric_allocations_by_profile["primary"]
        self.assertEqual(metrics[first], 10)
        self.assertEqual(metrics[second], 30)
        self.assertEqual(metrics[vpng.InterfaceBinding("vpns3", 3)], 20)

    def test_prefix_allocator_exhaustion_rejects_snapshot(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        with (
            mock.patch("vpn_gatewayd.daemon.BLACKHOLE_METRIC", 30),
            self.assertRaises(vpng.ReconciliationError),
        ):
            daemon._build_reconciliation_snapshot(
                records(
                    (
                        ("vpns1", 1, "172.20.130.1"),
                        ("vpns2", 2, "172.20.130.1"),
                        ("vpns3", 3, "172.20.130.1"),
                    )
                )
            )

    def test_explicit_list_preserves_priority_holes(self):
        profile = make_profile(
            interface=["vpnA", "vpnB", "vpnC"]
        )
        daemon = make_daemon(profile)
        _, desired = derive(
            daemon,
            (
                ("vpnA", 1, "172.20.130.1"),
                ("vpnC", 3, "172.20.130.1"),
            ),
        )
        unicast = by_type(
            desired["primary"],
            vpng.RouteType.UNICAST,
        )
        self.assertEqual(
            {(route.interface, route.metric) for route in unicast},
            {("vpnA", 10), ("vpnC", 30)},
        )

    def test_no_active_interface_keeps_blackhole_only(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        _, desired = derive(daemon, ())
        self.assertEqual(
            {route.route_type for route in desired["primary"]},
            {vpng.RouteType.BLACKHOLE},
        )

    def test_candidate_different_address_inside_network_gets_route(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        _, desired = derive(
            daemon,
            (("vpns0", 7, "172.20.130.2"),),
        )
        self.assertTrue(
            by_type(desired["primary"], vpng.RouteType.UNICAST)
        )

    def test_candidate_address_outside_network_does_not_get_route(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        _, desired = derive(
            daemon,
            (("vpns0", 7, "172.20.131.2"),),
        )
        self.assertFalse(
            by_type(desired["primary"], vpng.RouteType.UNICAST)
        )


class RoutePlanningTests(unittest.TestCase):
    def setUp(self):
        self.profile = make_profile()
        self.daemon = make_daemon(self.profile)
        self.state, self.desired = derive(
            self.daemon,
            (("vpns0", 7, "172.20.130.1"),),
        )

    def test_missing_desired_routes_become_adds(self):
        plan = self.daemon._build_plan(
            all_kernel_routes=frozenset(),
            desired_routes_by_profile=self.desired,
        )
        self.daemon._validate_plan(
            plan,
            all_kernel_routes=frozenset(),
            desired_routes_by_profile=self.desired,
        )
        self.assertEqual(
            plan.route_adds,
            self.desired["primary"],
        )

    def test_actual_desired_not_owned_becomes_replace(self):
        route = next(iter(self.desired["primary"]))
        plan = self.daemon._build_plan(
            all_kernel_routes=frozenset({route}),
            desired_routes_by_profile=self.desired,
        )
        self.assertEqual(
            plan.route_replaces,
            frozenset({route}),
        )

    def test_owned_desired_actual_is_kept(self):
        routes = self.desired["primary"]
        commit_state(self.profile, self.daemon, self.state, routes)
        plan = self.daemon._build_plan(
            all_kernel_routes=routes,
            desired_routes_by_profile=self.desired,
        )
        self.assertFalse(
            plan.route_adds
            or plan.route_deletes
            or plan.route_replaces
        )

    def test_foreign_competing_exact_route_is_deleted(self):
        foreign = foreign_route("10.0.0.0/8")
        plan = self.daemon._build_plan(
            all_kernel_routes=frozenset({foreign}),
            desired_routes_by_profile=self.desired,
        )
        self.assertIn(foreign, plan.route_deletes)

    def test_proto_kernel_exact_conflict_is_rejected(self):
        kernel = foreign_route(
            "10.0.0.0/8",
            proto=vpng.KERNEL_ROUTE_PROTO,
            interface="ens18",
            via=None,
            metric=None,
        )
        plan = self.daemon._build_plan(
            all_kernel_routes=frozenset({kernel}),
            desired_routes_by_profile=self.desired,
        )
        with self.assertRaises(vpng.PlanValidationError):
            self.daemon._validate_plan(
                plan,
                all_kernel_routes=frozenset({kernel}),
                desired_routes_by_profile=self.desired,
            )

    def test_more_less_specific_overlaps_are_not_modified(self):
        profile = make_profile(routes=("10.20.0.0/16",))
        daemon = make_daemon(profile)
        _, desired = derive(daemon, ())
        actual = frozenset(
            {
                foreign_route("10.20.30.0/24"),
                foreign_route("10.0.0.0/8"),
            }
        )
        plan = daemon._build_plan(
            all_kernel_routes=actual,
            desired_routes_by_profile=desired,
        )
        self.assertFalse(
            plan.route_deletes or plan.route_replaces
        )


class RouteVerificationTests(unittest.TestCase):
    def test_verified_zero_path_is_fail_but_structurally_verified(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        state, desired = derive(daemon, ())
        verified = daemon._verify_plan(
            all_kernel_routes=desired["primary"],
            desired_routes_by_profile=desired,
        )
        result = verified.profile_results["primary"]
        self.assertIs(
            result.result,
            vpng.ApplyStateResult.FAIL,
        )
        self.assertIs(
            result.reason.code,
            vpng.RuntimeReasonCode.PROFILE_NO_UNICAST_PATH,
        )
        self.assertEqual(
            verified.verified_profiles,
            frozenset({"primary"}),
        )

        allocations, cursors = daemon._build_prefix_metric_state(state)
        daemon._commit_owned(
            verified_routes_by_profile=(
                verified.owned_routes_by_profile
            ),
            verified_profiles=verified.verified_profiles,
            interface_state_by_profile=state,
            prefix_metric_allocations_by_profile=allocations,
            prefix_metric_cursor_by_profile=cursors,
        )
        self.assertEqual(
            profile.committed_active_bindings,
            (),
        )

    def test_verified_direct_path_is_success(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        _, desired = derive(
            daemon,
            (("vpns0", 7, "172.20.130.1"),),
        )
        verified = daemon._verify_plan(
            all_kernel_routes=desired["primary"],
            desired_routes_by_profile=desired,
        )
        self.assertIs(
            verified.profile_results["primary"].result,
            vpng.ApplyStateResult.SUCCESS,
        )
        self.assertEqual(
            verified.verified_profiles,
            frozenset({"primary"}),
        )

    def test_route_mismatch_is_not_verified(self):
        profile = make_profile()
        daemon = make_daemon(profile)
        _, desired = derive(
            daemon,
            (("vpns0", 7, "172.20.130.1"),),
        )
        verified = daemon._verify_plan(
            all_kernel_routes=frozenset(),
            desired_routes_by_profile=desired,
        )
        self.assertEqual(
            verified.verified_profiles,
            frozenset(),
        )
        self.assertIs(
            verified.profile_results["primary"].reason.code,
            vpng.RuntimeReasonCode.PROFILE_ROUTE_MISMATCH,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
