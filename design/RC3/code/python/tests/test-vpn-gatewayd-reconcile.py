#!/usr/bin/env python3
from __future__ import annotations

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
        local_address=IPv4Address("172.20.130.1"),
        peers=(IPv4Address("172.20.130.6"),),
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
    def test_policy_transition_detects_ifindex_and_ambiguous_change(self):
        daemon = make_daemon()
        first = daemon._build_reconciliation_snapshot((ready_record(7),))
        state = first.interface_state_by_profile["primary"]
        daemon.profiles["primary"].commit_verified_state(
            routes=frozenset(),
            binding=state.binding,
            ready=state.ready,
            resolution_state=state.resolution.state,
            match_count=len(state.resolution.matches),
        )

        self.assertFalse(daemon._snapshot_changes_policy(first))
        self.assertTrue(
            daemon._snapshot_changes_policy(
                daemon._build_reconciliation_snapshot((ready_record(8),))
            )
        )
        self.assertTrue(
            daemon._snapshot_changes_policy(
                daemon._build_reconciliation_snapshot(
                    (
                        ready_record(7),
                        vpng.InterfaceRecord("vpns1", 8, frozenset()),
                    )
                )
            )
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

    def test_transit_drift_uses_barrier_repair(self):
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
                "_repair_firewall_nat_with_barrier",
            ) as repair,
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
        repair.assert_called_once()
        self.assertIs(self.daemon.state, vpng.DaemonState.ACTIVE)

    def test_policy_transition_uses_barrier_even_when_policy_is_safe(self):
        safe = vpng.FirewallCheck(vpng.FirewallSafety.SAFE, None)
        with (
            mock.patch.object(
                self.daemon,
                "_snapshot_changes_policy",
                return_value=True,
            ),
            mock.patch.object(
                self.daemon,
                "_check_firewall_nat_policy",
                return_value=safe,
            ),
            mock.patch.object(
                self.daemon,
                "_best_effort_disable_forwarding",
                return_value=None,
            ) as disable,
            mock.patch.object(
                self.daemon,
                "_repair_firewall_nat_with_barrier",
            ) as repair,
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
        repair.assert_called_once()

    def test_barrier_repair_orders_isolation_nat_full(self):
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
            self.daemon._repair_firewall_nat_with_barrier(snapshot)

        self.assertEqual(events, ["isolation", "nat", "full"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
