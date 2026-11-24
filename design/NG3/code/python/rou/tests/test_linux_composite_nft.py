from __future__ import annotations

import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.interface_identity import InterfaceIdentity
from rou.linux_composite_nft import LinuxCompositeNftBackend
from rou.payload_forward_desired import PayloadForwardRuleSpec
from rou.payload_forward_observation import (
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
)
from rou.binding import LogicalPathId
from rou.network_policy_layout import ProbePolicyOwner
from rou.probe_local_mutation import ProbeLocalMutationStep
from rou.probe_policy import ProbeLocalHook, ProbeLocalRuleSpec


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


class LinuxCompositeNftBackendTests(unittest.TestCase):
    def test_add_new_profile_rule_uses_exact_exp045_shape(self):
        runner = FakeRunner()
        backend = LinuxCompositeNftBackend(runner, "managed")
        backend.add_profile_rule(
            PayloadForwardRuleSpec(
                kind=PayloadForwardRuleKind.NEW,
                ingress=HOST,
                egress=VPN,
                remote_field=PayloadForwardRemoteField.DESTINATION,
                remote_prefix=IPv4Network("10.0.0.0/8"),
            )
        )
        self.assertEqual(
            runner.scripts[-1],
            "add rule ip vpn_gate payload_forward "
            "ct state new meta iif 10 meta oif 20 "
            "ip daddr 10.0.0.0/8 accept "
            'comment "vpn-gate:ng3:payload-forward-new-v1"\n',
        )

    def test_add_return_profile_rule_uses_stateful_source_shape(self):
        runner = FakeRunner()
        backend = LinuxCompositeNftBackend(runner, "managed")
        backend.add_profile_rule(
            PayloadForwardRuleSpec(
                kind=PayloadForwardRuleKind.RETURN,
                ingress=VPN,
                egress=HOST,
                remote_field=PayloadForwardRemoteField.SOURCE,
                remote_prefix=IPv4Network("10.0.0.7/32"),
            )
        )
        self.assertEqual(
            runner.scripts[-1],
            "add rule ip vpn_gate payload_forward "
            "ct state established,related meta iif 20 meta oif 10 "
            "ip saddr 10.0.0.7/32 accept "
            'comment "vpn-gate:ng3:payload-forward-return-v1"\n',
        )

    def test_probe_local_step_delegates_to_shared_composite_runner(self):
        runner = FakeRunner()
        backend = LinuxCompositeNftBackend(runner, "managed")
        owner = ProbePolicyOwner("corp", LogicalPathId("device", 0, 0))
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

    def test_delete_profile_rule_uses_exact_handle(self):
        runner = FakeRunner()
        backend = LinuxCompositeNftBackend(runner, "managed")
        backend.delete_profile_rule(77)
        self.assertEqual(
            runner.commands[-1],
            (
                "ip", "netns", "exec", "managed",
                "nft", "delete", "rule", "ip", "vpn_gate",
                "payload_forward", "handle", "77",
            ),
        )


if __name__ == "__main__":
    unittest.main()
