from __future__ import annotations

import json
import os
import subprocess
import sys


TABLE_COMMENT = "vpn-gate:ng3:owner-v1"
FORWARD_COMMENT = "vpn-gate:ng3:payload-forward-v1"
CHILD = "device_fw_exp041"
CHILD_COMMENT = "vpn-gate:ng3:device-fw-child-v1"
JUMP_COMMENT = "vpn-gate:ng3:device-fw-jump-v1"
RULE_COMMENT = "vpn-gate:ng3:device-fw-rule-v1"
REVERSE_COMMENT = "vpn-gate:ng3:device-fw-reverse-v1"
REJECT_COMMENT = "vpn-gate:ng3:device-fw-reject-evidence-v1"
FALLTHROUGH_COMMENT = "vpn-gate:ng3:device-fw-fallthrough-v1"
PROFILE_NEW_COMMENT = "vpn-gate:ng3:payload-forward-new-v1"
PROFILE_RETURN_COMMENT = "vpn-gate:ng3:payload-forward-return-v1"


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
    assert index > 0, index
    return index


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
    value = json.loads(ns(namespace, "nft", "-j", "list", "ruleset").stdout)
    assert isinstance(value, dict), value
    assert isinstance(value.get("nftables"), list), value
    return value


def chain_row(value: dict, chain_name: str) -> dict:
    matches: list[dict] = []
    for row in value["nftables"]:
        if not isinstance(row, dict):
            continue
        chain = row.get("chain")
        if not isinstance(chain, dict):
            continue
        if (
            chain.get("family") == "ip"
            and chain.get("table") == "vpn_gate"
            and chain.get("name") == chain_name
        ):
            matches.append(chain)
    assert len(matches) == 1, matches
    return matches[0]


def rules_in_chain(value: dict, chain_name: str) -> list[dict]:
    result: list[dict] = []
    for row in value["nftables"]:
        if not isinstance(row, dict):
            continue
        rule = row.get("rule")
        if not isinstance(rule, dict):
            continue
        if (
            rule.get("family") == "ip"
            and rule.get("table") == "vpn_gate"
            and rule.get("chain") == chain_name
        ):
            result.append(rule)
    return result


