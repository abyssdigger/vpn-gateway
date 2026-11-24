from __future__ import annotations

"""Live strict payload_forward observer over real nft JSON."""

import os
import subprocess

from rou.interface_inventory import parse_ip_link_inventory
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.nft_namespace_inventory import LinuxNftNamespaceBackend
from rou.payload_forward_observation import (
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
    observe_payload_forward,
)


def run(*args: str, input_text: str | None = None) -> str:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        check=True,
        capture_output=True,
    ).stdout


def ns(namespace: str, *args: str, input_text: str | None = None) -> str:
    return run(
        "ip", "netns", "exec", namespace, *args,
        input_text=input_text,
    )


def inventory(namespace: str):
    return parse_ip_link_inventory(
        ns(namespace, "ip", "-j", "link", "show")
    )


def identity(namespace: str, name: str):
    found = [item for item in inventory(namespace) if item.ifname == name]
    assert len(found) == 1, found
    return found[0]


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("payload forward observer integration requires root")

    namespace = f"vpng-forward-observe-{os.getpid()}"
    try:
        run("ip", "netns", "add", namespace)
        ns(namespace, "ip", "link", "add", "host0", "type", "veth",
           "peer", "name", "hostpeer")
        ns(namespace, "ip", "link", "add", "vpn0", "type", "veth",
           "peer", "name", "vpnpeer")
        host = identity(namespace, "host0")
        old_vpn = identity(namespace, "vpn0")

        ns(
            namespace, "nft", "-f", "-",
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
                'add rule ip vpn_gate payload_forward '
                f'ct state new meta iif {host.ifindex} meta oif {old_vpn.ifindex} '
                'ip daddr 10.39.0.0/24 accept '
                'comment "vpn-gate:ng3:payload-forward-new-v1"\n'
                'add rule ip vpn_gate payload_forward '
                f'ct state established,related meta iif {old_vpn.ifindex} '
                f'meta oif {host.ifindex} ip saddr 10.39.0.0/24 accept '
                'comment "vpn-gate:ng3:payload-forward-return-v1"\n'
            ),
        )

        backend = LinuxNftNamespaceBackend(
            runner=SubprocessCommandRunner(),
            namespace=namespace,
        )
        current = observe_payload_forward(
            backend.observe_nft_namespace(),
            inventory(namespace),
        )
        assert current.conflict_free, current
        assert len(current.current_identity_rules) == 2 and not current.stale_identity_rules, current
        assert {
            item.kind for item in current.current_identity_rules
        } == {
            PayloadForwardRuleKind.NEW,
            PayloadForwardRuleKind.RETURN,
        }, current
        assert {
            item.remote_field for item in current.current_identity_rules
        } == {
            PayloadForwardRemoteField.DESTINATION,
            PayloadForwardRemoteField.SOURCE,
        }, current

        ns(namespace, "ip", "link", "del", "vpn0")
        ns(namespace, "ip", "link", "add", "vpn0", "type", "veth",
           "peer", "name", "vpnpeer")
        new_vpn = identity(namespace, "vpn0")
        assert new_vpn.ifindex != old_vpn.ifindex, (old_vpn, new_vpn)

        stale = observe_payload_forward(
            backend.observe_nft_namespace(),
            inventory(namespace),
        )
        assert stale.conflict_free, stale
        assert not stale.current_identity_rules and len(stale.stale_identity_rules) == 2, stale
        for item in stale.stale_identity_rules:
            operands = (item.ingress, item.egress)
            assert old_vpn.ifindex in operands, (item, old_vpn)
            assert new_vpn not in operands, (item, new_vpn)

        ns(
            namespace, "nft", "-f", "-",
            input_text=(
                'add rule ip vpn_gate payload_forward '
                f'ct state new meta iif {host.ifindex} meta oif {new_vpn.ifindex} '
                'ip daddr 10.40.0.0/24 accept comment "foreign"\n'
            ),
        )
        conflict = observe_payload_forward(
            backend.observe_nft_namespace(),
            inventory(namespace),
        )
        assert conflict.conflicts, conflict
        assert any(
            "owner comment" in item.reason
            for item in conflict.conflicts
        ), conflict

        print(
            "NG3 live strict payload_forward observation / stale generation: PASS"
        )
    finally:
        subprocess.run(
            ("ip", "netns", "del", namespace),
            text=True,
            check=False,
            capture_output=True,
        )


if __name__ == "__main__":
    main()
