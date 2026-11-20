#!/usr/bin/env python3
"""EXP-079: absolute managed-boundary bypass around helper RPDB rules."""

from __future__ import annotations

import json
import os
import subprocess


PID = os.getpid()
HOST = f"v79h-{PID}"
STACK = f"v79s-{PID}"
GW = f"v79g-{PID}"
BH, BS = "vpng0", "stack0"
HU, GU = "e79hu", "e79gu"
HOST_UP, GW_IP = "192.0.2.1", "192.0.2.2"
TARGET = "8.8.4.4"
TABLE = 0x7FFF0004
BYPASS = 0x6002
PRESERVE = 0x6003
DISPATCH = 0x6004
EXIT = 0x7000
PROTO = 204


def run(*args, check=True):
    return subprocess.run(
        args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check
    )


def ns(name, *args, check=True):
    return run("ip", "netns", "exec", name, *args, check=check)


def route_get(*extra, check=True):
    result = ns(HOST, "ip", "-j", "-4", "route", "get", TARGET, *extra, check=check)
    if not check:
        return result
    rows = json.loads(result.stdout)
    assert len(rows) == 1, rows
    return rows[0]


def setup():
    for name in (HOST, STACK, GW):
        run("ip", "netns", "add", name)
        ns(name, "ip", "link", "set", "lo", "up")

    run("ip", "link", "add", BH, "type", "veth", "peer", "name", BS)
    run("ip", "link", "set", BH, "netns", HOST)
    run("ip", "link", "set", BS, "netns", STACK)
    run("ip", "link", "add", HU, "type", "veth", "peer", "name", GU)
    run("ip", "link", "set", HU, "netns", HOST)
    run("ip", "link", "set", GU, "netns", GW)

    ns(HOST, "ip", "addr", "add", f"{HOST_UP}/30", "dev", HU)
    ns(GW, "ip", "addr", "add", f"{GW_IP}/30", "dev", GU)
    for name, interfaces in ((HOST, (BH, HU)), (STACK, (BS,)), (GW, (GU,))):
        for interface in interfaces:
            ns(name, "ip", "link", "set", interface, "up")

    ns(GW, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")
    ns(HOST, "ip", "route", "add", "default", "via", GW_IP, "dev", HU)
    ns(HOST, "ip", "-4", "route", "add", "table", str(TABLE), "default", "dev", BH, "proto", str(PROTO))

    ns(HOST, "ip", "-4", "rule", "add", "priority", str(BYPASS), "protocol", str(PROTO), "iif", BH, "goto", str(EXIT))
    ns(HOST, "ip", "-4", "rule", "add", "priority", str(PRESERVE), "protocol", str(PROTO), "lookup", "main", "suppress_prefixlength", "0")
    ns(HOST, "ip", "-4", "rule", "add", "priority", str(DISPATCH), "protocol", str(PROTO), "lookup", str(TABLE))
    ns(HOST, "ip", "-4", "rule", "add", "priority", str(EXIT), "protocol", str(PROTO), "type", "nop")


def main():
    if os.geteuid() != 0:
        print("EXP079_RESULT=SKIP root required")
        return 77

    try:
        setup()

        stack = route_get("from", "198.18.79.2", "iif", BH)
        assert stack.get("dev") == HU and stack.get("gateway") == GW_IP, stack
        print("EXP079_STACK_SKIPS_HELPER=PASS", flush=True)

        local = route_get()
        assert local.get("dev") == BH, local
        print("EXP079_NONSTACK_DISPATCH=PASS", flush=True)

        rules = json.loads(ns(HOST, "ip", "-j", "-4", "rule", "show").stdout)
        goto_rows = [r for r in rules if r.get("priority") == BYPASS]
        nop_rows = [r for r in rules if r.get("priority") == EXIT]
        assert len(goto_rows) == 1 and goto_rows[0].get("iif") == BH, goto_rows
        assert int(goto_rows[0].get("goto")) == EXIT, goto_rows
        assert len(nop_rows) == 1 and "nop" in nop_rows[0], nop_rows
        print("EXP079_JSON_SHAPE=PASS", flush=True)

        ns(HOST, "ip", "route", "del", "default", "via", GW_IP, "dev", HU)
        missing = route_get("from", "198.18.79.2", "iif", BH, check=False)
        assert missing.returncode != 0, (missing.returncode, missing.stdout, missing.stderr)
        assert BH not in missing.stdout, missing.stdout
        print("EXP079_NO_ROUTE_NO_RECAPTURE=PASS", flush=True)

        print("EXP079_RESULT=PASS", flush=True)
        return 0
    finally:
        for name in (GW, STACK, HOST):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
