#!/usr/bin/env python3
"""EXP-055: host-local conntrack mark return steering without remote-prefix host routes."""

from __future__ import annotations

import json
import os
import subprocess
import sys


PID = os.getpid()
REMOTE = f"vng55r-{PID}"
MANAGED = f"vng55m-{PID}"
HOST = f"vng55h-{PID}"
LAN = f"vng55l-{PID}"
WAN = f"vng55w-{PID}"

R_IF = "rm0"
M_REMOTE_IF = "mr0"
M_BOUNDARY_IF = "mh0"
H_BOUNDARY_IF = "hm0"
H_LAN_IF = "hl0"
LAN_IF = "lh0"
H_WAN_IF = "hw0"
WAN_IF = "wh0"

R_LINK = "192.0.2.2"
M_REMOTE_LINK = "192.0.2.1"
M_BOUNDARY = "198.19.255.2"
H_BOUNDARY = "198.19.255.1"
H_LAN = "203.0.113.1"
LAN_ADDR = "203.0.113.2"
H_WAN = "198.51.100.1"
WAN_ADDR = "198.51.100.2"

ROUTED_SOURCE = "10.77.0.10"
SNAT_SOURCE = "10.88.0.10"
HOST_LOCAL_SOURCE = "10.99.0.10"
REMOTE_PREFIXES = ("10.77.0.0/24", "10.88.0.0/24", "10.99.0.0/24")

RETURN_MARK = "0x00550055"
RETURN_TABLE = "555"
RETURN_RULE_PRIORITY = "1555"

ROUTED_PORT = 55101
SNAT_PORT = 55102
HOST_LOCAL_PORT = 55103
UNRELATED_PORT = 55104
UNDERLAY_PORT = 55105


