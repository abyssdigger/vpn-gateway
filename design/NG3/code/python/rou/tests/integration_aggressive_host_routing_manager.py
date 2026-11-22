#!/usr/bin/env python3
"""Production E.003 periodic recovery/escalation over E.004 + A.011/C.010."""

from __future__ import annotations

import time
from ipaddress import IPv4Network

import integration_aggressive_host_routing_enforcer as topo
from rou.aggressive_host_routing_enforcer import (
    AggressiveHostRoutingEnforcer,
    build_aggressive_host_routing_desired,
)
from rou.aggressive_host_routing_manager import (
    AGGRESSIVE_PROTECTIVE_SOURCE,
    AggressiveHostRoutingManager,
    AggressiveHostRoutingManagerStatus,
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
from rou.linux_protective_payload_gate import LinuxProtectivePayloadGateDriver
from rou.protective_mode_manager import ProtectiveModeManager, ProtectiveModeStatus


def wait_for(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError("timed out waiting for periodic Manager state")


def main() -> int:
    if topo.os.geteuid() != 0:
        print("E003_INTEGRATION=SKIP root required")
        return 77
    try:
        topo.setup()
        desired = build_aggressive_host_routing_desired(
            build_host_managed_routing_plan(
                (
                    HostManagedRoutingProfile(
                        profile_id="full",
                        direction=Direction.OUTBOUND,
                        destinations=(IPv4Network("0.0.0.0/0"),),
                    ),
                )
            ),
            host_interface=topo.BH,
            allocation=NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
        )
        routing = LinuxHostManagedRoutingDriver(
            SubprocessCommandRunner(),
            NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
            network_namespace=topo.HOST,
        )
        guard = LinuxAggressiveEscapeGuardDriver(
            SubprocessNftRunner(),
            network_namespace=topo.HOST,
        )
        protective = ProtectiveModeManager()
        protective_driver = LinuxProtectivePayloadGateDriver(
            SubprocessNftRunner(),
            topo.STACK,
        )
        manager = AggressiveHostRoutingManager(
            AggressiveHostRoutingEnforcer(routing, guard),
            protective,
            protective_driver,
            topo.BS,
            lambda: True,
            audit_interval_seconds=0.1,
        )

        active = manager.activate(desired)
        assert active.status is AggressiveHostRoutingManagerStatus.ACTIVE, active
        assert topo.ping(topo.HOST) and topo.ping(topo.LAN)
        print("E003_INITIAL_ACTIVE=PASS", flush=True)

        topo.ns(
            topo.HOST,
            "ip",
            "-4",
            "rule",
            "add",
            "priority",
            str(topo.FOREIGN_PRIORITY),
            "lookup",
            "main",
        )
        degraded = wait_for(
            lambda: (
                manager.current_state()
                if manager.current_state().status
                in {
                    AggressiveHostRoutingManagerStatus.DEGRADED,
                    AggressiveHostRoutingManagerStatus.PROBLEM,
                }
                else None
            )
        )
        assert degraded.protective_requested, degraded
        pstate = protective.current_state()
        assert AGGRESSIVE_PROTECTIVE_SOURCE in pstate.request_sources, pstate
        assert pstate.status is ProtectiveModeStatus.ACTIVE, pstate
        assert not topo.ping(topo.HOST) and not topo.ping(topo.LAN)
        print("E003_PERIODIC_ESCALATION=PASS", flush=True)

        topo.ns(
            topo.HOST,
            "ip",
            "-4",
            "rule",
            "del",
            "priority",
            str(topo.FOREIGN_PRIORITY),
        )
        recovered = wait_for(
            lambda: (
                manager.current_state()
                if manager.current_state().status
                is AggressiveHostRoutingManagerStatus.ACTIVE
                else None
            )
        )
        assert not recovered.protective_requested, recovered
        assert protective.current_state().status is ProtectiveModeStatus.INACTIVE
        assert topo.ping(topo.HOST) and topo.ping(topo.LAN)
        print("E003_PERIODIC_RECOVERY=PASS", flush=True)

        inactive = manager.deactivate()
        assert inactive.status is AggressiveHostRoutingManagerStatus.INACTIVE, inactive
        assert topo.ping(topo.HOST) and topo.ping(topo.LAN)
        print("E003_SAFE_DEACTIVATION=PASS", flush=True)
        print("E003_INTEGRATION=PASS", flush=True)
        return 0
    finally:
        for name in (topo.GW, topo.REMOTE, topo.STACK, topo.HOST, topo.LAN):
            topo.run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
