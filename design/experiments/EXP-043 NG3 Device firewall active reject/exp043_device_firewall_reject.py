from __future__ import annotations

import errno
import json
import os
import subprocess
import sys
import time


TABLE_COMMENT = "vpn-gate:ng3:owner-v1"
FORWARD_COMMENT = "vpn-gate:ng3:payload-forward-v1"
RULE_COMMENT = "vpn-gate:ng3:device-fw-rule-v1"


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


def start_in_ns(namespace: str, code: str) -> subprocess.Popen:
    return subprocess.Popen(
        ["ip", "netns", "exec", namespace, "python3", "-u", "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def tcp_client(namespace: str, host: str, port: int) -> subprocess.CompletedProcess:
    code = r"""
import errno
import socket
import sys
try:
    sock = socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=2.0)
except OSError as exc:
    print(f"TCP_ERROR={exc.errno}:{type(exc).__name__}:{exc}")
    if exc.errno == errno.ECONNREFUSED:
        raise SystemExit(10)
    if isinstance(exc, TimeoutError) or exc.errno == errno.ETIMEDOUT:
        raise SystemExit(20)
    raise SystemExit(30)
else:
    print("TCP_CONNECTED=1")
    sock.close()
    raise SystemExit(0)
"""
    return ns(
        namespace,
        "python3",
        "-c",
        code,
        host,
        str(port),
        check=False,
    )


def udp_client(namespace: str, host: str, port: int) -> subprocess.CompletedProcess:
    code = r"""
import errno
import socket
import sys
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(2.0)
sock.connect((sys.argv[1], int(sys.argv[2])))
try:
    sock.send(b"probe")
    data = sock.recv(1024)
except OSError as exc:
    print(f"UDP_ERROR={exc.errno}:{type(exc).__name__}:{exc}")
    if exc.errno == errno.ECONNREFUSED:
        raise SystemExit(10)
    if isinstance(exc, TimeoutError) or exc.errno == errno.ETIMEDOUT:
        raise SystemExit(20)
    raise SystemExit(30)
else:
    print("UDP_REPLY=" + data.decode("ascii", "replace"))
    raise SystemExit(0)
"""
    return ns(
        namespace,
        "python3",
        "-c",
        code,
        host,
        str(port),
        check=False,
    )


def chain_rules(namespace: str) -> list[dict]:
    value = json.loads(
        ns(
            namespace,
            "nft",
            "-j",
            "list",
            "chain",
            "ip",
            "vpn_gate",
            "payload_forward",
        ).stdout
    )
    result: list[dict] = []
    for row in value.get("nftables", []):
        if isinstance(row, dict) and isinstance(row.get("rule"), dict):
            result.append(row["rule"])
    return result


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-043 must run as root")

    suffix = str(os.getpid())
    ordinary = f"e43-o-{suffix}"
    managed = f"e43-m-{suffix}"
    vpn = f"e43-v-{suffix}"
    created: list[str] = []
    servers: list[subprocess.Popen] = []

    o_if = f"e43o-{suffix}"
    mo_if = f"e43mo-{suffix}"
    mv_if = f"e43mv-{suffix}"
    v_if = f"e43v-{suffix}"

    target = "10.43.2.2"

    tcp_server = r"""
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("10.43.2.2", 8080))
sock.listen(8)
print("TCP_READY", flush=True)
while True:
    conn, _ = sock.accept()
    conn.close()
"""
    udp_server = r"""
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("10.43.2.2", 8081))
print("UDP_READY", flush=True)
while True:
    data, peer = sock.recvfrom(2048)
    sock.sendto(data, peer)
"""

    try:
        for name in (ordinary, managed, vpn):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        run("ip", "link", "add", o_if, "type", "veth", "peer", "name", mo_if)
        run("ip", "link", "set", o_if, "netns", ordinary)
        run("ip", "link", "set", mo_if, "netns", managed)

        run("ip", "link", "add", mv_if, "type", "veth", "peer", "name", v_if)
        run("ip", "link", "set", mv_if, "netns", managed)
        run("ip", "link", "set", v_if, "netns", vpn)

        ns(ordinary, "ip", "addr", "add", "10.43.1.2/30", "dev", o_if)
        ns(managed, "ip", "addr", "add", "10.43.1.1/30", "dev", mo_if)
        ns(managed, "ip", "addr", "add", "10.43.2.1/30", "dev", mv_if)
        ns(vpn, "ip", "addr", "add", f"{target}/30", "dev", v_if)

        for namespace, interface in (
            (ordinary, o_if),
            (managed, mo_if),
            (managed, mv_if),
            (vpn, v_if),
        ):
            ns(namespace, "ip", "link", "set", interface, "up")

        ns(ordinary, "ip", "route", "add", "10.43.2.0/30", "via", "10.43.1.1")
        ns(vpn, "ip", "route", "add", "10.43.1.0/30", "via", "10.43.2.1")
        ns(managed, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")

        servers.append(start_in_ns(vpn, tcp_server))
        servers.append(start_in_ns(vpn, udp_server))
        time.sleep(0.25)
        for server in servers:
            if server.poll() is not None:
                stdout, stderr = server.communicate()
                raise AssertionError(
                    f"server exited early rc={server.returncode} stdout={stdout!r} stderr={stderr!r}"
                )

        # Baseline proves the target services and forwarding topology work before filtering.
        tcp_baseline = tcp_client(ordinary, target, 8080)
        assert tcp_baseline.returncode == 0, (tcp_baseline.stdout, tcp_baseline.stderr)
        udp_baseline = udp_client(ordinary, target, 8081)
        assert udp_baseline.returncode == 0, (udp_baseline.stdout, udp_baseline.stderr)
        ping_baseline = ns(
            ordinary,
            "ping",
            "-n",
            "-c",
            "1",
            "-W",
            "1",
            target,
            check=False,
        )
        assert ping_baseline.returncode == 0, (ping_baseline.stdout, ping_baseline.stderr)

        nft_script(
            managed,
            f"""table ip vpn_gate {{
    comment "{TABLE_COMMENT}"
    chain payload_forward {{
        type filter hook forward priority 0; policy drop;
        comment "{FORWARD_COMMENT}"
        ip daddr {target} tcp dport 8080 reject with tcp reset comment "{RULE_COMMENT}"
        ip daddr {target} udp dport 8081 reject comment "{RULE_COMMENT}"
        ip daddr {target} meta l4proto icmp reject comment "{RULE_COMMENT}"
    }}
}}
""",
        )

        tcp_reject = tcp_client(ordinary, target, 8080)
        assert tcp_reject.returncode == 10, (
            "TCP reject was not immediate connection-refused",
            tcp_reject.returncode,
            tcp_reject.stdout,
            tcp_reject.stderr,
        )

        udp_reject = udp_client(ordinary, target, 8081)
        assert udp_reject.returncode == 10, (
            "UDP reject was not active connection-refused",
            udp_reject.returncode,
            udp_reject.stdout,
            udp_reject.stderr,
        )

        ping_reject = ns(
            ordinary,
            "ping",
            "-n",
            "-c",
            "1",
            "-W",
            "2",
            target,
            check=False,
        )
        combined_ping = ping_reject.stdout + "\n" + ping_reject.stderr
        assert ping_reject.returncode != 0, combined_ping
        assert (
            "Destination Port Unreachable" in combined_ping
            or "Destination Unreachable" in combined_ping
        ), combined_ping

        found = chain_rules(managed)
        assert len(found) == 3, found
        tcp_rule, udp_rule, icmp_rule = found

        # Protocol-unspecified REJECT: replace the test rules with one generic IPv4 reject
        # and prove it remains active rather than degrading to silent DROP.
        nft_script(
            managed,
            f"""flush chain ip vpn_gate payload_forward
add rule ip vpn_gate payload_forward ip daddr {target} reject comment "{RULE_COMMENT}"
""",
        )
        generic_ping = ns(
            ordinary,
            "ping",
            "-n",
            "-c",
            "1",
            "-W",
            "2",
            target,
            check=False,
        )
        generic_output = generic_ping.stdout + "\n" + generic_ping.stderr
        assert generic_ping.returncode != 0, generic_output
        assert (
            "Destination Port Unreachable" in generic_output
            or "Destination Unreachable" in generic_output
        ), generic_output
        generic_rules = chain_rules(managed)
        assert len(generic_rules) == 1, generic_rules
        generic_rule = generic_rules[0]

        print("EXP043_TCP_REJECT_JSON=" + json.dumps(tcp_rule, sort_keys=True))
        print("EXP043_UDP_REJECT_JSON=" + json.dumps(udp_rule, sort_keys=True))
        print("EXP043_ICMP_REJECT_JSON=" + json.dumps(icmp_rule, sort_keys=True))
        print("EXP043_GENERIC_REJECT_JSON=" + json.dumps(generic_rule, sort_keys=True))
        print("EXP043_TCP_ACTIVE_REFUSED=1")
        print("EXP043_UDP_ACTIVE_REFUSED=1")
        print("EXP043_ICMP_ACTIVE_UNREACHABLE=1")
        print("EXP043_GENERIC_ACTIVE_UNREACHABLE=1")
        print("EXP-043 Device firewall active REJECT: PASS")
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
