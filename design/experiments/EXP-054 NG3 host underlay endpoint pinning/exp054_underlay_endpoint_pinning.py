#!/usr/bin/env python3
"""EXP-054: preserve VPN underlay endpoint before host full-tunnel bootstrap."""

from __future__ import annotations

import json
import os
import subprocess
from ipaddress import IPv4Address, IPv4Network

from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_host_boundary_policy import HostBoundaryRouteSpec
from rou.linux_host_boundary_routes import LinuxHostBoundaryRouteBackend


PID = os.getpid()
HOST = f"vng54h-{PID}"
GW = f"vng54g-{PID}"
STACK = f"vng54s-{PID}"

H_UP = "e54hu"
G_UP = "e54gu"
H_STACK = "e54hs"
S_HOST = "e54sh"

HOST_UP_IP = "192.0.2.1"
GW_IP = "192.0.2.2"
HOST_STACK_IP = "10.255.0.1"
STACK_IP = "10.255.0.2"
ENDPOINT = "198.51.100.10"
CAPTURE_TARGET = "203.0.113.77"


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


def route_get_raw(address: str) -> str:
    return ns(HOST, "ip", "-j", "-4", "route", "get", address).stdout


def route_get(address: str) -> dict:
    raw = route_get_raw(address)
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise AssertionError(f"unexpected route-get JSON: {raw!r}")
    return rows[0]


def ping_endpoint(*, expect_success: bool) -> None:
    result = ns(
        HOST,
        "ping",
        "-c",
        "1",
        "-W",
        "1",
        ENDPOINT,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(
            f"endpoint ping unexpectedly failed: stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    if not expect_success and result.returncode == 0:
        raise AssertionError("endpoint ping unexpectedly succeeded without underlay pin")


def setup() -> None:
    for name in (HOST, GW, STACK):
        add_ns(name)

    run("ip", "link", "add", H_UP, "type", "veth", "peer", "name", G_UP)
    run("ip", "link", "set", H_UP, "netns", HOST)
    run("ip", "link", "set", G_UP, "netns", GW)

    run("ip", "link", "add", H_STACK, "type", "veth", "peer", "name", S_HOST)
    run("ip", "link", "set", H_STACK, "netns", HOST)
    run("ip", "link", "set", S_HOST, "netns", STACK)

    ns(HOST, "ip", "addr", "add", f"{HOST_UP_IP}/30", "dev", H_UP)
    ns(HOST, "ip", "link", "set", H_UP, "up")
    ns(GW, "ip", "addr", "add", f"{GW_IP}/30", "dev", G_UP)
    ns(GW, "ip", "link", "set", G_UP, "up")
    ns(GW, "ip", "addr", "add", f"{ENDPOINT}/32", "dev", "lo")

    ns(HOST, "ip", "addr", "add", f"{HOST_STACK_IP}/30", "dev", H_STACK)
    ns(HOST, "ip", "link", "set", H_STACK, "up")
    ns(STACK, "ip", "addr", "add", f"{STACK_IP}/30", "dev", S_HOST)
    ns(STACK, "ip", "link", "set", S_HOST, "up")

    ns(HOST, "ip", "route", "add", "default", "via", GW_IP, "dev", H_UP)


def main() -> int:
    try:
        setup()

        backend = LinuxHostBoundaryRouteBackend(
            SubprocessCommandRunner(),
            network_namespace=HOST,
        )

        before = route_get(ENDPOINT)
        assert before.get("gateway") == GW_IP, before
        assert before.get("dev") == H_UP, before
        ping_endpoint(expect_success=True)

        pin = backend.observe_underlay_pin(
            IPv4Address(ENDPOINT),
            managed_interface=H_STACK,
            owner_protocol=203,
        )
        assert str(pin.gateway) == GW_IP, pin
        assert pin.interface == H_UP, pin
        print("EXP054_ORDINARY_ROUTE_OBSERVED=PASS")

        # Materialize only from freshly observed ordinary path facts using the
        # production host-boundary route Driver.
        backend.add_underlay_pin(pin)

        capture_routes = (
            HostBoundaryRouteSpec(
                destination=IPv4Network("0.0.0.0/1"),
                via=IPv4Address(STACK_IP),
                interface=H_STACK,
                protocol=203,
            ),
            HostBoundaryRouteSpec(
                destination=IPv4Network("128.0.0.0/1"),
                via=IPv4Address(STACK_IP),
                interface=H_STACK,
                protocol=203,
            ),
        )
        for route in capture_routes:
            backend.add_bootstrap_route(route)

        pinned = route_get(ENDPOINT)
        assert pinned.get("gateway") == GW_IP, pinned
        assert pinned.get("dev") == H_UP, pinned
        ping_endpoint(expect_success=True)
        print("EXP054_ENDPOINT_PIN_SURVIVES_CAPTURE=PASS")

        captured = route_get(CAPTURE_TARGET)
        assert captured.get("gateway") == STACK_IP, captured
        assert captured.get("dev") == H_STACK, captured
        print("EXP054_NON_ENDPOINT_CAPTURED=PASS")

        backend.delete_underlay_pin(pin)
        unpinned = route_get(ENDPOINT)
        assert unpinned.get("gateway") == STACK_IP, unpinned
        assert unpinned.get("dev") == H_STACK, unpinned
        ping_endpoint(expect_success=False)
        print("EXP054_PIN_NECESSITY=PASS")

        for route in reversed(capture_routes):
            backend.delete_bootstrap_route(route)
        restored = route_get(ENDPOINT)
        assert restored.get("gateway") == GW_IP, restored
        assert restored.get("dev") == H_UP, restored
        ping_endpoint(expect_success=True)
        print("EXP054_CLEANUP_RESTORES_ORDINARY=PASS")

        print("EXP054_RESULT=PASS")
        return 0
    finally:
        for name in (STACK, GW, HOST):
            del_ns(name)


if __name__ == "__main__":
    raise SystemExit(main())
