from __future__ import annotations

import json
import os
import subprocess
import sys


TABLE_COMMENT = "vpn-gate:ng3:owner-v1"
INPUT_COMMENT = "vpn-gate:ng3:stack-input-v1"
OUTPUT_COMMENT = "vpn-gate:ng3:stack-output-v1"


def run(*argv: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        argv,
        input=input_text,
        check=check,
        text=True,
        capture_output=True,
    )


def ns(name: str, *argv: str, check: bool = True, input_text: str | None = None):
    return run(
        "ip",
        "netns",
        "exec",
        name,
        *argv,
        check=check,
        input_text=input_text,
    )


def nft_script(namespace: str, script: str) -> None:
    ns(namespace, "nft", "-f", "-", input_text=script)


def ping(namespace: str, destination: str) -> bool:
    completed = ns(
        namespace,
        "ping",
        "-n",
        "-c",
        "2",
        "-W",
        "1",
        destination,
        check=False,
    )
    return completed.returncode == 0


def ruleset(namespace: str) -> dict:
    value = json.loads(ns(namespace, "nft", "-j", "list", "ruleset").stdout)
    assert isinstance(value, dict), value
    assert isinstance(value.get("nftables"), list), value
    return value


def chain_row(value: dict, table: str, name: str) -> dict:
    matches = []
    for row in value["nftables"]:
        if not isinstance(row, dict):
            continue
        chain = row.get("chain")
        if not isinstance(chain, dict):
            continue
        if (
            chain.get("family") == "ip"
            and chain.get("table") == table
            and chain.get("name") == name
        ):
            matches.append(chain)
    assert len(matches) == 1, matches
    return matches[0]


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-040 must run as root")

    suffix = str(os.getpid())
    ordinary = f"vpng-e40-o-{suffix}"
    managed = f"vpng-e40-m-{suffix}"
    created = []

    ordinary_if = f"e40o-{suffix}"
    managed_if = f"e40m-{suffix}"

    try:
        for name in (ordinary, managed):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        run(
            "ip",
            "link",
            "add",
            ordinary_if,
            "type",
            "veth",
            "peer",
            "name",
            managed_if,
        )
        run("ip", "link", "set", ordinary_if, "netns", ordinary)
        run("ip", "link", "set", managed_if, "netns", managed)

        ns(ordinary, "ip", "addr", "add", "10.40.0.1/30", "dev", ordinary_if)
        ns(managed, "ip", "addr", "add", "10.40.0.2/30", "dev", managed_if)

        ns(ordinary, "ip", "link", "set", ordinary_if, "up")
        ns(managed, "ip", "link", "set", managed_if, "up")

        # Foreign ACCEPT base chains intentionally surround the VPN-GATE priority.
        nft_script(
            managed,
            """table ip foreign_early {
    chain input_accept {
        type filter hook input priority -100; policy accept;
    }
    chain output_accept {
        type filter hook output priority -100; policy accept;
    }
}
table ip foreign_late {
    chain input_accept {
        type filter hook input priority 100; policy accept;
    }
    chain output_accept {
        type filter hook output priority 100; policy accept;
    }
}
""",
        )

        nft_script(
            managed,
            f"""table ip vpn_gate {{
    comment "{TABLE_COMMENT}"
    chain stack_input {{
        type filter hook input priority 0; policy drop;
        comment "{INPUT_COMMENT}"
    }}
    chain stack_output {{
        type filter hook output priority 0; policy drop;
        comment "{OUTPUT_COMMENT}"
    }}
}}
""",
        )

        # Empty owned chains must remain terminal despite foreign ACCEPT chains.
        assert not ping(ordinary, "10.40.0.2"), (
            "foreign ACCEPT chain bypassed stack_input policy drop"
        )
        assert not ping(managed, "10.40.0.1"), (
            "foreign ACCEPT chain bypassed stack_output policy drop"
        )

        value = ruleset(managed)
        input_chain = chain_row(value, "vpn_gate", "stack_input")
        output_chain = chain_row(value, "vpn_gate", "stack_output")

        assert input_chain.get("type") == "filter", input_chain
        assert input_chain.get("hook") == "input", input_chain
        assert input_chain.get("prio") == 0, input_chain
        assert input_chain.get("policy") == "drop", input_chain
        assert input_chain.get("comment") == INPUT_COMMENT, input_chain

        assert output_chain.get("type") == "filter", output_chain
        assert output_chain.get("hook") == "output", output_chain
        assert output_chain.get("prio") == 0, output_chain
        assert output_chain.get("policy") == "drop", output_chain
        assert output_chain.get("comment") == OUTPUT_COMMENT, output_chain

        print("EXP040_INPUT_CHAIN_JSON=" + json.dumps(input_chain, sort_keys=True))
        print("EXP040_OUTPUT_CHAIN_JSON=" + json.dumps(output_chain, sort_keys=True))

        # Explicit owner contributions can admit the tested local traffic.
        nft_script(
            managed,
            """add rule ip vpn_gate stack_input ip protocol icmp accept
add rule ip vpn_gate stack_output ip protocol icmp accept
""",
        )

        assert ping(ordinary, "10.40.0.2"), (
            "explicit stack_input/output ICMP allow did not permit inbound ping"
        )
        assert ping(managed, "10.40.0.1"), (
            "explicit stack_input/output ICMP allow did not permit outbound ping"
        )

        print("EXP040_FOREIGN_ACCEPT_INPUT_BYPASS=0")
        print("EXP040_FOREIGN_ACCEPT_OUTPUT_BYPASS=0")
        print("EXP040_EXPLICIT_ICMP_ALLOW=1")
        print("EXP-040 managed INPUT OUTPUT drop scaffold: PASS")
        return 0
    finally:
        for name in reversed(created):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