def run(
    *args: str,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def ns(
    namespace: str,
    *args: str,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run(
        "ip",
        "netns",
        "exec",
        namespace,
        *args,
        input_text=input_text,
        check=check,
    )


def add_namespace(name: str) -> None:
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def delete_namespace(name: str) -> None:
    run("ip", "netns", "del", name, check=False)


def add_veth(left_ns: str, left: str, right_ns: str, right: str) -> None:
    run("ip", "link", "add", left, "type", "veth", "peer", "name", right)
    run("ip", "link", "set", left, "netns", left_ns)
    run("ip", "link", "set", right, "netns", right_ns)


def addr_up(namespace: str, interface: str, cidr: str) -> None:
    ns(namespace, "ip", "addr", "add", cidr, "dev", interface)
    ns(namespace, "ip", "link", "set", interface, "up")


def nft(namespace: str, text: str) -> None:
    result = ns(namespace, "nft", "-f", "-", input_text=text, check=False)
    if result.returncode != 0:
        raise AssertionError(
            f"nft failed rc={result.returncode}: {result.stderr}\nscript:\n{text}"
        )


UDP_SERVER = r"""
import socket, sys
address = sys.argv[1]
port = int(sys.argv[2])
tag = sys.argv[3]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((address, port))
s.settimeout(8)
print("READY", flush=True)
data, peer = s.recvfrom(4096)
print(f"{tag}_PEER={peer[0]}:{peer[1]}", flush=True)
print(f"{tag}_DATA={data.decode()}", flush=True)
s.sendto(b"ACK:" + data, peer)
s.close()
"""

UDP_CLIENT = r"""
import socket, sys
source = sys.argv[1]
destination = sys.argv[2]
port = int(sys.argv[3])
payload = sys.argv[4].encode()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((source, 0))
s.settimeout(5)
s.sendto(payload, (destination, port))
data, peer = s.recvfrom(4096)
assert data == b"ACK:" + payload, (data, payload)
assert peer == (destination, port), (peer, (destination, port))
print(f"PEER={peer[0]}:{peer[1]}")
print("DATA=" + data.decode())
s.close()
"""


def start_server(namespace: str, address: str, port: int, tag: str) -> subprocess.Popen[str]:
    proc = subprocess.Popen(
        [
            "ip",
            "netns",
            "exec",
            namespace,
            "python3",
            "-u",
            "-c",
            UDP_SERVER,
            address,
            str(port),
            tag,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    ready = proc.stdout.readline().strip()
    if ready != "READY":
        out, err = proc.communicate(timeout=3)
        raise AssertionError(
            f"{tag} server did not become ready: {ready!r} out={out!r} err={err!r}"
        )
    return proc


def finish_server(proc: subprocess.Popen[str], tag: str) -> str:
    out, err = proc.communicate(timeout=8)
    if proc.returncode != 0:
        raise AssertionError(f"{tag} server failed rc={proc.returncode}: {err}")
    return out.strip()


def client(
    namespace: str,
    source: str,
    destination: str,
    port: int,
    payload: str,
) -> str:
    return ns(
        namespace,
        "python3",
        "-c",
        UDP_CLIENT,
        source,
        destination,
        str(port),
        payload,
    ).stdout


def setup() -> None:
    for name in (REMOTE, MANAGED, HOST, LAN, WAN):
        add_namespace(name)

    add_veth(REMOTE, R_IF, MANAGED, M_REMOTE_IF)
    add_veth(MANAGED, M_BOUNDARY_IF, HOST, H_BOUNDARY_IF)
    add_veth(HOST, H_LAN_IF, LAN, LAN_IF)
    add_veth(HOST, H_WAN_IF, WAN, WAN_IF)

    addr_up(REMOTE, R_IF, f"{R_LINK}/30")
    addr_up(MANAGED, M_REMOTE_IF, f"{M_REMOTE_LINK}/30")
    addr_up(MANAGED, M_BOUNDARY_IF, f"{M_BOUNDARY}/30")
    addr_up(HOST, H_BOUNDARY_IF, f"{H_BOUNDARY}/30")
    addr_up(HOST, H_LAN_IF, f"{H_LAN}/24")
    addr_up(LAN, LAN_IF, f"{LAN_ADDR}/24")
    addr_up(HOST, H_WAN_IF, f"{H_WAN}/24")
    addr_up(WAN, WAN_IF, f"{WAN_ADDR}/24")

    for address in (ROUTED_SOURCE, SNAT_SOURCE, HOST_LOCAL_SOURCE):
        ns(REMOTE, "ip", "addr", "add", f"{address}/32", "dev", "lo")

    ns(REMOTE, "ip", "route", "add", "default", "via", M_REMOTE_LINK, "dev", R_IF)

    for prefix in REMOTE_PREFIXES:
        ns(
            MANAGED,
            "ip",
            "route",
            "add",
            prefix,
            "via",
            R_LINK,
            "dev",
            M_REMOTE_IF,
        )
    ns(
        MANAGED,
        "ip",
        "route",
        "add",
        "default",
        "via",
        H_BOUNDARY,
        "dev",
        M_BOUNDARY_IF,
    )

    ns(LAN, "ip", "route", "add", "default", "via", H_LAN, "dev", LAN_IF)
    ns(WAN, "ip", "route", "add", "default", "via", H_WAN, "dev", WAN_IF)

    ns(MANAGED, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")
    ns(HOST, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")

    # Keep this experiment focused on return steering rather than host reverse-path
    # filtering. Production review must treat any rp_filter dependency explicitly.
    ns(HOST, "sysctl", "-q", "-w", "net.ipv4.conf.all.rp_filter=0")
    ns(HOST, "sysctl", "-q", "-w", "net.ipv4.conf.default.rp_filter=0")
    for interface in (H_BOUNDARY_IF, H_LAN_IF, H_WAN_IF):
        ns(HOST, "sysctl", "-q", "-w", f"net.ipv4.conf.{interface}.rp_filter=0")

    # The return table has no remote prefixes. Its only route is the boundary default.
    ns(
        HOST,
        "ip",
        "route",
        "add",
        "default",
        "via",
        M_BOUNDARY,
        "dev",
        H_BOUNDARY_IF,
        "table",
        RETURN_TABLE,
    )
    ns(
        HOST,
        "ip",
        "rule",
        "add",
        "priority",
        RETURN_RULE_PRIORITY,
        "fwmark",
        f"{RETURN_MARK}/0xffffffff",
        "lookup",
        RETURN_TABLE,
    )

    nft(
        HOST,
        f"""
table ip exp055_host {{
    chain remember_boundary_flow {{
        type filter hook prerouting priority mangle; policy accept;
        iifname "{H_BOUNDARY_IF}" ct mark set {RETURN_MARK} counter comment "exp055-remember"
        iifname != "{H_BOUNDARY_IF}" ct mark {RETURN_MARK} meta mark set ct mark counter comment "exp055-restore-forward"
    }}

    chain restore_host_local_reply {{
        type route hook output priority mangle; policy accept;
        ct mark {RETURN_MARK} meta mark set ct mark counter comment "exp055-restore-local"
    }}

    chain gateway_snat {{
        type nat hook postrouting priority srcnat; policy accept;
        iifname "{H_BOUNDARY_IF}" oifname "{H_LAN_IF}" ip saddr 10.88.0.0/24 counter masquerade comment "exp055-snat"
    }}
}}
""",
    )


def assert_no_host_remote_prefix_routes() -> None:
    raw = ns(HOST, "ip", "-j", "route", "show", "table", "all").stdout
    rows = json.loads(raw)
    text = json.dumps(rows, sort_keys=True)
    for prefix in REMOTE_PREFIXES:
        if prefix in text:
            raise AssertionError(f"host unexpectedly contains remote-prefix route {prefix}: {text}")
    print("EXP055_NO_HOST_REMOTE_PREFIX_ROUTES=PASS")


def nft_counter(comment: str) -> int:
    raw = ns(HOST, "nft", "-j", "list", "table", "ip", "exp055_host").stdout
    root = json.loads(raw)
    for row in root.get("nftables", []):
        rule = row.get("rule") if isinstance(row, dict) else None
        if not isinstance(rule, dict) or rule.get("comment") != comment:
            continue
        for expr in rule.get("expr", []):
            counter = expr.get("counter") if isinstance(expr, dict) else None
            if isinstance(counter, dict) and type(counter.get("packets")) is int:
                return counter["packets"]
    raise AssertionError(f"counter not found: {comment}")


def main() -> int:
    servers: list[subprocess.Popen[str]] = []
    try:
        setup()
        assert_no_host_remote_prefix_routes()

        routed = start_server(LAN, LAN_ADDR, ROUTED_PORT, "ROUTED")
        servers.append(routed)
        out = client(
            REMOTE,
            ROUTED_SOURCE,
            LAN_ADDR,
            ROUTED_PORT,
            "routed-inbound",
        )
        assert f"PEER={LAN_ADDR}:{ROUTED_PORT}" in out
        routed_server = finish_server(routed, "ROUTED")
        servers.remove(routed)
        assert f"ROUTED_PEER={ROUTED_SOURCE}:" in routed_server, routed_server
        print("EXP055_ROUTED_RETURN_WITHOUT_PREFIX_ROUTE=PASS")

        snat = start_server(LAN, LAN_ADDR, SNAT_PORT, "SNAT")
        servers.append(snat)
        out = client(
            REMOTE,
            SNAT_SOURCE,
            LAN_ADDR,
            SNAT_PORT,
            "snat-inbound",
        )
        assert f"PEER={LAN_ADDR}:{SNAT_PORT}" in out
        snat_server = finish_server(snat, "SNAT")
        servers.remove(snat)
        assert f"SNAT_PEER={H_LAN}:" in snat_server, snat_server
        assert nft_counter("exp055-snat") >= 1
        print("EXP055_SNAT_REVERSE_RETURN_WITHOUT_PREFIX_ROUTE=PASS")

        host_local = start_server(HOST, H_LAN, HOST_LOCAL_PORT, "HOSTLOCAL")
        servers.append(host_local)
        out = client(
            REMOTE,
            HOST_LOCAL_SOURCE,
            H_LAN,
            HOST_LOCAL_PORT,
            "host-local",
        )
        assert f"PEER={H_LAN}:{HOST_LOCAL_PORT}" in out
        host_local_server = finish_server(host_local, "HOSTLOCAL")
        servers.remove(host_local)
        assert f"HOSTLOCAL_PEER={HOST_LOCAL_SOURCE}:" in host_local_server, host_local_server
        assert nft_counter("exp055-restore-local") >= 1
        print("EXP055_HOST_LOCAL_REPLY_RETURN=PASS")

        unrelated = start_server(LAN, LAN_ADDR, UNRELATED_PORT, "UNRELATED")
        servers.append(unrelated)
        out = client(
            HOST,
            H_LAN,
            LAN_ADDR,
            UNRELATED_PORT,
            "ordinary-host",
        )
        assert f"PEER={LAN_ADDR}:{UNRELATED_PORT}" in out
        unrelated_server = finish_server(unrelated, "UNRELATED")
        servers.remove(unrelated)
        assert f"UNRELATED_PEER={H_LAN}:" in unrelated_server, unrelated_server
        print("EXP055_UNRELATED_HOST_TRAFFIC=PASS")

        underlay = start_server(WAN, WAN_ADDR, UNDERLAY_PORT, "UNDERLAY")
        servers.append(underlay)
        out = client(
            MANAGED,
            M_BOUNDARY,
            WAN_ADDR,
            UNDERLAY_PORT,
            "managed-underlay",
        )
        assert f"PEER={WAN_ADDR}:{UNDERLAY_PORT}" in out
        underlay_server = finish_server(underlay, "UNDERLAY")
        servers.remove(underlay)
        assert f"UNDERLAY_PEER={M_BOUNDARY}:" in underlay_server, underlay_server
        print("EXP055_DEFAULT_SCOPE_NO_RECURSION=PASS")

        assert nft_counter("exp055-remember") >= 4
        assert nft_counter("exp055-restore-forward") >= 3

        print("EXP055_RESULT=PASS")
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
        for name in (WAN, LAN, HOST, MANAGED, REMOTE):
            delete_namespace(name)


if __name__ == "__main__":
    raise SystemExit(main())
