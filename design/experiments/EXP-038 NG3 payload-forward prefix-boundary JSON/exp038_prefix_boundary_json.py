from __future__ import annotations

"""EXP-038: nft JSON canonicalization at IPv4 prefix boundaries."""

import json
import os
import subprocess


OWNER = "vpn-gate:ng3:owner-v1"
FORWARD_OWNER = "vpn-gate:ng3:payload-forward-v1"
NEW_OWNER = "vpn-gate:ng3:payload-forward-new-v1"
RETURN_OWNER = "vpn-gate:ng3:payload-forward-return-v1"

PREFIXES = (
    ("p0", "0.0.0.0/0"),
    ("p1", "0.0.0.0/1"),
    ("p31", "10.38.1.2/31"),
    ("p32", "10.38.1.2/32"),
)


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


def nft_script(namespace: str, script: str) -> None:
    ns(namespace, "nft", "-f", "-", input_text=script)


def ifindex(namespace: str, name: str) -> int:
    data = json.loads(
        ns(namespace, "ip", "-j", "link", "show", "dev", name).stdout
    )
    assert isinstance(data, list) and len(data) == 1, data
    value = data[0].get("ifindex")
    assert type(value) is int and value > 0, data
    return value


def rules(namespace: str, comment: str) -> list[dict]:
    data = json.loads(
        ns(
            namespace, "nft", "-j", "list", "chain",
            "ip", "vpn_gate", "payload_forward",
        ).stdout
    )
    return [
        row["rule"]
        for row in data.get("nftables", [])
        if isinstance(row, dict)
        and isinstance(row.get("rule"), dict)
        and row["rule"].get("comment") == comment
    ]


def latest(namespace: str, comment: str) -> dict:
    values = rules(namespace, comment)
    assert values, comment
    return max(values, key=lambda item: item["handle"])


def remote_shape(rule: dict, field: str) -> str:
    matches = [
        expr["match"]
        for expr in rule.get("expr", [])
        if isinstance(expr, dict)
        and isinstance(expr.get("match"), dict)
        and expr["match"].get("left")
        == {"payload": {"protocol": "ip", "field": field}}
    ]
    if not matches:
        return "omitted"
    assert len(matches) == 1, rule
    right = matches[0].get("right")
    if isinstance(right, str):
        return "address-string"
    if isinstance(right, dict) and set(right) == {"prefix"}:
        prefix = right["prefix"]
        assert isinstance(prefix, dict), right
        assert set(prefix) == {"addr", "len"}, prefix
        assert isinstance(prefix["addr"], str), prefix
        assert type(prefix["len"]) is int, prefix
        return "prefix-object"
    raise AssertionError(f"unsupported remote operand: {right!r}")


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-038 requires root")

    namespace = f"vpng-exp038-{os.getpid()}"
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
            ),
        )

        observed: dict[str, tuple[str, str]] = {}
        for label, prefix in PREFIXES:
            nft_script(
                namespace,
                (
                    "add rule ip vpn_gate payload_forward "
                    "ct state new "
                    f"meta iif {host_if} meta oif {vpn_if} "
                    f"ip daddr {prefix} "
                    f'accept comment "{NEW_OWNER}"\n'
                ),
            )
            new_rule = latest(namespace, NEW_OWNER)

            nft_script(
                namespace,
                (
                    "add rule ip vpn_gate payload_forward "
                    "ct state established,related "
                    f"meta iif {vpn_if} meta oif {host_if} "
                    f"ip saddr {prefix} "
                    f'accept comment "{RETURN_OWNER}"\n'
                ),
            )
            return_rule = latest(namespace, RETURN_OWNER)

            assert not any("counter" in expr for expr in new_rule.get("expr", []))
            assert not any("counter" in expr for expr in return_rule.get("expr", []))
            assert new_rule["expr"][-1] == {"accept": None}, new_rule
            assert return_rule["expr"][-1] == {"accept": None}, return_rule

            new_shape = remote_shape(new_rule, "daddr")
            return_shape = remote_shape(return_rule, "saddr")
            assert new_shape == return_shape, (label, new_shape, return_shape)
            observed[label] = (new_shape, return_shape)

            print(
                f"EXP038_NEW_{label.upper()}_JSON="
                + json.dumps(new_rule, sort_keys=True)
            )
            print(
                f"EXP038_RETURN_{label.upper()}_JSON="
                + json.dumps(return_rule, sort_keys=True)
            )
            print(f"EXP038_{label.upper()}_SHAPE={new_shape}")

        assert observed["p1"][0] == "prefix-object", observed
        assert observed["p31"][0] == "prefix-object", observed
        assert observed["p32"][0] == "address-string", observed
        assert observed["p0"][0] in {"omitted", "prefix-object"}, observed

        print("EXP-038 payload_forward prefix-boundary JSON: PASS")
        return 0
    finally:
        run("ip", "netns", "del", namespace, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
