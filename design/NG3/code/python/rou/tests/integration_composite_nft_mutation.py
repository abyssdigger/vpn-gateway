from __future__ import annotations

"""Live combined structural nft convergence for Profile + Device + NAT."""

import os
import subprocess
from ipaddress import IPv4Network

from rou.binding import LogicalPathId
from rou.composite_nft_mutation import (
    CompositeNftMutationStatus,
    converge_composite_nft_step_once,
)
from rou.composite_nft_plan import CompositeNftStepKind
from rou.composite_nft_policy import CompositeNftDesiredState
from rou.device_firewall_compiler import compile_device_firewall_policy
from rou.device_firewall_desired import DeviceFirewallDesiredState
from rou.device_policy import (
    DeviceFirewallAction,
    DeviceFirewallDirection,
    DeviceFirewallPolicyIntent,
    DeviceFirewallRuleIntent,
)
from rou.forwarding_gate import ForwardingGateState
from rou.interface_inventory import parse_ip_link_inventory
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_composite_nft import LinuxCompositeNftBackend
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.payload_forward_desired import (
    PayloadForwardDesiredState,
    PayloadForwardRuleSpec,
)
from rou.payload_forward_observation import (
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
)
from rou.payload_nat_desired import (
    PayloadMasqueradeSpec,
    PayloadNatDesiredState,
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


def converge(gate, backend, desired, limit=16):
    history = []
    for _ in range(limit):
        result = converge_composite_nft_step_once(
            gate, backend, desired,
        )
        history.append(result)
        if result.confirmed:
            return history
        assert result.status is CompositeNftMutationStatus.STEP_APPLIED, result
    raise AssertionError(history)


def main():
    if os.geteuid() != 0:
        raise SystemExit("composite nft integration requires root")

    namespace = f"vpng-composite-{os.getpid()}"
    try:
        run("ip", "netns", "add", namespace)
        ns_run(
            namespace, "ip", "link", "add", "host0",
            "type", "veth", "peer", "name", "hostpeer",
        )
        ns_run(
            namespace, "ip", "link", "add", "tun0",
            "type", "veth", "peer", "name", "tunpeer",
        )
        host = identity(namespace, "host0")
        path = identity(namespace, "tun0")

        ns_run(
            namespace,
            "nft",
            "-f",
            "-",
            input_text=(
                'table ip vpn_gate {\n'
                '  comment "vpn-gate:ng3:owner-v1"\n'
                '  chain stack_input {\n'
                '    type filter hook input priority 0; policy drop;\n'
                '    comment "vpn-gate:ng3:stack-input-v1"\n'
                '  }\n'
                '  chain payload_forward {\n'
                '    type filter hook forward priority 0; policy drop;\n'
                '    comment "vpn-gate:ng3:payload-forward-v1"\n'
                '  }\n'
                '  chain stack_output {\n'
                '    type filter hook output priority 0; policy drop;\n'
                '    comment "vpn-gate:ng3:stack-output-v1"\n'
                '  }\n'
                '  chain payload_postrouting {\n'
                '    type nat hook postrouting priority 100; policy accept;\n'
                '    comment "vpn-gate:ng3:payload-postrouting-v1"\n'
                '  }\n'
                '}\n'
            ),
        )

        gate = LinuxForwardingGateBackend(
            runner=SubprocessCommandRunner(),
            namespace=namespace,
        )
        backend = LinuxCompositeNftBackend(
            runner=SubprocessNftRunner(),
            namespace=namespace,
        )

        prefix = IPv4Network("10.46.2.0/30")
        profile = PayloadForwardDesiredState(
            (
                PayloadForwardRuleSpec(
                    PayloadForwardRuleKind.NEW,
                    host,
                    path,
                    PayloadForwardRemoteField.DESTINATION,
                    prefix,
                ),
                PayloadForwardRuleSpec(
                    PayloadForwardRuleKind.RETURN,
                    path,
                    host,
                    PayloadForwardRemoteField.SOURCE,
                    prefix,
                ),
            )
        )
        nat = PayloadNatDesiredState(
            (
                PayloadMasqueradeSpec(
                    LogicalPathId("device", 0, 0),
                    host,
                    path,
                ),
            )
        )
        device = compile_device_firewall_policy(
            DeviceFirewallPolicyIntent(
                "device",
                (
                    DeviceFirewallRuleIntent(
                        direction=DeviceFirewallDirection.OUT,
                        action=DeviceFirewallAction.ALLOW,
                        destination_ipv4_cidr=prefix,
                    ),
                    DeviceFirewallRuleIntent(
                        direction=DeviceFirewallDirection.IN,
                        action=DeviceFirewallAction.ALLOW,
                        source_ipv4_cidr=prefix,
                    ),
                ),
            ),
            host,
            path,
            out_chain_name="dfw_out",
            in_chain_name="dfw_in",
        )
        desired = CompositeNftDesiredState(profile, nat, device)

        ns_run(namespace, "sysctl", "-w", "net.ipv4.ip_forward=1")
        created = converge(gate, backend, desired)
        created_steps = [
            item.step.kind
            for item in created
            if item.step is not None
        ]
        assert created_steps == [
            CompositeNftStepKind.ADD_NAT_RULE,
            CompositeNftStepKind.CREATE_DEVICE_CHAIN,
            CompositeNftStepKind.CREATE_DEVICE_CHAIN,
            CompositeNftStepKind.ADD_PROFILE_RULE,
            CompositeNftStepKind.ADD_PROFILE_RULE,
        ], created_steps
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        snapshot = backend.observe_composite_snapshot()
        forward_rules = [
            item.canonical_json
            for item in snapshot.observation.objects
            if item.kind == "rule"
            and '"chain":"payload_forward"' in item.canonical_json
        ]
        assert len(forward_rules) == 4, forward_rules
        assert "device-fw-jump-v1" in forward_rules[0], forward_rules
        assert "device-fw-jump-v1" in forward_rules[1], forward_rules
        assert "payload-forward-" in forward_rules[2], forward_rules
        assert "payload-forward-" in forward_rules[3], forward_rules

        empty = CompositeNftDesiredState(
            PayloadForwardDesiredState(()),
            PayloadNatDesiredState(()),
            DeviceFirewallDesiredState(()),
        )
        removed = converge(gate, backend, empty)
        removed_steps = [
            item.step.kind
            for item in removed
            if item.step is not None
        ]
        assert removed_steps == [
            CompositeNftStepKind.DELETE_PROFILE_RULE,
            CompositeNftStepKind.DELETE_PROFILE_RULE,
            CompositeNftStepKind.DELETE_DEVICE_JUMP,
            CompositeNftStepKind.DELETE_DEVICE_JUMP,
            CompositeNftStepKind.DELETE_DEVICE_CHAIN,
            CompositeNftStepKind.DELETE_DEVICE_CHAIN,
            CompositeNftStepKind.DELETE_NAT_RULE,
        ], removed_steps
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        exact = backend.observe_composite_snapshot()
        assert all(item.kind == "chain" for item in exact.observation.objects)

        ns_run(
            namespace,
            "nft",
            "-f",
            "-",
            input_text=(
                'add rule ip vpn_gate stack_input '
                'meta l4proto icmp accept '
                'comment "vpn-gate:ng3:unclassified-local-v1"\n'
            ),
        )
        conflict = converge_composite_nft_step_once(
            gate, backend, empty,
        )
        assert conflict.status is CompositeNftMutationStatus.CONFLICT, conflict
        assert not conflict.mutation_attempted
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        print("NG3 live combined Profile Device NAT nft convergence: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", namespace),
            text=True, check=False, capture_output=True,
        )


if __name__ == "__main__":
    main()
