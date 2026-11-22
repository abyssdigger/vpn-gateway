#!/usr/bin/env python3
"""Production C.010 integration in a disposable network namespace."""

from __future__ import annotations

import os
import subprocess

from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_protective_payload_gate import (
    PROTECTIVE_NFT_TABLE,
    LinuxProtectivePayloadGateDriver,
)
from rou.protective_payload_gate import (
    ProtectivePayloadGateDesired,
    ProtectivePayloadGateObservationStatus,
    ProtectivePayloadGateState,
    converge_protective_payload_gate_once,
)


NS = f"ng3-c010-{os.getpid()}"
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
        print("C010_INTEGRATION=SKIP root required")
        return 77

    try:
        run("ip", "netns", "add", NS)
        ns("ip", "link", "set", "lo", "up")
        ns("ip", "link", "add", BOUNDARY, "type", "dummy")
        ns("ip", "link", "set", BOUNDARY, "up")

        driver = LinuxProtectivePayloadGateDriver(
            SubprocessNftRunner(),
            NS,
        )
        enabled = ProtectivePayloadGateDesired(
            ProtectivePayloadGateState.ENABLED,
            BOUNDARY,
        )
        disabled = ProtectivePayloadGateDesired(
            ProtectivePayloadGateState.DISABLED
        )

        result = converge_protective_payload_gate_once(driver, enabled)
        assert result.confirmed, result
        print("C010_ENABLE=PASS", flush=True)

        ns(
            "nft",
            "flush",
            "chain",
            "inet",
            PROTECTIVE_NFT_TABLE,
            "protect_forward",
        )
        drift = driver.observe_protective_payload_gate(enabled)
        assert (
            drift.status
            is ProtectivePayloadGateObservationStatus.OWNED_DRIFT
        ), drift
        repaired = converge_protective_payload_gate_once(driver, enabled)
        assert repaired.confirmed, repaired
        print("C010_OWNED_DRIFT_REPAIR=PASS", flush=True)

        stopped = converge_protective_payload_gate_once(driver, disabled)
        assert stopped.confirmed, stopped
        print("C010_DISABLE=PASS", flush=True)

        ns(
            "nft",
            "add",
            "table",
            "inet",
            PROTECTIVE_NFT_TABLE,
        )
        conflict = driver.observe_protective_payload_gate(enabled)
        assert (
            conflict.status
            is ProtectivePayloadGateObservationStatus.CONFLICT
        ), conflict
        refused = converge_protective_payload_gate_once(driver, enabled)
        assert not refused.confirmed, refused
        assert ns(
            "nft",
            "list",
            "table",
            "inet",
            PROTECTIVE_NFT_TABLE,
            check=False,
        ).returncode == 0
        print("C010_FOREIGN_CONFLICT_REFUSED=PASS", flush=True)

        print("C010_INTEGRATION=PASS", flush=True)
        return 0
    finally:
        run("ip", "netns", "del", NS, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
