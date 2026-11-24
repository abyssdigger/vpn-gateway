from __future__ import annotations

"""Live nft/ifindex integration for read-only payload NAT observation."""

import os
import subprocess

from rou.binding import LogicalPathId
from rou.interface_inventory import parse_ip_link_inventory
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.nft_namespace_inventory import LinuxNftNamespaceBackend
from rou.payload_nat_desired import PayloadMasqueradeSpec, PayloadNatDesiredState
from rou.payload_nat_observation import compare_payload_nat


def run(*argv: str, input_text: str | None = None) -> str:
    return subprocess.run(
        argv, input=input_text, text=True, check=True, capture_output=True,
    ).stdout


def in_ns(namespace: str, *argv: str, input_text: str | None = None) -> str:
    return run("ip", "netns", "exec", namespace, *argv, input_text=input_text)


def identity(namespace: str, name: str):
    inventory = parse_ip_link_inventory(in_ns(namespace, "ip", "-j", "link", "show"))
    matches = [item for item in inventory if item.ifname == name]
    assert len(matches) == 1, matches
    return matches[0]


def add_veth(namespace: str, name: str, peer: str) -> None:
    in_ns(namespace, "ip", "link", "add", name, "type", "veth",
          "peer", "name", peer)


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("NAT observer integration requires root")

    namespace = f"vpng-nat-observe-{os.getpid()}"
    try:
        run("ip", "netns", "add", namespace)
        add_veth(namespace, "host0", "hostpeer")
        add_veth(namespace, "tun0", "tunpeer")
        host = identity(namespace, "host0")
        old_path = identity(namespace, "tun0")

        in_ns(
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
            ),
        )
        backend = LinuxNftNamespaceBackend(
            runner=SubprocessCommandRunner(), namespace=namespace,
        )
        path_id = LogicalPathId("device", 0, 0)

        def compare(target):
            spec = PayloadMasqueradeSpec(path_id, host, target)
            result = compare_payload_nat(
                backend.observe_nft_namespace(),
                parse_ip_link_inventory(in_ns(namespace, "ip", "-j", "link", "show")),
                PayloadNatDesiredState((spec,)),
            )
            return spec, result

        spec, missing = compare(old_path)
        assert missing.missing == (spec,) and missing.conflict_free, missing
        assert not missing.confirmed and not missing.stale, missing

        in_ns(
            namespace, "nft", "-f", "-",
            input_text=(
                "add rule ip vpn_gate payload_postrouting "
                f"meta iif {host.ifindex} meta oif {old_path.ifindex} "
                'masquerade comment "vpn-gate:ng3:payload-nat-v1"\n'
            ),
        )
        spec, current = compare(old_path)
        assert current.confirmed == (spec,) and not current.missing, current
        assert not current.stale and current.conflict_free, current

        in_ns(namespace, "ip", "link", "del", "tun0")
        add_veth(namespace, "tun0", "tunpeer")
        new_path = identity(namespace, "tun0")
        assert new_path.ifindex != old_path.ifindex, (old_path, new_path)

        spec, replaced = compare(new_path)
        assert replaced.missing == (spec,) and not replaced.confirmed, replaced
        assert len(replaced.stale) == 1 and replaced.conflict_free, replaced
        assert replaced.stale[0].egress == old_path.ifindex, replaced
        assert replaced.stale[0].egress != new_path, replaced

        in_ns(
            namespace, "nft", "-f", "-",
            input_text=(
                "add rule ip vpn_gate payload_postrouting "
                f"meta iif {host.ifindex} meta oif {new_path.ifindex} "
                'masquerade comment "vpn-gate:ng3:payload-nat-v1"\n'
            ),
        )
        spec, combined = compare(new_path)
        assert combined.confirmed == (spec,) and not combined.missing, combined
        assert len(combined.stale) == 1 and combined.conflict_free, combined

        in_ns(
            namespace, "nft", "-f", "-",
            input_text=(
                "add rule ip vpn_gate payload_postrouting "
                f"meta iif {host.ifindex} meta oif {new_path.ifindex} "
                'masquerade comment "unknown-owner"\n'
            ),
        )
        _, conflict = compare(new_path)
        assert conflict.conflicts and not conflict.conflict_free, conflict

        print("NG3 live payload NAT observer / same-name ifindex replacement: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", namespace),
            text=True, check=False, capture_output=True,
        )


if __name__ == "__main__":
    main()
