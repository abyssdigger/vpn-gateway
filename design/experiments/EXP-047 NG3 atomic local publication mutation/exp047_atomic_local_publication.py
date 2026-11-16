from __future__ import annotations

import json
import os
import subprocess
import sys


COMMENT = "vpn-gate:ng3:local-publication-v1"
ADDR = "198.51.100.47"


def run(*argv: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        argv, input=input_text, check=check, text=True, capture_output=True,
    )


def ns(name: str, *argv: str, check: bool = True, input_text: str | None = None):
    return run(
        "ip", "netns", "exec", name, *argv,
        check=check, input_text=input_text,
    )


def nft_batch(namespace: str, script: str, *, check: bool = True):
    return ns(namespace, "nft", "-f", "-", check=check, input_text=script)


def ifindex(namespace: str, name: str) -> int:
    return int(ns(namespace, "cat", f"/sys/class/net/{name}/ifindex").stdout.strip())


def all_rules(namespace: str) -> list[dict]:
    root = json.loads(ns(namespace, "nft", "-j", "list", "ruleset").stdout)
    return [
        row["rule"]
        for row in root.get("nftables", [])
        if isinstance(row, dict) and isinstance(row.get("rule"), dict)
    ]


def publication_rules(namespace: str) -> list[dict]:
    return [rule for rule in all_rules(namespace) if rule.get("comment") == COMMENT]


def pub_add_lines(index: int, port: int) -> list[str]:
    return [
        f'add rule ip vpn_gate stack_input meta iif {index} ip daddr {ADDR} tcp dport {port} accept comment "{COMMENT}"',
        f'add rule ip vpn_gate stack_output meta oif {index} ip saddr {ADDR} tcp sport {port} accept comment "{COMMENT}"',
        f'add rule ip vpn_gate stack_input meta iif {index} ip daddr {ADDR} udp dport {port} accept comment "{COMMENT}"',
        f'add rule ip vpn_gate stack_output meta oif {index} ip saddr {ADDR} udp sport {port} accept comment "{COMMENT}"',
    ]


def canonical_rules(rules: list[dict]) -> list[str]:
    return sorted(json.dumps(rule, sort_keys=True) for rule in rules)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-047 must run as root")

    namespace = f"vpng-e47-{os.getpid()}"
    try:
        run("ip", "netns", "add", namespace)
        ns(namespace, "ip", "link", "add", "host0", "type", "veth", "peer", "name", "peer0")
        ns(namespace, "ip", "link", "set", "host0", "up")
        ns(namespace, "ip", "link", "set", "peer0", "up")
        host_index = ifindex(namespace, "host0")
        peer_index = ifindex(namespace, "peer0")

        nft_batch(
            namespace,
            f"""table ip vpn_gate {{
    comment "vpn-gate:ng3:owner-v1"
    chain stack_input {{
        type filter hook input priority 0; policy drop;
        comment "vpn-gate:ng3:stack-input-v1"
    }}
    chain payload_forward {{
        type filter hook forward priority 0; policy drop;
        comment "vpn-gate:ng3:payload-forward-v1"
        meta iif {host_index} meta oif {peer_index} accept comment "exp047:unrelated-forward"
    }}
    chain stack_output {{
        type filter hook output priority 0; policy drop;
        comment "vpn-gate:ng3:stack-output-v1"
    }}
    chain payload_postrouting {{
        type nat hook postrouting priority 100; policy accept;
        comment "vpn-gate:ng3:payload-postrouting-v1"
        meta iif {host_index} meta oif {peer_index} masquerade comment "exp047:unrelated-nat"
    }}
}}
""",
        )

        unrelated_before = canonical_rules(all_rules(namespace))

        failed_add = "\n".join(
            pub_add_lines(host_index, 44443)
            + ["add rule ip vpn_gate no_such_chain accept"]
        ) + "\n"
        result = nft_batch(namespace, failed_add, check=False)
        assert result.returncode != 0, result.stdout
        assert publication_rules(namespace) == [], "failed batch leaked partial add"
        assert canonical_rules(all_rules(namespace)) == unrelated_before

        nft_batch(
            namespace,
            "\n".join(pub_add_lines(host_index, 44443)) + "\n",
        )
        old_rules = publication_rules(namespace)
        assert len(old_rules) == 4, old_rules
        old_canonical = canonical_rules(old_rules)

        delete_lines = [
            f"delete rule ip vpn_gate {rule['chain']} handle {rule['handle']}"
            for rule in old_rules
        ]
        failed_replace = "\n".join(
            delete_lines
            + pub_add_lines(host_index, 44444)
            + ["add rule ip vpn_gate no_such_chain accept"]
        ) + "\n"
        result = nft_batch(namespace, failed_replace, check=False)
        assert result.returncode != 0
        assert canonical_rules(publication_rules(namespace)) == old_canonical, (
            "failed replacement did not roll back exact old local rules"
        )

        nft_batch(
            namespace,
            "\n".join(delete_lines + pub_add_lines(host_index, 44444)) + "\n",
        )
        new_rules = publication_rules(namespace)
        assert len(new_rules) == 4, new_rules
        rendered = json.dumps(new_rules, sort_keys=True)
        assert "44444" in rendered
        assert "44443" not in rendered

        unrelated_after = canonical_rules(
            [rule for rule in all_rules(namespace) if rule.get("comment") != COMMENT]
        )
        assert unrelated_after == unrelated_before

        print("EXP047_FAILED_ADD_ROLLBACK=1")
        print("EXP047_FAILED_REPLACE_ROLLBACK=1")
        print("EXP047_VALID_REPLACE=1")
        print("EXP047_UNRELATED_PRESERVED=1")
        print("EXP047_FINAL_LOCAL_JSON=" + json.dumps(new_rules, sort_keys=True))
        print("EXP-047 atomic local publication mutation: PASS")
        return 0
    finally:
        run("ip", "netns", "del", namespace, check=False)


if __name__ == "__main__":
    sys.exit(main())
