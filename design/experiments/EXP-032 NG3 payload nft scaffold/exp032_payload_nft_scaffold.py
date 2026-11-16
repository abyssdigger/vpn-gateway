from __future__ import annotations

import json
import os
import subprocess
import sys


TABLE_COMMENT = "vpn-gate:ng3:owner-v1"
FORWARD_COMMENT = "vpn-gate:ng3:payload-forward-v1"
POSTROUTING_COMMENT = "vpn-gate:ng3:payload-postrouting-v1"


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


def ping(namespace: str, destination: str) -> bool:
    completed = ns(
        namespace,
        "ping",
        "-n",
        "-c",
        "2",
        "-W",
        "1",
        destination,
        check=False,
    )
    return completed.returncode == 0


def ruleset(namespace: str) -> dict:
    value = json.loads(
        ns(namespace, "nft", "-j", "list", "ruleset").stdout
    )
    assert isinstance(value, dict), value
    assert isinstance(value.get("nftables"), list), value
    return value


def chain_row(value: dict, table: str, name: str) -> dict:
    matches = []
    for row in value["nftables"]:
        if not isinstance(row, dict):
            continue
        chain = row.get("chain")
        if not isinstance(chain, dict):
            continue
        if (
            chain.get("family") == "ip"
            and chain.get("table") == table
            and chain.get("name") == name
        ):
            matches.append(chain)
    assert len(matches) == 1, matches
    return matches[0]


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-032 must run as root")

    suffix = str(os.getpid())
    left = f"vpng-e32-l-{suffix}"
    gate = f"vpng-e32-g-{suffix}"
    right = f"vpng-e32-r-{suffix}"
    created = []

    left_if = f"e32l-{suffix}"
    gate_left = f"e32gl-{suffix}"
    right_if = f"e32r-{suffix}"
    gate_right = f"e32gr-{suffix}"

    try:
        for name in (left, gate, right):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        run("ip", "link", "add", left_if, "type", "veth", "peer", "name", gate_left)
        run("ip", "link", "set", left_if, "netns", left)
        run("ip", "link", "set", gate_left, "netns", gate)

        run("ip", "link", "add", right_if, "type", "veth", "peer", "name", gate_right)
        run("ip", "link", "set", right_if, "netns", right)
        run("ip", "link", "set", gate_right, "netns", gate)

        ns(left, "ip", "addr", "add", "10.32.1.2/24", "dev", left_if)
        ns(gate, "ip", "addr", "add", "10.32.1.1/24", "dev", gate_left)
        ns(gate, "ip", "addr", "add", "10.32.2.1/24", "dev", gate_right)
        ns(right, "ip", "addr", "add", "10.32.2.2/24", "dev", right_if)

        for namespace, ifname in (
            (left, left_if),
            (gate, gate_left),
            (gate, gate_right),
            (right, right_if),
        ):
            ns(namespace, "ip", "link", "set", ifname, "up")

        ns(left, "ip", "route", "add", "10.32.2.0/24", "via", "10.32.1.1")
        ns(right, "ip", "route", "add", "10.32.1.0/24", "via", "10.32.2.1")
        ns(gate, "sysctl", "-w", "net.ipv4.ip_forward=1")

        # Foreign accept chains intentionally surround the VPN-GATE priority.
        nft_script(
            gate,
            """table ip foreign_early {
    chain forward_accept {
        type filter hook forward priority -100; policy accept;
    }
}
table ip foreign_late {
    chain forward_accept {
        type filter hook forward priority 100; policy accept;
    }
}
""",
        )

        nft_script(
            gate,
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
}}
""",
        )

        # H3/H4: foreign ACCEPT chains cannot bypass VPN-GATE terminal drop.
        assert not ping(left, "10.32.2.2"), (
            "foreign ACCEPT chain bypassed payload_forward policy drop"
        )

        value = ruleset(gate)
        forward = chain_row(value, "vpn_gate", "payload_forward")
        postrouting = chain_row(value, "vpn_gate", "payload_postrouting")

        # H1/H2: exact metadata is observable.
        assert forward.get("type") == "filter", forward
        assert forward.get("hook") == "forward", forward
        assert forward.get("prio") == 0, forward
        assert forward.get("policy") == "drop", forward
        assert forward.get("comment") == FORWARD_COMMENT, forward

        assert postrouting.get("type") == "nat", postrouting
        assert postrouting.get("hook") == "postrouting", postrouting
        assert postrouting.get("prio") == 100, postrouting
        assert postrouting.get("policy") == "accept", postrouting
        assert postrouting.get("comment") == POSTROUTING_COMMENT, postrouting

        print("EXP032_FORWARD_CHAIN_JSON=" + json.dumps(forward, sort_keys=True))
        print("EXP032_POSTROUTING_CHAIN_JSON=" + json.dumps(postrouting, sort_keys=True))

        # H5: explicit VPN-GATE allow contributions can open only the tested path.
        nft_script(
            gate,
            f"""add rule ip vpn_gate payload_forward iifname "{gate_left}" oifname "{gate_right}" accept
add rule ip vpn_gate payload_forward iifname "{gate_right}" oifname "{gate_left}" accept
""",
        )
        assert ping(left, "10.32.2.2"), (
            "explicit payload_forward accept rules did not permit tested path"
        )

        # H6: no NAT rule exists in the accepted scaffold.
        value_after = ruleset(gate)
        postrouting_rules = [
            row["rule"]
            for row in value_after["nftables"]
            if isinstance(row, dict)
            and isinstance(row.get("rule"), dict)
            and row["rule"].get("family") == "ip"
            and row["rule"].get("table") == "vpn_gate"
            and row["rule"].get("chain") == "payload_postrouting"
        ]
        assert postrouting_rules == [], postrouting_rules

        print("EXP032_FOREIGN_ACCEPT_BYPASS=0")
        print("EXP032_EXPLICIT_ALLOW_FORWARDED=1")
        print("EXP032_EMPTY_POSTROUTING_RULES=1")
        print("EXP-032 payload nft scaffold: PASS")
        return 0
    finally:
        for name in reversed(created):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
