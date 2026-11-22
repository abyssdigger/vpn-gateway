#!/usr/bin/env python3
"""EXP-083: one atomic Private-network nft gate for protective-mode IPv4 containment."""

from __future__ import annotations

import json
import os
import subprocess
import sys


PID = os.getpid()
ORD = f"v83o-{PID}"
HOST = f"v83h-{PID}"
STACK = f"v83s-{PID}"
VPN1 = f"v83a-{PID}"
VPN2 = f"v83b-{PID}"

OH = "e83oh"
HO = "e83ho"
BH = "vpng0"
BS = "stack0"
SA = "e83sa"
AS = "e83as"
SB = "e83sb"
BS2 = "e83bs"

ORD_IP = "10.83.1.2"
HOST_ORD = "10.83.1.1"
HOST_BOUNDARY = "100.64.83.1"
STACK_BOUNDARY = "100.64.83.2"
STACK_A = "198.18.83.1"
VPN1_LINK = "198.18.83.2"
STACK_B = "198.18.83.5"
VPN2_LINK = "198.18.83.6"
VPN1_TARGET = "203.0.113.83"
VPN2_TARGET = "203.0.113.84"
NFT_TABLE = "vpng_protective83"


def run(*args: str, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def ns(name: str, *args: str, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return run("ip", "netns", "exec", name, *args, check=check, input_text=input_text)


def add_ns(name: str) -> None:
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def pair(a: str, b: str, na: str, nb: str) -> None:
    run("ip", "link", "add", a, "type", "veth", "peer", "name", b)
    run("ip", "link", "set", a, "netns", na)
    run("ip", "link", "set", b, "netns", nb)


def ping(namespace: str, target: str) -> bool:
    return ns(
        namespace,
        "ping",
        "-n",
        "-c",
        "1",
        "-W",
        "1",
        target,
        check=False,
    ).returncode == 0


def setup() -> None:
    for name in (ORD, HOST, STACK, VPN1, VPN2):
        add_ns(name)
    for a, b, na, nb in (
        (OH, HO, ORD, HOST),
        (BH, BS, HOST, STACK),
        (SA, AS, STACK, VPN1),
        (SB, BS2, STACK, VPN2),
    ):
        pair(a, b, na, nb)

    ns(ORD, "ip", "addr", "add", f"{ORD_IP}/24", "dev", OH)
    ns(HOST, "ip", "addr", "add", f"{HOST_ORD}/24", "dev", HO)
    ns(HOST, "ip", "addr", "add", f"{HOST_BOUNDARY}/30", "dev", BH)
    ns(STACK, "ip", "addr", "add", f"{STACK_BOUNDARY}/30", "dev", BS)
    ns(STACK, "ip", "addr", "add", f"{STACK_A}/30", "dev", SA)
    ns(VPN1, "ip", "addr", "add", f"{VPN1_LINK}/30", "dev", AS)
    ns(STACK, "ip", "addr", "add", f"{STACK_B}/30", "dev", SB)
    ns(VPN2, "ip", "addr", "add", f"{VPN2_LINK}/30", "dev", BS2)

    for name, interfaces in (
        (ORD, (OH,)),
        (HOST, (HO, BH)),
        (STACK, (BS, SA, SB)),
        (VPN1, (AS,)),
        (VPN2, (BS2,)),
    ):
        for interface in interfaces:
            ns(name, "ip", "link", "set", interface, "up")

    ns(VPN1, "ip", "addr", "add", f"{VPN1_TARGET}/32", "dev", "lo")
    ns(VPN2, "ip", "addr", "add", f"{VPN2_TARGET}/32", "dev", "lo")

    for prefix in (
        f"{STACK_BOUNDARY}/32",
        f"{VPN1_TARGET}/32",
        f"{VPN2_TARGET}/32",
        "198.18.83.0/30",
        "198.18.83.4/30",
    ):
        ns(ORD, "ip", "route", "add", prefix, "via", HOST_ORD)

    for prefix in (
        f"{VPN1_TARGET}/32",
        f"{VPN2_TARGET}/32",
        "198.18.83.0/30",
        "198.18.83.4/30",
    ):
        ns(HOST, "ip", "route", "add", prefix, "via", STACK_BOUNDARY, "dev", BH)

    ns(STACK, "ip", "route", "add", f"{VPN1_TARGET}/32", "via", VPN1_LINK, "dev", SA)
    ns(STACK, "ip", "route", "add", f"{VPN2_TARGET}/32", "via", VPN2_LINK, "dev", SB)
    ns(STACK, "ip", "route", "add", "10.83.1.0/24", "via", HOST_BOUNDARY, "dev", BS)

    ns(VPN1, "ip", "route", "add", "10.83.1.0/24", "via", STACK_A)
    ns(VPN2, "ip", "route", "add", "10.83.1.0/24", "via", STACK_B)
    ns(VPN1, "ip", "route", "add", f"{VPN2_TARGET}/32", "via", STACK_A)
    ns(VPN2, "ip", "route", "add", f"{VPN1_TARGET}/32", "via", STACK_B)
    ns(VPN1, "ip", "route", "add", "198.18.83.4/30", "via", STACK_A)
    ns(VPN2, "ip", "route", "add", "198.18.83.0/30", "via", STACK_B)

    for name in (HOST, STACK):
        ns(name, "sysctl", "-qw", "net.ipv4.ip_forward=1")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=0")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.default.rp_filter=0")


def path_state() -> dict[str, bool]:
    return {
        "ordinary_to_private_local": ping(ORD, STACK_BOUNDARY),
        "private_local_to_ordinary": ping(STACK, ORD_IP),
        "ordinary_to_vpn": ping(ORD, VPN1_TARGET),
        "vpn_to_ordinary": ping(VPN1, ORD_IP),
        "vpn_to_vpn": ping(VPN1, VPN2_TARGET),
    }


def assert_paths(expected: bool) -> None:
    state = path_state()
    assert all(value is expected for value in state.values()), state


def install_gate() -> None:
    rules = f"""
table inet {NFT_TABLE} {{
    chain input {{
        type filter hook input priority -500; policy accept;
        iifname "{BS}" meta nfproto ipv4 drop
    }}
    chain output {{
        type filter hook output priority -500; policy accept;
        oifname "{BS}" meta nfproto ipv4 drop
    }}
    chain forward {{
        type filter hook forward priority -500; policy accept;
        meta nfproto ipv4 drop
    }}
}}
"""
    ns(STACK, "nft", "-f", "-", input_text=rules)
    shown = ns(STACK, "nft", "list", "table", "inet", NFT_TABLE).stdout
    assert f"table inet {NFT_TABLE}" in shown
    assert "hook input" in shown and "hook output" in shown and "hook forward" in shown


def remove_gate() -> None:
    ns(STACK, "nft", "delete", "table", "inet", NFT_TABLE)


def main() -> int:
    if os.geteuid() != 0:
        print("EXP083_RESULT=SKIP root required")
        return 77

    try:
        setup()
        assert_paths(True)
        print("EXP083_BASELINE_PATHS=PASS", flush=True)

        before_links = json.loads(ns(STACK, "ip", "-j", "link", "show").stdout)
        before_routes = json.loads(ns(STACK, "ip", "-j", "-4", "route", "show").stdout)
        before_forward = ns(STACK, "sysctl", "-n", "net.ipv4.ip_forward").stdout.strip()
        assert before_forward == "1"

        install_gate()
        assert_paths(False)
        print("EXP083_PROTECTIVE_PATHS_BLOCKED=PASS", flush=True)

        after_links = json.loads(ns(STACK, "ip", "-j", "link", "show").stdout)
        after_routes = json.loads(ns(STACK, "ip", "-j", "-4", "route", "show").stdout)
        after_forward = ns(STACK, "sysctl", "-n", "net.ipv4.ip_forward").stdout.strip()
        assert before_links == after_links
        assert before_routes == after_routes
        assert after_forward == "1"
        print("EXP083_RUNTIME_STATE_PRESERVED=PASS", flush=True)

        remove_gate()
        assert_paths(True)
        print("EXP083_RESTORE_PATHS=PASS", flush=True)
        print("EXP083_RESULT=PASS", flush=True)
        return 0
    finally:
        for name in (VPN2, VPN1, STACK, HOST, ORD):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
