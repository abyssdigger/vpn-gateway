from __future__ import annotations

import json
import os
import subprocess
import sys
import time


TABLE_COMMENT = "vpn-gate:ng3:owner-v1"
INPUT_COMMENT = "vpn-gate:ng3:stack-input-v1"
OUTPUT_COMMENT = "vpn-gate:ng3:stack-output-v1"
FORWARD_COMMENT = "vpn-gate:ng3:payload-forward-v1"
POSTROUTING_COMMENT = "vpn-gate:ng3:payload-postrouting-v1"
PUBLICATION_COMMENT = "vpn-gate:ng3:local-publication-v1"
PROFILE_COMMENT = "vpn-gate:ng3:payload-forward-new-v1"
NAT_COMMENT = "vpn-gate:ng3:payload-nat-v1"


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
        "ip", "netns", "exec", name, *argv,
        check=check, input_text=input_text,
    )


def nft_script(namespace: str, script: str, *, check: bool = True):
    return ns(namespace, "nft", "-f", "-", input_text=script, check=check)


def ifindex(namespace: str, ifname: str) -> int:
    return int(
        ns(namespace, "cat", f"/sys/class/net/{ifname}/ifindex").stdout.strip()
    )


def start_in_ns(namespace: str, code: str) -> subprocess.Popen:
    return subprocess.Popen(
        ["ip", "netns", "exec", namespace, "python3", "-u", "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def tcp_client(namespace: str, host: str, port: int) -> bool:
    code = r"""
import socket, sys
try:
    sock = socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=1.0)
    data = sock.recv(16)
except OSError:
    raise SystemExit(1)
else:
    sock.close()
    raise SystemExit(0 if data == b"ok" else 2)
"""
    result = ns(
        namespace, "python3", "-c", code, host, str(port), check=False
    )
    return result.returncode == 0


def rules(namespace: str, chain: str) -> list[dict]:
    value = json.loads(
        ns(
            namespace, "nft", "-j", "list", "chain",
            "ip", "vpn_gate", chain,
        ).stdout
    )
    return [
        row["rule"]
        for row in value.get("nftables", [])
        if isinstance(row, dict) and isinstance(row.get("rule"), dict)
    ]


def pub_handles(namespace: str) -> tuple[int, int]:
    input_rules = [
        rule for rule in rules(namespace, "stack_input")
        if rule.get("comment") == PUBLICATION_COMMENT
    ]
    output_rules = [
        rule for rule in rules(namespace, "stack_output")
        if rule.get("comment") == PUBLICATION_COMMENT
    ]
    assert len(input_rules) == 1, input_rules
    assert len(output_rules) == 1, output_rules
    input_handle = input_rules[0].get("handle")
    output_handle = output_rules[0].get("handle")
    assert type(input_handle) is int and input_handle >= 0
    assert type(output_handle) is int and output_handle >= 0
    return input_handle, output_handle


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-047 must run as root")

    suffix = str(os.getpid())
    host_ns = f"e47-h-{suffix}"
    managed = f"e47-m-{suffix}"
    vpn_ns = f"e47-v-{suffix}"
    created: list[str] = []
    server = None

    h_if = f"e47h-{suffix}"
    mh_if = f"e47mh-{suffix}"
    v_if = f"e47v-{suffix}"
    mv_if = f"e47mv-{suffix}"

    publication_ip = "198.51.100.47"
    port = 44443

    tcp_server = rf"""
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("{publication_ip}", {port}))
sock.listen(8)
print("TCP_READY", flush=True)
while True:
    conn, _ = sock.accept()
    conn.sendall(b"ok")
    conn.close()
"""

    try:
        for name in (host_ns, managed, vpn_ns):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        run("ip", "link", "add", h_if, "type", "veth", "peer", "name", mh_if)
        run("ip", "link", "set", h_if, "netns", host_ns)
        run("ip", "link", "set", mh_if, "netns", managed)
        run("ip", "link", "add", v_if, "type", "veth", "peer", "name", mv_if)
        run("ip", "link", "set", v_if, "netns", vpn_ns)
        run("ip", "link", "set", mv_if, "netns", managed)

        ns(host_ns, "ip", "addr", "add", "10.47.1.1/30", "dev", h_if)
        ns(managed, "ip", "addr", "add", "10.47.1.2/30", "dev", mh_if)
        ns(vpn_ns, "ip", "addr", "add", "10.47.2.1/30", "dev", v_if)
        ns(managed, "ip", "addr", "add", "10.47.2.2/30", "dev", mv_if)
        ns(managed, "ip", "addr", "add", f"{publication_ip}/32", "dev", "lo")

        for namespace, interface in (
            (host_ns, h_if), (managed, mh_if),
            (vpn_ns, v_if), (managed, mv_if),
        ):
            ns(namespace, "ip", "link", "set", interface, "up")

        ns(
            host_ns, "ip", "route", "add", f"{publication_ip}/32",
            "via", "10.47.1.2",
        )

        host_index = ifindex(managed, mh_if)
        path_index = ifindex(managed, mv_if)

        nft_script(
            managed,
            f"""table ip vpn_gate {{
    comment "{TABLE_COMMENT}"
    chain stack_input {{
        type filter hook input priority 0; policy drop;
        comment "{INPUT_COMMENT}"
    }}
    chain payload_forward {{
        type filter hook forward priority 0; policy drop;
        comment "{FORWARD_COMMENT}"
        ct state new meta iif {host_index} meta oif {path_index} ip daddr 10.47.2.0/30 accept comment "{PROFILE_COMMENT}"
    }}
    chain stack_output {{
        type filter hook output priority 0; policy drop;
        comment "{OUTPUT_COMMENT}"
    }}
    chain payload_postrouting {{
        type nat hook postrouting priority 100; policy accept;
        comment "{POSTROUTING_COMMENT}"
        meta iif {host_index} meta oif {path_index} masquerade comment "{NAT_COMMENT}"
    }}
}}
""",
        )

        server = start_in_ns(managed, tcp_server)
        time.sleep(0.25)
        if server.poll() is not None:
            stdout, stderr = server.communicate()
            raise AssertionError(
                f"server exited early rc={server.returncode} stdout={stdout!r} stderr={stderr!r}"
            )

        assert not tcp_client(host_ns, publication_ip, port)

        add_pair = f"""add rule ip vpn_gate stack_output meta oif {host_index} ip saddr {publication_ip} tcp sport {port} accept comment "{PUBLICATION_COMMENT}"
add rule ip vpn_gate stack_input meta iif {host_index} ip daddr {publication_ip} tcp dport {port} accept comment "{PUBLICATION_COMMENT}"
"""
        nft_script(managed, add_pair)
        assert tcp_client(host_ns, publication_ip, port)

        input_handle, output_handle = pub_handles(managed)
        before_forward = rules(managed, "payload_forward")
        before_nat = rules(managed, "payload_postrouting")

        # A failed batch must not leave the valid first operation committed.
        failed = nft_script(
            managed,
            f"""delete rule ip vpn_gate stack_input handle {input_handle}
add rule ip vpn_gate does_not_exist accept
""",
            check=False,
        )
        assert failed.returncode != 0
        input_after_failed = [
            rule for rule in rules(managed, "stack_input")
            if rule.get("comment") == PUBLICATION_COMMENT
        ]
        assert len(input_after_failed) == 1, input_after_failed
        assert tcp_client(host_ns, publication_ip, port)

        delete_pair = f"""delete rule ip vpn_gate stack_input handle {input_handle}
delete rule ip vpn_gate stack_output handle {output_handle}
"""
        nft_script(managed, delete_pair)

        assert not tcp_client(host_ns, publication_ip, port)
        assert not [
            rule for rule in rules(managed, "stack_input")
            if rule.get("comment") == PUBLICATION_COMMENT
        ]
        assert not [
            rule for rule in rules(managed, "stack_output")
            if rule.get("comment") == PUBLICATION_COMMENT
        ]
        assert before_forward == rules(managed, "payload_forward")
        assert before_nat == rules(managed, "payload_postrouting")

        print("EXP047_ADD_PAIR_ATOMIC=1")
        print("EXP047_FAILED_BATCH_ROLLED_BACK=1")
        print("EXP047_DELETE_PAIR_ATOMIC=1")
        print("EXP047_PAYLOAD_PRESERVED=1")
        print("EXP-047 atomic publication local mutation: PASS")
        return 0
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=2)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=2)
        for name in reversed(created):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
