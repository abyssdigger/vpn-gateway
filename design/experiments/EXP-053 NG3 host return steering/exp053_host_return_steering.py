#!/usr/bin/env python3
"""EXP-053: host-side conntrack return steering into the NG3 managed stack."""

from __future__ import annotations

import os
import subprocess
import textwrap


PID = os.getpid()
HOST = f"vng53h-{PID}"
STACK = f"vng53s-{PID}"
REMOTE = f"vng53r-{PID}"
LAN = f"vng53l-{PID}"

H_STACK = "e53hs"
S_HOST = "e53sh"
S_REMOTE = "e53sr"
R_STACK = "e53rs"
H_LAN = "e53hl"
L_HOST = "e53lh"

HOST_STACK_IP = "192.0.2.1"
STACK_HOST_IP = "192.0.2.2"
STACK_REMOTE_IP = "203.0.113.1"
REMOTE_IP = "203.0.113.2"
HOST_LAN_IP = "10.0.0.1"
LAN_IP = "10.0.0.2"

MARK = "0x53"
TABLE = "1053"
RULE_PRIORITY = "1053"


def run(*args: str, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def ns(name: str, *args: str, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("ip", "netns", "exec", name, *args, input_text=input_text, check=check)


def add_ns(name: str) -> None:
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def del_ns(name: str) -> None:
    run("ip", "netns", "del", name, check=False)


def setup() -> None:
    for name in (HOST, STACK, REMOTE, LAN):
        add_ns(name)

    run("ip", "link", "add", H_STACK, "type", "veth", "peer", "name", S_HOST)
    run("ip", "link", "set", H_STACK, "netns", HOST)
    run("ip", "link", "set", S_HOST, "netns", STACK)

    run("ip", "link", "add", S_REMOTE, "type", "veth", "peer", "name", R_STACK)
    run("ip", "link", "set", S_REMOTE, "netns", STACK)
    run("ip", "link", "set", R_STACK, "netns", REMOTE)

    run("ip", "link", "add", H_LAN, "type", "veth", "peer", "name", L_HOST)
    run("ip", "link", "set", H_LAN, "netns", HOST)
    run("ip", "link", "set", L_HOST, "netns", LAN)

    ns(HOST, "ip", "addr", "add", f"{HOST_STACK_IP}/30", "dev", H_STACK)
    ns(HOST, "ip", "link", "set", H_STACK, "up")
    ns(HOST, "ip", "addr", "add", f"{HOST_LAN_IP}/24", "dev", H_LAN)
    ns(HOST, "ip", "link", "set", H_LAN, "up")

    ns(STACK, "ip", "addr", "add", f"{STACK_HOST_IP}/30", "dev", S_HOST)
    ns(STACK, "ip", "link", "set", S_HOST, "up")
    ns(STACK, "ip", "addr", "add", f"{STACK_REMOTE_IP}/24", "dev", S_REMOTE)
    ns(STACK, "ip", "link", "set", S_REMOTE, "up")

    ns(REMOTE, "ip", "addr", "add", f"{REMOTE_IP}/24", "dev", R_STACK)
    ns(REMOTE, "ip", "link", "set", R_STACK, "up")
    ns(REMOTE, "ip", "route", "add", "default", "via", STACK_REMOTE_IP)

    ns(LAN, "ip", "addr", "add", f"{LAN_IP}/24", "dev", L_HOST)
    ns(LAN, "ip", "link", "set", L_HOST, "up")
    ns(LAN, "ip", "route", "add", "default", "via", HOST_LAN_IP)

    ns(STACK, "ip", "route", "add", "10.0.0.0/24", "via", HOST_STACK_IP)

    # Deliberately wrong for remote replies unless policy steering is active.
    ns(HOST, "ip", "route", "add", "default", "via", LAN_IP, "dev", H_LAN)

    ns(HOST, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")
    ns(STACK, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")

    ns(HOST, "ip", "route", "add", "table", TABLE, "default", "via", STACK_HOST_IP, "dev", H_STACK)
    ns(HOST, "ip", "rule", "add", "priority", RULE_PRIORITY, "fwmark", MARK, "lookup", TABLE)

    nft = textwrap.dedent(
        f"""
        table inet exp053 {{
          chain prerouting {{
            type filter hook prerouting priority mangle; policy accept;
            iifname "{H_STACK}" ct state new ct mark set {MARK}
            iifname != "{H_STACK}" ct mark {MARK} meta mark set ct mark
          }}

          chain output {{
            type route hook output priority mangle; policy accept;
            ct mark {MARK} meta mark set ct mark
          }}
        }}
        """
    )
    ns(HOST, "nft", "-f", "-", input_text=nft)


TCP_SERVER = r"""
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
tag = sys.argv[3]
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((addr, port))
s.listen(1)
print("READY", flush=True)
c, peer = s.accept()
c.settimeout(5)
data = c.recv(4096)
print(f"{tag}_PEER={peer[0]}:{peer[1]}", flush=True)
c.sendall(b"ACK:" + data)
c.close()
s.close()
"""

TCP_CLIENT = r"""
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
payload = sys.argv[3].encode()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
s.connect((addr, port))
s.sendall(payload)
data = s.recv(4096)
peer = s.getpeername()
print(f"PEER={peer[0]}:{peer[1]}")
print("DATA=" + data.decode())
assert data == b"ACK:" + payload
s.close()
"""


def start_server(namespace: str, addr: str, port: int, tag: str) -> subprocess.Popen[str]:
    proc = subprocess.Popen(
        ["ip", "netns", "exec", namespace, "python3", "-u", "-c", TCP_SERVER, addr, str(port), tag],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    first = proc.stdout.readline().strip()
    if first != "READY":
        out, err = proc.communicate(timeout=3)
        raise AssertionError(f"{tag} server failed to start: first={first!r} out={out!r} err={err!r}")
    return proc


def finish_server(proc: subprocess.Popen[str], marker: str) -> str:
    out, err = proc.communicate(timeout=7)
    if proc.returncode != 0:
        raise AssertionError(f"{marker} server rc={proc.returncode}: {err}")
    if marker not in out:
        raise AssertionError(f"{marker} evidence missing: {out!r}")
    return out


def assert_no_remote_main_route() -> None:
    routes = ns(HOST, "ip", "-4", "route", "show", "table", "main").stdout
    for line in routes.splitlines():
        if line.startswith("203.0.113.0/24") or line.startswith(f"{REMOTE_IP} "):
            raise AssertionError(f"unexpected remote route in host main: {line}")
    print("EXP053_NO_REMOTE_MAIN_ROUTE=PASS")


def assert_route_split() -> None:
    ordinary = ns(HOST, "ip", "-4", "route", "get", REMOTE_IP).stdout.strip()
    marked = ns(HOST, "ip", "-4", "route", "get", REMOTE_IP, "mark", MARK).stdout.strip()
    if H_LAN not in ordinary:
        raise AssertionError(f"ordinary lookup did not use LAN default: {ordinary}")
    if H_STACK not in marked:
        raise AssertionError(f"marked lookup did not use stack table: {marked}")
    print("EXP053_ROUTE_PRECONDITION=PASS")


def main() -> int:
    servers: list[subprocess.Popen[str]] = []
    try:
        setup()
        assert_no_remote_main_route()
        assert_route_split()

        lan_server = start_server(LAN, LAN_IP, 18531, "LAN")
        servers.append(lan_server)
        lan_client = ns(REMOTE, "python3", "-c", TCP_CLIENT, LAN_IP, "18531", "forwarded")
        assert f"PEER={LAN_IP}:18531" in lan_client.stdout, lan_client.stdout
        lan_evidence = finish_server(lan_server, "LAN_PEER")
        assert f"LAN_PEER={REMOTE_IP}:" in lan_evidence, lan_evidence
        servers.remove(lan_server)
        print("EXP053_FORWARDED_REPLY=PASS")

        host_server = start_server(HOST, HOST_STACK_IP, 18532, "HOST")
        servers.append(host_server)
        host_client = ns(REMOTE, "python3", "-c", TCP_CLIENT, HOST_STACK_IP, "18532", "host-local")
        assert f"PEER={HOST_STACK_IP}:18532" in host_client.stdout, host_client.stdout
        host_evidence = finish_server(host_server, "HOST_PEER")
        assert f"HOST_PEER={REMOTE_IP}:" in host_evidence, host_evidence
        servers.remove(host_server)
        print("EXP053_HOST_LOCAL_REPLY=PASS")

        assert_no_remote_main_route()
        print("EXP053_RESULT=PASS")
        return 0
    finally:
        for proc in servers:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
        for name in (LAN, REMOTE, STACK, HOST):
            del_ns(name)


if __name__ == "__main__":
    raise SystemExit(main())
