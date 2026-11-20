#!/usr/bin/env python3
"""EXP-077: Release-1 peaceful host-routing helper over routed L3 boundary."""

from __future__ import annotations

import json
import os
import subprocess
from ipaddress import IPv4Interface

from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_host_managed_routing_backend import (
    LinuxHostManagedRoutingBackend,
    cleanup_host_managed_routing_once,
    converge_host_managed_routing_once,
)
from rou.linux_policy_platform import NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION
from rou.managed_network_domain import ManagedNetworkDomainSpec
from rou.release1_config import parse_release1_config
from rou.release1_host_route_helper import (
    build_release1_peaceful_host_routing_desired,
)


PID = os.getpid()
HOST = f"v77h-{PID}"
STACK = f"v77s-{PID}"
LAN = f"v77l-{PID}"
REMOTE = f"v77r-{PID}"
GW = f"v77g-{PID}"
STATIC = f"v77x-{PID}"

BH = "vpng0"
BS = "stack0"
HL = "e77hl"
LH = "e77lh"
SR = "e77sr"
RS = "e77rs"
HU = "e77hu"
GU = "e77gu"
HX = "e77hx"
XH = "e77xh"

HOST_LAN = "10.0.0.1"
LAN_IP = "10.0.0.2"
STACK_REMOTE = "198.18.77.1"
REMOTE_LINK = "198.18.77.2"
HOST_UP = "192.0.2.1"
GW_IP = "192.0.2.2"
HOST_STATIC = "172.16.0.1"
STATIC_GW = "172.16.0.2"

FULL_TARGET = "8.8.8.8"
STATIC_TARGET = "203.0.113.9"
DYNAMIC_TARGET = "198.51.100.9"

CONFIG = """
host_routing = "auto"

[device.vpn]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[profile.full]
enabled = true
direction = "outbound"
destinations = ["0.0.0.0/0"]
device_order = ["vpn"]
"""


def run(*args, check=True):
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def ns(name, *args, check=True):
    return run("ip", "netns", "exec", name, *args, check=check)


def add_ns(name):
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def del_ns(name):
    run("ip", "netns", "del", name, check=False)


def pair(a, b, na, nb):
    run("ip", "link", "add", a, "type", "veth", "peer", "name", b)
    run("ip", "link", "set", a, "netns", na)
    run("ip", "link", "set", b, "netns", nb)


def route_get(address, *extra):
    raw = ns(HOST, "ip", "-j", "-4", "route", "get", address, *extra).stdout
    rows = json.loads(raw)
    assert len(rows) == 1, raw
    return rows[0]


def ping_from_lan(target):
    return (
        ns(
            LAN,
            "ping",
            "-n",
            "-c",
            "1",
            "-W",
            "2",
            target,
            check=False,
        ).returncode
        == 0
    )


def setup():
    for name in (HOST, STACK, LAN, REMOTE, GW, STATIC):
        add_ns(name)

    for a, b, na, nb in (
        (BH, BS, HOST, STACK),
        (HL, LH, HOST, LAN),
        (SR, RS, STACK, REMOTE),
        (HU, GU, HOST, GW),
        (HX, XH, HOST, STATIC),
    ):
        pair(a, b, na, nb)

    ns(HOST, "ip", "addr", "add", f"{HOST_LAN}/24", "dev", HL)
    ns(LAN, "ip", "addr", "add", f"{LAN_IP}/24", "dev", LH)
    ns(STACK, "ip", "addr", "add", f"{STACK_REMOTE}/30", "dev", SR)
    ns(REMOTE, "ip", "addr", "add", f"{REMOTE_LINK}/30", "dev", RS)
    ns(HOST, "ip", "addr", "add", f"{HOST_UP}/30", "dev", HU)
    ns(GW, "ip", "addr", "add", f"{GW_IP}/30", "dev", GU)
    ns(HOST, "ip", "addr", "add", f"{HOST_STATIC}/30", "dev", HX)
    ns(STATIC, "ip", "addr", "add", f"{STATIC_GW}/30", "dev", XH)

    for name, interfaces in (
        (HOST, (BH, HL, HU, HX)),
        (STACK, (BS, SR)),
        (LAN, (LH,)),
        (REMOTE, (RS,)),
        (GW, (GU,)),
        (STATIC, (XH,)),
    ):
        for interface in interfaces:
            ns(name, "ip", "link", "set", interface, "up")

    ns(REMOTE, "ip", "addr", "add", f"{FULL_TARGET}/32", "dev", "lo")
    ns(STATIC, "ip", "addr", "add", f"{STATIC_TARGET}/32", "dev", "lo")
    ns(GW, "ip", "addr", "add", f"{DYNAMIC_TARGET}/32", "dev", "lo")

    ns(HOST, "ip", "route", "add", "default", "via", GW_IP, "dev", HU)
    ns(
        HOST,
        "ip",
        "route",
        "add",
        "203.0.113.0/24",
        "via",
        STATIC_GW,
        "dev",
        HX,
    )
    ns(LAN, "ip", "route", "add", "default", "via", HOST_LAN)

    ns(STACK, "ip", "route", "add", "default", "via", REMOTE_LINK, "dev", SR)
    ns(STACK, "ip", "route", "add", "10.0.0.0/24", "dev", BS)
    ns(
        REMOTE,
        "ip",
        "route",
        "add",
        "10.0.0.0/24",
        "via",
        STACK_REMOTE,
        "dev",
        RS,
    )
    ns(GW, "ip", "route", "add", "10.0.0.0/24", "via", HOST_UP, "dev", GU)
    ns(
        STATIC,
        "ip",
        "route",
        "add",
        "10.0.0.0/24",
        "via",
        HOST_STATIC,
        "dev",
        XH,
    )

    for name in (HOST, STACK):
        ns(name, "sysctl", "-qw", "net.ipv4.ip_forward=1")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=0")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.default.rp_filter=0")

    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{BH}.proxy_arp=1")
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{BS}.proxy_arp=1")
    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{BH}.rp_filter=0")
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{BS}.rp_filter=0")


