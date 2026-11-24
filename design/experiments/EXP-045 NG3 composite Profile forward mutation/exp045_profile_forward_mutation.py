from __future__ import annotations

import json
import os
import subprocess
import sys


TABLE_COMMENT = "vpn-gate:ng3:owner-v1"
FORWARD_COMMENT = "vpn-gate:ng3:payload-forward-v1"
POSTROUTING_COMMENT = "vpn-gate:ng3:payload-postrouting-v1"
DEVICE_CHILD_COMMENT = "vpn-gate:ng3:device-fw-child-v1"
DEVICE_JUMP_COMMENT = "vpn-gate:ng3:device-fw-jump-v1"
DEVICE_RULE_COMMENT = "vpn-gate:ng3:device-fw-rule-v1"
DEVICE_FALLTHROUGH_COMMENT = "vpn-gate:ng3:device-fw-fallthrough-v1"
PROFILE_NEW_COMMENT = "vpn-gate:ng3:payload-forward-new-v1"
PROFILE_RETURN_COMMENT = "vpn-gate:ng3:payload-forward-return-v1"
NAT_COMMENT = "vpn-gate:ng3:payload-nat-v1"
CHILD = "device_fw_exp045"


def run(*argv: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        argv,
        input=input_text,
        check=check,
        text=True,
        capture_output=True,
    )


def ns(name: str, *argv: str, check: bool = True, input_text: str | None = None):
    return run(
        "ip", "netns", "exec", name, *argv,
        check=check, input_text=input_text,
    )


def nft_script(namespace: str, script: str) -> None:
    ns(namespace, "nft", "-f", "-", input_text=script)


def ifindex(namespace: str, ifname: str) -> int:
    return int(
        ns(namespace, "cat", f"/sys/class/net/{ifname}/ifindex").stdout.strip()
    )


def rules(namespace: str, chain: str) -> list[dict]:
    value = json.loads(
        ns(
            namespace, "nft", "-j", "list", "chain",
            "ip", "vpn_gate", chain,
        ).stdout
    )
    return [
        row["rule"]
        for row in value.get("nftables", [])
        if isinstance(row, dict) and isinstance(row.get("rule"), dict)
    ]


def ping(namespace: str, target: str) -> bool:
    result = ns(
        namespace, "ping", "-n", "-c", "1", "-W", "1", target,
        check=False,
    )
    return result.returncode == 0


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-045 must run as root")

    suffix = str(os.getpid())
    ordinary = f"e45-o-{suffix}"
    managed = f"e45-m-{suffix}"
    vpn = f"e45-v-{suffix}"
    created: list[str] = []

    o_if = f"e45o-{suffix}"
    mo_if = f"e45mo-{suffix}"
    mv_if = f"e45mv-{suffix}"
    v_if = f"e45v-{suffix}"
    target = "10.45.2.2"

    try:
        for name in (ordinary, managed, vpn):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        run("ip", "link", "add", o_if, "type", "veth", "peer", "name", mo_if)
        run("ip", "link", "set", o_if, "netns", ordinary)
        run("ip", "link", "set", mo_if, "netns", managed)
        run("ip", "link", "add", mv_if, "type", "veth", "peer", "name", v_if)
        run("ip", "link", "set", mv_if, "netns", managed)
        run("ip", "link", "set", v_if, "netns", vpn)

        ns(ordinary, "ip", "addr", "add", "10.45.1.2/30", "dev", o_if)
        ns(managed, "ip", "addr", "add", "10.45.1.1/30", "dev", mo_if)
        ns(managed, "ip", "addr", "add", "10.45.2.1/30", "dev", mv_if)
        ns(vpn, "ip", "addr", "add", f"{target}/30", "dev", v_if)

        for namespace, interface in (
            (ordinary, o_if), (managed, mo_if),
            (managed, mv_if), (vpn, v_if),
        ):
            ns(namespace, "ip", "link", "set", interface, "up")

        ns(ordinary, "ip", "route", "add", "10.45.2.0/30", "via", "10.45.1.1")
        ns(vpn, "ip", "route", "add", "10.45.1.0/30", "via", "10.45.2.1")
        ns(managed, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")

        host_index = ifindex(managed, mo_if)
        path_index = ifindex(managed, mv_if)

        nft_script(
            managed,
            f"""table ip vpn_gate {{
    comment "{TABLE_COMMENT}"
    chain payload_forward {{
        type filter hook forward priority 0; policy drop;
        comment "{FORWARD_COMMENT}"
    }}
    chain payload_postrouting {{
        type nat hook postrouting priority 100; policy accept;
        comment "{POSTROUTING_COMMENT}"
    }}
    chain {CHILD} {{
        comment "{DEVICE_CHILD_COMMENT}"
        ip daddr {target} return comment "{DEVICE_RULE_COMMENT}"
        drop comment "{DEVICE_FALLTHROUGH_COMMENT}"
    }}
}}
insert rule ip vpn_gate payload_forward meta iif {host_index} meta oif {path_index} jump {CHILD} comment "{DEVICE_JUMP_COMMENT}"
add rule ip vpn_gate payload_postrouting meta iif {host_index} meta oif {path_index} masquerade comment "{NAT_COMMENT}"
""",
        )

        assert not ping(ordinary, target), "traffic passed before Profile admission"

        nft_script(
            managed,
            f"""add rule ip vpn_gate payload_forward ct state new meta iif {host_index} meta oif {path_index} ip daddr 10.45.2.0/30 accept comment "{PROFILE_NEW_COMMENT}"
add rule ip vpn_gate payload_forward ct state established,related meta iif {path_index} meta oif {host_index} ip saddr 10.45.2.0/30 accept comment "{PROFILE_RETURN_COMMENT}"
""",
        )

        forward = rules(managed, "payload_forward")
        comments = [rule.get("comment") for rule in forward]
        assert comments == [
            DEVICE_JUMP_COMMENT,
            PROFILE_NEW_COMMENT,
            PROFILE_RETURN_COMMENT,
        ], forward
        assert ping(ordinary, target), "Profile admission did not restore traffic"

        new_rules = [
            rule for rule in forward if rule.get("comment") == PROFILE_NEW_COMMENT
        ]
        assert len(new_rules) == 1, forward
        new_handle = new_rules[0].get("handle")
        assert type(new_handle) is int and new_handle >= 0

        before_child = rules(managed, CHILD)
        before_nat = rules(managed, "payload_postrouting")

        ns(
            managed,
            "nft", "delete", "rule", "ip", "vpn_gate",
            "payload_forward", "handle", str(new_handle),
        )

        after_forward = rules(managed, "payload_forward")
        after_child = rules(managed, CHILD)
        after_nat = rules(managed, "payload_postrouting")
        after_comments = [rule.get("comment") for rule in after_forward]

        assert after_comments == [
            DEVICE_JUMP_COMMENT,
            PROFILE_RETURN_COMMENT,
        ], after_forward
        assert before_child == after_child
        assert before_nat == after_nat
        assert not ping(ordinary, target), (
            "traffic still passed after exact NEW Profile rule deletion"
        )

        print("EXP045_INITIAL_ORDER=" + json.dumps(comments))
        print("EXP045_AFTER_DELETE_ORDER=" + json.dumps(after_comments))
        print("EXP045_PROFILE_ADD_AFTER_DEVICE=1")
        print("EXP045_EXACT_DELETE_PRESERVES_DEVICE=1")
        print("EXP045_EXACT_DELETE_PRESERVES_NAT=1")
        print("EXP-045 composite Profile forward mutation: PASS")
        return 0
    finally:
        for name in reversed(created):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
