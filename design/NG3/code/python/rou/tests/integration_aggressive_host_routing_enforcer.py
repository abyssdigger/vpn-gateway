#!/usr/bin/env python3
"""Production E.004 integration against a disposable Linux topology."""

from __future__ import annotations

import os
import subprocess
from ipaddress import IPv4Network

from rou.aggressive_host_routing_enforcer import (
    build_aggressive_host_routing_desired,
    converge_aggressive_host_routing_active_once,
    converge_aggressive_host_routing_inactive_once,
)
from rou.domain import Direction
from rou.host_managed_routing import (
    HostManagedRoutingProfile,
    build_host_managed_routing_plan,
)
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_aggressive_escape_guard import LinuxAggressiveEscapeGuardDriver
from rou.linux_host_managed_routing_backend import LinuxHostManagedRoutingDriver
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_policy_platform import NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION


PID = os.getpid()
LAN = f"e4l-{PID}"
HOST = f"e4h-{PID}"
STACK = f"e4s-{PID}"
REMOTE = f"e4r-{PID}"
GW = f"e4g-{PID}"

LH, HL = "e4lh", "e4hl"
BH, BS = "vpng0", "stack0"
SR, RS = "e4sr", "e4rs"
HU, GU = "e4hu", "e4gu"

LAN_IP = "10.86.1.2"
HOST_LAN = "10.86.1.1"
HOST_BOUNDARY = "100.64.86.1"
STACK_BOUNDARY = "100.64.86.2"
STACK_REMOTE = "198.18.86.1"
REMOTE_LINK = "198.18.86.2"
HOST_UP = "192.0.2.9"
GW_IP = "192.0.2.10"
TARGET = "203.0.113.86"
FOREIGN_PRIORITY = 100


def run(*args: str, check: bool = True):
    return subprocess.run(
        args,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def ns(name: str, *args: str, check: bool = True):
    return run("ip", "netns", "exec", name, *args, check=check)


def add_ns(name: str) -> None:
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def pair(a: str, b: str, na: str, nb: str) -> None:
    run("ip", "link", "add", a, "type", "veth", "peer", "name", b)
    run("ip", "link", "set", a, "netns", na)
    run("ip", "link", "set", b, "netns", nb)


def ping(namespace: str) -> bool:
    return ns(
        namespace,
        "ping",
        "-n",
        "-c",
        "1",
        "-W",
        "1",
        TARGET,
        check=False,
    ).returncode == 0


def setup() -> None:
    for name in (LAN, HOST, STACK, REMOTE, GW):
        add_ns(name)
    for a, b, na, nb in (
        (LH, HL, LAN, HOST),
        (BH, BS, HOST, STACK),
        (SR, RS, STACK, REMOTE),
        (HU, GU, HOST, GW),
    ):
        pair(a, b, na, nb)

    for name, interface, address in (
        (LAN, LH, f"{LAN_IP}/24"),
        (HOST, HL, f"{HOST_LAN}/24"),
        (HOST, BH, f"{HOST_BOUNDARY}/30"),
        (STACK, BS, f"{STACK_BOUNDARY}/30"),
        (STACK, SR, f"{STACK_REMOTE}/30"),
        (REMOTE, RS, f"{REMOTE_LINK}/30"),
        (HOST, HU, f"{HOST_UP}/30"),
        (GW, GU, f"{GW_IP}/30"),
    ):
        ns(name, "ip", "addr", "add", address, "dev", interface)
        ns(name, "ip", "link", "set", interface, "up")

    ns(REMOTE, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")
    ns(GW, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")

    ns(LAN, "ip", "route", "add", "default", "via", HOST_LAN)
    ns(HOST, "ip", "route", "add", f"{TARGET}/32", "via", GW_IP, "dev", HU)
    ns(STACK, "ip", "route", "add", f"{TARGET}/32", "via", REMOTE_LINK, "dev", SR)
    ns(REMOTE, "ip", "route", "add", "10.86.1.0/24", "via", STACK_REMOTE)
    ns(GW, "ip", "route", "add", "10.86.1.0/24", "via", HOST_UP)
    ns(STACK, "ip", "route", "add", "10.86.1.0/24", "via", HOST_BOUNDARY, "dev", BS)

    for name in (HOST, STACK):
        ns(name, "sysctl", "-qw", "net.ipv4.ip_forward=1")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=0")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.default.rp_filter=0")
    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{BH}.proxy_arp=1")
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{BS}.proxy_arp=1")


def main() -> int:
    if os.geteuid() != 0:
        print("E004_INTEGRATION=SKIP root required")
        return 77
    try:
        setup()
        plan = build_host_managed_routing_plan(
            (
                HostManagedRoutingProfile(
                    profile_id="full",
                    direction=Direction.OUTBOUND,
                    destinations=(IPv4Network("0.0.0.0/0"),),
                ),
            )
        )
        desired = build_aggressive_host_routing_desired(
            plan,
            host_interface=BH,
            allocation=NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
        )
        runner = SubprocessCommandRunner()
        routing = LinuxHostManagedRoutingDriver(
            runner,
            NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
            network_namespace=HOST,
        )
        guard = LinuxAggressiveEscapeGuardDriver(
            SubprocessNftRunner(),
            network_namespace=HOST,
        )

        active = converge_aggressive_host_routing_active_once(
            routing, guard, desired
        )
        assert active.confirmed_active, active
        assert ping(HOST) and ping(LAN)
        print("E004_ACTIVE=PASS", flush=True)

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
        failed = converge_aggressive_host_routing_active_once(
            routing, guard, desired
        )
        assert not failed.confirmed_active, failed
        assert failed.local_containment_confirmed, failed
        assert not ping(HOST) and not ping(LAN)
        print("E004_FOREIGN_RPDB_FAIL_CLOSED=PASS", flush=True)

        ns(
            HOST,
            "ip",
            "-4",
            "rule",
            "del",
            "priority",
            str(FOREIGN_PRIORITY),
        )
        recovered = converge_aggressive_host_routing_active_once(
            routing, guard, desired
        )
        assert recovered.confirmed_active, recovered
        assert ping(HOST) and ping(LAN)
        print("E004_RECOVERY=PASS", flush=True)

        inactive = converge_aggressive_host_routing_inactive_once(
            routing, guard, desired
        )
        assert inactive.confirmed_inactive, inactive
        assert ping(HOST) and ping(LAN)
        print("E004_SAFE_DEACTIVATION=PASS", flush=True)
        print("E004_INTEGRATION=PASS", flush=True)
        return 0
    finally:
        for name in (GW, REMOTE, STACK, HOST, LAN):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
