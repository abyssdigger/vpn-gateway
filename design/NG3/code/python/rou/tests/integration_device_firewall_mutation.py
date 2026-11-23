from __future__ import annotations

"""Live bounded guarded Device-firewall convergence; never re-enable ip_forward."""

import os
import subprocess

from rou.device_firewall_compiler import compile_device_firewall_policy
from rou.device_firewall_mutation import (
    DeviceFirewallMutationStatus,
    converge_device_firewall_step_once,
)
from rou.device_policy import (
    DeviceFirewallAction,
    DeviceFirewallDirection,
    DeviceFirewallPolicyIntent,
    DeviceFirewallRuleIntent,
)
from rou.forwarding_gate import ForwardingGateState
from rou.interface_inventory import parse_ip_link_inventory
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_device_firewall import LinuxDeviceFirewallDriver
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.port_bundle import PortBundle, PortSpan


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


def converge_until_confirmed(gate, backend, desired, limit=8):
    history = []
    for _ in range(limit):
        result = converge_device_firewall_step_once(gate, backend, desired)
        history.append(result)
        if result.confirmed:
            return history
        assert result.status is DeviceFirewallMutationStatus.STEP_APPLIED, result
    raise AssertionError(history)


def main():
    if os.geteuid() != 0:
        raise SystemExit("guarded Device firewall integration requires root")

    namespace = f"vpng-dfw-step-{os.getpid()}"
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
                f'    ct state new meta iif {host.ifindex} meta oif {path.ifindex} '
                'ip daddr 10.0.0.0/8 accept '
                'comment "vpn-gate:ng3:payload-forward-new-v1"\n'
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
        backend = LinuxDeviceFirewallDriver(
            runner=SubprocessNftRunner(),
            namespace=namespace,
        )

        policy = DeviceFirewallPolicyIntent(
            "device",
            (
                DeviceFirewallRuleIntent(
                    direction=DeviceFirewallDirection.OUT,
                    action=DeviceFirewallAction.ALLOW,
                    protocol="tcp",
                    destination_ports=PortBundle(
                        (
                            PortSpan(80, 80),
                            PortSpan(443, 443),
                            PortSpan(8000, 8007),
                        )
                    ),
                ),
                DeviceFirewallRuleIntent(
                    direction=DeviceFirewallDirection.OUT,
                    action=DeviceFirewallAction.DENY,
                ),
                DeviceFirewallRuleIntent(
                    direction=DeviceFirewallDirection.IN,
                    action=DeviceFirewallAction.REJECT,
                    protocol="tcp",
                ),
            ),
        )
        desired = compile_device_firewall_policy(
            policy,
            host,
            path,
            out_chain_name="dfw_out",
            in_chain_name="dfw_in",
        )

        ns_run(namespace, "sysctl", "-w", "net.ipv4.ip_forward=1")
        initial = converge_until_confirmed(gate, backend, desired)
        assert len(initial) == 2, initial
        assert initial[-1].confirmed
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        ruleset = backend.observe_device_firewall_snapshot().observation
        payload_rules = [
            obj.canonical_json
            for obj in ruleset.objects
            if obj.kind == "rule" and '"chain":"payload_forward"' in obj.canonical_json
        ]
        assert len(payload_rules) == 3, payload_rules
        # Two inserted Device jumps must precede the original Profile rule.
        assert "device-fw-jump-v1" in payload_rules[0], payload_rules
        assert "device-fw-jump-v1" in payload_rules[1], payload_rules
        assert "payload-forward-new-v1" in payload_rules[2], payload_rules

        replacement_policy = DeviceFirewallPolicyIntent(
            "device",
            (
                DeviceFirewallRuleIntent(
                    direction=DeviceFirewallDirection.OUT,
                    action=DeviceFirewallAction.DENY,
                    destination_ipv4_cidr=__import__("ipaddress").IPv4Network("10.1.0.0/16"),
                ),
                DeviceFirewallRuleIntent(
                    direction=DeviceFirewallDirection.IN,
                    action=DeviceFirewallAction.REJECT,
                    protocol="tcp",
                ),
            ),
        )
        replacement_desired = compile_device_firewall_policy(
            replacement_policy,
            host,
            path,
            out_chain_name="dfw_out",
            in_chain_name="dfw_in",
        )
        replacement = converge_until_confirmed(
            gate,
            backend,
            replacement_desired,
        )
        assert [item.step for item in replacement] == [
            next(item.step for item in replacement if item.step and item.step.startswith("delete-jump")),
            "delete-chain:dfw_out",
            "create-chain:dfw_out",
        ], replacement
        assert replacement[-1].confirmed
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        ns_run(
            namespace,
            "nft",
            "-f",
            "-",
            input_text=(
                "add rule ip vpn_gate payload_postrouting "
                f"meta iif {host.ifindex} meta oif {path.ifindex} "
                'masquerade comment "vpn-gate:ng3:payload-nat-v1"\n'
            ),
        )
        conflict = converge_device_firewall_step_once(
            gate,
            backend,
            replacement_desired,
        )
        assert conflict.status is DeviceFirewallMutationStatus.CONFLICT, conflict
        assert not conflict.mutation_attempted
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        print("NG3 live bounded guarded Device firewall mutation: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", namespace),
            text=True, check=False, capture_output=True,
        )


if __name__ == "__main__":
    main()
