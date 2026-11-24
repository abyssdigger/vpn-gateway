from __future__ import annotations

import unittest
from ipaddress import IPv4Address

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.linux_probe_local import LinuxProbeLocalBackend
from rou.network_policy_layout import ProbePolicyOwner
from rou.probe_local_mutation import (
    ProbeLocalDeleteRef,
    ProbeLocalMutationStep,
    select_probe_local_step,
)
from rou.probe_local_observation import (
    ObservedProbeLocalRule,
    ProbeLocalComparison,
)
from rou.probe_policy import ProbeLocalHook, ProbeLocalRuleSpec


PATH = LogicalPathId("device", 0, 0)
OWNER = ProbePolicyOwner("corp", PATH)
EP = InterfaceIdentity("path0", 2)
TARGET = IPv4Address("198.51.100.7")
MARK = 0x20000001


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


def output_spec():
    return ProbeLocalRuleSpec(
        owner=OWNER,
        hook=ProbeLocalHook.OUTPUT,
        endpoint=EP,
        target=TARGET,
        conntrack_mark=MARK,
        process_uid=4242,
    )


def input_spec():
    return ProbeLocalRuleSpec(
        owner=OWNER,
        hook=ProbeLocalHook.INPUT,
        endpoint=EP,
        target=TARGET,
        conntrack_mark=MARK,
    )


class ProbeLocalMutationTests(unittest.TestCase):
    def test_full_diff_deletes_stale_and_adds_missing_atomically(self):
        stale = ObservedProbeLocalRule(
            handle=9,
            hook=ProbeLocalHook.INPUT,
            endpoint=EP,
            target=IPv4Address("203.0.113.9"),
            conntrack_mark=MARK,
        )
        comparison = ProbeLocalComparison(
            confirmed=(),
            missing=(output_spec(), input_spec()),
            stale=(stale,),
            conflicts=(),
        )
        step = select_probe_local_step(comparison)
        self.assertEqual(step.delete_rules, (ProbeLocalDeleteRef(ProbeLocalHook.INPUT, 9),))
        self.assertEqual(set(step.add_rules), {output_spec(), input_spec()})

        runner = FakeRunner()
        backend = LinuxProbeLocalBackend(runner, "managed")
        backend.apply_probe_local_step(step)
        self.assertEqual(runner.commands[-1], ("ip", "netns", "exec", "managed", "nft", "-f", "-"))
        script = runner.scripts[-1]
        self.assertIn("delete rule ip vpn_gate stack_input handle 9", script)
        self.assertIn(
            "add rule ip vpn_gate stack_output meta skuid 4242 meta oif 2 "
            "ip daddr 198.51.100.7 ip protocol icmp "
            "ct mark set 0x20000001 accept "
            'comment "vpn-gate:ng3:probe-local-v1"',
            script,
        )
        self.assertIn(
            "add rule ip vpn_gate stack_input meta iif 2 "
            "ip saddr 198.51.100.7 ip protocol icmp "
            "ct mark 0x20000001 accept "
            'comment "vpn-gate:ng3:probe-local-v1"',
            script,
        )

    def test_exact_comparison_has_no_step(self):
        self.assertIsNone(
            select_probe_local_step(
                ProbeLocalComparison(
                    confirmed=(output_spec(), input_spec()),
                    missing=(),
                    stale=(),
                    conflicts=(),
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
