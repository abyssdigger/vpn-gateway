#!/usr/bin/env python3
"""EXP-061: stack-side established-flow return affinity across host boundary."""

from __future__ import annotations

import os
import subprocess


PID = os.getpid()
A = f"vng55a-{PID}"
B = f"vng55b-{PID}"
STACK = f"vng55s-{PID}"
HOST = f"vng55h-{PID}"
LAN = f"vng55l-{PID}"

A_S, S_A = "e55as", "e55sa"
B_S, S_B = "e55bs", "e55sb"
S_H, H_S = "e55sh", "e55hs"
H_L, L_H = "e55hl", "e55lh"

REMOTE = "10.0.0.2"
LAN_IP = "192.0.2.2"


def run(*args: str, check: bool = True):
    return subprocess.run(
        args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check
    )


def ns(name: str, *args: str, check: bool = True):
    return run("ip", "netns", "exec", name, *args, check=check)


def add_ns(name: str):
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def del_ns(name: str):
    run("ip", "netns", "del", name, check=False)


def veth(left_ns, left_if, right_ns, right_if):
    run("ip", "link", "add", left_if, "type", "veth", "peer", "name", right_if)
    run("ip", "link", "set", left_if, "netns", left_ns)
    run("ip", "link", "set", right_if, "netns", right_ns)


def addr(name, interface, cidr):
    ns(name, "ip", "addr", "add", cidr, "dev", interface)
    ns(name, "ip", "link", "set", interface, "up")


def setup():
    for name in (A, B, STACK, HOST, LAN):
        add_ns(name)

    veth(A, A_S, STACK, S_A)
    veth(B, B_S, STACK, S_B)
    veth(STACK, S_H, HOST, H_S)
    veth(HOST, H_L, LAN, L_H)

    addr(A, A_S, "172.16.10.2/30")
    ns(A, "ip", "addr", "add", f"{REMOTE}/32", "dev", "lo")
    addr(STACK, S_A, "172.16.10.1/30")

    addr(B, B_S, "172.16.20.2/30")
    addr(STACK, S_B, "172.16.20.1/30")

    addr(STACK, S_H, "198.18.0.2/30")
    addr(HOST, H_S, "198.18.0.1/30")

    addr(HOST, H_L, "192.0.2.1/30")
    addr(LAN, L_H, "192.0.2.2/30")

    ns(STACK, "sysctl", "-qw", "net.ipv4.ip_forward=1")
    ns(HOST, "sysctl", "-qw", "net.ipv4.ip_forward=1")
    # Strict reverse-path filtering would reject the intentionally asymmetric
    # source before the return-affinity mechanism is exercised.
    for name in (STACK, HOST):
        ns(name, "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=0")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.default.rp_filter=0")
    for interface in (S_A, S_B, S_H):
        ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{interface}.rp_filter=0")
    for interface in (H_S, H_L):
        ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{interface}.rp_filter=0")

    ns(A, "ip", "route", "add", "192.0.2.0/30", "via", "172.16.10.1", "dev", A_S)

    ns(STACK, "ip", "route", "add", "192.0.2.0/30", "via", "198.18.0.1", "dev", S_H)
    ns(STACK, "ip", "route", "add", "10.0.0.0/16", "via", "172.16.10.2", "dev", S_A)
    ns(STACK, "ip", "route", "add", "10.0.0.0/24", "via", "172.16.20.2", "dev", S_B)

    ns(LAN, "ip", "route", "add", "default", "via", "192.0.2.1", "dev", L_H)

    # EXP-053-style host return steering: no remote route in host main.
    ns(HOST, "ip", "route", "add", "default", "via", "198.18.0.2", "dev", H_S, "table", "1053")
    ns(HOST, "ip", "rule", "add", "priority", "1053", "fwmark", "0x53", "lookup", "1053")
    host_nft = f"""
table inet exp061_host {{
  chain prerouting {{
    type filter hook prerouting priority mangle; policy accept;
    iifname "{H_S}" ip saddr 10.0.0.0/8 ct state new ct mark set 0x53
    iifname "{H_L}" ct mark 0x53 meta mark set ct mark
  }}
}}
"""
    completed = subprocess.run(
        ("ip", "netns", "exec", HOST, "nft", "-f", "-"),
        input=host_nft,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)


def install_stack_affinity():
    ns(STACK, "ip", "route", "add", "10.0.0.0/8", "via", "172.16.10.2", "dev", S_A, "table", "1155")
    ns(STACK, "ip", "rule", "add", "priority", "1155", "fwmark", "0xa1", "lookup", "1155")
    script = f"""
table inet exp061_stack {{
  chain prerouting {{
    type filter hook prerouting priority mangle; policy accept;
    iifname "{S_A}" ip saddr 10.0.0.0/16 ct state new ct mark set 0xa1
    iifname "{S_H}" ct mark 0xa1 meta mark set ct mark
  }}
}}
"""
    completed = subprocess.run(
        ("ip", "netns", "exec", STACK, "nft", "-f", "-"),
        input=script,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)


def remove_stack_affinity():
    ns(STACK, "nft", "delete", "table", "inet", "exp061_stack", check=False)
    ns(STACK, "ip", "rule", "del", "priority", "1155", "fwmark", "0xa1", "lookup", "1155", check=False)
    ns(STACK, "ip", "route", "flush", "table", "1155", check=False)


def flush_conntrack():
    for name in (STACK, HOST):
        ns(name, "conntrack", "-F", check=False)


def ping(expect_success: bool):
    result = ns(
        A, "ping", "-I", REMOTE, "-c", "1", "-W", "1", LAN_IP, check=False
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(f"ping failed: {result.stdout} {result.stderr}")
    if not expect_success and result.returncode == 0:
        raise AssertionError("ping unexpectedly succeeded")


def main():
    try:
        setup()

        lookup = ns(STACK, "ip", "-4", "route", "get", REMOTE).stdout
        if S_B not in lookup or "172.16.20.2" not in lookup:
            raise AssertionError(f"ordinary lookup did not select /24 channel B: {lookup!r}")
        print("EXP061_MORE_SPECIFIC_BASELINE=PASS")

        host_routes = ns(HOST, "ip", "-4", "route", "show", "table", "main").stdout
        if "10.0.0.0" in host_routes:
            raise AssertionError(f"host main unexpectedly contains remote route: {host_routes!r}")
        print("EXP061_HOST_NO_REMOTE_ROUTE=PASS")

        flush_conntrack()
        ping(False)
        print("EXP061_WITHOUT_STACK_AFFINITY_FAILS=PASS")

        flush_conntrack()
        install_stack_affinity()
        ping(True)
        print("EXP061_STACK_AFFINITY_RETURN=PASS")

        remove_stack_affinity()
        flush_conntrack()
        ping(False)
        print("EXP061_AFFINITY_REMOVAL_RESTORES_FAILURE=PASS")

        print("EXP061_RESULT=PASS")
        return 0
    finally:
        for name in (LAN, HOST, STACK, B, A):
            del_ns(name)


if __name__ == "__main__":
    raise SystemExit(main())
