from __future__ import annotations

"""EXP-036: prefix-scoped ESTABLISHED/RELATED return primitive on real Linux."""

import json
import os
import subprocess


OWNER = "vpn-gate:ng3:owner-v1"
FORWARD_OWNER = "vpn-gate:ng3:payload-forward-v1"
NEW_OWNER = "vpn-gate:ng3:payload-forward-new-v1"
RETURN_OWNER = "vpn-gate:ng3:payload-forward-return-v1"
TEST_OUTSIDE_OWNER = "vpn-gate:exp036:outside-new"


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
    value = json.loads(
        ns(namespace, "ip", "-j", "link", "show", "dev", name).stdout
    )
    assert isinstance(value, list) and len(value) == 1, value
    index = value[0].get("ifindex")
    assert type(index) is int and index > 0, value
    return index


def add_pair(left_ns: str, right_ns: str, left_if: str, right_if: str) -> None:
    run("ip", "link", "add", left_if, "type", "veth", "peer", "name", right_if)
    run("ip", "link", "set", left_if, "netns", left_ns)
    run("ip", "link", "set", right_if, "netns", right_ns)


def set_up(namespace: str, ifname: str, address: str) -> None:
    ns(namespace, "ip", "addr", "add", address, "dev", ifname)
    ns(namespace, "ip", "link", "set", ifname, "up")


def forward_rules(namespace: str) -> list[dict]:
    value = json.loads(
        ns(
            namespace, "nft", "-j", "list", "chain",
            "ip", "vpn_gate", "payload_forward",
        ).stdout
    )
    return [
        row["rule"]
        for row in value.get("nftables", [])
        if isinstance(row, dict) and isinstance(row.get("rule"), dict)
    ]


def rules_by_comment(namespace: str, comment: str) -> list[dict]:
    return [
        rule for rule in forward_rules(namespace)
        if rule.get("comment") == comment
    ]


def counter(rule: dict) -> int:
    values = [
        expr["counter"]["packets"]
        for expr in rule.get("expr", [])
        if isinstance(expr, dict)
        and isinstance(expr.get("counter"), dict)
        and type(expr["counter"].get("packets")) is int
    ]
    assert len(values) == 1, rule
    return values[0]


def rule_by_handle(namespace: str, handle: int) -> dict:
    found = [rule for rule in forward_rules(namespace) if rule.get("handle") == handle]
    assert len(found) == 1, (handle, found)
    return found[0]


def add_outbound_new(namespace: str, host_if: int, vpn_if: int) -> int:
    nft_script(
        namespace,
        (
            "add rule ip vpn_gate payload_forward "
            "ct state new "
            f"meta iif {host_if} meta oif {vpn_if} "
            "ip daddr 10.36.1.0/24 "
            f'counter accept comment "{NEW_OWNER}"\n'
        ),
    )
    rules = rules_by_comment(namespace, NEW_OWNER)
    return max(rule["handle"] for rule in rules)


def add_return(namespace: str, vpn_if: int, host_if: int) -> int:
    nft_script(
        namespace,
        (
            "add rule ip vpn_gate payload_forward "
            "ct state established,related "
            f"meta iif {vpn_if} meta oif {host_if} "
            "ip saddr 10.36.1.0/24 "
            f'counter accept comment "{RETURN_OWNER}"\n'
        ),
    )
    rules = rules_by_comment(namespace, RETURN_OWNER)
    return max(rule["handle"] for rule in rules)


