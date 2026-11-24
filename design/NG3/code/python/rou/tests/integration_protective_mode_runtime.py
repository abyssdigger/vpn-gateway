#!/usr/bin/env python3
"""A.011 operator control, data-plane containment and periodic repair evidence."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
from threading import RLock
from time import monotonic, sleep

from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_protective_payload_gate import (
    PROTECTIVE_NFT_TABLE,
    LinuxProtectivePayloadGateDriver,
)
from rou.protective_mode_control import (
    ProtectiveModeControlService,
    request_protective_control,
)
from rou.protective_mode_manager import ProtectiveModeManager
from rou.protective_payload_gate import (
    ProtectivePayloadGateDesired,
    ProtectivePayloadGateObservationStatus,
    ProtectivePayloadGateState,
)


NS = f"ng3-a011-runtime-{os.getpid()}"
PEER_A = f"ng3-a011-a-{os.getpid()}"
PEER_B = f"ng3-a011-b-{os.getpid()}"
BOUNDARY = "stack0"
HOST_IF = "a011h0"
VPN_A = "vpna0"
VPN_B = "vpnb0"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def ns(namespace: str, *args: str, check: bool = True):
    return run("ip", "netns", "exec", namespace, *args, check=check)


def wait_until(description, predicate, timeout=3.0):
    deadline = monotonic() + timeout
    last = None
    while monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception as exc:
            last = exc
        sleep(0.02)
    raise AssertionError(
        f"timeout waiting for {description}"
        + (f": {last!r}" if last is not None else "")
    )


def ping(namespace: str | None, address: str) -> bool:
    args = ("ping", "-c", "1", "-W", "1", address)
    result = ns(namespace, *args, check=False) if namespace else run(*args, check=False)
    return result.returncode == 0


def setup() -> None:
    run("ip", "netns", "add", NS)
    run("ip", "netns", "add", PEER_A)
    run("ip", "netns", "add", PEER_B)

    run("ip", "link", "add", HOST_IF, "type", "veth", "peer", "name", BOUNDARY)
    run("ip", "link", "set", BOUNDARY, "netns", NS)
    run("ip", "addr", "add", "10.240.0.1/24", "dev", HOST_IF)
    run("ip", "link", "set", HOST_IF, "up")
    ns(NS, "ip", "addr", "add", "10.240.0.2/24", "dev", BOUNDARY)
    ns(NS, "ip", "link", "set", BOUNDARY, "up")

    ns(NS, "ip", "link", "add", VPN_A, "type", "veth", "peer", "name", "peer0")
    ns(NS, "ip", "link", "set", "peer0", "netns", PEER_A)
    ns(NS, "ip", "addr", "add", "10.241.0.1/24", "dev", VPN_A)
    ns(NS, "ip", "link", "set", VPN_A, "up")
    ns(PEER_A, "ip", "addr", "add", "10.241.0.2/24", "dev", "peer0")
    ns(PEER_A, "ip", "link", "set", "peer0", "up")

    ns(NS, "ip", "link", "add", VPN_B, "type", "veth", "peer", "name", "peer0")
    ns(NS, "ip", "link", "set", "peer0", "netns", PEER_B)
    ns(NS, "ip", "addr", "add", "10.242.0.1/24", "dev", VPN_B)
    ns(NS, "ip", "link", "set", VPN_B, "up")
    ns(PEER_B, "ip", "addr", "add", "10.242.0.2/24", "dev", "peer0")
    ns(PEER_B, "ip", "link", "set", "peer0", "up")

    for namespace in (NS, PEER_A, PEER_B):
        ns(namespace, "ip", "link", "set", "lo", "up")

    ns(NS, "sysctl", "-qw", "net.ipv4.ip_forward=1")
    ns(PEER_A, "ip", "route", "add", "10.242.0.0/24", "via", "10.241.0.1")
    ns(PEER_B, "ip", "route", "add", "10.241.0.0/24", "via", "10.242.0.1")


def cleanup() -> None:
    for namespace in (PEER_B, PEER_A, NS):
        run("ip", "netns", "del", namespace, check=False)
    run("ip", "link", "del", HOST_IF, check=False)


def main() -> int:
    if os.geteuid() != 0:
        print("A011_RUNTIME_INTEGRATION=SKIP root required")
        return 77

    cleanup()
    setup()
    root = tempfile.TemporaryDirectory(prefix="a011-control-")
    socket_path = Path(root.name) / "control.sock"
    driver = LinuxProtectivePayloadGateDriver(SubprocessNftRunner(), NS)
    manager = ProtectiveModeManager()
    normal = {"ready": True}
    service = ProtectiveModeControlService(
        manager,
        driver,
        BOUNDARY,
        lambda: normal["ready"],
        RLock(),
        socket_path=socket_path,
        audit_interval_seconds=0.05,
    )

    try:
        assert ping(None, "10.240.0.2")
        assert ping(NS, "10.240.0.1")
        assert ping(PEER_A, "10.242.0.2")
        print("A011_BASELINE_TRAFFIC=PASS", flush=True)

        service.start()
        entered = request_protective_control(
            socket_path,
            "active",
            source="operator",
        )
        assert entered["ok"], entered

        assert not ping(None, "10.240.0.2")
        assert not ping(NS, "10.240.0.1")
        assert not ping(PEER_A, "10.242.0.2")
        assert ns(NS, "ip", "link", "show", BOUNDARY, check=False).returncode == 0
        assert ns(NS, "ip", "link", "show", VPN_A, check=False).returncode == 0
        assert ns(NS, "ip", "link", "show", VPN_B, check=False).returncode == 0
        print("A011_ALL_IP_DIRECTIONS_BLOCKED=PASS", flush=True)
        print("A011_RUNTIME_STATE_PRESERVED=PASS", flush=True)

        ns(NS, "nft", "delete", "table", "inet", PROTECTIVE_NFT_TABLE)
        desired = ProtectivePayloadGateDesired(
            ProtectivePayloadGateState.ENABLED,
            BOUNDARY,
        )
        wait_until(
            "periodic protective repair",
            lambda: (
                driver.observe_protective_payload_gate(desired).status
                is ProtectivePayloadGateObservationStatus.EXACT
            ),
        )
        assert not ping(PEER_A, "10.242.0.2")
        print("A011_PERIODIC_REPAIR=PASS", flush=True)

        normal["ready"] = False
        blocked = request_protective_control(
            socket_path,
            "inactive",
            source="operator",
        )
        assert not blocked["ok"], blocked
        assert not ping(None, "10.240.0.2")
        print("A011_FAILED_LEAVE_RETAINS_BLOCK=PASS", flush=True)

        normal["ready"] = True
        wait_until(
            "safe periodic release",
            lambda: (
                request_protective_control(
                    socket_path, "status"
                )["protective"]["status"]
                == "inactive"
            ),
        )
        assert ping(None, "10.240.0.2")
        assert ping(NS, "10.240.0.1")
        assert ping(PEER_A, "10.242.0.2")
        print("A011_SAFE_LEAVE_RESTORES_TRAFFIC=PASS", flush=True)
        print("A011_RUNTIME_INTEGRATION=PASS", flush=True)
        return 0
    finally:
        service.stop()
        root.cleanup()
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
