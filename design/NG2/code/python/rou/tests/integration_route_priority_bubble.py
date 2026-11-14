from __future__ import annotations

import json
import os
import shutil
import subprocess


NS = "vpng2-bubble"
PREFIX = "198.51.100.0/24"
TARGET = "198.51.100.1"
NORMAL_PROTO = "202"
TERMINAL_PROTO = "201"
TERMINAL_METRIC = 65536


def run(*argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        text=True,
        capture_output=True,
        check=check,
    )


def ns(*argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("ip", "netns", "exec", NS, *argv, check=check)


def cleanup() -> None:
    run("ip", "netns", "del", NS, check=False)


def setup() -> None:
    cleanup()
    run("ip", "netns", "add", NS)
    ns("ip", "link", "set", "lo", "up")
    for suffix in ("patha", "pathb", "pathc", "pathd"):
        path = f"path{suffix}"
        peer = f"peer{suffix}"
        run("ip", "link", "del", peer, check=False)
        run("ip", "link", "add", path, "type", "veth", "peer", "name", peer)
        run("ip", "link", "set", path, "netns", NS)
        run("ip", "link", "set", peer, "netns", NS)
        ns("ip", "link", "set", path, "up")
        ns("ip", "link", "set", peer, "up")


def routes(table: int) -> list[dict]:
    result = ns(
        "ip",
        "-j",
        "-4",
        "route",
        "show",
        "table",
        str(table),
    )
    return json.loads(result.stdout)


def route_map(table: int, destination: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for item in routes(table):
        if item.get("dst") != destination:
            continue
        if item.get("type", "unicast") != "unicast":
            continue
        if str(item.get("protocol")) not in {NORMAL_PROTO, "202"}:
            continue
        metric = item.get("metric")
        dev = item.get("dev")
        if not isinstance(metric, int) or not isinstance(dev, str):
            continue
        if metric in out:
            raise RuntimeError(
                f"multiple unicast routes occupy metric {metric} in table {table}: "
                f"{routes(table)!r}"
            )
        out[metric] = dev
    return out


def terminal_present(table: int, destination: str) -> bool:
    for item in routes(table):
        if item.get("dst") != destination:
            continue
        if item.get("type") != "blackhole":
            continue
        if item.get("metric") != TERMINAL_METRIC:
            continue
        return True
    return False


def assert_map(
    table: int,
    destination: str,
    expected: dict[int, str],
    label: str,
) -> None:
    observed = route_map(table, destination)
    if observed != expected:
        raise RuntimeError(
            f"{label}: expected {expected!r}, observed {observed!r}; "
            f"full routes={routes(table)!r}"
        )
    if not terminal_present(table, destination):
        raise RuntimeError(
            f"{label}: terminal blackhole disappeared: {routes(table)!r}"
        )


def add_initial(table: int, destination: str) -> None:
    for metric, dev in ((10, "patha"), (20, "pathb"), (30, "pathc"), (40, "pathd")):
        ns(
            "ip",
            "route",
            "add",
            destination,
            "dev",
            dev,
            "metric",
            str(metric),
            "proto",
            NORMAL_PROTO,
            "table",
            str(table),
        )
    ns(
        "ip",
        "route",
        "add",
        "blackhole",
        destination,
        "metric",
        str(TERMINAL_METRIC),
        "proto",
        TERMINAL_PROTO,
        "table",
        str(table),
    )


def replace_slot(
    table: int,
    destination: str,
    metric: int,
    dev: str,
) -> None:
    result = ns(
        "ip",
        "route",
        "replace",
        destination,
        "dev",
        dev,
        "metric",
        str(metric),
        "proto",
        NORMAL_PROTO,
        "table",
        str(table),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"route replace failed for {destination} metric={metric} dev={dev}: "
            f"{result.stdout}{result.stderr}; routes={routes(table)!r}"
        )


def exercise(table: int, destination: str, label: str) -> None:
    add_initial(table, destination)
    assert_map(
        table,
        destination,
        {10: "patha", 20: "pathb", 30: "pathc", 40: "pathd"},
        f"{label} initial",
    )

    replace_slot(table, destination, 10, "pathb")
    assert_map(
        table,
        destination,
        {10: "pathb", 20: "pathb", 30: "pathc", 40: "pathd"},
        f"{label} duplicate-b",
    )
    print(
        f"PASS {label}1: metric-10 slot replaced A->B while B metric-20 survived"
    )

    replace_slot(table, destination, 20, "pathc")
    assert_map(
        table,
        destination,
        {10: "pathb", 20: "pathc", 30: "pathc", 40: "pathd"},
        f"{label} duplicate-c",
    )
    print(
        f"PASS {label}2: metric-20 slot replaced B->C while C metric-30 survived"
    )

    replace_slot(table, destination, 30, "patha")
    assert_map(
        table,
        destination,
        {10: "pathb", 20: "pathc", 30: "patha", 40: "pathd"},
        f"{label} final",
    )
    print(
        f"PASS {label}3: bubble transition converged A,B,C,D -> B,C,A,D"
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration experiment must run as root")
    if shutil.which("ip") is None:
        raise SystemExit("iproute2 is required")

    setup()
    try:
        exercise(427, PREFIX, "P")
        exercise(428, "default", "D")
        print("EXP027=PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
