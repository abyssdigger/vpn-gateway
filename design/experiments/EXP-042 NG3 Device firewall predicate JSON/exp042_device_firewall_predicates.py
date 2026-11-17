from __future__ import annotations

import json
import os
import subprocess
import sys


TABLE_COMMENT = "vpn-gate:ng3:owner-v1"
CHAIN_COMMENT = "vpn-gate:ng3:device-fw-child-v1"
RULE_COMMENT = "vpn-gate:ng3:device-fw-rule-v1"


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


def rules(namespace: str) -> list[dict]:
    value = json.loads(
        ns(namespace, "nft", "-j", "list", "chain", "ip", "vpn_gate", "device_fw_exp042").stdout
    )
    rows = value.get("nftables")
    assert isinstance(rows, list), value
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rule = row.get("rule")
        if isinstance(rule, dict):
            result.append(rule)
    return result


def match(left: dict, right: object) -> dict:
    return {"match": {"op": "==", "left": left, "right": right}}


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-042 must run as root")

    namespace = f"vpng-e42-{os.getpid()}"
    try:
        run("ip", "netns", "add", namespace)

        nft_script(
            namespace,
            f"""table ip vpn_gate {{
    comment "{TABLE_COMMENT}"
    chain device_fw_exp042 {{
        comment "{CHAIN_COMMENT}"
        ip saddr 192.0.2.0/24 ip daddr 198.51.100.10 meta l4proto tcp tcp sport 12345 tcp dport 443 return comment "{RULE_COMMENT}"
        meta l4proto udp udp sport 5353 udp dport 53 drop comment "{RULE_COMMENT}"
        meta l4proto icmp return comment "{RULE_COMMENT}"
        meta l4proto tcp return comment "{RULE_COMMENT}"
        meta l4proto udp return comment "{RULE_COMMENT}"
        tcp sport 1000-1003 tcp dport {{ 80, 443, 8000-8007 }} return comment "{RULE_COMMENT}"
    }}
}}
""",
        )

        found = rules(namespace)
        assert len(found) == 6, found

        tcp = found[0]
        udp = found[1]
        icmp = found[2]
        tcp_only = found[3]
        udp_only = found[4]
        bundle = found[5]


        expected_tcp = [
            match(
                {"payload": {"protocol": "ip", "field": "saddr"}},
                {"prefix": {"addr": "192.0.2.0", "len": 24}},
            ),
            match(
                {"payload": {"protocol": "ip", "field": "daddr"}},
                "198.51.100.10",
            ),
            match({"payload": {"protocol": "tcp", "field": "sport"}}, 12345),
            match({"payload": {"protocol": "tcp", "field": "dport"}}, 443),
            {"return": None},
        ]
        expected_udp = [
            match({"payload": {"protocol": "udp", "field": "sport"}}, 5353),
            match({"payload": {"protocol": "udp", "field": "dport"}}, 53),
            {"drop": None},
        ]
        expected_icmp = [
            match({"meta": {"key": "l4proto"}}, "icmp"),
            {"return": None},
        ]
        expected_tcp_only = [
            match({"meta": {"key": "l4proto"}}, "tcp"),
            {"return": None},
        ]
        expected_udp_only = [
            match({"meta": {"key": "l4proto"}}, "udp"),
            {"return": None},
        ]
        expected_bundle = [
            match(
                {"payload": {"protocol": "tcp", "field": "sport"}},
                {"range": [1000, 1003]},
            ),
            match(
                {"payload": {"protocol": "tcp", "field": "dport"}},
                {
                    "set": [
                        80,
                        443,
                        {"range": [8000, 8007]},
                    ]
                },
            ),
            {"return": None},
        ]

        assert tcp.get("expr") == expected_tcp, tcp
        assert udp.get("expr") == expected_udp, udp
        assert icmp.get("expr") == expected_icmp, icmp
        assert tcp_only.get("expr") == expected_tcp_only, tcp_only
        assert udp_only.get("expr") == expected_udp_only, udp_only
        assert bundle.get("expr") == expected_bundle, bundle
        assert all(rule.get("comment") == RULE_COMMENT for rule in found), found

        print("EXP042_TCP_JSON=" + json.dumps(tcp, sort_keys=True))
        print("EXP042_UDP_JSON=" + json.dumps(udp, sort_keys=True))
        print("EXP042_ICMP_JSON=" + json.dumps(icmp, sort_keys=True))
        print("EXP042_TCP_ONLY_JSON=" + json.dumps(tcp_only, sort_keys=True))
        print("EXP042_UDP_ONLY_JSON=" + json.dumps(udp_only, sort_keys=True))
        print("EXP042_PORT_BUNDLE_JSON=" + json.dumps(bundle, sort_keys=True))
        print("EXP042_IPV4_SOURCE_PREFIX=1")
        print("EXP042_IPV4_DESTINATION_32=1")
        print("EXP042_META_L4PROTO=1")
        print("EXP042_TCP_PORTS=1")
        print("EXP042_UDP_PORTS=1")
        print("EXP042_PORT_BUNDLE=1")
        print("EXP-042 Device firewall predicate JSON: PASS")
        return 0
    finally:
        run("ip", "netns", "del", namespace, check=False)


if __name__ == "__main__":
    sys.exit(main())
