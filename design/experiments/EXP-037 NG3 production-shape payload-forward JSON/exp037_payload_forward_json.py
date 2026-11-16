from __future__ import annotations

"""EXP-037: final no-counter /32 payload_forward JSON representation."""

import ipaddress
import json
import os
import subprocess


OWNER = "vpn-gate:ng3:owner-v1"
FORWARD_OWNER = "vpn-gate:ng3:payload-forward-v1"
NEW_OWNER = "vpn-gate:ng3:payload-forward-new-v1"
RETURN_OWNER = "vpn-gate:ng3:payload-forward-return-v1"
TARGET = ipaddress.IPv4Address("10.37.1.2")


def run(*args: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        args, check=check, input=input_text, text=True, capture_output=True,
    )


def ns(namespace: str, *args: str, check: bool = True,
       input_text: str | None = None):
    return run(
        "ip", "netns", "exec", namespace, *args,
        check=check, input_text=input_text,
    )


def ifindex(namespace: str, name: str) -> int:
    data = json.loads(
        ns(namespace, "ip", "-j", "link", "show", "dev", name).stdout
    )
    assert isinstance(data, list) and len(data) == 1, data
    value = data[0].get("ifindex")
    assert type(value) is int and value > 0, data
    return value


def nft_script(namespace: str, script: str) -> None:
    ns(namespace, "nft", "-f", "-", input_text=script)


def rule_by_comment(namespace: str, comment: str) -> dict:
    data = json.loads(
        ns(
            namespace, "nft", "-j", "list", "chain",
            "ip", "vpn_gate", "payload_forward",
        ).stdout
    )
    rules = [
        row["rule"]
        for row in data.get("nftables", [])
        if isinstance(row, dict)
        and isinstance(row.get("rule"), dict)
        and row["rule"].get("comment") == comment
    ]
    assert len(rules) == 1, rules
    return rules[0]


def remote_operand(rule: dict, field: str):
    matches = [
        expr["match"]
        for expr in rule.get("expr", [])
        if isinstance(expr, dict)
        and isinstance(expr.get("match"), dict)
        and expr["match"].get("left")
        == {"payload": {"protocol": "ip", "field": field}}
    ]
    assert len(matches) == 1, rule
    return matches[0].get("right")


def assert_unambiguous_32(value) -> str:
    if isinstance(value, str):
        parsed = ipaddress.IPv4Address(value)
        assert parsed == TARGET, value
        return "address-string"
    if isinstance(value, dict) and set(value) == {"prefix"}:
        prefix = value["prefix"]
        assert isinstance(prefix, dict), value
        assert prefix.get("addr") == str(TARGET), value
        assert prefix.get("len") == 32, value
        return "prefix-object"
    raise AssertionError(f"unsupported /32 nft JSON operand: {value!r}")


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-037 requires root")

    namespace = f"vpng-exp037-{os.getpid()}"
    try:
        run("ip", "netns", "add", namespace)
        ns(namespace, "ip", "link", "set", "lo", "up")
        ns(namespace, "ip", "link", "add", "host0", "type", "veth",
           "peer", "name", "hostpeer")
        ns(namespace, "ip", "link", "add", "vpn0", "type", "veth",
           "peer", "name", "vpnpeer")
        host_if = ifindex(namespace, "host0")
        vpn_if = ifindex(namespace, "vpn0")

        nft_script(
            namespace,
            (
                "table ip vpn_gate {\n"
                f'  comment "{OWNER}"\n'
                "  chain payload_forward {\n"
                "    type filter hook forward priority 0; policy drop;\n"
                f'    comment "{FORWARD_OWNER}"\n'
                "  }\n"
                "}\n"
                "add rule ip vpn_gate payload_forward "
                "ct state new "
                f"meta iif {host_if} meta oif {vpn_if} "
                f"ip daddr {TARGET}/32 "
                f'accept comment "{NEW_OWNER}"\n'
                "add rule ip vpn_gate payload_forward "
                "ct state established,related "
                f"meta iif {vpn_if} meta oif {host_if} "
                f"ip saddr {TARGET}/32 "
                f'accept comment "{RETURN_OWNER}"\n'
            ),
        )

        new_rule = rule_by_comment(namespace, NEW_OWNER)
        return_rule = rule_by_comment(namespace, RETURN_OWNER)

        assert len(new_rule.get("expr", [])) == 5, new_rule
        assert len(return_rule.get("expr", [])) == 5, return_rule
        assert not any("counter" in expr for expr in new_rule["expr"]), new_rule
        assert not any("counter" in expr for expr in return_rule["expr"]), return_rule
        assert new_rule["expr"][-1] == {"accept": None}, new_rule
        assert return_rule["expr"][-1] == {"accept": None}, return_rule

        new_form = assert_unambiguous_32(remote_operand(new_rule, "daddr"))
        return_form = assert_unambiguous_32(remote_operand(return_rule, "saddr"))
        assert new_form == return_form, (new_form, return_form)

        print("EXP037_NEW_RULE_JSON=" + json.dumps(new_rule, sort_keys=True))
        print(
            "EXP037_RETURN_RULE_JSON="
            + json.dumps(return_rule, sort_keys=True)
        )
        print(f"EXP037_32_RENDERING={new_form}")
        print("EXP037_COUNTER_PRESENT=0")
        print("EXP-037 production-shape payload_forward JSON: PASS")
        return 0
    finally:
        run("ip", "netns", "del", namespace, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
