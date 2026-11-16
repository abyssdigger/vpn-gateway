from __future__ import annotations

import json
import os
import subprocess
import sys


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
        "ip", "netns", "exec", name,
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


def ifindex(namespace: str, ifname: str) -> int:
    value = json.loads(
        ns(namespace, "ip", "-j", "link", "show", "dev", ifname).stdout
    )
    assert isinstance(value, list) and len(value) == 1, value
    index = value[0].get("ifindex")
    assert type(index) is int and index > 0, value
    return index


def ruleset(namespace: str) -> dict:
    value = json.loads(
        ns(namespace, "nft", "-j", "list", "ruleset").stdout
    )
    assert isinstance(value, dict), value
    return value


def nat_rules(value: dict) -> list[dict]:
    return [
        row["rule"]
        for row in value.get("nftables", [])
        if isinstance(row, dict)
        and isinstance(row.get("rule"), dict)
        and row["rule"].get("family") == "ip"
        and row["rule"].get("table") == "vpn_gate"
        and row["rule"].get("chain") == "payload_postrouting"
    ]


def add_link_pair(
    suffix: str,
    left_ns: str,
    gate_ns: str,
    left_if: str,
    gate_if: str,
) -> None:
    run("ip", "link", "add", left_if, "type", "veth", "peer", "name", gate_if)
    run("ip", "link", "set", left_if, "netns", left_ns)
    run("ip", "link", "set", gate_if, "netns", gate_ns)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-033 must run as root")

    suffix = str(os.getpid())
    left = f"vpng-e33-l-{suffix}"
    other = f"vpng-e33-o-{suffix}"
    gate = f"vpng-e33-g-{suffix}"
    right = f"vpng-e33-r-{suffix}"
    created = []

    left_if = f"e33l-{suffix}"
    gate_left = f"e33gl-{suffix}"
    other_if = f"e33o-{suffix}"
    gate_other = f"e33go-{suffix}"
    right_if = f"e33r-{suffix}"
    gate_right = f"e33gr-{suffix}"

    try:
        for name in (left, other, gate, right):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        add_link_pair(suffix, left, gate, left_if, gate_left)
        add_link_pair(suffix, other, gate, other_if, gate_other)
        add_link_pair(suffix, right, gate, right_if, gate_right)

        ns(left, "ip", "addr", "add", "10.33.1.2/24", "dev", left_if)
        ns(gate, "ip", "addr", "add", "10.33.1.1/24", "dev", gate_left)
        ns(other, "ip", "addr", "add", "10.33.3.2/24", "dev", other_if)
        ns(gate, "ip", "addr", "add", "10.33.3.1/24", "dev", gate_other)
        ns(right, "ip", "addr", "add", "10.33.2.2/24", "dev", right_if)
        ns(gate, "ip", "addr", "add", "10.33.2.1/24", "dev", gate_right)

        for namespace, ifname in (
            (left, left_if),
            (gate, gate_left),
            (other, other_if),
            (gate, gate_other),
            (right, right_if),
            (gate, gate_right),
        ):
            ns(namespace, "ip", "link", "set", ifname, "up")

        ns(left, "ip", "route", "add", "10.33.2.0/24", "via", "10.33.1.1")
        ns(other, "ip", "route", "add", "10.33.2.0/24", "via", "10.33.3.1")

        # Deliberately no route on right back to 10.33.1.0/24 or 10.33.3.0/24.
        ns(gate, "sysctl", "-w", "net.ipv4.ip_forward=1")

        nft_script(
            gate,
            f"""table ip vpn_gate {{
    comment "vpn-gate:ng3:owner-v1"
    chain payload_forward {{
        type filter hook forward priority 0; policy drop;
        comment "vpn-gate:ng3:payload-forward-v1"
        iifname "{gate_left}" oifname "{gate_right}" accept
        iifname "{gate_right}" oifname "{gate_left}" accept
        iifname "{gate_other}" oifname "{gate_right}" accept
        iifname "{gate_right}" oifname "{gate_other}" accept
    }}
    chain payload_postrouting {{
        type nat hook postrouting priority 100; policy accept;
        comment "vpn-gate:ng3:payload-postrouting-v1"
    }}
}}
""",
        )

        # Baseline: forwarding is permitted, but reply cannot return without NAT.
        assert not ping(left, "10.33.2.2"), (
            "baseline unexpectedly succeeded without return route/NAT"
        )

        host_iif = ifindex(gate, gate_left)
        path_oif = ifindex(gate, gate_right)

        # H1/H3: numeric exact-ifindex rule performs real masquerade.
        nft_script(
            gate,
            (
                "add rule ip vpn_gate payload_postrouting "
                f"meta iif {host_iif} meta oif {path_oif} "
                'masquerade comment "vpn-gate:ng3:payload-nat-v1"\n'
            ),
        )
        assert ping(left, "10.33.2.2"), (
            "matching exact-ifindex masquerade did not restore return path"
        )

        value = ruleset(gate)
        rules = nat_rules(value)
        assert len(rules) == 1, rules
        print("EXP033_NAT_RULE_JSON=" + json.dumps(rules[0], sort_keys=True))

        # H4: a different ingress does not match the host-boundary iif index.
        assert not ping(other, "10.33.2.2"), (
            "payload NAT rule matched a different ingress interface"
        )

        # H5: replace egress with same name but fresh ifindex.
        old_oif = path_oif
        ns(gate, "ip", "link", "del", gate_right)

        run("ip", "link", "add", right_if, "type", "veth", "peer", "name", gate_right)
        run("ip", "link", "set", right_if, "netns", right)
        run("ip", "link", "set", gate_right, "netns", gate)

        ns(right, "ip", "addr", "add", "10.33.2.3/24", "dev", right_if)
        ns(gate, "ip", "addr", "add", "10.33.2.1/24", "dev", gate_right)
        ns(right, "ip", "link", "set", right_if, "up")
        ns(gate, "ip", "link", "set", gate_right, "up")

        new_oif = ifindex(gate, gate_right)
        assert new_oif != old_oif, (old_oif, new_oif)

        assert not ping(left, "10.33.2.3"), (
            "stale numeric oif rule matched same-name replacement interface"
        )

        nft_script(
            gate,
            (
                "add rule ip vpn_gate payload_postrouting "
                f"meta iif {host_iif} meta oif {new_oif} "
                'masquerade comment "vpn-gate:ng3:payload-nat-v1"\n'
            ),
        )
        assert ping(left, "10.33.2.3"), (
            "fresh replacement-ifindex masquerade did not match"
        )

        print(f"EXP033_HOST_IIF={host_iif}")
        print(f"EXP033_OLD_PATH_OIF={old_oif}")
        print(f"EXP033_NEW_PATH_OIF={new_oif}")
        print("EXP033_OTHER_INGRESS_MATCHED=0")
        print("EXP033_STALE_SAME_NAME_MATCHED=0")
        print("EXP-033 exact-ifindex payload masquerade: PASS")
        return 0
    finally:
        for name in reversed(created):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