def desired():
    config = parse_release1_config(CONFIG)
    domain = ManagedNetworkDomainSpec(
        namespace=STACK,
        host_interface=BH,
        inner_interface=BS,
        inner_address=IPv4Interface("198.19.255.2/32"),
    )
    result = build_release1_peaceful_host_routing_desired(config, domain)
    assert result is not None
    return result


def main():
    if os.geteuid() != 0:
        print("EXP077_RESULT=SKIP root required")
        return 77

    try:
        setup()
        target = desired()
        allocation = NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION
        backend = LinuxHostManagedRoutingBackend(
            SubprocessCommandRunner(),
            allocation,
            network_namespace=HOST,
        )

        main_before = json.loads(
            ns(HOST, "ip", "-j", "-4", "route", "show", "table", "main").stdout
        )

        converged = converge_host_managed_routing_once(backend, target)
        assert converged.exact, converged

        full = route_get(FULL_TARGET)
        assert full.get("dev") == BH and "gateway" not in full, full
        assert ping_from_lan(FULL_TARGET), full
        print("EXP077_DEFAULT_ASSISTANCE=PASS", flush=True)

        static = route_get(STATIC_TARGET)
        assert static.get("dev") == HX and static.get("gateway") == STATIC_GW, static
        assert ping_from_lan(STATIC_TARGET), static
        print("EXP077_ADMIN_NONDEFAULT_WINS=PASS", flush=True)

        ns(
            HOST,
            "ip",
            "route",
            "add",
            f"{DYNAMIC_TARGET}/32",
            "via",
            GW_IP,
            "dev",
            HU,
        )
        dynamic = route_get(DYNAMIC_TARGET)
        assert dynamic.get("dev") == HU and dynamic.get("gateway") == GW_IP, dynamic
        assert ping_from_lan(DYNAMIC_TARGET), dynamic
        print("EXP077_DYNAMIC_ADMIN_ROUTE_WINS=PASS", flush=True)

        stack_origin = route_get(
            STATIC_TARGET,
            "from",
            FULL_TARGET,
            "iif",
            BH,
        )
        assert (
            stack_origin.get("dev") == HX
            and stack_origin.get("gateway") == STATIC_GW
        ), stack_origin
        print("EXP077_STACK_ORIGIN_MAIN_BYPASS=PASS", flush=True)

        main_during = json.loads(
            ns(HOST, "ip", "-j", "-4", "route", "show", "table", "main").stdout
        )
        expected_during = main_before + [
            row
            for row in main_during
            if row.get("dst") == f"{DYNAMIC_TARGET}"
            or row.get("dst") == f"{DYNAMIC_TARGET}/32"
        ]
        assert sorted(main_during, key=repr) == sorted(expected_during, key=repr)
        print("EXP077_MAIN_UNTOUCHED_EXCEPT_ADMIN=PASS", flush=True)

        preserve = target.preserve_main
        assert preserve is not None
        ns(
            HOST,
            "ip",
            "-4",
            "rule",
            "del",
            "priority",
            str(preserve.priority),
            "protocol",
            str(preserve.protocol),
        )
        ns(
            HOST,
            "ip",
            "-4",
            "rule",
            "add",
            "priority",
            str(preserve.priority),
            "protocol",
            "99",
            "lookup",
            "main",
            "suppress_prefixlength",
            "0",
        )

        cleaned = cleanup_host_managed_routing_once(
            backend,
            target,
            tolerate_foreign_replacements=True,
        )
        assert not cleaned.routes and not cleaned.rule_priorities, cleaned

        rules_after = json.loads(
            ns(HOST, "ip", "-j", "-4", "rule", "show").stdout
        )
        foreign = [
            row
            for row in rules_after
            if row.get("priority") == preserve.priority
            and row.get("table") == "main"
            and row.get("suppress_prefixlen") == 0
            and str(row.get("protocol")) != str(preserve.protocol)
        ]
        assert len(foreign) == 1, rules_after
        print("EXP077_FOREIGN_REPLACEMENT_PRESERVED=PASS", flush=True)

        ns(
            HOST,
            "ip",
            "-4",
            "rule",
            "del",
            "priority",
            str(preserve.priority),
            "protocol",
            "99",
        )
        ns(
            HOST,
            "ip",
            "route",
            "del",
            f"{DYNAMIC_TARGET}/32",
            "via",
            GW_IP,
            "dev",
            HU,
        )

        main_after = json.loads(
            ns(HOST, "ip", "-j", "-4", "route", "show", "table", "main").stdout
        )
        assert main_after == main_before, (main_before, main_after)
        print("EXP077_CLEANUP_MAIN_IDENTICAL=PASS", flush=True)
        print("EXP077_RESULT=PASS", flush=True)
        return 0
    finally:
        for name in (STATIC, GW, REMOTE, LAN, STACK, HOST):
            del_ns(name)


if __name__ == "__main__":
    raise SystemExit(main())
