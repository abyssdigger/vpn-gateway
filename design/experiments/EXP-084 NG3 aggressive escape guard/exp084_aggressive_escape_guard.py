#!/usr/bin/env python3
"""EXP-084: independent nft guard prevents aggressive-routing escape during RPDB bypass."""

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
LAN = f"v84l-{PID}"
HOST = f"v84h-{PID}"
STACK = f"v84s-{PID}"
REMOTE = f"v84r-{PID}"
GW = f"v84g-{PID}"

LH = "e84lh"
HL = "e84hl"
BH = "vpng0"
BS = "stack0"
SR = "e84sr"
RS = "e84rs"
HU = "e84hu"
GU = "e84gu"

LAN_IP = "10.84.1.2"
HOST_LAN = "10.84.1.1"
HOST_BOUNDARY = "100.64.84.1"
STACK_BOUNDARY = "100.64.84.2"
STACK_REMOTE = "198.18.84.1"
REMOTE_LINK = "198.18.84.2"
HOST_UP = "192.0.2.1"
GW_IP = "192.0.2.2"
TARGET = "203.0.113.84"
MANAGED_PREFIX = "203.0.113.0/24"
FOREIGN_PRIORITY = 100
NFT_TABLE = "vpng_aggressive_guard84"


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


def route_get_forwarded() -> dict[str, object]:
    rows = json.loads(
        ns(
            HOST,
            "ip",
            "-j",
            "-4",
            "route",
            "get",
            TARGET,
            "from",
            LAN_IP,
            "iif",
            HL,
        ).stdout
    )
    assert len(rows) == 1, rows
    return rows[0]


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

    ns(LAN, "ip", "addr", "add", f"{LAN_IP}/24", "dev", LH)
    ns(HOST, "ip", "addr", "add", f"{HOST_LAN}/24", "dev", HL)
    ns(HOST, "ip", "addr", "add", f"{HOST_BOUNDARY}/30", "dev", BH)
    ns(STACK, "ip", "addr", "add", f"{STACK_BOUNDARY}/30", "dev", BS)
    ns(STACK, "ip", "addr", "add", f"{STACK_REMOTE}/30", "dev", SR)
    ns(REMOTE, "ip", "addr", "add", f"{REMOTE_LINK}/30", "dev", RS)
    ns(HOST, "ip", "addr", "add", f"{HOST_UP}/30", "dev", HU)
    ns(GW, "ip", "addr", "add", f"{GW_IP}/30", "dev", GU)

    for name, interfaces in (
        (LAN, (LH,)),
        (HOST, (HL, BH, HU)),
        (STACK, (BS, SR)),
        (REMOTE, (RS,)),
        (GW, (GU,)),
    ):
        for interface in interfaces:
            ns(name, "ip", "link", "set", interface, "up")

    ns(REMOTE, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")
    ns(GW, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")

    ns(LAN, "ip", "route", "add", f"{TARGET}/32", "via", HOST_LAN)
    ns(HOST, "ip", "route", "add", f"{TARGET}/32", "via", GW_IP, "dev", HU)
    ns(STACK, "ip", "route", "add", f"{TARGET}/32", "via", REMOTE_LINK, "dev", SR)

    ns(REMOTE, "ip", "route", "add", "10.84.1.0/24", "via", STACK_REMOTE)
    ns(REMOTE, "ip", "route", "add", f"{HOST_BOUNDARY}/32", "via", STACK_REMOTE)
    ns(GW, "ip", "route", "add", "10.84.1.0/24", "via", HOST_UP)
    ns(STACK, "ip", "route", "add", "10.84.1.0/24", "via", HOST_BOUNDARY, "dev", BS)
    ns(STACK, "ip", "route", "add", f"{HOST_BOUNDARY}/32", "dev", BS)

    for name in (HOST, STACK):
        ns(name, "sysctl", "-qw", "net.ipv4.ip_forward=1")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=0")
        ns(name, "sysctl", "-qw", "net.ipv4.conf.default.rp_filter=0")


def desired():
    plan = build_host_managed_routing_plan(
        (
            HostManagedRoutingProfile(
                profile_id="managed",
                direction=Direction.OUTBOUND,
                destinations=(IPv4Network(MANAGED_PREFIX),),
            ),
        )
    )
    return build_linux_host_managed_routing_desired(
        plan,
        host_interface=BH,
        allocation=NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
        stack_service_address=None,
    )


def install_guard() -> None:
    rules = f"""
table inet {NFT_TABLE} {{
    set managed_v4 {{
        type ipv4_addr
        flags interval
        elements = {{ {MANAGED_PREFIX} }}
    }}
    chain output {{
        type filter hook output priority 100; policy accept;
        ip daddr @managed_v4 oifname != "{BH}" drop
    }}
    chain forward {{
        type filter hook forward priority 100; policy accept;
        ip daddr @managed_v4 oifname != "{BH}" drop
    }}
}}
"""
    ns(HOST, "nft", "-f", "-", input_text=rules)
    shown = ns(HOST, "nft", "list", "table", "inet", NFT_TABLE).stdout
    assert f"table inet {NFT_TABLE}" in shown


def remove_guard() -> None:
    ns(HOST, "nft", "delete", "table", "inet", NFT_TABLE)


def main() -> int:
    if os.geteuid() != 0:
        print("EXP084_RESULT=SKIP root required")
        return 77

    try:
        setup()
        target = desired()
        backend = LinuxHostManagedRoutingBackend(
            SubprocessCommandRunner(),
            NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
            network_namespace=HOST,
        )
        observed = converge_host_managed_routing_once(backend, target)
        assert observed.exact, observed

        baseline_route = route_get_forwarded()
        assert baseline_route.get("dev") == BH, baseline_route
        assert ping(LAN) and ping(HOST)
        print("EXP084_BASELINE_MANAGED_PATH=PASS", flush=True)

        install_guard()
        assert ping(LAN) and ping(HOST)
        print("EXP084_GUARD_ALLOWS_MANAGED_EGRESS=PASS", flush=True)

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
        bypass_route = route_get_forwarded()
        assert bypass_route.get("dev") == HU and bypass_route.get("gateway") == GW_IP, bypass_route

        assert not ping(LAN), "forwarded managed traffic escaped via ordinary uplink"
        assert not ping(HOST), "local managed traffic escaped via ordinary uplink"
        print("EXP084_GUARD_BLOCKS_RPDB_ESCAPE=PASS", flush=True)

        owner_view = backend.observe(target)
        assert owner_view.exact and not owner_view.conflicts, owner_view
        print("EXP084_OWNER_STILL_BLIND_TO_FOREIGN_RULE=PASS", flush=True)

        ns(HOST, "ip", "-4", "rule", "del", "priority", str(FOREIGN_PRIORITY))
        restored_route = route_get_forwarded()
        assert restored_route.get("dev") == BH, restored_route
        assert ping(LAN) and ping(HOST)
        print("EXP084_RECOVERY_WITH_GUARD_ACTIVE=PASS", flush=True)

        remove_guard()
        cleanup_host_managed_routing_once(backend, target)
        print("EXP084_RESULT=PASS", flush=True)
        return 0
    finally:
        for name in (GW, REMOTE, STACK, HOST, LAN):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
