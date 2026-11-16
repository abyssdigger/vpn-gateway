from __future__ import annotations

import json
import os
import subprocess
import sys


TABLE_COMMENT = "vpn-gate:ng3:owner-v1"
FORWARD_COMMENT = "vpn-gate:ng3:payload-forward-v1"
CHILD_COMMENT = "vpn-gate:ng3:device-fw-child-v1"
JUMP_COMMENT = "vpn-gate:ng3:device-fw-jump-v1"
RULE_COMMENT = "vpn-gate:ng3:device-fw-rule-v1"
PROFILE_NEW_COMMENT = "vpn-gate:ng3:payload-forward-new-v1"
PROFILE_RETURN_COMMENT = "vpn-gate:ng3:payload-forward-return-v1"
CHILD = "device_fw_exp044"


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
        "ip",
        "netns",
        "exec",
        name,
        *argv,
        check=check,
        input_text=input_text,
    )


def nft_script(namespace: str, script: str) -> None:
    ns(namespace, "nft", "-f", "-", input_text=script)


def ifindex(namespace: str, ifname: str) -> int:
    value = ns(namespace, "cat", f"/sys/class/net/{ifname}/ifindex").stdout.strip()
    index = int(value)
    assert index > 0
    return index


def ping(namespace: str, target: str) -> bool:
    result = ns(
        namespace,
        "ping",
        "-n",
        "-c",
        "2",
        "-W",
        "1",
        target,
        check=False,
    )
    return result.returncode == 0


def forward_rules(namespace: str) -> list[dict]:
    value = json.loads(
        ns(
            namespace,
            "nft",
            "-j",
            "list",
            "chain",
            "ip",
            "vpn_gate",
            "payload_forward",
        ).stdout
    )
    rules: list[dict] = []
    for row in value.get("nftables", []):
        if isinstance(row, dict) and isinstance(row.get("rule"), dict):
            rules.append(row["rule"])
    return rules


def jump_handle(rules: list[dict]) -> int:
    matches = [
        rule.get("handle")
        for rule in rules
        if rule.get("comment") == JUMP_COMMENT
    ]
    assert len(matches) == 1, rules
    handle = matches[0]
    assert type(handle) is int and handle >= 0
    return handle


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-044 must run as root")

    suffix = str(os.getpid())
    ordinary = f"e44-o-{suffix}"
    managed = f"e44-m-{suffix}"
    vpn = f"e44-v-{suffix}"
    created: list[str] = []

    o_if = f"e44o-{suffix}"
    mo_if = f"e44mo-{suffix}"
    mv_if = f"e44mv-{suffix}"
    v_if = f"e44v-{suffix}"
    target = "10.44.2.2"

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

        ns(ordinary, "ip", "addr", "add", "10.44.1.2/30", "dev", o_if)
        ns(managed, "ip", "addr", "add", "10.44.1.1/30", "dev", mo_if)
        ns(managed, "ip", "addr", "add", "10.44.2.1/30", "dev", mv_if)
        ns(vpn, "ip", "addr", "add", f"{target}/30", "dev", v_if)

        for namespace, interface in (
            (ordinary, o_if),
            (managed, mo_if),
            (managed, mv_if),
            (vpn, v_if),
        ):
            ns(namespace, "ip", "link", "set", interface, "up")

        ns(ordinary, "ip", "route", "add", "10.44.2.0/30", "via", "10.44.1.1")
        ns(vpn, "ip", "route", "add", "10.44.1.0/30", "via", "10.44.2.1")
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
        ct state new meta iif {host_index} meta oif {path_index} ip daddr 10.44.2.0/30 accept comment "{PROFILE_NEW_COMMENT}"
        ct state established,related meta iif {path_index} meta oif {host_index} ip saddr 10.44.2.0/30 accept comment "{PROFILE_RETURN_COMMENT}"
    }}
    chain {CHILD} {{
        comment "{CHILD_COMMENT}"
        ip daddr {target} drop comment "{RULE_COMMENT}"
    }}
}}
""",
        )

        assert ping(ordinary, target), "Profile baseline did not pass"

        # Wrong primitive: append puts Device policy after terminal Profile acceptance.
        nft_script(
            managed,
            f"""add rule ip vpn_gate payload_forward meta iif {host_index} meta oif {path_index} jump {CHILD} comment "{JUMP_COMMENT}"
""",
        )
        appended = forward_rules(managed)
        appended_comments = [rule.get("comment") for rule in appended]
        assert appended_comments == [
            PROFILE_NEW_COMMENT,
            PROFILE_RETURN_COMMENT,
            JUMP_COMMENT,
        ], appended
        assert ping(ordinary, target), (
            "appended Device jump unexpectedly narrowed earlier Profile accept"
        )

        handle = jump_handle(appended)
        ns(
            managed,
            "nft",
            "delete",
            "rule",
            "ip",
            "vpn_gate",
            "payload_forward",
            "handle",
            str(handle),
        )

        # Correct primitive: insert puts Device policy before Profile acceptance.
        nft_script(
            managed,
            f"""insert rule ip vpn_gate payload_forward meta iif {host_index} meta oif {path_index} jump {CHILD} comment "{JUMP_COMMENT}"
""",
        )
        inserted = forward_rules(managed)
        inserted_comments = [rule.get("comment") for rule in inserted]
        assert inserted_comments == [
            JUMP_COMMENT,
            PROFILE_NEW_COMMENT,
            PROFILE_RETURN_COMMENT,
        ], inserted
        assert not ping(ordinary, target), (
            "inserted Device jump did not narrow later Profile accept"
        )

        print("EXP044_APPENDED_ORDER=" + json.dumps(appended_comments))
        print("EXP044_INSERTED_ORDER=" + json.dumps(inserted_comments))
        print("EXP044_APPEND_BYPASS=1")
        print("EXP044_INSERT_ENFORCES_DEVICE_BEFORE_PROFILE=1")
        print("EXP044_INSERTED_RULE_JSON=" + json.dumps(inserted[0], sort_keys=True))
        print("EXP-044 Device firewall jump insertion: PASS")
        return 0
    finally:
        for name in reversed(created):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
