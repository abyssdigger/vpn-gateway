#!/usr/bin/env python3
"""EXP-078: Linux RPDB facts for scoped peaceful host-routing selectors."""

from __future__ import annotations

import json
import os
import subprocess


PID = os.getpid()
HOST = f"v78h-{PID}"
STACK = f"v78s-{PID}"
LANA = f"v78a-{PID}"
LANB = f"v78b-{PID}"
GW = f"v78g-{PID}"
STATIC = f"v78x-{PID}"
REMOTE = f"v78r-{PID}"

BH, BS = "vpng0", "stack0"
HA, AH = "e78ha", "e78ah"
HB, BH2 = "e78hb", "e78bh"
HU, GU = "e78hu", "e78gu"
HX, XH = "e78hx", "e78xh"
SR, RS = "e78sr", "e78rs"

HOST_A = "10.78.1.1"
LAN_A = "10.78.1.2"
HOST_B = "10.78.2.1"
LAN_B = "10.78.2.2"
HOST_UP = "192.0.2.1"
GW_IP = "192.0.2.2"
HOST_STATIC = "172.18.78.1"
STATIC_GW = "172.18.78.2"
STACK_REMOTE = "198.18.78.1"
REMOTE_LINK = "198.18.78.2"

FULL_TARGET = "8.8.8.8"
STATIC_TARGET = "203.0.113.78"

TABLE = 0x7FFF0004
BYPASS_PRIO = 0x6002
PRESERVE_PRIO = 0x6003
DISPATCH_FIRST = 0x6004
PROTO = 204


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def ns(name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("ip", "netns", "exec", name, *args, check=check)


def add_ns(name: str) -> None:
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def del_ns(name: str) -> None:
    run("ip", "netns", "del", name, check=False)


def pair(a: str, b: str, na: str, nb: str) -> None:
    run("ip", "link", "add", a, "type", "veth", "peer", "name", b)
    run("ip", "link", "set", a, "netns", na)
    run("ip", "link", "set", b, "netns", nb)


def route_get(address: str, *extra: str) -> dict[str, object]:
    rows = json.loads(ns(HOST, "ip", "-j", "-4", "route", "get", address, *extra).stdout)
    assert len(rows) == 1, rows
    return rows[0]


def ping(name: str, target: str, *, source: str | None = None) -> bool:
    args = ["ping", "-n", "-c", "1", "-W", "2"]
    if source is not None:
        args.extend(("-I", source))
    args.append(target)
    return ns(name, *args, check=False).returncode == 0


def setup() -> None:
    for name in (HOST, STACK, LANA, LANB, GW, STATIC, REMOTE):
        add_ns(name)
    for a, b, na, nb in (
        (BH, BS, HOST, STACK),
        (HA, AH, HOST, LANA),
        (HB, BH2, HOST, LANB),
        (HU, GU, HOST, GW),
        (HX, XH, HOST, STATIC),
        (SR, RS, STACK, REMOTE),
    ):
        pair(a, b, na, nb)

    addresses = (
        (HOST, HOST_A, 24, HA),
        (LANA, LAN_A, 24, AH),
        (HOST, HOST_B, 24, HB),
        (LANB, LAN_B, 24, BH2),
        (HOST, HOST_UP, 30, HU),
        (GW, GW_IP, 30, GU),
        (HOST, HOST_STATIC, 30, HX),
        (STATIC, STATIC_GW, 30, XH),
        (STACK, STACK_REMOTE, 30, SR),
        (REMOTE, REMOTE_LINK, 30, RS),
    )
    for name, address, prefix, interface in addresses:
        ns(name, "ip", "addr", "add", f"{address}/{prefix}", "dev", interface)

    for name, interfaces in (
        (HOST, (BH, HA, HB, HU, HX)),
        (STACK, (BS, SR)),
        (LANA, (AH,)),
        (LANB, (BH2,)),
        (GW, (GU,)),
        (STATIC, (XH,)),
        (REMOTE, (RS,)),
    ):
        for interface in interfaces:
            ns(name, "ip", "link", "set", interface, "up")

    # Same full-tunnel target exists behind both candidate exits.
    ns(GW, "ip", "addr", "add", f"{FULL_TARGET}/32", "dev", "lo")
    ns(REMOTE, "ip", "addr", "add", f"{FULL_TARGET}/32", "dev", "lo")
    ns(STATIC, "ip", "addr", "add", f"{STATIC_TARGET}/32", "dev", "lo")

    ns(HOST, "ip", "route", "add", "default", "via", GW_IP, "dev", HU)
    ns(HOST, "ip", "route", "add", "203.0.113.0/24", "via", STATIC_GW, "dev", HX)
    ns(LANA, "ip", "route", "add", "default", "via", HOST_A)
    ns(LANB, "ip", "route", "add", "default", "via", HOST_B)

    ns(STACK, "ip", "route", "add", "default", "via", REMOTE_LINK, "dev", SR)
    ns(STACK, "ip", "route", "add", "10.78.0.0/16", "dev", BS)
    ns(REMOTE, "ip", "route", "add", "10.78.0.0/16", "via", STACK_REMOTE, "dev", RS)
    ns(GW, "ip", "route", "add", "10.78.0.0/16", "via", HOST_UP, "dev", GU)
    ns(STATIC, "ip", "route", "add", "10.78.0.0/16", "via", HOST_STATIC, "dev", XH)

    for name in (HOST, STACK):
        ns(name, "sysctl", "-qw", "net.ipv4.ip_forward=1")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=0")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.default.rp_filter=0")
    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{BH}.proxy_arp=1")
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{BS}.proxy_arp=1")
    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{BH}.rp_filter=0")
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{BS}.rp_filter=0")

    ns(HOST, "ip", "-4", "route", "add", "table", str(TABLE), "default", "dev", BH, "proto", str(PROTO))
    ns(HOST, "ip", "-4", "rule", "add", "priority", str(BYPASS_PRIO), "protocol", str(PROTO), "iif", BH, "lookup", "main")
    ns(HOST, "ip", "-4", "rule", "add", "priority", str(PRESERVE_PRIO), "protocol", str(PROTO), "lookup", "main", "suppress_prefixlength", "0")


