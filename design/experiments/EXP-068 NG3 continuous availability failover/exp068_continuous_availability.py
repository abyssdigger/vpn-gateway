#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "design/NG3/code/python"))

from rou.availability_manager import AvailabilityManager, AvailabilityManagerPolicy
from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.icmp_probe_driver import (
    IcmpProbeExecutionPolicy,
    LinuxIcmpProbeDriver,
    SubprocessProbeCommandRunner,
)
from rou.interface_identity import InterfaceIdentity
from rou.linux_availability_cycle import run_linux_availability_cycle_once
from rou.linux_nft_scaffold import LinuxNftScaffoldBackend, SubprocessNftRunner
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM, NG3_PROBE_LOCAL_PLATFORM
from rou.linux_probe_local import LinuxProbeLocalBackend
from rou.payload_profile import PayloadProfileRequest
from rou.probe_desired import build_probe_desired_assembly
from rou.probe_local_mutation import ProbeLocalMutationStep
from rou.probe_runtime import AvailabilityProbeRuntime
from rou.release1_config import parse_release1_config
from rou.route_priority_inventory import RoutePriorityPathRoute


DEST = "10.77.0.0/16"
A_TARGET = "192.0.2.2"
B_TARGET = "198.51.100.2"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    value = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and value.returncode != 0:
        raise RuntimeError(
            f"command failed {args!r}: rc={value.returncode}\n"
            f"stdout={value.stdout}\nstderr={value.stderr}"
        )
    return value


def ns(name: str, *args: str, check: bool = True):
    return run("ip", "netns", "exec", name, *args, check=check)


def interface(name: str, ifname: str) -> InterfaceIdentity:
    row = json.loads(ns(name, "ip", "-j", "link", "show", "dev", ifname).stdout)[0]
    return InterfaceIdentity(ifname, int(row["ifindex"]))


def route_metrics(name: str, table: int) -> dict[str, int]:
    rows = json.loads(
        ns(
            name,
            "ip", "-j", "-N", "-4",
            "route", "show", "table", str(table), "proto", "202",
        ).stdout
    )
    result = {}
    for row in rows:
        if row.get("dst") != DEST:
            continue
        result[str(row["dev"])] = int(row.get("metric", 0))
    return result


