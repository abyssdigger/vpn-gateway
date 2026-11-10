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


def config():
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


def state():
    record = vpng.InterfaceRecord(
        "vpns0",
        7,
        frozenset({IPv4Address("172.20.130.1")}),
    )
    resolved = vpng.resolve_profile_interface_state(
        vpng.InterfaceSelector.parse("vpns+"),
        (record,),
        IPv4Network("172.20.130.0/29"),
    )
    return MappingProxyType({"primary": resolved})


def daemon():
    d = vpng.VpnGatewayDaemon(
        config_path=Path("/dev/null"),
        kernel=mock.Mock(),
        config_loader=mock.Mock(),
    )
    d._install_config(config())
    return d


def serialize_policy(desired, *, foreign_input=(), foreign_forward=(), foreign_nat=()):
    lines = [
        "*filter",
        ":INPUT ACCEPT [0:0]",
        ":FORWARD ACCEPT [0:0]",
        ":OUTPUT ACCEPT [0:0]",
    ]
    for chain in sorted(c.name for c in desired.filter.chains):
        lines.append(f":{chain} - [0:0]")
    lines.extend(desired.filter.input_jumps)
    lines.extend(foreign_input)
    lines.extend(desired.filter.forward_jumps)
    lines.extend(foreign_forward)
    for chain in sorted(desired.filter.chains, key=lambda item: item.name):
        lines.extend(chain.rules)
    lines.append("COMMIT")
    lines.extend(
        (
            "*nat",
            ":PREROUTING ACCEPT [0:0]",
            ":INPUT ACCEPT [0:0]",
            ":OUTPUT ACCEPT [0:0]",
            ":POSTROUTING ACCEPT [0:0]",
        )
    )
    for chain in sorted(c.name for c in desired.nat.chains):
        lines.append(f":{chain} - [0:0]")
    lines.extend(desired.nat.postrouting_jumps)
    lines.extend(foreign_nat)
    for chain in sorted(desired.nat.chains, key=lambda item: item.name):
        lines.extend(chain.rules)
    lines.append("COMMIT")
    return "\n".join(lines) + "\n"


class FirewallPolicyOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.daemon = daemon()
        self.desired = vpng.desired_full_policy(config(), state())

    def test_compare_accepts_exact_policy_before_foreign_rules(self):
        snapshot = serialize_policy(
            self.desired,
            foreign_input=("-A INPUT -p tcp --dport 22 -j ACCEPT",),
            foreign_forward=("-A FORWARD -j ACCEPT",),
            foreign_nat=("-A POSTROUTING -o ens18 -j MASQUERADE",),
        )
        result = self.daemon._compare_firewall_nat_policy(
            snapshot,
            self.desired,
        )
        self.assertIs(result.safety, vpng.FirewallSafety.SAFE)

    def test_input_prefix_drift_is_input_only(self):
        snapshot = serialize_policy(self.desired)
        first = self.desired.filter.input_jumps[0]
        snapshot = snapshot.replace(
            first,
            "-A INPUT -p tcp --dport 22 -j FOREIGN\n" + first,
            1,
        )
        result = self.daemon._compare_firewall_nat_policy(
            snapshot,
            self.desired,
        )
        self.assertIs(result.safety, vpng.FirewallSafety.UNSAFE)
        self.assertIs(result.scope, vpng.FirewallDriftScope.INPUT_ONLY)

    def test_input_chain_drift_is_input_only(self):
        snapshot = serialize_policy(self.desired)
        expected = self.desired.filter.chain(
            "VPNG-PRIMARY-INPUT"
        ).rules[0]
        snapshot = snapshot.replace(expected, expected + " -m comment --comment drift")
        result = self.daemon._compare_firewall_nat_policy(
            snapshot,
            self.desired,
        )
        self.assertIs(result.scope, vpng.FirewallDriftScope.INPUT_ONLY)

    def test_forward_or_nat_drift_is_transit(self):
        cases = []
        forward_first = self.desired.filter.forward_jumps[0]
        cases.append(
            serialize_policy(self.desired).replace(
                forward_first,
                "-A FORWARD -j FOREIGN\n" + forward_first,
                1,
            )
        )
        nat_first = self.desired.nat.postrouting_jumps[0]
        cases.append(
            serialize_policy(self.desired).replace(
                nat_first,
                "-A POSTROUTING -j FOREIGN\n" + nat_first,
                1,
            )
        )

        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                result = self.daemon._compare_firewall_nat_policy(
                    snapshot,
                    self.desired,
                )
                self.assertIs(
                    result.scope,
                    vpng.FirewallDriftScope.TRANSIT,
                )

    def test_quoted_comment_does_not_fake_vpng_jump(self):
        snapshot = serialize_policy(
            self.desired,
            foreign_input=(
                '-A INPUT -m comment --comment "x -j VPNG-PRIMARY-INPUT" '
                '-j ACCEPT',
            ),
        )

        result = self.daemon._compare_firewall_nat_policy(
            snapshot,
            self.desired,
        )
        self.assertIs(result.safety, vpng.FirewallSafety.SAFE)

        cleanup = self.daemon._build_firewall_cleanup_payload(snapshot)
        self.assertNotIn(
            '-D INPUT -m comment --comment "x -j VPNG-PRIMARY-INPUT" '
            '-j ACCEPT',
            cleanup,
        )

    def test_real_goto_reference_to_vpng_chain_is_detected(self):
        snapshot = serialize_policy(
            self.desired,
            foreign_input=(
                "-A INPUT -p tcp --dport 2222 -g VPNG-PRIMARY-INPUT",
            ),
        )
        result = self.daemon._compare_firewall_nat_policy(
            snapshot,
            self.desired,
        )
        self.assertIs(result.safety, vpng.FirewallSafety.UNSAFE)
        self.assertIs(result.scope, vpng.FirewallDriftScope.INPUT_ONLY)

        cleanup = self.daemon._build_firewall_cleanup_payload(snapshot)
        self.assertIn(
            "-D INPUT -p tcp --dport 2222 -g VPNG-PRIMARY-INPUT",
            cleanup,
        )

    def test_malformed_quoted_rule_makes_inspection_unknown(self):
        self.daemon.kernel.iptables_save.return_value = (
            serialize_policy(self.desired).replace(
                self.desired.filter.input_jumps[0],
                '-A INPUT -m comment --comment "unterminated '
                '-j ACCEPT\n' + self.desired.filter.input_jumps[0],
                1,
            )
        )

        result = self.daemon._check_firewall_nat_policy(self.desired)
        self.assertIs(result.safety, vpng.FirewallSafety.UNKNOWN)
        self.assertIsNone(result.scope)

    def test_input_only_payload_contains_no_forward_or_nat_operations(self):
        snapshot = serialize_policy(self.desired)
        snapshot = snapshot.replace(
            self.desired.filter.input_jumps[0],
            "-A INPUT -p tcp --dport 22 -j FOREIGN\n"
            + self.desired.filter.input_jumps[0],
            1,
        )

        payload = self.daemon._build_filter_restore_payload(
            self.desired.filter,
            snapshot,
            input_only=True,
        )

        self.assertIn(":VPNG-PRIMARY-INPUT - [0:0]", payload)
        self.assertIn(":VPNG-INPUT-GUARD - [0:0]", payload)
        self.assertIn("-I INPUT 1 -j VPNG-PRIMARY-INPUT", payload)
        self.assertNotIn("FORWARD", payload)
        self.assertNotIn("VPNG-INGRESS", payload)
        self.assertNotIn("VPNG-PRIMARY-FORWARD", payload)
        self.assertNotIn("*nat", payload)

    def test_full_filter_payload_restores_terminal_forward_prefix(self):
        snapshot = serialize_policy(self.desired)
        payload = self.daemon._build_filter_restore_payload(
            self.desired.filter,
            snapshot,
        )

        self.assertIn("-I FORWARD 1 -j VPNG-INGRESS", payload)
        self.assertIn("-I FORWARD 2 -j VPNG-RESERVED", payload)
        self.assertIn("-I FORWARD 3 -j VPNG-PRIMARY-FORWARD", payload)
        self.assertIn("-I FORWARD 4 -j VPNG-FORWARD-DENY", payload)
        self.assertIn(":VPNG-FORWARD-DENY - [0:0]", payload)

    def test_nat_payload_uses_exact_runtime_binding(self):
        snapshot = serialize_policy(self.desired)
        payload = self.daemon._build_nat_restore_payload(
            self.desired.nat,
            snapshot,
        )

        self.assertIn("-I POSTROUTING 1 -j VPNG-PRIMARY-NAT", payload)
        self.assertIn(
            "-A VPNG-PRIMARY-NAT -o vpns0 "
            "-m addrtype ! --src-type LOCAL -j MASQUERADE",
            payload,
        )
        self.assertNotIn("vpns+", payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