def clear_dispatch() -> None:
    rows = json.loads(ns(HOST, "ip", "-j", "-4", "rule", "show").stdout)
    for row in rows:
        priority = row.get("priority")
        if (
            isinstance(priority, int)
            and DISPATCH_FIRST <= priority < DISPATCH_FIRST + 16
            and str(row.get("protocol")) in {str(PROTO), "static"}
        ):
            ns(HOST, "ip", "-4", "rule", "del", "priority", str(priority), check=False)


def add_dispatch(priority: int, *selector: str) -> None:
    ns(
        HOST,
        "ip", "-4", "rule", "add",
        "priority", str(priority),
        "protocol", str(PROTO),
        *selector,
        "lookup", str(TABLE),
    )


def assert_dev(row: dict[str, object], dev: str) -> None:
    assert row.get("dev") == dev, row


def main() -> int:
    if os.geteuid() != 0:
        print("EXP078_RESULT=SKIP root required")
        return 77

    try:
        setup()
        main_before = json.loads(ns(HOST, "ip", "-j", "-4", "route", "show", "table", "main").stdout)

        # :local -> iif lo. Actual host packet must take STACK, forwarded LAN packet ordinary GW.
        add_dispatch(DISPATCH_FIRST, "iif", "lo")
        assert_dev(route_get(FULL_TARGET), BH)
        assert_dev(route_get(FULL_TARGET, "from", LAN_A, "iif", HA), HU)
        assert ping(HOST, FULL_TARGET, source=HOST_A)
        assert ping(LANA, FULL_TARGET)
        print("EXP078_LOCAL_SELECTOR=PASS", flush=True)
        clear_dispatch()

        # Exact ingress selector: LAN-A is helped, LAN-B is not.
        add_dispatch(DISPATCH_FIRST, "iif", HA)
        assert_dev(route_get(FULL_TARGET, "from", LAN_A, "iif", HA), BH)
        assert_dev(route_get(FULL_TARGET, "from", LAN_B, "iif", HB), HU)
        assert ping(LANA, FULL_TARGET)
        assert ping(LANB, FULL_TARGET)
        print("EXP078_EXACT_INGRESS_SELECTOR=PASS", flush=True)

        # Explicit non-default main route wins even for selected ingress.
        static = route_get(STATIC_TARGET, "from", LAN_A, "iif", HA)
        assert_dev(static, HX)
        assert static.get("gateway") == STATIC_GW, static
        assert ping(LANA, STATIC_TARGET)
        print("EXP078_MAIN_NONDEFAULT_PRECEDENCE=PASS", flush=True)
        clear_dispatch()

        # :external -> not iif lo. Local stays ordinary; forwarded ingress is helped.
        add_dispatch(DISPATCH_FIRST, "not", "iif", "lo")
        assert_dev(route_get(FULL_TARGET), HU)
        assert_dev(route_get(FULL_TARGET, "from", LAN_A, "iif", HA), BH)
        assert ping(HOST, FULL_TARGET, source=HOST_A)
        assert ping(LANA, FULL_TARGET)
        print("EXP078_EXTERNAL_SELECTOR=PASS", flush=True)

        # STACK-origin packets must hit higher-priority bypass, not :external dispatch.
        stack_origin = route_get(FULL_TARGET, "from", REMOTE_LINK, "iif", BH)
        assert_dev(stack_origin, HU)
        assert stack_origin.get("gateway") == GW_IP, stack_origin
        print("EXP078_STACK_ORIGIN_BYPASS=PASS", flush=True)
        clear_dispatch()

        # :any -> unconditional dispatch after preserve-main.
        add_dispatch(DISPATCH_FIRST)
        assert_dev(route_get(FULL_TARGET), BH)
        assert_dev(route_get(FULL_TARGET, "from", LAN_A, "iif", HA), BH)
        assert ping(HOST, FULL_TARGET, source=HOST_A)
        assert ping(LANA, FULL_TARGET)
        print("EXP078_ANY_SELECTOR=PASS", flush=True)
        clear_dispatch()

        # Multiple dispatch selectors represent a union; here :local + LAN-A.
        add_dispatch(DISPATCH_FIRST, "iif", "lo")
        add_dispatch(DISPATCH_FIRST + 1, "iif", HA)
        assert_dev(route_get(FULL_TARGET), BH)
        assert_dev(route_get(FULL_TARGET, "from", LAN_A, "iif", HA), BH)
        assert_dev(route_get(FULL_TARGET, "from", LAN_B, "iif", HB), HU)
        print("EXP078_SELECTOR_UNION=PASS", flush=True)
        clear_dispatch()

        main_after = json.loads(ns(HOST, "ip", "-j", "-4", "route", "show", "table", "main").stdout)
        assert main_after == main_before, (main_before, main_after)
        print("EXP078_MAIN_UNTOUCHED=PASS", flush=True)
        print("EXP078_RESULT=PASS", flush=True)
        return 0
    finally:
        for name in (REMOTE, STATIC, GW, LANB, LANA, STACK, HOST):
            del_ns(name)


if __name__ == "__main__":
    raise SystemExit(main())