def set_remote_a_drop(remote: str, enabled: bool) -> None:
    if enabled:
        script = """
table ip exp068_drop {
    chain input {
        type filter hook input priority 0; policy accept;
        ip protocol icmp drop
    }
}
"""
        value = subprocess.run(
            ("ip", "netns", "exec", remote, "nft", "-f", "-"),
            input=script,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if value.returncode != 0:
            raise RuntimeError(value.stderr)
    else:
        ns(remote, "nft", "delete", "table", "ip", "exp068_drop")


def main() -> int:
    if os.geteuid() != 0:
        print("EXP068_RESULT=SKIP root required")
        return 77

    suffix = uuid.uuid4().hex[:8]
    managed = "vpng-exp068-m-" + suffix
    remote_a = "vpng-exp068-a-" + suffix
    remote_b = "vpng-exp068-b-" + suffix

    for name in (managed, remote_a, remote_b):
        run("ip", "netns", "add", name)

    try:
        run("ip", "link", "add", "x68a0", "type", "veth", "peer", "name", "x68a1")
        run("ip", "link", "set", "x68a0", "netns", managed)
        run("ip", "link", "set", "x68a1", "netns", remote_a)
        run("ip", "link", "add", "x68b0", "type", "veth", "peer", "name", "x68b1")
        run("ip", "link", "set", "x68b0", "netns", managed)
        run("ip", "link", "set", "x68b1", "netns", remote_b)

        ns(managed, "ip", "link", "set", "x68a0", "name", "path0")
        ns(managed, "ip", "link", "set", "x68b0", "name", "path1")
        ns(remote_a, "ip", "link", "set", "x68a1", "name", "peer0")
        ns(remote_b, "ip", "link", "set", "x68b1", "name", "peer1")

        ns(managed, "ip", "addr", "add", "192.0.2.1/24", "dev", "path0")
        ns(remote_a, "ip", "addr", "add", f"{A_TARGET}/24", "dev", "peer0")
        ns(managed, "ip", "addr", "add", "198.51.100.1/24", "dev", "path1")
        ns(remote_b, "ip", "addr", "add", f"{B_TARGET}/24", "dev", "peer1")

        for name, dev in (
            (managed, "lo"), (remote_a, "lo"), (remote_b, "lo"),
            (managed, "path0"), (managed, "path1"),
            (remote_a, "peer0"), (remote_b, "peer1"),
        ):
            ns(name, "ip", "link", "set", dev, "up")

        ep_a = interface(managed, "path0")
        ep_b = interface(managed, "path1")
        path_a = LogicalPathId("a", 0, 0)
        path_b = LogicalPathId("b", 0, 0)
        path_routes = (
            RoutePriorityPathRoute(path_a, ep_a),
            RoutePriorityPathRoute(path_b, ep_b),
        )
        profile = PayloadProfileRequest(
            "corp",
            Direction.OUTBOUND,
            (__import__("ipaddress").IPv4Network(DEST),),
            (path_a, path_b),
        )
        config = parse_release1_config(f"""
[device.a]
enabled = true
expected_interfaces = ["path0"]
use_outbound_nat = false

[device.a.availability_check]
mechanism = "icmp"
target = "{A_TARGET}"

[device.b]
enabled = true
expected_interfaces = ["path1"]
use_outbound_nat = false

[device.b.availability_check]
mechanism = "icmp"
target = "{B_TARGET}"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["{DEST}"]
device_order = ["a", "b"]
availability_check = "default"
""")
        assembly = build_probe_desired_assembly(
            config,
            (profile,),
            path_routes,
            NG3_LINUX_POLICY_PLATFORM,
            NG3_PROBE_LOCAL_PLATFORM,
        )

        runner = SubprocessNftRunner()
        LinuxNftScaffoldBackend(runner, managed).create_payload_scaffold()
        LinuxProbeLocalBackend(runner, managed).apply_probe_local_step(
            ProbeLocalMutationStep((), assembly.probe.local_rules)
        )

        allocation = assembly.layout.payload[0]
        for dev, metric in (("path0", 1), ("path1", 2)):
            ns(
                managed,
                "ip", "-4", "route", "add", DEST,
                "dev", dev,
                "table", str(allocation.table),
                "proto", str(allocation.path_route_protocol),
                "metric", str(metric),
            )

        runtime = AvailabilityProbeRuntime()
        manager = AvailabilityManager(AvailabilityManagerPolicy(1, 1))
        driver = LinuxIcmpProbeDriver(
            SubprocessProbeCommandRunner(),
            managed,
            NG3_PROBE_LOCAL_PLATFORM.process_uid,
            IcmpProbeExecutionPolicy(1),
        )

        healthy = run_linux_availability_cycle_once(
            config, (profile,), path_routes, assembly, runtime, manager, driver,
            runner=runner, namespace=managed, platform=NG3_LINUX_POLICY_PLATFORM,
        )
        if not healthy.confirmed:
            raise AssertionError(f"healthy cycle unconfirmed: {healthy}")
        m0 = route_metrics(managed, allocation.table)
        print(f"EXP068_HEALTHY_METRICS={m0}")
        if m0 != {"path0": 1, "path1": 2}:
            raise AssertionError(m0)

        set_remote_a_drop(remote_a, True)
        failed = run_linux_availability_cycle_once(
            config, (profile,), path_routes, assembly, runtime, manager, driver,
            runner=runner, namespace=managed, platform=NG3_LINUX_POLICY_PLATFORM,
        )
        if not failed.confirmed:
            raise AssertionError(f"failover cycle unconfirmed: {failed}")
        m1 = route_metrics(managed, allocation.table)
        print(f"EXP068_FAILOVER_METRICS={m1}")
        if m1 != {"path0": 2, "path1": 1}:
            raise AssertionError(m1)

        set_remote_a_drop(remote_a, False)
        recovered = run_linux_availability_cycle_once(
            config, (profile,), path_routes, assembly, runtime, manager, driver,
            runner=runner, namespace=managed, platform=NG3_LINUX_POLICY_PLATFORM,
        )
        if not recovered.confirmed:
            raise AssertionError(f"recovery cycle unconfirmed: {recovered}")
        m2 = route_metrics(managed, allocation.table)
        print(f"EXP068_RECOVERY_STICKY_METRICS={m2}")
        if m2 != {"path0": 2, "path1": 1}:
            raise AssertionError(m2)

        print("EXP068_RESULT=PASS")
        return 0
    finally:
        for name in (managed, remote_a, remote_b):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
