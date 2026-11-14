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


def setup() -> None:
    cleanup()
    run("ip", "netns", "add", NS)
    ns("ip", "link", "set", "lo", "up")
    for name in PATHS:
        peer = "peer-" + name
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
                f"multiple owned routes occupy metric {metric}: {routes(table)!r}"
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
        if str(item.get("protocol")) not in {TERMINAL_PROTO, "201"}:
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


def move_gap(
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
            f"{label}: target metric {target_metric} is not free: {before!r}"
        )
    if before.get(source_metric) != dev:
        raise RuntimeError(
            f"{label}: source metric does not contain {dev}: {before!r}"
        )

    # Make: the complete eligible set remains present and the moved path is the
    # only temporary duplicate.
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
            f"{label}: add phase did not create one extra route: {duplicated!r}"
        )
    if set(duplicated.values()) != set(PATHS):
        raise RuntimeError(
            f"{label}: add phase lost an eligible path: {duplicated!r}"
        )
    if counts[dev] != 2 or sum(value == 2 for value in counts.values()) != 1:
        raise RuntimeError(
            f"{label}: add phase must have exactly one duplicate: {duplicated!r}"
        )
    if not terminal_present(table, destination):
        raise RuntimeError(f"{label}: terminal disappeared during add phase")

    # Break only the old copy. Its metric automatically becomes the new free slot.
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
            f"{label}: old metric did not become free: {after!r}"
        )
    if after.get(target_metric) != dev:
        raise RuntimeError(
            f"{label}: moved path is absent from target metric: {after!r}"
        )
    if not terminal_present(table, destination):
        raise RuntimeError(f"{label}: terminal disappeared during delete phase")


def apply_moves(
    table: int,
    destination: str,
    label: str,
    moves: tuple[tuple[str, int, int], ...],
) -> None:
    for index, (dev, source_metric, target_metric) in enumerate(moves, 1):
        move_gap(
            table,
            destination,
            dev=dev,
            source_metric=source_metric,
            target_metric=target_metric,
            label=f"{label}-{index}-{dev}",
        )


def exercise(table: int, destination: str, label: str) -> None:
    # Recovery with a real steady-state gap before the first non-confirmed path:
    # A B G D . V E J -> A B V G D . E J
    middle_dead = {
        10: "patha",
        20: "pathb",
        30: "pathg",
        40: "pathd",
        60: "pathv",
        70: "pathe",
        80: "pathj",
    }
    middle_live = {
        10: "patha",
        20: "pathb",
        30: "pathv",
        40: "pathg",
        50: "pathd",
        70: "pathe",
        80: "pathj",
    }
    reset_routes(table, destination, middle_dead)
    apply_moves(
        table,
        destination,
        f"{label}-recover-middle",
        (
            ("pathd", 40, 50),
            ("pathg", 30, 40),
            ("pathv", 60, 30),
        ),
    )
    assert_steady(table, destination, middle_live, f"{label} recovery middle")
    print(
        f"PASS {label}1: ABGD.VEJ -> ABVGD.EJ kept the full eligible set"
    )

    # Demotion is the same primitive in the other direction:
    # A B V G D . E J -> A B G D . V E J
    apply_moves(
        table,
        destination,
        f"{label}-demote-middle",
        (
            ("pathv", 30, 60),
            ("pathg", 40, 30),
            ("pathd", 50, 40),
        ),
    )
    assert_steady(table, destination, middle_dead, f"{label} demotion middle")
    print(
        f"PASS {label}2: ABVGD.EJ -> ABGD.VEJ kept the full eligible set"
    )

    # Recovery when the recovered path is the last non-confirmed path:
    # A B G D E J . V -> A B V G D E J
    tail_dead = {
        10: "patha",
        20: "pathb",
        30: "pathg",
        40: "pathd",
        50: "pathe",
        60: "pathj",
        80: "pathv",
    }
    all_live = {
        10: "patha",
        20: "pathb",
        30: "pathv",
        40: "pathg",
        50: "pathd",
        60: "pathe",
        70: "pathj",
    }
    reset_routes(table, destination, tail_dead)
    apply_moves(
        table,
        destination,
        f"{label}-recover-tail",
        (
            ("pathj", 60, 70),
            ("pathe", 50, 60),
            ("pathd", 40, 50),
            ("pathg", 30, 40),
            ("pathv", 80, 30),
        ),
    )
    assert_steady(table, destination, all_live, f"{label} all live")
    print(
        f"PASS {label}3: ABGDEJ.V -> ABVGDEJ used the free N+1 metric only as scratch"
    )

    # Death from all-live has no steady-state gap initially. The next metric is
    # simply unused and can receive the newly non-confirmed path first:
    # A B V G D E J -> A B G D E J . V
    apply_moves(
        table,
        destination,
        f"{label}-demote-from-all-live",
        (
            ("pathv", 30, 80),
            ("pathg", 40, 30),
            ("pathd", 50, 40),
            ("pathe", 60, 50),
            ("pathj", 70, 60),
        ),
    )
    assert_steady(table, destination, tail_dead, f"{label} death from all-live")
    print(
        f"PASS {label}4: ABVGDEJ -> ABGDEJ.V created the boundary gap without route loss"
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
