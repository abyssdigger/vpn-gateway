#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import uuid

UID = 4242
TARGET = "198.51.100.7"
MARK = 0x20000001
COMMENT = "vpn-gate:ng3:probe-local-v1"


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


def nsexec(ns: str, *args: str) -> subprocess.CompletedProcess[str]:
    return run("ip", "netns", "exec", ns, *args)


def main() -> int:
    if os.geteuid() != 0:
        print("EXP066_RESULT=SKIP root required")
        return 77

    ns = "vpng-exp066-" + uuid.uuid4().hex[:8]
    run("ip", "netns", "add", ns)
    try:
        nsexec(ns, "ip", "link", "add", "path0", "type", "dummy")
        nsexec(ns, "ip", "link", "set", "path0", "up")
        link = json.loads(
            nsexec(ns, "ip", "-j", "link", "show", "dev", "path0").stdout
        )[0]
        ifindex = int(link["ifindex"])

        script = "\n".join(
            (
                "table ip vpn_gate {",
                "  chain stack_output {",
                "    type filter hook output priority 0; policy drop;",
                "  }",
                "  chain stack_input {",
                "    type filter hook input priority 0; policy drop;",
                "  }",
                "}",
                (
                    "add rule ip vpn_gate stack_output "
                    f"meta skuid {UID} "
                    f"meta oif {ifindex} "
                    f"ip daddr {TARGET} "
                    "ip protocol icmp "
                    f"ct mark set {hex(MARK)} "
                    "accept "
                    f'comment "{COMMENT}"'
                ),
                (
                    "add rule ip vpn_gate stack_input "
                    f"meta iif {ifindex} "
                    f"ip saddr {TARGET} "
                    "ip protocol icmp "
                    f"ct mark {hex(MARK)} "
                    "accept "
                    f'comment "{COMMENT}"'
                ),
                "",
            )
        )
        proc = subprocess.run(
            ("ip", "netns", "exec", ns, "nft", "-f", "-"),
            input=script,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr)

        output_doc = json.loads(
            nsexec(
                ns, "nft", "-j", "-nn", "list", "chain",
                "ip", "vpn_gate", "stack_output",
            ).stdout
        )
        input_doc = json.loads(
            nsexec(
                ns, "nft", "-j", "-nn", "list", "chain",
                "ip", "vpn_gate", "stack_input",
            ).stdout
        )
        print("EXP066_OUTPUT_JSON=" + json.dumps(output_doc, sort_keys=True, separators=(",", ":")))
        print("EXP066_INPUT_JSON=" + json.dumps(input_doc, sort_keys=True, separators=(",", ":")))

        handles = []
        for document in (output_doc, input_doc):
            for row in document.get("nftables", []):
                payload = row.get("rule") if isinstance(row, dict) else None
                if isinstance(payload, dict) and payload.get("comment") == COMMENT:
                    handle = payload.get("handle")
                    chain = payload.get("chain")
                    if type(handle) is not int or chain not in {"stack_output", "stack_input"}:
                        raise AssertionError(payload)
                    handles.append((chain, handle))

        if len(handles) != 2:
            raise AssertionError(handles)

        delete_script = "\n".join(
            f"delete rule ip vpn_gate {chain} handle {handle}"
            for chain, handle in handles
        ) + "\n"
        proc = subprocess.run(
            ("ip", "netns", "exec", ns, "nft", "-f", "-"),
            input=delete_script,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr)

        ruleset = json.loads(nsexec(ns, "nft", "-j", "list", "ruleset").stdout)
        leftovers = [
            row
            for row in ruleset.get("nftables", [])
            if isinstance(row, dict)
            and isinstance(row.get("rule"), dict)
            and row["rule"].get("comment") == COMMENT
        ]
        if leftovers:
            raise AssertionError(leftovers)
        print("EXP066_HANDLE_DELETE=PASS")
        print("EXP066_RESULT=PASS")
        return 0
    finally:
        run("ip", "netns", "del", ns, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
