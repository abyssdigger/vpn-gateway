from __future__ import annotations

import json
import os
import subprocess
import sys


PAYLOAD_TABLE_FIRST = 0x80000000
PROBE_TABLE_FIRST = 0xC0000000
PROBE_RULE_FIRST = 0x2000
PAYLOAD_RULE_FIRST = 0x4000
AMBIENT_MAIN_RULE = 32766
PATH_PROTO = 202
GUARD_PROTO = 201
FIRST_METRIC = 1
GUARD_METRIC = 0xFFFFFFFF
NFT_FAMILY = "ip"
NFT_TABLE = "vpn_gate"


def run(*argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=check,
        text=True,
        capture_output=True,
    )


def ip_json(ns: str, *args: str) -> list[dict]:
    completed = run("ip", "-n", ns, "-j", "-N", *args)
    value = json.loads(completed.stdout)
    assert isinstance(value, list), value
    assert all(isinstance(item, dict) for item in value), value
    return value


def route_protocol(row: dict) -> int | None:
    value = row.get("protocol")
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    raise AssertionError(f"unexpected protocol representation: {value!r}")


def route_table(row: dict) -> int | None:
    value = row.get("table")
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    raise AssertionError(f"unexpected table representation: {value!r}")


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-028 must run as root")

    ns = f"vpng-exp028-{os.getpid()}"

    try:
        run("ip", "netns", "add", ns)
        for ifname in ("host0", "path0", "path1"):
            run("ip", "-n", ns, "link", "add", ifname, "type", "dummy")
            run("ip", "-n", ns, "link", "set", ifname, "up")

        # H1/H3/H4: high 32-bit table IDs, role protocols and full u32 guard metric.
        run(
            "ip", "-n", ns, "-4", "route", "add", "unicast",
            "10.77.0.0/16",
            "table", str(PAYLOAD_TABLE_FIRST),
            "proto", str(PATH_PROTO),
            "metric", str(FIRST_METRIC),
            "dev", "path0",
        )
        run(
            "ip", "-n", ns, "-4", "route", "add", "blackhole", "default",
            "table", str(PAYLOAD_TABLE_FIRST),
            "proto", str(GUARD_PROTO),
            "metric", str(GUARD_METRIC),
        )
        run(
            "ip", "-n", ns, "-4", "route", "add", "unicast",
            "198.51.100.7/32",
            "table", str(PROBE_TABLE_FIRST),
            "proto", str(PATH_PROTO),
            "metric", str(FIRST_METRIC),
            "dev", "path1",
        )

        payload_routes = ip_json(
            ns, "-4", "route", "show", "table", str(PAYLOAD_TABLE_FIRST)
        )
        probe_routes = ip_json(
            ns, "-4", "route", "show", "table", str(PROBE_TABLE_FIRST)
        )

        assert len(payload_routes) == 2, payload_routes
        assert len(probe_routes) == 1, probe_routes

        normal = next(row for row in payload_routes if row.get("dst") == "10.77.0.0/16")
        guard_rows = [
            row
            for row in payload_routes
            if route_protocol(row) == GUARD_PROTO
            and row.get("dst") == "default"
            and row.get("metric") == GUARD_METRIC
        ]
        assert len(guard_rows) == 1, payload_routes
        guard = guard_rows[0]
        probe = probe_routes[0]

        assert route_table(normal) in (None, PAYLOAD_TABLE_FIRST), normal
        assert route_protocol(normal) == PATH_PROTO, normal
        assert normal.get("metric") == FIRST_METRIC, normal
        assert normal.get("dev") == "path0", normal

        assert guard.get("type") in ("blackhole", 6, "6"), guard
        assert route_protocol(guard) == GUARD_PROTO, guard
        assert guard.get("metric") == GUARD_METRIC, guard
        assert guard.get("dst") == "default", guard

        assert route_table(probe) in (None, PROBE_TABLE_FIRST), probe
        assert route_protocol(probe) == PATH_PROTO, probe
        assert probe.get("metric") == FIRST_METRIC, probe
        assert probe.get("dev") == "path1", probe

        # Filtered protocol inventory must still find the selected owned route.
        filtered = ip_json(
            ns,
            "-4", "route", "show",
            "table", str(PAYLOAD_TABLE_FIRST),
            "proto", str(PATH_PROTO),
        )
        assert len(filtered) == 1, filtered
        assert filtered[0].get("dst") == "10.77.0.0/16", filtered

        # H2: selected RPDB quarters coexist before the default main rule.
        run(
            "ip", "-n", ns, "-4", "rule", "add",
            "priority", str(PROBE_RULE_FIRST),
            "fwmark", "0x1",
            "lookup", str(PROBE_TABLE_FIRST),
        )
        run(
            "ip", "-n", ns, "-4", "rule", "add",
            "priority", str(PAYLOAD_RULE_FIRST),
            "iif", "host0",
            "to", "10.77.0.0/16",
            "lookup", str(PAYLOAD_TABLE_FIRST),
        )

        rules = ip_json(ns, "-4", "rule", "show")
        priorities = [
            int(row["priority"])
            for row in rules
            if "priority" in row
        ]
        assert PROBE_RULE_FIRST in priorities, rules
        assert PAYLOAD_RULE_FIRST in priorities, rules
        assert AMBIENT_MAIN_RULE in priorities, rules
        assert PROBE_RULE_FIRST < PAYLOAD_RULE_FIRST < AMBIENT_MAIN_RULE

        # Route lookup proves that the actual rules select the high-ID tables.
        probe_get = ip_json(
            ns, "-4", "route", "get", "198.51.100.7", "mark", "0x1"
        )
        assert len(probe_get) == 1, probe_get
        assert route_table(probe_get[0]) == PROBE_TABLE_FIRST, probe_get
        assert probe_get[0].get("dev") == "path1", probe_get

        payload_get = ip_json(
            ns,
            "-4", "route", "get",
            "10.77.1.1",
            "from", "192.0.2.2",
            "iif", "host0",
        )
        assert len(payload_get) == 1, payload_get
        assert route_table(payload_get[0]) == PAYLOAD_TABLE_FIRST, payload_get
        assert payload_get[0].get("dev") == "path0", payload_get

        # H5: dedicated nft namespace is representable and removable in the netns.
        run(
            "ip", "netns", "exec", ns,
            "nft", "add", "table", NFT_FAMILY, NFT_TABLE,
        )
        nft_list = run(
            "ip", "netns", "exec", ns,
            "nft", "-j", "list", "table", NFT_FAMILY, NFT_TABLE,
        )
        nft_doc = json.loads(nft_list.stdout)
        assert isinstance(nft_doc, dict), nft_doc
        assert "nftables" in nft_doc, nft_doc
        run(
            "ip", "netns", "exec", ns,
            "nft", "delete", "table", NFT_FAMILY, NFT_TABLE,
        )
        absent = run(
            "ip", "netns", "exec", ns,
            "nft", "list", "table", NFT_FAMILY, NFT_TABLE,
            check=False,
        )
        assert absent.returncode != 0, absent

        print("EXP-028 lower policy platform space: PASS")
        return 0
    finally:
        run("ip", "netns", "del", ns, check=False)


if __name__ == "__main__":
    sys.exit(main())
