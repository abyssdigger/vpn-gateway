from __future__ import annotations

"""Live Linux proof for managed Profile SNAT materialization/observation."""

from ipaddress import IPv4Address
import os
import subprocess

from rou.interface_inventory import parse_ip_link_inventory
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_payload_nat import LinuxPayloadNatBackend
from rou.payload_nat_desired import PayloadNatDesiredState, PayloadProfileSnatSpec
from rou.payload_nat_observation import compare_payload_nat


def run(*argv: str, input_text: str | None = None) -> str:
    return subprocess.run(
        argv, input=input_text, text=True, check=True, capture_output=True,
    ).stdout


def in_ns(namespace: str, *argv: str, input_text: str | None = None) -> str:
    return run("ip", "netns", "exec", namespace, *argv, input_text=input_text)


def links(namespace: str):
    return parse_ip_link_inventory(in_ns(namespace, "ip", "-j", "link", "show"))


def identity(namespace: str, name: str):
    found = [item for item in links(namespace) if item.ifname == name]
    assert len(found) == 1, found
    return found[0]


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Profile SNAT integration requires root")
    namespace = f"vpng-profile-snat-{os.getpid()}"
    try:
        run("ip", "netns", "add", namespace)
        in_ns(namespace, "ip", "link", "add", "host0", "type", "veth",
              "peer", "name", "hostpeer")
        host = identity(namespace, "host0")
        in_ns(
            namespace, "nft", "-f", "-",
            input_text=(
                'table ip vpn_gate {\n'
                '  comment "vpn-gate:ng3:owner-v1"\n'
                '  chain stack_input { type filter hook input priority 0; policy drop; '
                'comment "vpn-gate:ng3:stack-input-v1"; }\n'
                '  chain payload_forward { type filter hook forward priority 0; policy drop; '
                'comment "vpn-gate:ng3:payload-forward-v1"; }\n'
                '  chain stack_output { type filter hook output priority 0; policy drop; '
                'comment "vpn-gate:ng3:stack-output-v1"; }\n'
                '  chain payload_postrouting { type nat hook postrouting priority 100; policy accept; '
                'comment "vpn-gate:ng3:payload-postrouting-v1"; }\n'
                '}\n'
            ),
        )
        backend = LinuxPayloadNatBackend(
            runner=SubprocessNftRunner(),
            namespace=namespace,
        )
        spec = PayloadProfileSnatSpec(
            profile_id="p",
            mark=0x10000001,
            egress=host,
            source_address=IPv4Address("198.19.255.10"),
        )
        desired = PayloadNatDesiredState((), (spec,))
        backend.add_nat_rule(spec)
        snap = backend.observe_nat_snapshot()
        comparison = compare_payload_nat(
            snap.observation,
            snap.interfaces,
            desired,
        )
        assert comparison.confirmed == (spec,), comparison
        assert not comparison.missing and not comparison.stale, comparison
        assert comparison.conflict_free, comparison
        print("NG3 live Profile SNAT materialization/observation: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", namespace),
            text=True, check=False, capture_output=True,
        )


if __name__ == "__main__":
    main()
