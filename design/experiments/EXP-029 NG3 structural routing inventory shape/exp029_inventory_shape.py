from __future__ import annotations

import json
import os
import subprocess
import sys


PAYLOAD_TABLE = 0x80000000
PROBE_TABLE = 0xC0000000
PROBE_RULE = 0x2000
PAYLOAD_RULE = 0x4000
PATH_PROTO = 202
GUARD_PROTO = 201


def run(*argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=check,
        text=True,
        capture_output=True,
    )


def load_json(stdout: str):
    value = json.loads(stdout)
    assert isinstance(value, list), value
    assert all(isinstance(row, dict) for row in value), value
    return value


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-029 must run as root")

    ns = f"vpng-exp029-{os.getpid()}"
    try:
        run("ip", "netns", "add", ns)
        for ifname in ("host0", "path0", "path1"):
            run("ip", "-n", ns, "link", "add", ifname, "type", "dummy")
            run("ip", "-n", ns, "link", "set", ifname, "up")
        run("ip", "-n", ns, "-4", "addr", "add", "192.0.2.1/24", "dev", "host0")

        run(
            "ip", "-n", ns, "-4", "route", "add", "unicast",
            "10.77.0.0/16",
            "table", str(PAYLOAD_TABLE),
            "proto", str(PATH_PROTO),
            "metric", "1",
            "dev", "path0",
        )
        run(
            "ip", "-n", ns, "-4", "route", "add", "blackhole", "default",
            "table", str(PAYLOAD_TABLE),
            "proto", str(GUARD_PROTO),
            "metric", str(0xFFFFFFFF),
        )
        run(
            "ip", "-n", ns, "-4", "route", "add", "unicast",
            "198.51.100.7/32",
            "table", str(PROBE_TABLE),
            "proto", str(PATH_PROTO),
            "metric", "1",
            "dev", "path1",
        )

        run(
            "ip", "-n", ns, "-4", "rule", "add",
            "priority", str(PROBE_RULE),
            "fwmark", "0x1234/0xffff",
            "lookup", str(PROBE_TABLE),
        )
        run(
            "ip", "-n", ns, "-4", "rule", "add",
            "priority", str(PAYLOAD_RULE),
            "iif", "host0",
            "to", "10.77.0.0/16",
            "lookup", str(PAYLOAD_TABLE),
        )

        routes = load_json(
            run(
                "ip", "-n", ns, "-j", "-N", "-4",
                "route", "show", "table", "all",
            ).stdout
        )
        rules = load_json(
            run(
                "ip", "-n", ns, "-j", "-N", "-4",
                "rule", "show",
            ).stdout
        )

        managed_routes = [
            row for row in routes
            if str(row.get("table")) in (str(PAYLOAD_TABLE), str(PROBE_TABLE))
        ]
        managed_rules = [
            row for row in rules
            if str(row.get("priority")) in (str(PROBE_RULE), str(PAYLOAD_RULE))
        ]

        assert len(managed_routes) == 3, managed_routes
        assert len(managed_rules) == 2, managed_rules

        print("EXP029_ROUTES_JSON=" + json.dumps(managed_routes, sort_keys=True))
        print("EXP029_RULES_JSON=" + json.dumps(managed_rules, sort_keys=True))
        print("EXP-029 structural routing inventory shape: PASS")
        return 0
    finally:
        run("ip", "netns", "del", ns, check=False)


if __name__ == "__main__":
    sys.exit(main())
