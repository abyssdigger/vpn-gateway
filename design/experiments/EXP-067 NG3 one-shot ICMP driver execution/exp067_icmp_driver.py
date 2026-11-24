#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import uuid

UID = 4242
MARK = 0x20000001
TABLE = 0xC0000000
PRIORITY = 0x2000
REPLY_TARGET = "192.0.2.2"
SILENT_TARGET = "192.0.2.3"
LOCAL_ERROR_TARGET = "203.0.113.7"


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


def ns(nsname: str, *args: str, check: bool = True):
    return run("ip", "netns", "exec", nsname, *args, check=check)


def ping_as_probe(nsname: str, target: str):
    return ns(
        nsname,
        "setpriv",
        "--reuid", str(UID),
        "--regid", str(UID),
        "--clear-groups",
        "ping",
        "-n",
        "-c", "1",
        "-W", "1",
        target,
        check=False,
    )


def add_probe_target(nsname: str, ifindex: int, target: str, priority: int):
    ns(
        nsname,
        "ip", "-4", "route", "add", f"{target}/32",
        "dev", "path0",
        "table", str(TABLE),
        "protocol", "202",
        "metric", "1",
    )
    ns(
        nsname,
        "ip", "-4", "rule", "add",
        "priority", str(priority),
        "uidrange", f"{UID}-{UID}",
        "ipproto", "icmp",
        "to", f"{target}/32",
        "lookup", str(TABLE),
    )
    script = "\n".join(
        (
            (
                "add rule ip vpn_gate stack_output "
                f"meta skuid {UID} meta oif {ifindex} "
                f"ip daddr {target} ip protocol icmp "
                f"ct mark set {hex(MARK)} accept "
                'comment "vpn-gate:ng3:probe-local-v1"'
            ),
            (
                "add rule ip vpn_gate stack_input "
                f"meta iif {ifindex} ip saddr {target} "
                f"ip protocol icmp ct mark {hex(MARK)} accept "
                'comment "vpn-gate:ng3:probe-local-v1"'
            ),
            "",
        )
    )
    value = subprocess.run(
        ("ip", "netns", "exec", nsname, "nft", "-f", "-"),
        input=script,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if value.returncode != 0:
        raise RuntimeError(value.stderr)


def main() -> int:
    if os.geteuid() != 0:
        print("EXP067_RESULT=SKIP root required")
        return 77

    suffix = uuid.uuid4().hex[:8]
    managed = "vpng-exp067-m-" + suffix
    remote = "vpng-exp067-r-" + suffix
    run("ip", "netns", "add", managed)
    run("ip", "netns", "add", remote)
    try:
        run(
            "ip", "link", "add", "vpng067m", "type", "veth",
            "peer", "name", "vpng067r",
        )
        run("ip", "link", "set", "vpng067m", "netns", managed)
        run("ip", "link", "set", "vpng067r", "netns", remote)
        ns(managed, "ip", "link", "set", "vpng067m", "name", "path0")
        ns(remote, "ip", "link", "set", "vpng067r", "name", "peer0")
        ns(managed, "ip", "addr", "add", "192.0.2.1/24", "dev", "path0")
        ns(remote, "ip", "addr", "add", "192.0.2.2/24", "dev", "peer0")
        ns(managed, "ip", "link", "set", "lo", "up")
        ns(remote, "ip", "link", "set", "lo", "up")
        ns(managed, "ip", "link", "set", "path0", "up")
        ns(remote, "ip", "link", "set", "peer0", "up")

        link = json.loads(
            ns(managed, "ip", "-j", "link", "show", "dev", "path0").stdout
        )[0]
        ifindex = int(link["ifindex"])

        nft_script = "\n".join(
            (
                "table ip vpn_gate {",
                "  chain stack_output {",
                "    type filter hook output priority 0; policy drop;",
                "  }",
                "  chain stack_input {",
                "    type filter hook input priority 0; policy drop;",
                "  }",
                "}",
                "",
            )
        )
        value = subprocess.run(
            ("ip", "netns", "exec", managed, "nft", "-f", "-"),
            input=nft_script,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if value.returncode != 0:
            raise RuntimeError(value.stderr)

        ns(
            managed,
            "ip", "-4", "route", "add", "blackhole", "default",
            "table", str(TABLE),
            "protocol", "201",
            "metric", str(0xFFFFFFFF),
        )
        add_probe_target(managed, ifindex, REPLY_TARGET, PRIORITY)
        add_probe_target(managed, ifindex, SILENT_TARGET, PRIORITY + 1)

        lookup = ns(
            managed,
            "ip", "-j", "-4", "route", "get", REPLY_TARGET,
            "uid", str(UID),
            "ipproto", "icmp",
        )
        lookup_row = json.loads(lookup.stdout)[0]
        print(
            "EXP067_LOOKUP_JSON="
            + json.dumps(lookup_row, sort_keys=True, separators=(",", ":"))
        )
        if lookup_row.get("dev") != "path0":
            raise AssertionError(lookup_row)
        if str(lookup_row.get("table")) != str(TABLE):
            raise AssertionError(lookup_row)

        reply = ping_as_probe(managed, REPLY_TARGET)
        print(
            f"EXP067_REPLY_RC={reply.returncode} "
            f"OUT={reply.stdout.strip().replace(chr(10), ' ')} "
            f"ERR={reply.stderr.strip().replace(chr(10), ' ')}"
        )
        if reply.returncode != 0:
            raise AssertionError("reply target did not produce ping exit 0")

        silent = ping_as_probe(managed, SILENT_TARGET)
        print(
            f"EXP067_NO_REPLY_RC={silent.returncode} "
            f"OUT={silent.stdout.strip().replace(chr(10), ' ')} "
            f"ERR={silent.stderr.strip().replace(chr(10), ' ')}"
        )
        if silent.returncode != 1:
            raise AssertionError(
                f"silent valid target expected exit 1, got {silent.returncode}"
            )

        local_error = ping_as_probe(managed, LOCAL_ERROR_TARGET)
        print(
            f"EXP067_LOCAL_ERROR_RC={local_error.returncode} "
            f"OUT={local_error.stdout.strip().replace(chr(10), ' ')} "
            f"ERR={local_error.stderr.strip().replace(chr(10), ' ')}"
        )
        if local_error.returncode in (0, 1):
            raise AssertionError(
                "local route/setup failure did not produce distinct exit status"
            )

        print("EXP067_RESULT=PASS")
        return 0
    finally:
        run("ip", "netns", "del", managed, check=False)
        run("ip", "netns", "del", remote, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
