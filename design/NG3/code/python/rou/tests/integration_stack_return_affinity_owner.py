#!/usr/bin/env python3
"""Privileged production-backend evidence for the stack return-affinity owner."""

from __future__ import annotations

from ipaddress import IPv4Network
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rou.forwarding_gate import ForwardingGateState, converge_forwarding_gate_once
from rou.interface_identity import InterfaceIdentity
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_policy_platform import NG3_STACK_RETURN_AFFINITY_PLATFORM
from rou.linux_stack_return_affinity import LinuxStackReturnAffinityBackend
from rou.stack_return_affinity import (
    StackReturnAffinityDesired,
    StackReturnClassifierSpec,
    StackReturnRuleSpec,
)
from rou.stack_return_affinity_convergence import (
    StackReturnAffinityOwnerStatus,
    converge_stack_return_affinity_once,
)


NS = f"vng-aff-owner-{os.getpid()}"
HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)
RULE = StackReturnRuleSpec("p", 0x10000000, 0x80000000, 0x1800)
DESIRED = StackReturnAffinityDesired(
    HOST,
    (
        StackReturnClassifierSpec(
            "p",
            VPN,
            IPv4Network("10.0.0.0/16"),
            RULE.mark,
        ),
    ),
    (RULE,),
)


def raw(*argv: str) -> str:
    return subprocess.run(
        argv,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def main() -> int:
    runner = SubprocessNftRunner()
    try:
        raw("ip", "netns", "add", NS)
        raw("ip", "-n", NS, "link", "add", "host0", "type", "dummy")
        raw("ip", "-n", NS, "link", "add", "vpn0", "type", "dummy")
        # The semantic desired state uses stable observed ifindices.
        inventory = runner.run(("ip", "-n", NS, "-j", "link", "show"))
        import json
        rows = json.loads(inventory)
        by_name = {item["ifname"]: item["ifindex"] for item in rows}
        desired = StackReturnAffinityDesired(
            InterfaceIdentity("host0", by_name["host0"]),
            (
                StackReturnClassifierSpec(
                    "p",
                    InterfaceIdentity("vpn0", by_name["vpn0"]),
                    IPv4Network("10.0.0.0/16"),
                    RULE.mark,
                ),
            ),
            (RULE,),
        )

        gate = LinuxForwardingGateBackend(runner, NS)
        contained = converge_forwarding_gate_once(gate, ForwardingGateState.DISABLED)
        assert contained.confirmed

        backend = LinuxStackReturnAffinityBackend(
            runner,
            NS,
            NG3_STACK_RETURN_AFFINITY_PLATFORM,
        )
        initial = backend.observe(desired)
        assert initial.status is StackReturnAffinityOwnerStatus.ABSENT

        applied = converge_stack_return_affinity_once(gate, backend, desired)
        if not applied.confirmed:
            print(f"STACK_AFFINITY_OWNER_APPLY_DIAGNOSTIC={applied!r}", flush=True)
            print(
                "STACK_AFFINITY_OWNER_NFT_JSON="
                + runner.run(("ip", "netns", "exec", NS, "nft", "-j", "list", "ruleset")),
                flush=True,
            )
            print(
                "STACK_AFFINITY_OWNER_RULE_JSON="
                + runner.run(("ip", "netns", "exec", NS, "ip", "-j", "-4", "rule", "show")),
                flush=True,
            )
        assert applied.confirmed
        assert backend.observe(desired).status is StackReturnAffinityOwnerStatus.EXACT
        print("STACK_AFFINITY_OWNER_APPLY=PASS")

        backend.delete_rule(RULE)
        assert backend.observe(desired).status is StackReturnAffinityOwnerStatus.STALE
        repaired = converge_stack_return_affinity_once(gate, backend, desired)
        assert repaired.confirmed
        assert backend.observe(desired).status is StackReturnAffinityOwnerStatus.EXACT
        print("STACK_AFFINITY_OWNER_STALE_REPAIR=PASS")

        backend.cleanup_owned()
        runner.run_script(
            ("ip", "netns", "exec", NS, "nft", "-f", "-"),
            "table ip vpn_gate_return_affinity {\n  comment \"foreign\"\n}\n",
        )
        conflict = backend.observe(desired)
        assert conflict.status is StackReturnAffinityOwnerStatus.CONFLICT
        result = converge_stack_return_affinity_once(gate, backend, desired)
        assert not result.confirmed
        assert result.status.value == "conflict"
        print("STACK_AFFINITY_OWNER_CONFLICT=PASS")
        print("STACK_AFFINITY_OWNER_RESULT=PASS")
        return 0
    finally:
        subprocess.run(("ip", "netns", "del", NS), check=False)


if __name__ == "__main__":
    raise SystemExit(main())
