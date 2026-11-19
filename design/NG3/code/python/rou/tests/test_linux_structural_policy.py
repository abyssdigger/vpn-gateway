from __future__ import annotations

import json
import unittest
from ipaddress import IPv4Address

from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.linux_structural_policy import LinuxStructuralPolicyBackend
from rou.probe_local_mutation import ProbeLocalMutationStep
from rou.probe_policy import ProbeLocalHook, ProbeLocalRuleSpec
from rou.network_policy_layout import ProbePolicyOwner
from rou.binding import LogicalPathId
from rou.nft_namespace_inventory import NftNamespaceStatus


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)


def links(*values):
    return json.dumps([
        {"ifname": value.ifname, "ifindex": value.ifindex}
        for value in values
    ])


def scaffold():
    return json.dumps({"nftables": [
        {"table": {
            "family": "ip",
            "name": "vpn_gate",
            "comment": "vpn-gate:ng3:owner-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "stack_input",
            "type": "filter", "hook": "input", "prio": 0,
            "policy": "drop", "comment": "vpn-gate:ng3:stack-input-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "payload_forward",
            "type": "filter", "hook": "forward", "prio": 0,
            "policy": "drop", "comment": "vpn-gate:ng3:payload-forward-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "stack_output",
            "type": "filter", "hook": "output", "prio": 0,
            "policy": "drop", "comment": "vpn-gate:ng3:stack-output-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "payload_postrouting",
            "type": "nat", "hook": "postrouting", "prio": 100,
            "policy": "accept",
            "comment": "vpn-gate:ng3:payload-postrouting-v1",
        }},
    ]})


class FakeRunner:
    def __init__(self, *, link_payloads=None):
        self.link_payloads = list(link_payloads or [links(HOST, VPN), links(HOST, VPN)])
        self.commands = []
        self.scripts = []

    def run(self, argv):
        command = tuple(argv)
        self.commands.append(command)
        if command[-2:] == ("link", "show"):
            return self.link_payloads.pop(0)
        if "route" in command and "show" in command:
            return "[]"
        if "rule" in command and "show" in command:
            return "[]"
        if "nft" in command and "list" in command:
            return scaffold()
        return ""

    def run_script(self, argv, script):
        self.commands.append(tuple(argv))
        self.scripts.append(script)
        return ""


class LinuxStructuralPolicyBackendTests(unittest.TestCase):
    def backend(self, runner):
        return LinuxStructuralPolicyBackend(
            runner=runner,
            namespace="managed",
            platform=NG3_LINUX_POLICY_PLATFORM,
        )

    def test_observation_is_one_link_bracket_over_route_rule_and_nft(self):
        runner = FakeRunner()
        snapshot = self.backend(runner).observe_structural_snapshot()

        self.assertEqual(snapshot.interfaces, (HOST, VPN))
        self.assertEqual(snapshot.routing.routes, ())
        self.assertEqual(snapshot.routing.rules, ())
        self.assertEqual(snapshot.routing.conflicts, ())
        self.assertEqual(snapshot.nft.status, NftNamespaceStatus.OWNED)
        self.assertEqual(
            runner.commands,
            [
                ("ip", "-n", "managed", "-j", "link", "show"),
                (
                    "ip", "-n", "managed", "-j", "-N", "-4",
                    "route", "show", "table", "all",
                ),
                (
                    "ip", "-n", "managed", "-j", "-N", "-4",
                    "rule", "show",
                ),
                (
                    "ip", "netns", "exec", "managed",
                    "nft", "-j", "list", "ruleset",
                ),
                ("ip", "-n", "managed", "-j", "link", "show"),
            ],
        )

    def test_link_identity_drift_rejects_whole_snapshot(self):
        changed = InterfaceIdentity("vpn0", 21)
        runner = FakeRunner(
            link_payloads=[links(HOST, VPN), links(HOST, changed)]
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "identity inventory drift",
        ):
            self.backend(runner).observe_structural_snapshot()

    def test_probe_local_mutation_delegates_to_composite_nft_backend(self):
        runner = FakeRunner()
        backend = self.backend(runner)
        owner = ProbePolicyOwner(
            "corp",
            LogicalPathId("device", 0, 0),
        )
        backend.apply_probe_local_step(
            ProbeLocalMutationStep(
                delete_rules=(),
                add_rules=(
                    ProbeLocalRuleSpec(
                        owner=owner,
                        hook=ProbeLocalHook.INPUT,
                        endpoint=VPN,
                        target=IPv4Address("198.51.100.7"),
                        conntrack_mark=0x20000001,
                    ),
                ),
            )
        )
        self.assertEqual(
            runner.scripts[-1],
            "add rule ip vpn_gate stack_input "
            "meta iif 20 ip saddr 198.51.100.7 "
            "ip protocol icmp ct mark 0x20000001 accept "
            'comment "vpn-gate:ng3:probe-local-v1"\n',
        )

    def test_route_and_rule_mutation_delegate_to_exp048_driver(self):
        from ipaddress import IPv4Network
        from rou.payload_routing_desired import (
            ManagedRouteSpec,
            ManagedRouteType,
            ManagedRuleSpec,
        )

        runner = FakeRunner()
        backend = self.backend(runner)
        backend.add_route(
            ManagedRouteSpec(
                table=0x80000000,
                destination=IPv4Network("0.0.0.0/0"),
                route_type=ManagedRouteType.BLACKHOLE,
                protocol=201,
                metric=0xFFFFFFFF,
            )
        )
        backend.add_rule(
            ManagedRuleSpec(
                priority=0x4000,
                ingress=HOST,
                destination=IPv4Network("10.0.0.0/8"),
                table=0x80000000,
            )
        )
        self.assertIn(
            (
                "ip", "-n", "managed", "-4", "route", "add",
                "blackhole", "default",
                "table", str(0x80000000),
                "proto", "201", "metric", str(0xFFFFFFFF),
            ),
            runner.commands,
        )
        self.assertIn(
            (
                "ip", "-n", "managed", "-4", "rule", "add",
                "priority", str(0x4000),
                "iif", "host0",
                "to", "10.0.0.0/8",
                "lookup", str(0x80000000),
            ),
            runner.commands,
        )


if __name__ == "__main__":
    unittest.main()
