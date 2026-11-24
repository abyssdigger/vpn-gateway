from __future__ import annotations

"""Live combined structural nft convergence for Profile + Device + NAT + local publication."""

import os
import subprocess
from ipaddress import IPv4Address, IPv4Network

from rou.binding import LogicalPathId
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
from rou.linux_structural_policy import LinuxStructuralPolicyBackend
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.local_publication_policy import (
    PublicationLocalEndpointIntent,
    PublicationProtocol,
    build_local_publication_desired,
)
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
from rou.payload_routing_desired import PayloadRoutingDesiredState
from rou.structural_policy_mutation import (
    StructuralPolicyMutationStatus,
    converge_structural_policy_step_once,
)
from rou.structural_policy_plan import StructuralPolicyStepKind
from rou.structural_policy_transaction import (
    StructuralPolicyTransactionStatus,
    converge_structural_policy,
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


def converge(gate, backend, routing, desired):
    result = converge_structural_policy(
        gate,
        backend,
        routing,
        desired,
        NG3_LINUX_POLICY_PLATFORM,
    )
    assert result.status is StructuralPolicyTransactionStatus.CONFIRMED, result
    assert result.confirmed
    return result.attempts


def nft_steps(attempts):
    return [
        item.step.nft_step.kind
        for item in attempts
        if (
            item.step is not None
            and item.step.kind is StructuralPolicyStepKind.APPLY_NFT_STEP
            and item.step.nft_step is not None
        )
    ]


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
        publication_ip = IPv4Address("198.51.100.48")
        ns_run(
            namespace,
            "ip",
            "addr",
            "add",
            f"{publication_ip}/32",
            "dev",
            "lo",
        )

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
        backend = LinuxStructuralPolicyBackend(
            runner=SubprocessNftRunner(),
            namespace=namespace,
            platform=NG3_LINUX_POLICY_PLATFORM,
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
        local_publication = build_local_publication_desired(
            (
                PublicationLocalEndpointIntent(
                    "device",
                    PublicationProtocol.TCP,
                    publication_ip,
                    44443,
                    host,
                ),
            )
        )
        desired = CompositeNftDesiredState(
            profile,
            nat,
            device,
            local_publication,
        )
        routing = PayloadRoutingDesiredState(host, (), ())

        ns_run(namespace, "sysctl", "-w", "net.ipv4.ip_forward=1")
        created = converge(gate, backend, routing, desired)
        created_steps = nft_steps(created)
        assert created_steps == [
            CompositeNftStepKind.ADD_NAT_RULE,
            CompositeNftStepKind.CREATE_DEVICE_CHAIN,
            CompositeNftStepKind.CREATE_DEVICE_CHAIN,
            CompositeNftStepKind.ADD_PROFILE_RULE,
            CompositeNftStepKind.ADD_PROFILE_RULE,
            CompositeNftStepKind.APPLY_LOCAL_PUBLICATION,
        ], created_steps
        assert gate.observe_forwarding_gate() is ForwardingGateState.ENABLED

        replacement_local = build_local_publication_desired(
            (
                PublicationLocalEndpointIntent(
                    "device",
                    PublicationProtocol.TCP,
                    publication_ip,
                    44444,
                    host,
                ),
            )
        )
        replacement_desired = CompositeNftDesiredState(
            profile,
            nat,
            device,
            replacement_local,
        )
        replacement = converge(gate, backend, routing, replacement_desired)
        replacement_steps = nft_steps(replacement)
        assert replacement_steps == [
            CompositeNftStepKind.APPLY_LOCAL_PUBLICATION,
        ], replacement_steps
        local_after_replace = backend.observe_structural_snapshot().nft
        local_json = "\n".join(
            item.canonical_json
            for item in local_after_replace.objects
            if item.kind == "rule"
            and "local-publication-v1" in item.canonical_json
        )
        assert "44444" in local_json
        assert "44443" not in local_json
        assert gate.observe_forwarding_gate() is ForwardingGateState.ENABLED

        snapshot = backend.observe_structural_snapshot().nft
        forward_rules = [
            item.canonical_json
            for item in snapshot.objects
            if item.kind == "rule"
            and '"chain":"payload_forward"' in item.canonical_json
        ]
        assert len(forward_rules) == 4, forward_rules
        assert "device-fw-jump-v1" in forward_rules[0], forward_rules
        assert "device-fw-jump-v1" in forward_rules[1], forward_rules
        assert "payload-forward-" in forward_rules[2], forward_rules
        assert "payload-forward-" in forward_rules[3], forward_rules
        local_input = [
            item.canonical_json
            for item in snapshot.objects
            if item.kind == "rule"
            and '"chain":"stack_input"' in item.canonical_json
        ]
        local_output = [
            item.canonical_json
            for item in snapshot.objects
            if item.kind == "rule"
            and '"chain":"stack_output"' in item.canonical_json
        ]
        assert len(local_input) == 1 and "local-publication-v1" in local_input[0]
        assert len(local_output) == 1 and "local-publication-v1" in local_output[0]

        empty = CompositeNftDesiredState(
            PayloadForwardDesiredState(()),
            PayloadNatDesiredState(()),
            DeviceFirewallDesiredState(()),
        )
        removed = converge(gate, backend, routing, empty)
        removed_steps = nft_steps(removed)
        assert removed_steps == [
            CompositeNftStepKind.APPLY_LOCAL_PUBLICATION,
            CompositeNftStepKind.DELETE_PROFILE_RULE,
            CompositeNftStepKind.DELETE_PROFILE_RULE,
            CompositeNftStepKind.DELETE_DEVICE_JUMP,
            CompositeNftStepKind.DELETE_DEVICE_JUMP,
            CompositeNftStepKind.DELETE_DEVICE_CHAIN,
            CompositeNftStepKind.DELETE_DEVICE_CHAIN,
            CompositeNftStepKind.DELETE_NAT_RULE,
        ], removed_steps
        assert gate.observe_forwarding_gate() is ForwardingGateState.ENABLED

        exact = backend.observe_structural_snapshot().nft
        assert all(item.kind == "chain" for item in exact.objects)

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
        conflict = converge_structural_policy_step_once(
            gate,
            backend,
            routing,
            empty,
            NG3_LINUX_POLICY_PLATFORM,
        )
        assert conflict.status is StructuralPolicyMutationStatus.CONFLICT, conflict
        assert not conflict.mutation_attempted
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        print("NG3 live combined Profile Device NAT local-publication nft convergence: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", namespace),
            text=True, check=False, capture_output=True,
        )


if __name__ == "__main__":
    main()
