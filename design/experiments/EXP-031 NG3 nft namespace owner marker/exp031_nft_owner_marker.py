from __future__ import annotations

import json
import os
import subprocess
import sys


OWNER_COMMENT = "vpn-gate:ng3:owner-v1"


def run(*argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=check,
        text=True,
        capture_output=True,
    )


def nft_script(namespace: str, script: str) -> None:
    completed = subprocess.run(
        (
            "ip",
            "netns",
            "exec",
            namespace,
            "nft",
            "-f",
            "-",
        ),
        input=script,
        check=True,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0


def ruleset(namespace: str) -> dict:
    completed = run(
        "ip",
        "netns",
        "exec",
        namespace,
        "nft",
        "-j",
        "list",
        "ruleset",
    )
    value = json.loads(completed.stdout)
    assert isinstance(value, dict), value
    assert isinstance(value.get("nftables"), list), value
    return value


def tables(value: dict) -> list[dict]:
    return [
        row["table"]
        for row in value["nftables"]
        if isinstance(row, dict)
        and isinstance(row.get("table"), dict)
    ]


def find_table(value: dict, family: str, name: str) -> dict | None:
    matches = [
        row
        for row in tables(value)
        if row.get("family") == family and row.get("name") == name
    ]
    assert len(matches) <= 1, matches
    return matches[0] if matches else None


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-031 must run as root")

    ns = f"vpng-exp031-{os.getpid()}"
    try:
        run("ip", "netns", "add", ns)

        initial = ruleset(ns)
        assert find_table(initial, "ip", "vpn_gate") is None

        # A foreign table coexists and must remain distinguishable.
        nft_script(
            ns,
            """table ip foreign_test {
    comment "foreign:keep"
}
""",
        )

        # H1/H2: exact versioned owner comment is accepted and round-trips.
        nft_script(
            ns,
            f"""table ip vpn_gate {{
    comment "{OWNER_COMMENT}"
}}
""",
        )
        marked = ruleset(ns)
        owned = find_table(marked, "ip", "vpn_gate")
        foreign = find_table(marked, "ip", "foreign_test")
        assert owned is not None, marked
        assert owned.get("comment") == OWNER_COMMENT, owned
        assert foreign is not None, marked
        assert foreign.get("comment") == "foreign:keep", foreign

        print("EXP031_MARKED_TABLE_JSON=" + json.dumps(owned, sort_keys=True))

        # H3: same-name table without marker is observably different.
        run(
            "ip", "netns", "exec", ns,
            "nft", "delete", "table", "ip", "vpn_gate",
        )
        run(
            "ip", "netns", "exec", ns,
            "nft", "add", "table", "ip", "vpn_gate",
        )
        unmarked_ruleset = ruleset(ns)
        unmarked = find_table(unmarked_ruleset, "ip", "vpn_gate")
        assert unmarked is not None, unmarked_ruleset
        assert unmarked.get("comment") != OWNER_COMMENT, unmarked

        # H4: foreign table survived all owner-table operations.
        foreign_after = find_table(unmarked_ruleset, "ip", "foreign_test")
        assert foreign_after is not None, unmarked_ruleset
        assert foreign_after.get("comment") == "foreign:keep", foreign_after

        print("EXP031_UNMARKED_TABLE_JSON=" + json.dumps(unmarked, sort_keys=True))
        print("EXP-031 nft namespace owner marker: PASS")
        return 0
    finally:
        run("ip", "netns", "del", ns, check=False)


if __name__ == "__main__":
    sys.exit(main())
