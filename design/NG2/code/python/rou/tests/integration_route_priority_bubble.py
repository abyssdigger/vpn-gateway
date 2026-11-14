from __future__ import annotations

from collections import Counter
import json
import os
import shutil
import subprocess


NS = "vpng2-bubble"
PREFIX = "198.51.100.0/24"
NORMAL_PROTO = "202"
TERMINAL_PROTO = "201"
TERMINAL_METRIC = 65536
PATHS = ("patha", "pathb", "pathv", "pathg", "pathd", "pathe", "pathj")


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
    for name in PATHS:
        run("ip", "link", "del", name, check=False)


def setup() -> None:
    cleanup()
    run("ip", "netns", "add", NS)
    ns("ip", "link", "set", "lo", "up")
    for name in PATHS:
        peer = "peer-" + name
        run("ip", "link", "del", peer, check=False)
        run("ip", "link", "add", name, "type", "veth", "peer", "name", peer)
        run("ip", "link", "set", name, "netns", NS)
        run("ip", "link", "set", peer, "netns", NS)
        ns("ip", "link", "set", name, "up")
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


def assert_steady(
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
    if set(observed.values()) != set(PATHS):
        raise RuntimeError(
            f"{label}: eligible path set changed: {observed!r}"
        )
    if len(observed) != len(PATHS):
        raise RuntimeError(
            f"{label}: steady state must contain exactly one route per path"
        )
    if not terminal_present(table, destination):
        raise RuntimeError(
            f"{label}: terminal blackhole disappeared: {routes(table)!r}"
        )


def reset_routes(
    table: int,
    destination: str,
    mapping: dict[int, str],
) -> None:
    ns("ip", "route", "flush", "table", str(table), check=False)
    for metric, dev in sorted(mapping.items()):
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
    assert_steady(table, destination, mapping, "reset")


def move_empty(
    table: int,
    destination: str,
    *,
    dev: str,
    source_metric: int,
    target_metric: int,
    label: str,
) -> None:
    before = route_map(table, destination)
    if target_metric in before:
        raise RuntimeError(
            f"{label}: target metric {target_metric} is not EMPTY: {before!r}"
        )
    if before.get(source_metric) != dev:
        raise RuntimeError(
            f"{label}: source slot mismatch: {before!r}"
        )

    ns(
        "ip",
        "route",
        "add",
        destination,
        "dev",
        dev,
        "metric",
        str(target_metric),
        "proto",
        NORMAL_PROTO,
        "table",
        str(table),
    )

    duplicated = route_map(table, destination)
    counts = Counter(duplicated.values())
    if len(duplicated) != len(PATHS) + 1:
        raise RuntimeError(
            f"{label}: add phase did not create exactly one extra route: "
            f"{duplicated!r}"
        )
    if set(duplicated.values()) != set(PATHS):
        raise RuntimeError(
            f"{label}: add phase lost an eligible path: {duplicated!r}"
        )
    if counts[dev] != 2 or sum(value == 2 for value in counts.values()) != 1:
        raise RuntimeError(
            f"{label}: add phase must contain exactly one duplicated path: "
            f"{duplicated!r}"
        )
    if not terminal_present(table, destination):
        raise RuntimeError(f"{label}: terminal disappeared during add phase")

    ns(
        "ip",
        "route",
        "del",
        destination,
        "dev",
        dev,
        "metric",
        str(source_metric),
        "proto",
        NORMAL_PROTO,
        "table",
        str(table),
    )

    after = route_map(table, destination)
    if len(after) != len(PATHS):
        raise RuntimeError(
            f"{label}: delete phase did not restore one route per path: {after!r}"
        )
    if set(after.values()) != set(PATHS):
        raise RuntimeError(
            f"{label}: delete phase lost an eligible path: {after!r}"
        )
    if source_metric in after:
        raise RuntimeError(
            f"{label}: old metric did not become EMPTY: {after!r}"
        )
    if after.get(target_metric) != dev:
        raise RuntimeError(
            f"{label}: moved path is absent from target metric: {after!r}"
        )
    if not terminal_present(table, destination):
        raise RuntimeError(f"{label}: terminal disappeared during delete phase")


def exercise(table: int, destination: str, label: str) -> None:
    # "." below is the technical EMPTY metric slot, not the availability
    # live/non-confirmed boundary. Production keeps it canonical at the tail.
    recovery_start = {
        10: "patha",
        20: "pathb",
        30: "pathg",
        40: "pathd",
        50: "pathv",
        60: "pathe",
        70: "pathj",
    }
    recovery_target = {
        10: "patha",
        20: "pathb",
        30: "pathv",
        40: "pathg",
        50: "pathd",
        60: "pathe",
        70: "pathj",
    }
    reset_routes(table, destination, recovery_start)
    for dev, source_metric, target_metric in (
        ("pathg", 30, 80),
        ("pathv", 50, 30),
        ("pathd", 40, 50),
        ("pathg", 80, 40),
    ):
        move_empty(
            table,
            destination,
            dev=dev,
            source_metric=source_metric,
            target_metric=target_metric,
            label=f"{label} recovery-{dev}",
        )
    assert_steady(table, destination, recovery_target, f"{label} recovery")
    print(
        f"PASS {label}1: recovery ABGDVEJ. -> ABVGDEJ. kept every path"
    )

    for dev, source_metric, target_metric in (
        ("pathv", 30, 80),
        ("pathg", 40, 30),
        ("pathd", 50, 40),
        ("pathv", 80, 50),
    ):
        move_empty(
            table,
            destination,
            dev=dev,
            source_metric=source_metric,
            target_metric=target_metric,
            label=f"{label} demotion-{dev}",
        )
    assert_steady(table, destination, recovery_start, f"{label} demotion")
    print(
        f"PASS {label}2: demotion ABVGDEJ. -> ABGDVEJ. kept every path"
    )

    end_start = {
        10: "patha",
        20: "pathb",
        30: "pathg",
        40: "pathd",
        50: "pathe",
        60: "pathj",
        70: "pathv",
    }
    end_target = recovery_target
    reset_routes(table, destination, end_start)
    for dev, source_metric, target_metric in (
        ("pathg", 30, 80),
        ("pathv", 70, 30),
        ("pathj", 60, 70),
        ("pathe", 50, 60),
        ("pathd", 40, 50),
        ("pathg", 80, 40),
    ):
        move_empty(
            table,
            destination,
            dev=dev,
            source_metric=source_metric,
            target_metric=target_metric,
            label=f"{label} tail-{dev}",
        )
    assert_steady(table, destination, end_target, f"{label} tail recovery")
    print(
        f"PASS {label}3: recovery ABGDEJV. -> ABVGDEJ. kept every path"
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
