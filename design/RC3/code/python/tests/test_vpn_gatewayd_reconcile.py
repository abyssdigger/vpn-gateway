#!/usr/bin/env python3
from __future__ import annotations

import errno
import socket
import sys
import unittest
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import vpn_gatewayd as vpng


def make_config():
    profile = vpng.VpnProfileConfig(
        profile_id="primary",
        interface=vpng.InterfaceSelector.parse("vpns+"),
        network=IPv4Network("172.20.130.0/29"),
        routes=(IPv4Network("10.0.0.0/8"),),
        allowed_sources=(),
    )
    return vpng.GatewayConfig(
        reconcile_interval=10.0,
        common_allowed_sources=(IPv4Network("10.200.200.8/32"),),
        vpns=MappingProxyType({"primary": profile}),
    )


def ready_record(ifindex=7):
    return vpng.InterfaceRecord(
        "vpns0",
        ifindex,
        frozenset({IPv4Address("172.20.130.1")}),
    )


def make_daemon(kernel=None):
    if kernel is None:
        kernel = mock.Mock()
    daemon = vpng.VpnGatewayDaemon(
        config_path=Path("/dev/null"),
        kernel=kernel,
        config_loader=mock.Mock(),
    )
    daemon._install_config(make_config())
    return daemon


def success_results():
    return MappingProxyType(
        {"primary": vpng.ProfileResult(vpng.ApplyStateResult.SUCCESS)}
    )


