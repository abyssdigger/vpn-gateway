from __future__ import annotations

import json
import os
import subprocess
import sys
import time


TABLE_COMMENT = "vpn-gate:ng3:owner-v1"
INPUT_COMMENT = "vpn-gate:ng3:stack-input-v1"
OUTPUT_COMMENT = "vpn-gate:ng3:stack-output-v1"
PUBLICATION_COMMENT = "vpn-gate:ng3:local-publication-v1"


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


def nft_script(namespace: str, script: str) -> None:
    ns(namespace, "nft", "-f", "-", input_text=script)


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


def udp_client(namespace: str, host: str, port: int) -> bool:
    code = r"""
import socket, sys
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(1.0)
sock.sendto(b"probe", (sys.argv[1], int(sys.argv[2])))
try:
    data, _ = sock.recvfrom(16)
except OSError:
    raise SystemExit(1)
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


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-046 must run as root")

    suffix = str(os.getpid())
    host_ns = f"e46-h-{suffix}"
    managed = f"e46-m-{suffix}"
    device_ns = f"e46-d-{suffix}"
    created: list[str] = []
    servers: list[subprocess.Popen] = []

    h_if = f"e46h-{suffix}"
    mh_if = f"e46mh-{suffix}"
    d_if = f"e46d-{suffix}"
    md_if = f"e46md-{suffix}"

    publication_ip = "198.51.100.46"
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
    udp_server = rf"""
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("{publication_ip}", {port}))
print("UDP_READY", flush=True)
while True:
    data, peer = sock.recvfrom(2048)
    sock.sendto(b"ok", peer)
"""

    try:
        for name in (host_ns, managed, device_ns):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        run("ip", "link", "add", h_if, "type", "veth", "peer", "name", mh_if)
        run("ip", "link", "set", h_if, "netns", host_ns)
        run("ip", "link", "set", mh_if, "netns", managed)

        run("ip", "link", "add", d_if, "type", "veth", "peer", "name", md_if)
        run("ip", "link", "set", d_if, "netns", device_ns)
        run("ip", "link", "set", md_if, "netns", managed)

        ns(host_ns, "ip", "addr", "add", "10.46.1.1/30", "dev", h_if)
        ns(managed, "ip", "addr", "add", "10.46.1.2/30", "dev", mh_if)
        ns(device_ns, "ip", "addr", "add", "10.46.2.1/30", "dev", d_if)
        ns(managed, "ip", "addr", "add", "10.46.2.2/30", "dev", md_if)
        ns(managed, "ip", "addr", "add", f"{publication_ip}/32", "dev", "lo")

        for namespace, interface in (
            (host_ns, h_if), (managed, mh_if),
            (device_ns, d_if), (managed, md_if),
        ):
            ns(namespace, "ip", "link", "set", interface, "up")

        ns(
            host_ns, "ip", "route", "add", f"{publication_ip}/32",
            "via", "10.46.1.2",
        )
        ns(
            device_ns, "ip", "route", "add", f"{publication_ip}/32",
            "via", "10.46.2.2",
        )

        host_index = ifindex(managed, mh_if)

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

        servers.append(start_in_ns(managed, tcp_server))
        servers.append(start_in_ns(managed, udp_server))
        time.sleep(0.25)
        for server in servers:
            if server.poll() is not None:
                stdout, stderr = server.communicate()
                raise AssertionError(
                    f"server exited early rc={server.returncode} "
                    f"stdout={stdout!r} stderr={stderr!r}"
                )

        assert not tcp_client(host_ns, publication_ip, port)
        assert not udp_client(host_ns, publication_ip, port)

        nft_script(
            managed,
            f"""add rule ip vpn_gate stack_input meta iif {host_index} ip daddr {publication_ip} tcp dport {port} accept comment "{PUBLICATION_COMMENT}"
add rule ip vpn_gate stack_output meta oif {host_index} ip saddr {publication_ip} tcp sport {port} accept comment "{PUBLICATION_COMMENT}"
add rule ip vpn_gate stack_input meta iif {host_index} ip daddr {publication_ip} udp dport {port} accept comment "{PUBLICATION_COMMENT}"
add rule ip vpn_gate stack_output meta oif {host_index} ip saddr {publication_ip} udp sport {port} accept comment "{PUBLICATION_COMMENT}"
""",
        )

        assert tcp_client(host_ns, publication_ip, port)
        assert udp_client(host_ns, publication_ip, port)

        assert not tcp_client(host_ns, publication_ip, port + 1)
        assert not udp_client(host_ns, publication_ip, port + 1)

        assert not tcp_client(device_ns, publication_ip, port)
        assert not udp_client(device_ns, publication_ip, port)

        input_rules = rules(managed, "stack_input")
        output_rules = rules(managed, "stack_output")
        assert len(input_rules) == 2, input_rules
        assert len(output_rules) == 2, output_rules
        assert all(r.get("comment") == PUBLICATION_COMMENT for r in input_rules)
        assert all(r.get("comment") == PUBLICATION_COMMENT for r in output_rules)

        print("EXP046_INPUT_JSON=" + json.dumps(input_rules, sort_keys=True))
        print("EXP046_OUTPUT_JSON=" + json.dumps(output_rules, sort_keys=True))
        print("EXP046_TCP_PUBLICATION=1")
        print("EXP046_UDP_PUBLICATION=1")
        print("EXP046_WRONG_PORT_BLOCKED=1")
        print("EXP046_DEVICE_INGRESS_BLOCKED=1")
        print("EXP-046 publication local admission: PASS")
        return 0
    finally:
        for server in servers:
            if server.poll() is None:
                server.terminate()
        for server in servers:
            try:
                server.wait(timeout=2)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=2)
        for name in reversed(created):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