def ping(namespace: str, destination: str, source: str | None = None) -> bool:
    argv = ["ping", "-n", "-c", "1", "-W", "1"]
    if source is not None:
        argv.extend(("-I", source))
    argv.append(destination)
    return ns(namespace, *argv, check=False).returncode == 0


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-036 requires root")

    suffix = str(os.getpid())
    gateway = f"vpng-e36-g-{suffix}"
    host = f"vpng-e36-h-{suffix}"
    vpn = f"vpng-e36-v-{suffix}"
    created: list[str] = []

    try:
        for namespace in (gateway, host, vpn):
            run("ip", "netns", "add", namespace)
            created.append(namespace)
            ns(namespace, "ip", "link", "set", "lo", "up")

        add_pair(host, gateway, "hpeer", "host0")
        add_pair(vpn, gateway, "vpeer", "vpn0")

        set_up(host, "hpeer", "10.36.0.2/24")
        for addr in ("10.36.0.3/24", "10.36.0.4/24", "10.36.0.5/24"):
            ns(host, "ip", "addr", "add", addr, "dev", "hpeer")
        set_up(gateway, "host0", "10.36.0.1/24")

        set_up(vpn, "vpeer", "10.36.1.2/24")
        ns(vpn, "ip", "addr", "add", "10.36.9.2/32", "dev", "vpeer")
        set_up(gateway, "vpn0", "10.36.1.1/24")

        ns(host, "ip", "route", "add", "10.36.1.0/24", "via", "10.36.0.1")
        ns(host, "ip", "route", "add", "10.36.9.2/32", "via", "10.36.0.1")
        ns(vpn, "ip", "route", "add", "10.36.0.0/24", "via", "10.36.1.1")
        ns(gateway, "ip", "route", "add", "10.36.9.2/32", "dev", "vpn0")
        ns(gateway, "sysctl", "-w", "net.ipv4.ip_forward=1")

        nft_script(
            gateway,
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

        host_if = ifindex(gateway, "host0")
        old_vpn_if = ifindex(gateway, "vpn0")
        old_new_handle = add_outbound_new(gateway, host_if, old_vpn_if)
        old_return_handle = add_return(gateway, old_vpn_if, host_if)

        old_return = rule_by_handle(gateway, old_return_handle)
        print(
            "EXP036_RETURN_RULE_JSON="
            + json.dumps(old_return, sort_keys=True)
        )

        # Fully scoped NEW + return pair produces a real bidirectional ICMP flow.
        before_return = counter(old_return)
        assert ping(host, "10.36.1.2"), "scoped outbound + return pair did not pass ping"
        after_return = counter(rule_by_handle(gateway, old_return_handle))
        assert after_return - before_return == 1, (before_return, after_return)

        # Unsolicited reverse NEW is not return traffic.
        reverse_before = counter(rule_by_handle(gateway, old_return_handle))
        assert not ping(vpn, "10.36.0.5"), "unsolicited reverse NEW unexpectedly passed"
        reverse_after = counter(rule_by_handle(gateway, old_return_handle))
        assert reverse_after == reverse_before, (reverse_before, reverse_after)

        # Permit a test-only outbound NEW to an address outside the Profile prefix.
        # Its reply is ESTABLISHED but must not match the prefix-scoped return rule.
        nft_script(
            gateway,
            (
                "add rule ip vpn_gate payload_forward "
                "ct state new "
                f"meta iif {host_if} meta oif {old_vpn_if} "
                "ip daddr 10.36.9.2/32 "
                f'counter accept comment "{TEST_OUTSIDE_OWNER}"\n'
            ),
        )
        outside_before = counter(rule_by_handle(gateway, old_return_handle))
        assert not ping(host, "10.36.9.2", source="10.36.0.3"), (
            "outside-prefix reply unexpectedly passed scoped return rule"
        )
        outside_after = counter(rule_by_handle(gateway, old_return_handle))
        assert outside_after == outside_before, (outside_before, outside_after)

        # Replace vpn0 with the same name and a fresh ifindex.
        ns(gateway, "ip", "link", "del", "vpn0")
        run("ip", "link", "add", "vpeer", "type", "veth", "peer", "name", "vpn0")
        run("ip", "link", "set", "vpeer", "netns", vpn)
        run("ip", "link", "set", "vpn0", "netns", gateway)
        set_up(vpn, "vpeer", "10.36.1.2/24")
        ns(vpn, "ip", "addr", "add", "10.36.9.2/32", "dev", "vpeer")
        set_up(gateway, "vpn0", "10.36.1.1/24")
        ns(vpn, "ip", "route", "replace", "10.36.0.0/24", "via", "10.36.1.1")
        ns(gateway, "ip", "route", "replace", "10.36.9.2/32", "dev", "vpn0")
        new_vpn_if = ifindex(gateway, "vpn0")
        assert new_vpn_if != old_vpn_if, (old_vpn_if, new_vpn_if)

        stale_return = rule_by_handle(gateway, old_return_handle)
        print(
            "EXP036_STALE_RETURN_AFTER_REPLACEMENT_JSON="
            + json.dumps(stale_return, sort_keys=True)
        )

        # Add only a fresh NEW rule. The stale old return rule must not admit reply.
        fresh_new_handle = add_outbound_new(gateway, host_if, new_vpn_if)
        stale_before = counter(rule_by_handle(gateway, old_return_handle))
        assert not ping(host, "10.36.1.2", source="10.36.0.4"), (
            "same-name replacement inherited stale return rule"
        )
        stale_after = counter(rule_by_handle(gateway, old_return_handle))
        assert stale_after == stale_before, (stale_before, stale_after)

        # Add current reverse rule and verify a fresh tuple succeeds.
        fresh_return_handle = add_return(gateway, new_vpn_if, host_if)
        fresh_before = counter(rule_by_handle(gateway, fresh_return_handle))
        assert ping(host, "10.36.1.2", source="10.36.0.5"), (
            "fresh return primitive did not restore current flow"
        )
        fresh_after = counter(rule_by_handle(gateway, fresh_return_handle))
        assert fresh_after - fresh_before == 1, (fresh_before, fresh_after)

        print(f"EXP036_HOST_IFINDEX={host_if}")
        print(f"EXP036_OLD_VPN_IFINDEX={old_vpn_if}")
        print(f"EXP036_NEW_VPN_IFINDEX={new_vpn_if}")
        print(f"EXP036_OLD_NEW_HANDLE={old_new_handle}")
        print(f"EXP036_FRESH_NEW_HANDLE={fresh_new_handle}")
        print(f"EXP036_OLD_RETURN_HANDLE={old_return_handle}")
        print(f"EXP036_FRESH_RETURN_HANDLE={fresh_return_handle}")
        print("EXP036_UNSOLICITED_REVERSE_NEW_PASSED=0")
        print("EXP036_OUTSIDE_PREFIX_RETURN_PASSED=0")
        print("EXP036_STALE_RETURN_MATCHED=0")
        print("EXP-036 prefix-scoped stateful return: PASS")
        return 0
    finally:
        for namespace in reversed(created):
            run("ip", "netns", "del", namespace, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