class SnapshotTests(unittest.TestCase):
    def test_policy_transition_tracks_active_identity_not_candidate_only_change(self):
        daemon = make_daemon()
        first = daemon._build_reconciliation_snapshot((ready_record(7),))
        state = first.interface_state_by_profile["primary"]
        daemon.profiles["primary"].commit_verified_state(
            routes=frozenset(),
            active_bindings=state.active_bindings,
            prefix_metrics=first.prefix_metric_allocations_by_profile["primary"],
            prefix_metric_cursor=first.prefix_metric_cursor_by_profile["primary"],
        )

        self.assertFalse(daemon._snapshot_changes_policy(first))
        self.assertTrue(
            daemon._snapshot_changes_policy(
                daemon._build_reconciliation_snapshot((ready_record(8),))
            )
        )

        candidate_only = daemon._build_reconciliation_snapshot(
            (
                ready_record(7),
                vpng.InterfaceRecord("vpns1", 8, frozenset()),
            )
        )
        self.assertFalse(daemon._snapshot_changes_policy(candidate_only))

        second_active = daemon._build_reconciliation_snapshot(
            (
                ready_record(7),
                vpng.InterfaceRecord(
                    "vpns1",
                    8,
                    frozenset({IPv4Address("172.20.130.1")}),
                ),
            )
        )
        self.assertTrue(daemon._snapshot_changes_policy(second_active))

    def test_same_name_new_ifindex_builds_remove_then_add_gap(self):
        daemon = make_daemon()
        previous = daemon._build_reconciliation_snapshot((ready_record(7),))
        previous_state = previous.interface_state_by_profile["primary"]
        daemon.profiles["primary"].commit_verified_state(
            routes=previous.desired_routes_by_profile["primary"],
            active_bindings=previous_state.active_bindings,
            prefix_metrics=previous.prefix_metric_allocations_by_profile["primary"],
            prefix_metric_cursor=previous.prefix_metric_cursor_by_profile["primary"],
        )

        current = daemon._build_reconciliation_snapshot((ready_record(8),))
        (
            previous_policy,
            intermediate_policy,
            previous_routes,
            intermediate_routes,
            has_remove,
            has_add,
        ) = daemon._build_local_transition(current)

        self.assertTrue(has_remove)
        self.assertTrue(has_add)
        self.assertNotEqual(
            previous_routes["primary"],
            intermediate_routes["primary"],
        )

        previous_filter = "\n".join(
            rule
            for chain in previous_policy.filter.chains
            for rule in chain.rules
        )
        intermediate_filter = "\n".join(
            rule
            for chain in intermediate_policy.filter.chains
            for rule in chain.rules
        )
        self.assertIn("-i vpns0", previous_filter)
        self.assertIn("-o vpns0", previous_filter)
        self.assertNotIn("-i vpns0 -m conntrack", intermediate_filter)
        self.assertNotIn(" -o vpns0 ", intermediate_filter)

    def test_local_route_source_rejects_unexpected_exact_route_before_add(self):
        kernel = mock.Mock()
        daemon = make_daemon(kernel)
        previous = daemon._build_reconciliation_snapshot(())
        current = daemon._build_reconciliation_snapshot((ready_record(7),))

        daemon.profiles["primary"].commit_verified_state(
            routes=previous.desired_routes_by_profile["primary"],
            active_bindings=(),
            prefix_metrics=previous.prefix_metric_allocations_by_profile["primary"],
            prefix_metric_cursor=previous.prefix_metric_cursor_by_profile["primary"],
        )
        (
            _previous_policy,
            _intermediate_policy,
            previous_routes,
            intermediate_routes,
            _has_remove,
            _has_add,
        ) = daemon._build_local_transition(current)

        unexpected = next(
            route
            for route in current.desired_routes_by_profile["primary"]
            if route.route_type is vpng.RouteType.UNICAST
        )
        kernel.list_routes.return_value = frozenset(
            set(previous_routes["primary"]) | {unexpected}
        )

        with self.assertRaises(vpng.ReconciliationError):
            daemon._validate_local_route_source(
                previous_routes,
                intermediate_routes,
            )

    def test_local_route_source_allows_kernel_removed_route_for_remove(self):
        kernel = mock.Mock()
        daemon = make_daemon(kernel)
        previous = daemon._build_reconciliation_snapshot((ready_record(7),))
        previous_state = previous.interface_state_by_profile["primary"]
        daemon.profiles["primary"].commit_verified_state(
            routes=previous.desired_routes_by_profile["primary"],
            active_bindings=previous_state.active_bindings,
            prefix_metrics=previous.prefix_metric_allocations_by_profile["primary"],
            prefix_metric_cursor=previous.prefix_metric_cursor_by_profile["primary"],
        )
        current = daemon._build_reconciliation_snapshot(())
        (
            _previous_policy,
            _intermediate_policy,
            previous_routes,
            intermediate_routes,
            _has_remove,
            _has_add,
        ) = daemon._build_local_transition(current)

        kernel.list_routes.return_value = intermediate_routes["primary"]

        daemon._validate_local_route_source(
            previous_routes,
            intermediate_routes,
        )

    def test_ipv6_check_covers_every_prefix_match_before_resolution(self):
        kernel = mock.Mock()
        kernel.get_interface_ipv6_disabled.side_effect = (
            lambda name: name == "vpns0"
        )
        daemon = make_daemon(kernel)
        interfaces = (
            ready_record(7),
            vpng.InterfaceRecord("vpns1", 8, frozenset()),
        )

        with self.assertRaises(vpng.ReconciliationError):
            daemon._check_interface_ipv6_prerequisites(interfaces)

        self.assertEqual(
            kernel.get_interface_ipv6_disabled.call_args_list,
            [mock.call("vpns0"), mock.call("vpns1")],
        )


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.kernel = mock.Mock()
        self.kernel.list_interfaces.return_value = (ready_record(),)
        self.kernel.get_ipv6_all_forwarding.return_value = False
        self.kernel.get_ipv6_default_forwarding.return_value = False
        self.kernel.get_ipv6_default_disabled.return_value = True
        self.kernel.get_interface_ipv6_disabled.return_value = True
        self.daemon = make_daemon(self.kernel)

    def test_input_only_drift_repairs_without_disabling_forwarding(self):
        unsafe = vpng.FirewallCheck(
            vpng.FirewallSafety.UNSAFE,
            vpng.DiagnosticFact(
                vpng.RuntimeReasonCode.FIREWALL_DRIFT,
                "INPUT prefix differs",
            ),
            vpng.FirewallDriftScope.INPUT_ONLY,
        )
        safe = vpng.FirewallCheck(vpng.FirewallSafety.SAFE, None)

        with (
            mock.patch.object(
                self.daemon,
                "_snapshot_changes_policy",
                return_value=False,
            ),
            mock.patch.object(
                self.daemon,
                "_check_firewall_nat_policy",
                side_effect=(unsafe, safe),
            ),
            mock.patch.object(
                self.daemon,
                "_restore_filter_policy",
            ) as restore_filter,
            mock.patch.object(
                self.daemon,
                "_reconcile_routes_snapshot",
                return_value=success_results(),
            ),
            mock.patch.object(
                self.daemon,
                "_best_effort_disable_forwarding",
            ) as disable,
            mock.patch.object(
                self.daemon,
                "_best_effort_enable_forwarding",
                return_value=(True, None),
            ),
        ):
            self.daemon.reconcile()

        disable.assert_not_called()
        self.assertTrue(restore_filter.called)
        self.assertTrue(restore_filter.call_args.kwargs["input_only"])
        self.assertIs(self.daemon.state, vpng.DaemonState.ACTIVE)

    def test_snapshot_projection_failure_isolates_without_partial_apply(self):
        with (
            mock.patch.object(
                self.daemon,
                "_build_reconciliation_snapshot",
                side_effect=vpng.ReconciliationError(
                    "prefix metric allocator exhausted"
                ),
            ),
            mock.patch.object(
                self.daemon,
                "_best_effort_disable_forwarding",
                return_value=None,
            ) as disable,
            mock.patch.object(
                self.daemon,
                "_best_effort_apply_isolation_filter",
                return_value=None,
            ) as isolation,
            mock.patch.object(
                self.daemon,
                "_check_firewall_nat_policy",
            ) as firewall,
        ):
            self.daemon.reconcile()

        self.assertIs(self.daemon.state, vpng.DaemonState.ISOLATED)
        disable.assert_called_once()
        isolation.assert_called_once()
        firewall.assert_not_called()

    def test_runtime_ipv6_violation_latches_isolation_until_restart(self):
        self.kernel.get_ipv6_all_forwarding.return_value = True
        with (
            mock.patch.object(
                self.daemon,
                "_best_effort_disable_forwarding",
                return_value=None,
            ) as disable,
            mock.patch.object(
                self.daemon,
                "_best_effort_apply_isolation_filter",
                return_value=None,
            ) as isolation,
        ):
            self.daemon.reconcile()

        self.assertIs(self.daemon.state, vpng.DaemonState.ISOLATED)
        self.assertTrue(self.daemon._host_prerequisite_latched)
        disable.assert_called_once()
        isolation.assert_called_once()

        self.kernel.get_ipv6_all_forwarding.return_value = False
        self.kernel.list_interfaces.reset_mock()
        with (
            mock.patch.object(
                self.daemon,
                "_best_effort_disable_forwarding",
                return_value=None,
            ),
            mock.patch.object(
                self.daemon,
                "_best_effort_apply_isolation_filter",
                return_value=None,
            ),
            mock.patch.object(
                self.daemon,
                "_build_reconciliation_snapshot",
            ) as snapshot,
        ):
            self.daemon.reconcile()
        snapshot.assert_not_called()
        self.kernel.list_interfaces.assert_not_called()
        self.assertIs(self.daemon.state, vpng.DaemonState.ISOLATED)

    def test_transit_drift_uses_init_panic_rebuild(self):
        unsafe = vpng.FirewallCheck(
            vpng.FirewallSafety.UNSAFE,
            vpng.DiagnosticFact(
                vpng.RuntimeReasonCode.FIREWALL_DRIFT,
                "FORWARD prefix differs",
            ),
            vpng.FirewallDriftScope.TRANSIT,
        )

        with (
            mock.patch.object(
                self.daemon,
                "_snapshot_changes_policy",
                return_value=False,
            ),
            mock.patch.object(
                self.daemon,
                "_check_firewall_nat_policy",
                return_value=unsafe,
            ),
            mock.patch.object(
                self.daemon,
                "_best_effort_disable_forwarding",
                return_value=None,
            ) as disable,
            mock.patch.object(
                self.daemon,
                "_rebuild_firewall_nat_init_panic",
            ) as rebuild,
            mock.patch.object(
                self.daemon,
                "_reconcile_routes_snapshot",
                return_value=success_results(),
            ),
            mock.patch.object(
                self.daemon,
                "_best_effort_enable_forwarding",
                return_value=(True, None),
            ),
        ):
            self.daemon.reconcile()

        disable.assert_called_once()
        rebuild.assert_called_once()
        self.assertTrue(rebuild.call_args.kwargs["forwarding_disabled"])
        self.assertIs(self.daemon.state, vpng.DaemonState.ACTIVE)

    def test_local_binding_transition_does_not_disable_forwarding(self):
        safe = vpng.FirewallCheck(vpng.FirewallSafety.SAFE, None)
        snapshot = self.daemon._build_reconciliation_snapshot(
            (ready_record(),)
        )
        previous_policy = snapshot.desired_full_policy
        intermediate_policy = snapshot.desired_full_policy
        previous_routes = snapshot.desired_routes_by_profile
        intermediate_routes = snapshot.desired_routes_by_profile

        with (
            mock.patch.object(
                self.daemon,
                "_snapshot_changes_policy",
                return_value=True,
            ),
            mock.patch.object(
                self.daemon,
                "_build_local_transition",
                return_value=(
                    previous_policy,
                    intermediate_policy,
                    previous_routes,
                    intermediate_routes,
                    False,
                    True,
                ),
            ),
            mock.patch.object(
                self.daemon,
                "_check_firewall_nat_policy",
                return_value=safe,
            ),
            mock.patch.object(
                self.daemon,
                "_validate_local_route_source",
            ),
            mock.patch.object(
                self.daemon,
                "_apply_local_add",
            ) as add,
            mock.patch.object(
                self.daemon,
                "_verify_and_commit_local_transition",
                return_value=success_results(),
            ),
            mock.patch.object(
                self.daemon,
                "_best_effort_disable_forwarding",
            ) as disable,
            mock.patch.object(
                self.daemon,
                "_rebuild_firewall_nat_init_panic",
            ) as rebuild,
            mock.patch.object(
                self.daemon,
                "_best_effort_enable_forwarding",
                return_value=(True, None),
            ),
        ):
            self.daemon.reconcile()

        disable.assert_not_called()
        add.assert_called_once()
        rebuild.assert_not_called()
        self.assertIs(self.daemon.state, vpng.DaemonState.ACTIVE)

    def test_replacement_runs_remove_before_add_without_disabling_forwarding(self):
        safe = vpng.FirewallCheck(vpng.FirewallSafety.SAFE, None)
        snapshot = self.daemon._build_reconciliation_snapshot(
            (ready_record(),)
        )
        policy = snapshot.desired_full_policy
        routes = snapshot.desired_routes_by_profile
        events = []

        with (
            mock.patch.object(
                self.daemon,
                "_snapshot_changes_policy",
                return_value=True,
            ),
            mock.patch.object(
                self.daemon,
                "_build_local_transition",
                return_value=(policy, policy, routes, routes, True, True),
            ),
            mock.patch.object(
                self.daemon,
                "_check_firewall_nat_policy",
                return_value=safe,
            ),
            mock.patch.object(
                self.daemon,
                "_validate_local_route_source",
            ),
            mock.patch.object(
                self.daemon,
                "_apply_local_remove",
                side_effect=lambda *args: events.append("remove"),
            ),
            mock.patch.object(
                self.daemon,
                "_apply_local_add",
                side_effect=lambda *args: events.append("add"),
            ),
            mock.patch.object(
                self.daemon,
                "_verify_and_commit_local_transition",
                return_value=success_results(),
            ),
            mock.patch.object(
                self.daemon,
                "_best_effort_disable_forwarding",
            ) as disable,
            mock.patch.object(
                self.daemon,
                "_best_effort_enable_forwarding",
                return_value=(True, None),
            ),
        ):
            self.daemon.reconcile()

        self.assertEqual(events, ["remove", "add"])
        disable.assert_not_called()

    def test_failed_local_transition_falls_back_to_init_panic(self):
        safe = vpng.FirewallCheck(vpng.FirewallSafety.SAFE, None)
        snapshot = self.daemon._build_reconciliation_snapshot(
            (ready_record(),)
        )
        policy = snapshot.desired_full_policy
        routes = snapshot.desired_routes_by_profile

        with (
            mock.patch.object(
                self.daemon,
                "_snapshot_changes_policy",
                return_value=True,
            ),
            mock.patch.object(
                self.daemon,
                "_build_local_transition",
                return_value=(policy, policy, routes, routes, False, True),
            ),
            mock.patch.object(
                self.daemon,
                "_check_firewall_nat_policy",
                return_value=safe,
            ),
            mock.patch.object(
                self.daemon,
                "_validate_local_route_source",
            ),
            mock.patch.object(
                self.daemon,
                "_apply_local_add",
                side_effect=vpng.ReconciliationError("boom"),
            ),
            mock.patch.object(
                self.daemon,
                "_best_effort_disable_forwarding",
                return_value=None,
            ) as disable,
            mock.patch.object(
                self.daemon,
                "_rebuild_firewall_nat_init_panic",
            ) as rebuild,
            mock.patch.object(
                self.daemon,
                "_reconcile_routes_snapshot",
                return_value=success_results(),
            ),
            mock.patch.object(
                self.daemon,
                "_best_effort_enable_forwarding",
                return_value=(True, None),
            ),
        ):
            self.daemon.reconcile()

        disable.assert_called_once()
        rebuild.assert_called_once()
        self.assertIs(self.daemon.state, vpng.DaemonState.ACTIVE)

    def test_init_panic_uses_direct_full_rebuild_when_forwarding_is_off(self):
        snapshot = self.daemon._build_reconciliation_snapshot(
            (ready_record(),)
        )
        events = []

        def restore_filter(policy, *, input_only=False):
            self.assertFalse(input_only)
            accepts = any(
                "-j ACCEPT" in rule
                for chain in policy.chains
                for rule in chain.rules
            )
            events.append("full" if accepts else "isolation")

        def restore_nat(policy):
            del policy
            events.append("nat")

        safe = vpng.FirewallCheck(vpng.FirewallSafety.SAFE, None)
        with (
            mock.patch.object(
                self.daemon,
                "_restore_filter_policy",
                side_effect=restore_filter,
            ),
            mock.patch.object(
                self.daemon,
                "_restore_nat_policy",
                side_effect=restore_nat,
            ),
            mock.patch.object(
                self.daemon,
                "_check_filter_policy",
                return_value=safe,
            ),
            mock.patch.object(
                self.daemon,
                "_check_firewall_nat_policy",
                return_value=safe,
            ),
        ):
            self.daemon._rebuild_firewall_nat_init_panic(
                snapshot,
                forwarding_disabled=True,
            )

        self.assertEqual(events, ["full", "nat"])

    def test_init_panic_uses_isolation_when_forwarding_cannot_be_disabled(self):
        snapshot = self.daemon._build_reconciliation_snapshot(
            (ready_record(),)
        )
        events = []

        def restore_filter(policy, *, input_only=False):
            self.assertFalse(input_only)
            accepts = any(
                "-j ACCEPT" in rule
                for chain in policy.chains
                for rule in chain.rules
            )
            events.append("full" if accepts else "isolation")

        def restore_nat(policy):
            del policy
            events.append("nat")

        safe = vpng.FirewallCheck(vpng.FirewallSafety.SAFE, None)
        with (
            mock.patch.object(
                self.daemon,
                "_restore_filter_policy",
                side_effect=restore_filter,
            ),
            mock.patch.object(
                self.daemon,
                "_restore_nat_policy",
                side_effect=restore_nat,
            ),
            mock.patch.object(
                self.daemon,
                "_check_filter_policy",
                return_value=safe,
            ),
            mock.patch.object(
                self.daemon,
                "_check_nat_policy",
                return_value=safe,
            ),
            mock.patch.object(
                self.daemon,
                "_check_firewall_nat_policy",
                return_value=safe,
            ),
        ):
            self.daemon._rebuild_firewall_nat_init_panic(
                snapshot,
                forwarding_disabled=False,
            )

        self.assertEqual(events, ["isolation", "nat", "full"])