def has_action(rule: dict, action: str) -> bool:
    expr = rule.get("expr")
    assert isinstance(expr, list), rule
    return any(
        isinstance(item, dict) and action in item
        for item in expr
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-041 must run as root")

    suffix = str(os.getpid())
    ordinary = f"vpng-e41-o-{suffix}"
    managed = f"vpng-e41-m-{suffix}"
    vpn = f"vpng-e41-v-{suffix}"
    created: list[str] = []

    o_if = f"e41o-{suffix}"
    m_o_if = f"e41mo-{suffix}"
    m_v_if = f"e41mv-{suffix}"
    v_if = f"e41v-{suffix}"

    try:
        for name in (ordinary, managed, vpn):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        run("ip", "link", "add", o_if, "type", "veth", "peer", "name", m_o_if)
        run("ip", "link", "set", o_if, "netns", ordinary)
        run("ip", "link", "set", m_o_if, "netns", managed)

        run("ip", "link", "add", m_v_if, "type", "veth", "peer", "name", v_if)
        run("ip", "link", "set", m_v_if, "netns", managed)
        run("ip", "link", "set", v_if, "netns", vpn)

        ns(ordinary, "ip", "addr", "add", "10.41.1.2/30", "dev", o_if)
        ns(managed, "ip", "addr", "add", "10.41.1.1/30", "dev", m_o_if)
        ns(managed, "ip", "addr", "add", "10.41.2.1/29", "dev", m_v_if)
        ns(vpn, "ip", "addr", "add", "10.41.2.2/29", "dev", v_if)
        ns(vpn, "ip", "addr", "add", "10.41.2.3/29", "dev", v_if)

        for namespace, interface in (
            (ordinary, o_if),
            (managed, m_o_if),
            (managed, m_v_if),
            (vpn, v_if),
        ):
            ns(namespace, "ip", "link", "set", interface, "up")

        ns(ordinary, "ip", "route", "add", "10.41.2.0/29", "via", "10.41.1.1")
        ns(vpn, "ip", "route", "add", "10.41.1.0/30", "via", "10.41.2.1")
        ns(managed, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")

        host_index = ifindex(managed, m_o_if)
        path_index = ifindex(managed, m_v_if)

        nft_script(
            managed,
            f"""table ip vpn_gate {{
    comment "{TABLE_COMMENT}"
    chain payload_forward {{
        type filter hook forward priority 0; policy drop;
        comment "{FORWARD_COMMENT}"
        meta iif {host_index} meta oif {path_index} jump {CHILD} comment "{JUMP_COMMENT}"
        ct state new meta iif {host_index} meta oif {path_index} ip daddr 10.41.2.0/29 accept comment "{PROFILE_NEW_COMMENT}"
        ct state established,related meta iif {path_index} meta oif {host_index} ip saddr 10.41.2.0/29 accept comment "{PROFILE_RETURN_COMMENT}"
    }}
    chain {CHILD} {{
        comment "{CHILD_COMMENT}"
        ip daddr 10.41.2.2 drop comment "{RULE_COMMENT}"
        ip saddr 10.41.2.0/29 return comment "{REVERSE_COMMENT}"
        drop comment "{FALLTHROUGH_COMMENT}"
    }}
}}
""",
        )

        assert not ping(ordinary, "10.41.2.2"), (
            "Device child drop did not narrow later Profile allow"
        )

        nft_script(
            managed,
            f"""flush chain ip vpn_gate {CHILD}
add rule ip vpn_gate {CHILD} ip daddr 10.41.2.2 return comment "{RULE_COMMENT}"
add rule ip vpn_gate {CHILD} ip saddr 10.41.2.0/29 return comment "{REVERSE_COMMENT}"
add rule ip vpn_gate {CHILD} ip daddr 10.41.2.4 reject comment "{REJECT_COMMENT}"
add rule ip vpn_gate {CHILD} drop comment "{FALLTHROUGH_COMMENT}"
""",
        )

        assert ping(ordinary, "10.41.2.2"), (
            "Device child return did not continue to Profile hard gate"
        )
        assert not ping(ordinary, "10.41.2.3"), (
            "explicit-policy terminal child drop did not fail closed on no match"
        )

        value = ruleset(managed)
        base_rules = rules_in_chain(value, "payload_forward")
        child_chain = chain_row(value, CHILD)
        child_rules = rules_in_chain(value, CHILD)

        assert child_chain.get("comment") == CHILD_COMMENT, child_chain
        assert "hook" not in child_chain, child_chain
        assert "type" not in child_chain, child_chain
        assert "policy" not in child_chain, child_chain

        assert len(base_rules) == 3, base_rules
        assert [rule.get("comment") for rule in base_rules] == [
            JUMP_COMMENT,
            PROFILE_NEW_COMMENT,
            PROFILE_RETURN_COMMENT,
        ], base_rules
        assert has_action(base_rules[0], "jump"), base_rules[0]
        assert not has_action(base_rules[0], "accept"), base_rules[0]
        jump_expr = next(item["jump"] for item in base_rules[0]["expr"] if "jump" in item)
        assert isinstance(jump_expr, dict), jump_expr
        assert jump_expr.get("target") == CHILD, jump_expr

        expected_child_comments = [
            RULE_COMMENT,
            REVERSE_COMMENT,
            REJECT_COMMENT,
            FALLTHROUGH_COMMENT,
        ]
        assert [rule.get("comment") for rule in child_rules] == expected_child_comments, child_rules
        assert has_action(child_rules[0], "return"), child_rules[0]
        assert not has_action(child_rules[0], "accept"), child_rules[0]
        assert has_action(child_rules[1], "return"), child_rules[1]
        assert has_action(child_rules[2], "reject"), child_rules[2]
        assert has_action(child_rules[3], "drop"), child_rules[3]

        print("EXP041_CHILD_CHAIN_JSON=" + json.dumps(child_chain, sort_keys=True))
        print("EXP041_BASE_RULES_JSON=" + json.dumps(base_rules, sort_keys=True))
        print("EXP041_CHILD_RULES_JSON=" + json.dumps(child_rules, sort_keys=True))
        print("EXP041_CHILD_DROP_NARROWS_PROFILE=1")
        print("EXP041_CHILD_RETURN_CONTINUES_TO_PROFILE=1")
        print("EXP041_TERMINAL_NO_MATCH_DROP=1")
        print("EXP041_ORDER_PRESERVED=1")
        print("EXP041_REJECT_JSON_PRIMITIVE=1")
        print("EXP-041 ordered Device firewall child chain: PASS")
        return 0
    finally:
        for name in reversed(created):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
