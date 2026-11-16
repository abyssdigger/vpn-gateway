from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import NamespaceBackend, SubprocessBackend, execute_kernel_mutation_plan
from rou.environment import collect_environment_snapshot
from rou.kernel_mutation import compile_lifecycle_route_rebuild_plan
from rou.kernel_state import KernelDesiredState, KernelRouteSpec


NS = "vpn-gate-ng1-ci-diff"
TARGET = "10.20.1.1"
SOURCE = "192.0.2.1"


def run(*argv: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def cleanup() -> None:
    run("ip", "netns", "del", NS, check=False)


def ns(*argv: str, check: bool = True) -> subprocess.CompletedProcess:
    return run("ip", "netns", "exec", NS, *argv, check=check)


def route_get() -> subprocess.CompletedProcess:
    return ns(
        "ip", "route", "get",
        TARGET,
        "from", SOURCE,
        "iif", "host0",
        check=False,
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration test must run as root")

    cleanup()
    try:
        run("ip", "netns", "add", NS)
        run("ip", "-n", NS, "link", "set", "lo", "up")
        for ifname in ("host0", "vpns00", "vpns01"):
            run("ip", "-n", NS, "link", "add", ifname, "type", "dummy")
            run("ip", "-n", NS, "link", "set", ifname, "up")
        run("ip", "-n", NS, "addr", "add", "192.0.2.2/30", "dev", "host0")

        # More-specific Profile table 1.
        ns(
            "ip", "route", "add", "table", "1",
            "10.20.0.0/16", "dev", "vpns00",
            "proto", "202", "metric", "1",
        )
        ns(
            "ip", "route", "add", "table", "1",
            "blackhole", "default",
            "proto", "201", "metric", "65536",
        )

        # Broader Profile table 2. If table 1 becomes empty, this is the path we must NOT
        # fall through to.
        ns(
            "ip", "route", "add", "table", "2",
            "10.0.0.0/8", "dev", "vpns01",
            "proto", "202", "metric", "1",
        )
        ns(
            "ip", "route", "add", "table", "2",
            "blackhole", "default",
            "proto", "201", "metric", "65536",
        )

        ns(
            "ip", "rule", "add", "priority", "1",
            "iif", "host0", "to", "10.20.0.0/16", "lookup", "1",
        )
        ns(
            "ip", "rule", "add", "priority", "2",
            "iif", "host0", "to", "10.0.0.0/8", "lookup", "2",
        )
        ns(
            "ip", "rule", "add", "priority", "3",
            "iif", "host0", "type", "unreachable",
        )

        before = route_get()
        before_text = before.stdout + before.stderr
        if "vpns00" not in before_text:
            print("FAIL before: more-specific Profile did not select vpns00")
            print(before_text)
            return 1

        backend = SubprocessBackend()
        snapshot = collect_environment_snapshot(
            NS,
            lambda argv: backend.run(argv).stdout,
        )

        desired = KernelDesiredState(
            routes=(
                KernelRouteSpec(
                    table=1,
                    destination=ipaddress.IPv4Network("0.0.0.0/0"),
                    route_type="blackhole",
                    protocol=201,
                    metric=65536,
                ),
                KernelRouteSpec(
                    table=2,
                    destination=ipaddress.IPv4Network("10.0.0.0/8"),
                    route_type="unicast",
                    protocol=202,
                    metric=1,
                    ifname="vpns01",
                ),
                KernelRouteSpec(
                    table=2,
                    destination=ipaddress.IPv4Network("0.0.0.0/0"),
                    route_type="blackhole",
                    protocol=201,
                    metric=65536,
                ),
            ),
            rules=(),
            owned_tables=(1, 2),
        )
        plan = compile_lifecycle_route_rebuild_plan(desired, snapshot)
        if any(command.argv[:4] == ("ip", "route", "flush", "table") for command in plan.commands):
            print("FAIL plan contains route flush")
            return 1
        if not any(
            command.argv[:4] == ("ip", "route", "del", "table")
            and "10.20.0.0/16" in command.argv
            for command in plan.commands
        ):
            print("FAIL plan did not delete stale more-specific route")
            return 1

        execute_kernel_mutation_plan(plan, NamespaceBackend(NS, backend))

        table1 = ns("ip", "route", "show", "table", "1").stdout
        if "blackhole default" not in table1:
            print("FAIL terminal blackhole disappeared")
            print(table1)
            return 1
        if "10.20.0.0/16" in table1:
            print("FAIL stale route remains")
            print(table1)
            return 1

        after = route_get()
        after_text = after.stdout + after.stderr
        if "vpns01" in after_text:
            print("FAIL more-specific lookup fell through to broader Profile")
            print(after_text)
            return 1

        print("NG1_LIFECYCLE_ROUTE_DIFF=PASS")
        print("AFTER_LOOKUP:", after_text.strip() or f"returncode={after.returncode}")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