class NetlinkEventTests(unittest.TestCase):
    def test_open_netlink_socket_subscribes_required_groups(self):
        daemon = make_daemon()
        sock = mock.Mock()

        with mock.patch("vpn_gatewayd.daemon.socket.socket", return_value=sock) as ctor:
            result = daemon._open_netlink_socket()

        self.assertIs(result, sock)
        ctor.assert_called_once_with(
            socket.AF_NETLINK,
            socket.SOCK_RAW,
            socket.NETLINK_ROUTE,
        )
        sock.setblocking.assert_called_once_with(False)
        sock.bind.assert_called_once_with((0, 0x1 | 0x10 | 0x40))

    def test_netlink_enobufs_requests_full_reconcile(self):
        sock = mock.Mock()
        sock.recv.side_effect = OSError(errno.ENOBUFS, "buffer full")

        self.assertTrue(
            vpng.VpnGatewayDaemon._drain_netlink_socket(sock)
        )

    def test_netlink_burst_is_coalesced_into_one_trigger(self):
        sock = mock.Mock()
        sock.recv.side_effect = [b"event-1", b"event-2", BlockingIOError()]

        self.assertTrue(
            vpng.VpnGatewayDaemon._drain_netlink_socket(sock)
        )
        self.assertEqual(sock.recv.call_count, 3)

    def test_run_schedules_optional_systemd_watchdog(self):
        daemon = make_daemon()
        reader = mock.Mock()
        netlink = mock.Mock()
        daemon._signal_wakeup_reader = reader
        daemon._netlink_socket = netlink
        daemon.notifier = mock.Mock()
        daemon.notifier.watchdog_interval.return_value = 2.0

        monotonic = iter((100.0, 100.0, 102.0, 102.0))
        select_calls = 0

        def fake_select(readers, _w, _x, timeout):
            nonlocal select_calls
            select_calls += 1
            self.assertEqual(readers, [reader, netlink])
            self.assertEqual(timeout, 2.0)
            if select_calls == 2:
                daemon._shutdown_requested = True
            return ([], [], [])

        with (
            mock.patch(
                "vpn_gatewayd.daemon.time.monotonic",
                side_effect=lambda: next(monotonic),
            ),
            mock.patch(
                "vpn_gatewayd.daemon.select.select",
                side_effect=fake_select,
            ),
        ):
            daemon.run()

        daemon.notifier.watchdog.assert_called_once_with()


if __name__ == "__main__":
    unittest.main(verbosity=2)
