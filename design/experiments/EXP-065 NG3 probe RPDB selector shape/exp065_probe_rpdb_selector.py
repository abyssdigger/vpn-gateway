#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

TABLE = 0xC0000000
PRIORITY = 0x2000
UID = 4242
TARGET = "198.51.100.7"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed {args!r}: rc={result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def ipn(ns: str, *args: str, check: bool = True):
    return run("ip", "-n", ns, *args, check=check)


def main() -> int:
    if os.geteuid() != 0:
        print("EXP065_RESULT=SKIP root required")
        return 77

    ns = "vpng-exp065-" + uuid.uuid4().hex[:8]
    run("ip", "netns", "add", ns)
    try:
        ipn(ns, "link", "add", "path0", "type", "dummy")
        ipn(ns, "link", "set", "path0", "up")
        ipn(
            ns, "-4", "route", "add", f"{TARGET}/32",
            "dev", "path0",
            "table", str(TABLE),
            "protocol", "202",
            "metric", "1",
        )
        ipn(
            ns, "-4", "route", "add", "blackhole", "default",
            "table", str(TABLE),
            "protocol", "201",
            "metric", str(0xFFFFFFFF),
        )
        ipn(
            ns, "-4", "rule", "add",
            "priority", str(PRIORITY),
            "uidrange", f"{UID}-{UID}",
            "ipproto", "icmp",
            "to", f"{TARGET}/32",
            "lookup", str(TABLE),
        )

        raw = ipn(ns, "-j", "-N", "-4", "rule", "show").stdout
        rows = json.loads(raw)
        row = next(item for item in rows if item.get("priority") == PRIORITY)
        print("EXP065_RULE_JSON=" + json.dumps(row, sort_keys=True, separators=(",", ":")))

        if row.get("table") not in (TABLE, str(TABLE)):
            raise AssertionError(row)
        if row.get("src") != "all":
            raise AssertionError(row)

        matching = ipn(
            ns, "-j", "-4", "route", "get", TARGET,
            "uid", str(UID),
            "ipproto", "icmp",
        )
        matching_rows = json.loads(matching.stdout)
        if not matching_rows:
            raise AssertionError("matching lookup returned no rows")
        match = matching_rows[0]
        print("EXP065_MATCH_JSON=" + json.dumps(match, sort_keys=True, separators=(",", ":")))
        if match.get("dev") != "path0":
            raise AssertionError(match)

        other = ipn(
            ns, "-j", "-4", "route", "get", TARGET,
            "uid", str(UID + 1),
            "ipproto", "icmp",
            check=False,
        )
        print(
            "EXP065_OTHER_UID_RC="
            + str(other.returncode)
            + " OUT="
            + other.stdout.strip().replace("\n", " ")
        )
        if other.returncode == 0:
            other_rows = json.loads(other.stdout)
            if other_rows and other_rows[0].get("dev") == "path0":
                raise AssertionError(
                    "non-matching UID unexpectedly selected probe path"
                )

        print("EXP065_RESULT=PASS")
        return 0
    finally:
        run("ip", "netns", "del", ns, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
