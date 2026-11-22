#!/usr/bin/env python3
"""EXP-081: prove the current aggressive owner is bypassable by earlier foreign RPDB policy."""

from __future__ import annotations

import json
import os
import subprocess
from ipaddress import IPv4Network

from rou.domain import Direction
from rou.host_managed_routing import HostManagedRoutingProfile, build_host_managed_routing_plan
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_host_managed_routing import build_linux_host_managed_routing_desired
from rou.linux_host_managed_routing_backend import (
    LinuxHostManagedRoutingBackend,
    cleanup_host_managed_routing_once,
    converge_host_managed_routing_once,
)
from rou.linux_policy_platform import NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION


PID = os.getpid()
HOST = f"v81h-{PID}"
STACK = f"v81s-{PID}"
REMOTE = f"v81r-{PID}"
GW = f"v81g-{PID}"
BH = "vpng0"
BS = "stack0"
SR = "e81sr"
RS = "e81rs"
HU = "e81hu"
GU = "e81gu"
STACK_REMOTE = "198.18.81.1"
REMOTE_LINK = "198.18.81.2"
HOST_UP = "192.0.2.1"
GW_IP = "192.0.2.2"
TARGET = "203.0.113.81"
FOREIGN_PRIORITY = 100


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def ns(name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("ip", "netns", "exec", name, *args, check=check)


def add_ns(name: str) -> None:
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def pair(a: str, b: str, na: str, nb: str) -> None:
    run("ip", "link", "add", a, "type", "veth", "peer", "name", b)
    run("ip", "link", "set", a, "netns", na)
    run("ip", "link", "set", b, "netns", nb)


def route_get() -> dict[str, object]:
    rows = json.loads(ns(HOST, "ip", "-j", "-4", "route", "get", TARGET).stdout)
    assert len(rows) == 1, rows
    return rows[0]


def setup() -> None:
    for name in (HOST, STACK, REMOTE, GW):
        add_ns(name)
    pair(BH, BS, HOST, STACK)
    pair(SR, RS, STACK, REMOTE)
    pair(HU, GU, HOST, GW)

    ns(STACK, "ip", "addr", "add", f"{STACK_REMOTE}/30", "dev", SR)
    ns(REMOTE, "ip", "addr", "add", f"{REMOTE_LINK}/30", "dev", RS)
    ns(HOST, "ip", "addr", "add", f"{HOST_UP}/30", "dev", HU)
    ns(GW, "ip", "addr", "add", f"{GW_IP}/30", "dev", GU)

    for name, interfaces in (
        (HOST, (BH, HU)),
        (STACK, (BS, SR)),
        (REMOTE, (RS,)),
        (GW, (GU,)),
    ):
        for interface in interfaces:
            ns(name, "ip", "link", "set", interface, "up")

    ns(REMOTE, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")
    ns(GW, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")

    ns(HOST, "ip", "route", "add", "default", "via", GW_IP, "dev", HU)
    ns(STACK, "ip", "route", "add", "default", "via", REMOTE_LINK, "dev", SR)

    for name in (HOST, STACK):
        ns(name, "sysctl", "-qw", "net.ipv4.ip_forward=1")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=0")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.default.rp_filter=0")
    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{BH}.proxy_arp=1")
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{BS}.proxy_arp=1")


def desired():
    plan = build_host_managed_routing_plan(
        (
            HostManagedRoutingProfile(
                profile_id="managed",
                direction=Direction.OUTBOUND,
                destinations=(IPv4Network("0.0.0.0/0"),),
            ),
        )
    )
    return build_linux_host_managed_routing_desired(
        plan,
        host_interface=BH,
        allocation=NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
    )


def main() -> int:
    if os.geteuid() != 0:
        print("EXP081_RESULT=SKIP root required")
        return 77

    try:
        setup()
        target = desired()
        backend = LinuxHostManagedRoutingBackend(
            SubprocessCommandRunner(),
            NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
            network_namespace=HOST,
        )
        converged = converge_host_managed_routing_once(backend, target)
        assert converged.exact, converged
        assert backend.observe(target).exact
        print("EXP081_BASELINE_OWNER_EXACT=PASS", flush=True)

        before = route_get()
        assert before.get("dev") == BH, before
        print("EXP081_BASELINE_MANAGED_CAPTURE=PASS", flush=True)

        ns(
            HOST,
            "ip",
            "-4",
            "rule",
            "add",
            "priority",
            str(FOREIGN_PRIORITY),
            "lookup",
            "main",
        )
        after = route_get()
        assert after.get("dev") == HU and after.get("gateway") == GW_IP, after
        print("EXP081_FOREIGN_RPDB_BYPASS=PASS", flush=True)

        observed = backend.observe(target)
        assert observed.exact and not observed.conflicts, observed
        print("EXP081_OWNER_BLIND_TO_EARLIER_RPDB=PASS", flush=True)

        ns(HOST, "ip", "-4", "rule", "del", "priority", str(FOREIGN_PRIORITY))
        cleanup_host_managed_routing_once(backend, target)
        print("EXP081_RESULT=PASS", flush=True)
        return 0
    finally:
        for name in (GW, REMOTE, STACK, HOST):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
