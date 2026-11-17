from __future__ import annotations

import json
import unittest
from ipaddress import IPv4Network

from rou.device_firewall_compiler import (
    DeviceFirewallCompileError,
    compile_device_firewall_policy,
)
from rou.device_firewall_structure import DeviceFirewallRuleAction
from rou.device_policy import (
    DeviceFirewallAction,
    DeviceFirewallDirection,
    DeviceFirewallPolicyIntent,
    DeviceFirewallRuleIntent,
)
from rou.interface_identity import InterfaceIdentity


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)


class DeviceFirewallCompilerTests(unittest.TestCase):
    def test_omitted_policy_produces_no_child_chains(self):
        value = compile_device_firewall_policy(
            DeviceFirewallPolicyIntent("wg-main", None),
            HOST,
            VPN,
            out_chain_name="dfw_out",
            in_chain_name="dfw_in",
        )
        self.assertEqual(value.chains, ())

    def test_explicit_policy_partitions_direction_and_preserves_order(self):
        out_first = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.OUT,
            action=DeviceFirewallAction.DENY,
            destination_ipv4_cidr=IPv4Network("10.0.0.0/8"),
        )
        in_middle = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.IN,
            action=DeviceFirewallAction.ALLOW,
            source_ipv4_cidr=IPv4Network("192.0.2.0/24"),
        )
        out_last = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.OUT,
            action=DeviceFirewallAction.ALLOW,
            destination_ipv4_cidr=IPv4Network("10.1.0.0/16"),
        )
        value = compile_device_firewall_policy(
            DeviceFirewallPolicyIntent(
                "wg-main",
                (out_first, in_middle, out_last),
            ),
            HOST,
            VPN,
            out_chain_name="dfw_out",
            in_chain_name="dfw_in",
        )
        self.assertEqual(len(value.chains), 2)
        out_chain, in_chain = value.chains
        self.assertEqual((out_chain.ingress, out_chain.egress), (HOST, VPN))
        self.assertEqual((in_chain.ingress, in_chain.egress), (VPN, HOST))
        self.assertEqual(
            [rule.action for rule in out_chain.rules],
            [
                DeviceFirewallRuleAction.DROP,
                DeviceFirewallRuleAction.RETURN,
                DeviceFirewallRuleAction.DROP,
            ],
        )
        self.assertEqual(
            [rule.action for rule in in_chain.rules],
            [
                DeviceFirewallRuleAction.RETURN,
                DeviceFirewallRuleAction.DROP,
            ],
        )
        self.assertTrue(out_chain.rules[-1].terminal_fallthrough)
        self.assertTrue(in_chain.rules[-1].terminal_fallthrough)

    def test_tcp_ports_compile_to_exp042_canonical_shape(self):
        rule = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.OUT,
            action=DeviceFirewallAction.ALLOW,
            protocol="tcp",
            source_ports=12345,
            destination_ports=443,
            source_ipv4_cidr=IPv4Network("192.0.2.0/24"),
            destination_ipv4_cidr=IPv4Network("198.51.100.10/32"),
        )
        value = compile_device_firewall_policy(
            DeviceFirewallPolicyIntent("wg-main", (rule,)),
            HOST,
            VPN,
            out_chain_name="dfw_out",
            in_chain_name="dfw_in",
        )
        compiled = value.chains[0].rules[0]
        expr = [json.loads(item) for item in compiled.match_expr_json]
        self.assertEqual(len(expr), 4)
        self.assertEqual(
            expr[0]["match"]["right"],
            {"prefix": {"addr": "192.0.2.0", "len": 24}},
        )
        self.assertEqual(
            expr[1]["match"]["right"],
            "198.51.100.10",
        )
        self.assertEqual(
            expr[2]["match"]["left"],
            {"payload": {"protocol": "tcp", "field": "sport"}},
        )
        self.assertEqual(
            expr[3]["match"]["left"],
            {"payload": {"protocol": "tcp", "field": "dport"}},
        )
        self.assertFalse(
            any(
                item["match"]["left"] == {"meta": {"key": "l4proto"}}
                for item in expr
            )
        )

    def test_protocol_only_uses_l4proto(self):
        for protocol in ("tcp", "udp", "icmp"):
            with self.subTest(protocol=protocol):
                rule = DeviceFirewallRuleIntent(
                    direction=DeviceFirewallDirection.IN,
                    action=DeviceFirewallAction.DENY,
                    protocol=protocol,
                )
                value = compile_device_firewall_policy(
                    DeviceFirewallPolicyIntent("wg-main", (rule,)),
                    HOST,
                    VPN,
                    out_chain_name="dfw_out",
                    in_chain_name="dfw_in",
                )
                compiled = value.chains[1].rules[0]
                self.assertEqual(
                    json.loads(compiled.match_expr_json[0]),
                    {
                        "match": {
                            "op": "==",
                            "left": {"meta": {"key": "l4proto"}},
                            "right": protocol,
                        }
                    },
                )

    def test_ports_without_proven_normalized_protocol_are_blocked(self):
        rule = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.OUT,
            action=DeviceFirewallAction.DENY,
            destination_ports=443,
        )
        with self.assertRaisesRegex(
            DeviceFirewallCompileError,
            "require normalized tcp or udp",
        ):
            compile_device_firewall_policy(
                DeviceFirewallPolicyIntent("wg-main", (rule,)),
                HOST,
                VPN,
                out_chain_name="dfw_out",
                in_chain_name="dfw_in",
            )

    def test_unknown_protocol_is_blocked_by_lower_gate(self):
        rule = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.OUT,
            action=DeviceFirewallAction.DENY,
            protocol="future-token",
        )
        with self.assertRaisesRegex(
            DeviceFirewallCompileError,
            "not proven",
        ):
            compile_device_firewall_policy(
                DeviceFirewallPolicyIntent("wg-main", (rule,)),
                HOST,
                VPN,
                out_chain_name="dfw_out",
                in_chain_name="dfw_in",
            )

    def test_tcp_reject_compiles_to_reset(self):
        rule = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.OUT,
            action=DeviceFirewallAction.REJECT,
            protocol="tcp",
            destination_ports=443,
        )
        value = compile_device_firewall_policy(
            DeviceFirewallPolicyIntent("wg-main", (rule,)),
            HOST,
            VPN,
            out_chain_name="dfw_out",
            in_chain_name="dfw_in",
        )
        compiled = value.chains[0].rules[0]
        self.assertEqual(compiled.action, DeviceFirewallRuleAction.REJECT)
        self.assertEqual(
            compiled.action_json,
            '{"reject":{"type":"tcp reset"}}',
        )

    def test_protocol_only_tcp_reject_omits_redundant_l4proto(self):
        rule = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.IN,
            action=DeviceFirewallAction.REJECT,
            protocol="tcp",
        )
        value = compile_device_firewall_policy(
            DeviceFirewallPolicyIntent("wg-main", (rule,)),
            HOST,
            VPN,
            out_chain_name="dfw_out",
            in_chain_name="dfw_in",
        )
        compiled = value.chains[1].rules[0]
        self.assertEqual(compiled.match_expr_json, ())
        self.assertEqual(
            compiled.action_json,
            '{"reject":{"type":"tcp reset"}}',
        )

    def test_non_tcp_and_generic_reject_compile_to_icmp_unreachable(self):
        cases = (
            DeviceFirewallRuleIntent(
                direction=DeviceFirewallDirection.OUT,
                action=DeviceFirewallAction.REJECT,
            ),
            DeviceFirewallRuleIntent(
                direction=DeviceFirewallDirection.OUT,
                action=DeviceFirewallAction.REJECT,
                protocol="udp",
            ),
            DeviceFirewallRuleIntent(
                direction=DeviceFirewallDirection.OUT,
                action=DeviceFirewallAction.REJECT,
                protocol="icmp",
            ),
        )
        for rule in cases:
            with self.subTest(protocol=rule.protocol):
                value = compile_device_firewall_policy(
                    DeviceFirewallPolicyIntent("wg-main", (rule,)),
                    HOST,
                    VPN,
                    out_chain_name="dfw_out",
                    in_chain_name="dfw_in",
                )
                compiled = value.chains[0].rules[0]
                self.assertEqual(
                    compiled.action,
                    DeviceFirewallRuleAction.REJECT,
                )
                self.assertEqual(
                    compiled.action_json,
                    '{"reject":{"expr":"port-unreachable","type":"icmp"}}',
                )


if __name__ == "__main__":
    unittest.main()
