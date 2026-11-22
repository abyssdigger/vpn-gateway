#!/usr/bin/env python3
"""A.011 Manager core composed with production C.010 in a disposable namespace."""

from __future__ import annotations

import os
import subprocess

from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_protective_payload_gate import LinuxProtectivePayloadGateDriver
from rou.protective_mode_manager import (
    ProtectiveModeActionStatus,
    ProtectiveModeManager,
)
from rou.protective_payload_gate import (
    ProtectivePayloadGateDesired,
    ProtectivePayloadGateState,
)


NS = f"ng3-a011-{os.getpid()}"
BOUNDARY = "stack0"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def ns(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("ip", "netns", "exec", NS, *args, check=check)


def main() -> int:
    if os.geteuid() != 0:
        print("A011_CORE_INTEGRATION=SKIP root required")
        return 77

    try:
        run("ip", "netns", "add", NS)
        ns("ip", "link", "set", "lo", "up")
        ns("ip", "link", "add", BOUNDARY, "type", "dummy")
        ns("ip", "link", "set", BOUNDARY, "up")

        driver = LinuxProtectivePayloadGateDriver(SubprocessNftRunner(), NS)
        manager = ProtectiveModeManager()

        assert manager.request_active(
            "operator", BOUNDARY, driver
        ).confirmed_active
        assert manager.request_active(
            "aggressive", BOUNDARY, driver
        ).confirmed_active
        print("A011_MULTI_SOURCE_ACTIVE=PASS", flush=True)

        remaining = manager.request_inactive(
            "operator",
            BOUNDARY,
            normal_release_confirmed=True,
            driver=driver,
        )
        assert remaining.confirmed_active
        assert remaining.projection.request_sources == frozenset({"aggressive"})
        print("A011_SOURCE_ISOLATION=PASS", flush=True)

        blocked = manager.request_inactive(
            "aggressive",
            BOUNDARY,
            normal_release_confirmed=False,
            driver=driver,
        )
        assert blocked.action_status is ProtectiveModeActionStatus.LEAVE_BLOCKED
        enabled = driver.observe_protective_payload_gate(
            ProtectivePayloadGateDesired(
                ProtectivePayloadGateState.ENABLED,
                BOUNDARY,
            )
        )
        assert enabled.matches(
            ProtectivePayloadGateDesired(
                ProtectivePayloadGateState.ENABLED,
                BOUNDARY,
            )
        )
        print("A011_BLOCKED_LEAVE_STAYS_PROTECTED=PASS", flush=True)

        released = manager.reconcile_once(
            BOUNDARY,
            normal_release_confirmed=True,
            driver=driver,
        )
        assert released.confirmed_inactive
        print("A011_CONFIRMED_RELEASE=PASS", flush=True)
        print("A011_CORE_INTEGRATION=PASS", flush=True)
        return 0
    finally:
        run("ip", "netns", "del", NS, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
