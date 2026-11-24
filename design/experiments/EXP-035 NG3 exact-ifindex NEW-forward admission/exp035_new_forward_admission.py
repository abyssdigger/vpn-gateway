from __future__ import annotations

"""EXP-035: exact-ifindex NEW-flow payload_forward primitive on real Linux."""

import json
import os
import subprocess


OWNER = "vpn-gate:ng3:owner-v1"
FORWARD_OWNER = "vpn-gate:ng3:payload-forward-v1"
RULE_OWNER = "vpn-gate:ng3:payload-forward-new-v1"


def run(*args: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        args,
        check=check,
        input=input_text,
        text=True,
        capture_output=True,
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


def add_pair(
    left_ns: str,
    right_ns: str,
    left_if: str,
    right_if: str,
) -> None:
    run("ip", "link", "add", left_if, "type", "veth", "peer", "name", right_if)
    run("ip", "link", "set", left_if, "netns", left_ns)
    run("ip", "link", "set", right_if, "netns", right_ns)


def set_up(namespace: str, ifname: str, address: str) -> None:
    ns(namespace, "ip", "addr", "add", address, "dev", ifname)
    ns(namespace, "ip", "link", "set", ifname, "up")


def forward_rule(namespace: str) -> dict:
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
    matches = []
    for row in value.get("nftables", []):
        if not isinstance(row, dict) or not isinstance(row.get("rule"), dict):
            continue
        rule = row["rule"]
        if rule.get("comment") == RULE_OWNER:
            matches.append(rule)
    assert len(matches) == 1, matches
    return matches[0]


def packet_counter(rule: dict) -> int:
    counters = [
        item["counter"]
        for item in rule.get("expr", [])
        if isinstance(item, dict) and isinstance(item.get("counter"), dict)
    ]
    assert len(counters) == 1, rule
    packets = counters[0].get("packets")
    assert type(packets) is int and packets >= 0, counters[0]
    return packets


def ping_one(namespace: str, destination: str, *, source: str | None = None) -> None:
    argv = ["ping", "-n", "-c", "1", "-W", "1"]
    if source is not None:
        argv.extend(("-I", source))
    argv.append(destination)
    # Reply is expected to be denied because this experiment admits only NEW
    # forward traffic and deliberately has no return-flow allow primitive.
    ns(namespace, *argv, check=False)


def expect_counter_delta(
    gateway: str,
    source_ns: str,
    destination: str,
    expected_delta: int,
    *,
    source: str | None = None,
) -> None:
    before = packet_counter(forward_rule(gateway))
    ping_one(source_ns, destination, source=source)
    after = packet_counter(forward_rule(gateway))
    assert after - before == expected_delta, (
        destination,
        before,
        after,
        expected_delta,
        forward_rule(gateway),
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-035 requires root")

    suffix = str(os.getpid())
    gateway = f"vpng-e35-g-{suffix}"
    host = f"vpng-e35-h-{suffix}"
    vpn = f"vpng-e35-v-{suffix}"
    alt = f"vpng-e35-a-{suffix}"
    created: list[str] = []

    try:
        for namespace in (gateway, host, vpn, alt):
            run("ip", "netns", "add", namespace)
            created.append(namespace)
            ns(namespace, "ip", "link", "set", "lo", "up")

        add_pair(host, gateway, "hpeer", "host0")
        add_pair(vpn, gateway, "vpeer", "vpn0")
        add_pair(alt, gateway, "apeer", "alt0")

        set_up(host, "hpeer", "10.35.0.2/24")
        ns(host, "ip", "addr", "add", "10.35.0.3/24", "dev", "hpeer")
        set_up(gateway, "host0", "10.35.0.1/24")

        set_up(vpn, "vpeer", "10.35.1.2/24")
        ns(vpn, "ip", "addr", "add", "10.35.9.2/32", "dev", "vpeer")
        set_up(gateway, "vpn0", "10.35.1.1/24")

        set_up(alt, "apeer", "10.35.2.2/24")
        ns(alt, "ip", "addr", "add", "10.35.1.99/32", "dev", "apeer")
        set_up(gateway, "alt0", "10.35.2.1/24")

        ns(host, "ip", "route", "add", "10.35.1.0/24", "via", "10.35.0.1")
        ns(host, "ip", "route", "add", "10.35.9.2/32", "via", "10.35.0.1")
        ns(vpn, "ip", "route", "add", "10.35.0.0/24", "via", "10.35.1.1")
        ns(alt, "ip", "route", "add", "10.35.1.0/24", "via", "10.35.2.1")

        # More-specific routes create isolated negative controls:
        # 10.35.1.99 is inside the allowed prefix but exits via alt0.
        # 10.35.9.2 exits via vpn0 but is outside the allowed prefix.
        ns(gateway, "ip", "route", "add", "10.35.1.99/32", "dev", "alt0")
        ns(gateway, "ip", "route", "add", "10.35.9.2/32", "dev", "vpn0")
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

        # Baseline without allow rule: no request reaches the VPN peer.
        baseline = ns(
            host, "ping", "-n", "-c", "1", "-W", "1", "10.35.1.2",
            check=False,
        )
        assert baseline.returncode != 0, baseline

        host_if = ifindex(gateway, "host0")
        old_vpn_if = ifindex(gateway, "vpn0")
        nft_script(
            gateway,
            (
                "add rule ip vpn_gate payload_forward "
                "ct state new "
                f"meta iif {host_if} meta oif {old_vpn_if} "
                "ip daddr 10.35.1.0/24 "
                f'counter accept comment "{RULE_OWNER}"\n'
            ),
        )

        observed = forward_rule(gateway)
        print("EXP035_FORWARD_RULE_JSON=" + json.dumps(observed, sort_keys=True))

        # Positive NEW path: the request hits the rule exactly once.
        expect_counter_delta(gateway, host, "10.35.1.2", 1)

        # Different ingress, same permitted remote prefix and same vpn0 egress.
        expect_counter_delta(gateway, alt, "10.35.1.2", 0)

        # Same ingress and permitted destination prefix, but different egress.
        expect_counter_delta(gateway, host, "10.35.1.99", 0)

        # Same ingress and vpn0 egress, but destination outside the allowed prefix.
        expect_counter_delta(gateway, host, "10.35.9.2", 0)

        # Same-name replacement must not inherit the old numeric-oif rule.
        ns(gateway, "ip", "link", "del", "vpn0")
        run("ip", "link", "add", "vpeer", "type", "veth", "peer", "name", "vpn0")
        run("ip", "link", "set", "vpeer", "netns", vpn)
        run("ip", "link", "set", "vpn0", "netns", gateway)
        set_up(vpn, "vpeer", "10.35.1.2/24")
        ns(vpn, "ip", "addr", "add", "10.35.9.2/32", "dev", "vpeer")
        set_up(gateway, "vpn0", "10.35.1.1/24")
        ns(vpn, "ip", "route", "replace", "10.35.0.0/24", "via", "10.35.1.1")
        ns(gateway, "ip", "route", "replace", "10.35.9.2/32", "dev", "vpn0")

        new_vpn_if = ifindex(gateway, "vpn0")
        assert new_vpn_if != old_vpn_if, (old_vpn_if, new_vpn_if)
        stale = forward_rule(gateway)
        print(
            "EXP035_STALE_RULE_AFTER_REPLACEMENT_JSON="
            + json.dumps(stale, sort_keys=True)
        )

        # Secondary host source yields a fresh conntrack tuple, so a zero delta
        # demonstrates stale oif identity rather than inherited flow state.
        expect_counter_delta(
            gateway, host, "10.35.1.2", 0, source="10.35.0.3",
        )

        print(f"EXP035_HOST_IIF={host_if}")
        print(f"EXP035_OLD_VPN_OIF={old_vpn_if}")
        print(f"EXP035_NEW_VPN_OIF={new_vpn_if}")
        print("EXP035_OTHER_INGRESS_MATCHED=0")
        print("EXP035_OTHER_EGRESS_MATCHED=0")
        print("EXP035_OUTSIDE_PREFIX_MATCHED=0")
        print("EXP035_STALE_SAME_NAME_MATCHED=0")
        print("EXP-035 exact-ifindex NEW-forward admission: PASS")
        return 0
    finally:
        for namespace in reversed(created):
            run("ip", "netns", "del", namespace, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
