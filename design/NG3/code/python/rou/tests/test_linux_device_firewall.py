from __future__ import annotations

import json
import unittest

from rou.device_firewall_desired import (
    DeviceFirewallChainSpec,
    DeviceFirewallRuleSpec,
)
from rou.device_firewall_structure import DeviceFirewallRuleAction
from rou.interface_identity import InterfaceIdentity
from rou.linux_device_firewall import LinuxDeviceFirewallBackend


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)


class FakeRunner:
    def __init__(self):
        self.commands = []
        self.scripts = []

    def run(self, argv):
        self.commands.append(tuple(argv))
        return ""

    def run_script(self, argv, script):
        self.commands.append(tuple(argv))
        self.scripts.append(script)
        return ""


def match(left: dict, right: object) -> str:
    return json.dumps(
        {"match": {"op": "==", "left": left, "right": right}},
        sort_keys=True,
        separators=(",", ":"),
    )


class LinuxDeviceFirewallBackendTests(unittest.TestCase):
    def test_create_renders_ordered_rules_then_insert_jump(self):
        runner = FakeRunner()
        backend = LinuxDeviceFirewallBackend(runner, "managed")
        spec = DeviceFirewallChainSpec(
            ingress=HOST,
            egress=VPN,
            child_chain_name="dfw_out",
            rules=(
                DeviceFirewallRuleSpec(
                    match_expr_json=(
                        match(
                            {"payload": {"protocol": "ip", "field": "daddr"}},
                            {"prefix": {"addr": "10.0.0.0", "len": 8}},
                        ),
                        match(
                            {"payload": {"protocol": "tcp", "field": "dport"}},
                            443,
                        ),
                    ),
                    action=DeviceFirewallRuleAction.RETURN,
                    action_json='{"return":null}',
                ),
                DeviceFirewallRuleSpec(
                    match_expr_json=(
                        match({"meta": {"key": "l4proto"}}, "tcp"),
                    ),
                    action=DeviceFirewallRuleAction.REJECT,
                    action_json='{"reject":{"type":"tcp reset"}}',
                ),
                DeviceFirewallRuleSpec(
                    match_expr_json=(),
                    action=DeviceFirewallRuleAction.DROP,
                    action_json='{"drop":null}',
                    terminal_fallthrough=True,
                ),
            ),
        )

        backend.create_device_chain(spec)
        self.assertEqual(len(runner.scripts), 1)
        script = runner.scripts[0]
        self.assertIn(
            'add chain ip vpn_gate dfw_out { comment "vpn-gate:ng3:device-fw-child-v1"; }',
            script,
        )
        self.assertIn(
            'ip daddr 10.0.0.0/8 tcp dport 443 return comment "vpn-gate:ng3:device-fw-rule-v1"',
            script,
        )
        self.assertIn(
            'meta l4proto tcp reject with tcp reset comment "vpn-gate:ng3:device-fw-rule-v1"',
            script,
        )
        self.assertIn(
            'drop comment "vpn-gate:ng3:device-fw-fallthrough-v1"',
            script,
        )
        self.assertTrue(
            script.rstrip().endswith(
                'insert rule ip vpn_gate payload_forward meta iif 10 meta oif 20 '
                'jump dfw_out comment "vpn-gate:ng3:device-fw-jump-v1"'
            )
        )

    def test_generic_reject_renders_bare_reject(self):
        runner = FakeRunner()
        backend = LinuxDeviceFirewallBackend(runner, "managed")
        spec = DeviceFirewallChainSpec(
            ingress=HOST,
            egress=VPN,
            child_chain_name="dfw_out",
            rules=(
                DeviceFirewallRuleSpec(
                    match_expr_json=(),
                    action=DeviceFirewallRuleAction.REJECT,
                    action_json='{"reject":{"expr":"port-unreachable","type":"icmp"}}',
                ),
            ),
        )
        backend.create_device_chain(spec)
        self.assertIn(
            'reject comment "vpn-gate:ng3:device-fw-rule-v1"',
            runner.scripts[0],
        )

    def test_delete_jump_uses_exact_handle(self):
        runner = FakeRunner()
        backend = LinuxDeviceFirewallBackend(runner, "managed")
        backend.delete_device_jump(77)
        self.assertEqual(
            runner.commands[-1],
            (
                "ip", "netns", "exec", "managed",
                "nft", "delete", "rule", "ip", "vpn_gate",
                "payload_forward", "handle", "77",
            ),
        )

    def test_delete_chain_flushes_before_delete_in_one_script(self):
        runner = FakeRunner()
        backend = LinuxDeviceFirewallBackend(runner, "managed")
        backend.delete_device_child_chain("dfw_out")
        self.assertEqual(
            runner.scripts[-1],
            "flush chain ip vpn_gate dfw_out\n"
            "delete chain ip vpn_gate dfw_out\n",
        )

    def test_unsafe_child_identifier_is_rejected(self):
        runner = FakeRunner()
        backend = LinuxDeviceFirewallBackend(runner, "managed")
        spec = DeviceFirewallChainSpec(
            ingress=HOST,
            egress=VPN,
            child_chain_name="bad-name",
            rules=(),
        )
        with self.assertRaisesRegex(ValueError, "unsafe"):
            backend.create_device_chain(spec)


if __name__ == "__main__":
    unittest.main()
