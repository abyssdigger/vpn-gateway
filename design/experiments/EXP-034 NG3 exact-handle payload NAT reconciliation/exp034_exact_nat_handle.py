from __future__ import annotations

"""EXP-034: exact nft handle deletion after same-name ifindex replacement."""

import json
import os
import subprocess

from rou.binding import LogicalPathId
from rou.interface_inventory import parse_ip_link_inventory
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.nft_namespace_inventory import LinuxNftNamespaceBackend
from rou.payload_nat_desired import PayloadMasqueradeSpec, PayloadNatDesiredState
from rou.payload_nat_observation import compare_payload_nat


def run(*argv: str, input_text: str | None = None, check: bool = True):
    return subprocess.run(
        argv, input=input_text, text=True, capture_output=True, check=check,
    )


def ns_cmd(namespace: str, *argv: str, input_text: str | None = None,
           check: bool = True):
    return run(
        "ip", "netns", "exec", namespace, *argv,
        input_text=input_text, check=check,
    )


def inventory(namespace):
    return parse_ip_link_inventory(
        ns_cmd(namespace, "ip", "-j", "link", "show").stdout,
    )


def identity(namespace, name):
    found = [item for item in inventory(namespace) if item.ifname == name]
    assert len(found) == 1, found
    return found[0]


def veth(namespace, ifname, peer):
    ns_cmd(namespace, "ip", "link", "add", ifname,
           "type", "veth", "peer", "name", peer)


def observe_rules(backend):
    obs = backend.observe_nft_namespace()
    nat = [
        json.loads(obj.canonical_json)["rule"]
        for obj in obs.objects
        if obj.kind == "rule"
        and json.loads(obj.canonical_json)["rule"].get("chain") ==
        "payload_postrouting"
    ]
    handles = [row["handle"] for row in nat]
    assert all(type(handle) is int and handle >= 0 for handle in handles)
    assert len(set(handles)) == len(handles), handles
    return obs, tuple(sorted(handles))


def main():
    if os.geteuid() != 0:
        raise SystemExit("EXP-034 requires root in a disposable namespace")
    namespace = f"vpng-exp034-{os.getpid()}"
    try:
        run("ip", "netns", "add", namespace)
        ns_cmd(namespace, "sysctl", "-w", "net.ipv4.ip_forward=0")
        assert ns_cmd(
            namespace, "sysctl", "-n", "net.ipv4.ip_forward",
        ).stdout.strip() == "0"

        veth(namespace, "host0", "hostpeer")
        veth(namespace, "tun0", "tunpeer")
        host = identity(namespace, "host0")
        old = identity(namespace, "tun0")
        ns_cmd(
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
        backend = LinuxNftNamespaceBackend(
            runner=SubprocessCommandRunner(), namespace=namespace,
        )
        path_id = LogicalPathId("device", 0, 0)

        def compare(target):
            desired = PayloadMasqueradeSpec(path_id, host, target)
            obs, handles = observe_rules(backend)
            result = compare_payload_nat(
                obs, inventory(namespace), PayloadNatDesiredState((desired,)),
            )
            return desired, result, handles

        def add_nat(target):
            ns_cmd(
                namespace, "nft", "-f", "-",
                input_text=(
                    "add rule ip vpn_gate payload_postrouting "
                    f"meta iif {host.ifindex} meta oif {target.ifindex} "
                    'masquerade comment "vpn-gate:ng3:payload-nat-v1"\n'
                ),
            )

        add_nat(old)
        old_spec, current, handles = compare(old)
        assert current.confirmed == (old_spec,) and current.conflict_free
        assert not current.missing and not current.stale and len(handles) == 1
        old_handle = handles[0]

        ns_cmd(namespace, "ip", "link", "del", "tun0")
        veth(namespace, "tun0", "tunpeer")
        fresh = identity(namespace, "tun0")
        assert fresh.ifindex != old.ifindex
        new_spec, stale, handles = compare(fresh)
        assert stale.missing == (new_spec,) and len(stale.stale) == 1
        assert stale.stale[0].egress == old.ifindex
        assert stale.stale[0].handle == old_handle
        assert stale.conflict_free and handles == (old_handle,)

        add_nat(fresh)
        new_spec, mixed, handles = compare(fresh)
        assert mixed.confirmed == (new_spec,) and len(mixed.stale) == 1
        assert mixed.stale[0].handle == old_handle and len(handles) == 2
        assert mixed.conflict_free and not mixed.missing
        new_handle = next(handle for handle in handles if handle != old_handle)

        assert ns_cmd(
            namespace, "sysctl", "-n", "net.ipv4.ip_forward",
        ).stdout.strip() == "0"
        ns_cmd(
            namespace, "nft", "delete", "rule", "ip", "vpn_gate",
            "payload_postrouting", "handle", str(old_handle),
        )
        new_spec, cleaned, handles = compare(fresh)
        assert cleaned.confirmed == (new_spec,) and not cleaned.stale
        assert not cleaned.missing and cleaned.conflict_free
        assert handles == (new_handle,), (handles, new_handle)

        before, before_handles = observe_rules(backend)
        missing_handle = max(before_handles) + 10000
        failed = ns_cmd(
            namespace, "nft", "delete", "rule", "ip", "vpn_gate",
            "payload_postrouting", "handle", str(missing_handle),
            check=False,
        )
        assert failed.returncode != 0, failed
        after, after_handles = observe_rules(backend)
        assert after.objects == before.objects and after_handles == before_handles
        assert ns_cmd(
            namespace, "sysctl", "-n", "net.ipv4.ip_forward",
        ).stdout.strip() == "0"

        print(f"EXP034_OLD_IFINDEX={old.ifindex}")
        print(f"EXP034_NEW_IFINDEX={fresh.ifindex}")
        print(f"EXP034_STALE_HANDLE={old_handle}")
        print(f"EXP034_NEW_HANDLE={new_handle}")
        print("EXP-034 exact-handle stale NAT deletion: PASS")
    finally:
        run("ip", "netns", "del", namespace, check=False)


if __name__ == "__main__":
    main()
