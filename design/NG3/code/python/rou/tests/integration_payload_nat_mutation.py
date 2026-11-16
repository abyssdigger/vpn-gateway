from __future__ import annotations

"""Bounded live guarded payload NAT step; never re-enable ip_forward."""

import os
import subprocess

from rou.binding import LogicalPathId
from rou.forwarding_gate import ForwardingGateState
from rou.interface_inventory import parse_ip_link_inventory
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_payload_nat import LinuxPayloadNatBackend
from rou.payload_nat_desired import PayloadMasqueradeSpec, PayloadNatDesiredState
from rou.payload_nat_mutation import (
    PayloadNatMutationStatus, converge_payload_nat_step_once,
)


def run(*args, input_text=None):
    return subprocess.run(
        args, check=True, input=input_text, text=True, capture_output=True,
    ).stdout


def ns_run(namespace, *args, input_text=None):
    return run("ip", "netns", "exec", namespace, *args, input_text=input_text)


def identity(namespace, name):
    links = parse_ip_link_inventory(
        ns_run(namespace, "ip", "-j", "link", "show"),
    )
    found = [item for item in links if item.ifname == name]
    assert len(found) == 1, found
    return found[0]


def main():
    if os.geteuid() != 0:
        raise SystemExit("guarded NAT integration requires root")
    namespace = f"vpng-nat-step-{os.getpid()}"
    try:
        run("ip", "netns", "add", namespace)
        ns_run(namespace, "ip", "link", "add", "host0",
               "type", "veth", "peer", "name", "hostpeer")
        ns_run(namespace, "ip", "link", "add", "tun0",
               "type", "veth", "peer", "name", "tunpeer")
        host = identity(namespace, "host0")
        old = identity(namespace, "tun0")
        ns_run(
            namespace, "nft", "-f", "-",
            input_text=(
                'table ip vpn_gate {\n'
                '  comment "vpn-gate:ng3:owner-v1"\n'
                '  chain payload_forward {\n'
                '    type filter hook forward priority 0; policy drop;\n'
                '    comment "vpn-gate:ng3:payload-forward-v1"\n'
                '  }\n'
                '  chain payload_postrouting {\n'
                '    type nat hook postrouting priority 100; policy accept;\n'
                '    comment "vpn-gate:ng3:payload-postrouting-v1"\n'
                '  }\n'
                '}\n'
            ),
        )
        runner = SubprocessCommandRunner()
        gate = LinuxForwardingGateBackend(runner=runner, namespace=namespace)
        backend = LinuxPayloadNatBackend(
            runner=SubprocessNftRunner(), namespace=namespace,
        )
        path_id = LogicalPathId("device", 0, 0)

        ns_run(namespace, "sysctl", "-w", "net.ipv4.ip_forward=1")
        old_spec = PayloadMasqueradeSpec(path_id, host, old)
        first = converge_payload_nat_step_once(
            gate, backend, PayloadNatDesiredState((old_spec,)),
        )
        assert first.status is PayloadNatMutationStatus.CONFIRMED, first
        assert first.mutation_attempted and first.confirmed
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        ns_run(namespace, "ip", "link", "del", "tun0")
        ns_run(namespace, "ip", "link", "add", "tun0",
               "type", "veth", "peer", "name", "tunpeer")
        new = identity(namespace, "tun0")
        assert new.ifindex != old.ifindex
        new_spec = PayloadMasqueradeSpec(path_id, host, new)
        desired = PayloadNatDesiredState((new_spec,))

        stale_cleanup = converge_payload_nat_step_once(gate, backend, desired)
        assert stale_cleanup.status is PayloadNatMutationStatus.STEP_APPLIED, stale_cleanup
        assert stale_cleanup.mutation_attempted and not stale_cleanup.confirmed
        assert stale_cleanup.initial.stale[0].egress == old.ifindex
        assert not stale_cleanup.final.stale

        replacement = converge_payload_nat_step_once(gate, backend, desired)
        assert replacement.status is PayloadNatMutationStatus.CONFIRMED, replacement
        assert replacement.confirmed and not replacement.final.stale
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        before = backend.observe_nat_snapshot()
        ns_run(
            namespace, "nft", "-f", "-",
            input_text=(
                "add rule ip vpn_gate payload_forward "
                f"meta iif {host.ifindex} accept\n"
            ),
        )
        unknown = converge_payload_nat_step_once(
            gate, backend, PayloadNatDesiredState(()),
        )
        assert unknown.status is PayloadNatMutationStatus.CONFLICT, unknown
        assert not unknown.mutation_attempted
        after = backend.observe_nat_snapshot()
        before_rules = {
            o for o in before.observation.objects if o.kind == "rule"
        }
        after_rules = {
            o for o in after.observation.objects
            if o.kind == "rule" and "payload_postrouting" in o.canonical_json
        }
        assert before_rules == after_rules
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        print("NG3 live bounded guarded NAT-only mutation: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", namespace),
            text=True, check=False, capture_output=True,
        )


if __name__ == "__main__":
    main()
