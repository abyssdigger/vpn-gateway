#!/usr/bin/env python3
"""Privileged nft ownership evidence for the EXP-064 production behavior owner."""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rou.host_boundary_behavior import (
    HostBoundaryBehaviorIntent,
    HostBoundaryBehaviorLane,
)
from rou.linux_host_boundary_behavior import (
    HOST_BEHAVIOR_TABLE,
    HostBoundaryBehaviorHostLane,
    LinuxHostBoundaryBehaviorNftBackend,
    build_host_boundary_behavior_nft_desired,
    converge_host_boundary_behavior_nft_once,
)
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_policy_platform import (
    NG3_HOST_BOUNDARY_BEHAVIOR_LINUX_ALLOCATION,
)


NS = f"vng-host-beh-{os.getpid()}"


def raw(*argv: str, check: bool = True) -> str:
    return subprocess.run(
        argv,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def main() -> int:
    runner = SubprocessNftRunner()
    lanes = (
        HostBoundaryBehaviorHostLane(
            HostBoundaryBehaviorLane.STATEFUL_NO_NAT,
            "lane-s0",
        ),
        HostBoundaryBehaviorHostLane(
            HostBoundaryBehaviorLane.STATEFUL_NAT,
            "lane-s1",
        ),
        HostBoundaryBehaviorHostLane(
            HostBoundaryBehaviorLane.ROUTE_NO_NAT,
            "lane-r0",
        ),
        HostBoundaryBehaviorHostLane(
            HostBoundaryBehaviorLane.ROUTE_NAT,
            "lane-r1",
        ),
    )
    desired = build_host_boundary_behavior_nft_desired(
        (
            HostBoundaryBehaviorIntent(
                "s0",
                HostBoundaryBehaviorLane.STATEFUL_NO_NAT,
            ),
            HostBoundaryBehaviorIntent(
                "s1",
                HostBoundaryBehaviorLane.STATEFUL_NAT,
            ),
            HostBoundaryBehaviorIntent(
                "r0",
                HostBoundaryBehaviorLane.ROUTE_NO_NAT,
            ),
            HostBoundaryBehaviorIntent(
                "r1",
                HostBoundaryBehaviorLane.ROUTE_NAT,
            ),
        ),
        lanes,
        NG3_HOST_BOUNDARY_BEHAVIOR_LINUX_ALLOCATION,
    )
    assert desired is not None

    try:
        raw("ip", "netns", "add", NS)
        for item in lanes:
            raw("ip", "-n", NS, "link", "add", item.host_interface, "type", "dummy")
            raw("ip", "-n", NS, "link", "set", item.host_interface, "up")

        backend = LinuxHostBoundaryBehaviorNftBackend(runner, NS)
        initial = backend.observe(desired)
        assert not initial.table_present
        assert not initial.exact

        applied = converge_host_boundary_behavior_nft_once(backend, desired)
        if not applied.exact:
            print(f"HOST_BEHAVIOR_OWNER_APPLY_DIAGNOSTIC={applied!r}", flush=True)
            print(
                "HOST_BEHAVIOR_OWNER_NFT_JSON="
                + runner.run(
                    ("ip", "netns", "exec", NS, "nft", "-j", "-y", "list", "ruleset")
                ),
                flush=True,
            )
        assert applied.exact
        assert backend.observe(desired).exact
        print("HOST_BEHAVIOR_OWNER_APPLY=PASS")

        converge_host_boundary_behavior_nft_once(backend, None)
        absent = backend.observe(None)
        assert not absent.table_present
        assert absent.exact
        print("HOST_BEHAVIOR_OWNER_CLEANUP=PASS")

        runner.run_script(
            ("ip", "netns", "exec", NS, "nft", "-f", "-"),
            (
                f'table inet {HOST_BEHAVIOR_TABLE} {{\n'
                '  comment "foreign";\n'
                '}\n'
            ),
        )
        conflict = backend.observe(desired)
        assert conflict.conflicts
        try:
            converge_host_boundary_behavior_nft_once(backend, desired)
        except RuntimeError:
            pass
        else:
            raise AssertionError("foreign owner conflict was not rejected")
        print("HOST_BEHAVIOR_OWNER_CONFLICT=PASS")

        print("HOST_BEHAVIOR_OWNER_RESULT=PASS")
        return 0
    finally:
        raw("ip", "netns", "del", NS, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
