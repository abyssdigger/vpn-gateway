#!/usr/bin/env python3
"""EXP-082: prove a two-barrier Linux lower composition for protective mode."""

from __future__ import annotations

import json
import os
import subprocess
import sys


PID = os.getpid()
ORD = f"v82o-{PID}"
HOST = f"v82h-{PID}"
STACK = f"v82s-{PID}"
VPN1 = f"v82a-{PID}"
VPN2 = f"v82b-{PID}"

OH = "e82oh"
HO = "e82ho"
BH = "vpng0"
BS = "stack0"
SA = "e82sa"
AS = "e82as"
SB = "e82sb"
BS2 = "e82bs"

ORD_IP = "10.82.1.2"
HOST_ORD = "10.82.1.1"
STACK_A = "198.18.82.1"
VPN1_LINK = "198.18.82.2"
STACK_B = "198.18.82.5"
VPN2_LINK = "198.18.82.6"
VPN1_TARGET = "203.0.113.81"
VPN2_TARGET = "203.0.113.82"
NFT_TABLE = "vpng_protective_test"


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


def forwarding(value: int) -> None:
    assert value in (0, 1)
    ns(STACK, "sysctl", "-qw", f"net.ipv4.ip_forward={value}")
    observed = ns(STACK, "sysctl", "-n", "net.ipv4.ip_forward").stdout.strip()
    assert observed == str(value), observed


def install_host_boundary_gate() -> None:
    nft = f"""
table netdev {NFT_TABLE} {{
    chain ingress {{
        type filter hook ingress device \"{BH}\" priority -500; policy accept;
        ether type ip drop
    }}
    chain egress {{
        type filter hook egress device \"{BH}\" priority 500; policy accept;
        ether type ip drop
    }}
}}
"""
    ns(HOST, "nft", "-f", "-", input_text=nft)
    shown = ns(HOST, "nft", "list", "table", "netdev", NFT_TABLE).stdout
    assert f"table netdev {NFT_TABLE}" in shown
    assert 'hook ingress' in shown and 'hook egress' in shown


def remove_host_boundary_gate() -> None:
    ns(HOST, "nft", "delete", "table", "netdev", NFT_TABLE)


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

    ns(ORD, "ip", "route", "add", f"{VPN1_TARGET}/32", "via", HOST_ORD)
    ns(ORD, "ip", "route", "add", f"{VPN2_TARGET}/32", "via", HOST_ORD)
    ns(HOST, "ip", "route", "add", f"{VPN1_TARGET}/32", "dev", BH)
    ns(HOST, "ip", "route", "add", f"{VPN2_TARGET}/32", "dev", BH)
    ns(STACK, "ip", "route", "add", f"{VPN1_TARGET}/32", "via", VPN1_LINK, "dev", SA)
    ns(STACK, "ip", "route", "add", f"{VPN2_TARGET}/32", "via", VPN2_LINK, "dev", SB)

    ns(STACK, "ip", "route", "add", "10.82.1.0/24", "dev", BS)
    ns(VPN1, "ip", "route", "add", "10.82.1.0/24", "via", STACK_A)
    ns(VPN2, "ip", "route", "add", "10.82.1.0/24", "via", STACK_B)
    ns(VPN1, "ip", "route", "add", f"{VPN2_TARGET}/32", "via", STACK_A)
    ns(VPN2, "ip", "route", "add", f"{VPN1_TARGET}/32", "via", STACK_B)

    for name in (HOST, STACK):
        ns(name, "sysctl", "-qw", "net.ipv4.ip_forward=1")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=0")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.default.rp_filter=0")
    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{BH}.proxy_arp=1")
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{BS}.proxy_arp=1")
    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{BH}.rp_filter=0")
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{BS}.rp_filter=0")


def assert_paths(expected: bool) -> None:
    checks = {
        "ordinary_to_vpn": ping(ORD, VPN1_TARGET),
        "vpn_to_ordinary": ping(VPN1, ORD_IP),
        "vpn_to_vpn": ping(VPN1, VPN2_TARGET),
    }
    assert all(value is expected for value in checks.values()), checks


def main() -> int:
    if os.geteuid() != 0:
        print("EXP082_RESULT=SKIP root required")
        return 77

    try:
        setup()
        assert_paths(True)
        print("EXP082_BASELINE_PATHS=PASS", flush=True)

        before_link = json.loads(ns(HOST, "ip", "-j", "link", "show", "dev", BH).stdout)
        before_routes = json.loads(ns(HOST, "ip", "-j", "-4", "route", "show").stdout)

        forwarding(0)
        install_host_boundary_gate()
        assert_paths(False)
        print("EXP082_PROTECTIVE_PATHS_BLOCKED=PASS", flush=True)

        after_link = json.loads(ns(HOST, "ip", "-j", "link", "show", "dev", BH).stdout)
        after_routes = json.loads(ns(HOST, "ip", "-j", "-4", "route", "show").stdout)
        assert before_routes == after_routes, (before_routes, after_routes)
        assert before_link[0]["ifname"] == after_link[0]["ifname"] == BH
        assert "UP" in after_link[0].get("flags", ()), after_link
        print("EXP082_RUNTIME_OBJECTS_PRESERVED=PASS", flush=True)

        remove_host_boundary_gate()
        forwarding(1)
        assert_paths(True)
        print("EXP082_RESTORE_PATHS=PASS", flush=True)
        print("EXP082_RESULT=PASS", flush=True)
        return 0
    finally:
        for name in (VPN2, VPN1, STACK, HOST, ORD):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
