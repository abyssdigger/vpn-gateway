#!/usr/bin/env python3
"""EXP-053: carry selected Profile identity across the managed/host veth."""

from __future__ import annotations

import json
import os
import subprocess
import sys


PID = os.getpid()
REMOTE_A = f"vng53a-{PID}"
REMOTE_B = f"vng53b-{PID}"
MANAGED = f"vng53m-{PID}"
HOST = f"vng53h-{PID}"
LAN = f"vng53l-{PID}"

A_REMOTE_IF = "ra0"
A_MANAGED_IF = "ma0"
B_REMOTE_IF = "rb0"
B_MANAGED_IF = "mb0"
MANAGED_BOUNDARY = "mh0"
HOST_BOUNDARY = "hm0"
HOST_LAN = "hl0"
LAN_IF = "lh0"

A_LINK_REMOTE = "192.0.2.2"
A_LINK_MANAGED = "192.0.2.1"
B_LINK_REMOTE = "192.0.2.6"
B_LINK_MANAGED = "192.0.2.5"
A_SOURCE = "10.77.0.10"
B_SOURCE = "10.77.0.20"
BAD_SOURCE = "10.88.0.10"
REMOTE_PREFIX = "10.77.0.0/24"

MANAGED_BOUNDARY_IP = "198.19.255.2"
HOST_BOUNDARY_IP = "198.19.255.1"
HOST_LAN_IP = "203.0.113.1"
LAN_IP = "203.0.113.2"

PROFILE_A_MARK = 0x00530001
PROFILE_B_MARK = 0x00530002

LAN_PORT = 53053
HOST_LOCAL_PORT = 53054
HOST_ORIGIN_PORT = 53055


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


def add_veth(
    left_ns: str,
    left_name: str,
    right_ns: str,
    right_name: str,
) -> None:
    run(
        "ip",
        "link",
        "add",
        left_name,
        "type",
        "veth",
        "peer",
        "name",
        right_name,
    )
    run("ip", "link", "set", left_name, "netns", left_ns)
    run("ip", "link", "set", right_name, "netns", right_ns)


def addr_up(namespace: str, name: str, cidr: str) -> None:
    ns(namespace, "ip", "addr", "add", cidr, "dev", name)
    ns(namespace, "ip", "link", "set", name, "up")


def nft(namespace: str, text: str) -> None:
    ns(namespace, "nft", "-f", "-", input_text=text)


UDP_SERVER = r"""
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
count = int(sys.argv[3])
tag = sys.argv[4]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((addr, port))
s.settimeout(8)
print("READY", flush=True)
for index in range(count):
    data, peer = s.recvfrom(4096)
    print(f"{tag}_PEER{index}={peer[0]}:{peer[1]}", flush=True)
    print(f"{tag}_DATA{index}={data.decode()}", flush=True)
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
print(f"PEER={peer[0]}:{peer[1]}")
print("DATA=" + data.decode())
assert data == b"ACK:" + payload
assert peer == (destination, port), (peer, (destination, port))
s.close()
"""


UDP_BLOCKED = r"""
import socket, sys
source = sys.argv[1]
destination = sys.argv[2]
port = int(sys.argv[3])
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((source, 0))
s.settimeout(1.5)
s.sendto(b"must-not-arrive", (destination, port))
try:
    data, peer = s.recvfrom(4096)
except TimeoutError:
    print("BLOCKED=1")
else:
    raise AssertionError(f"unexpected reply from {peer!r}: {data!r}")
finally:
    s.close()
"""


def start_udp_server(
    namespace: str,
    address: str,
    port: int,
    count: int,
    tag: str,
) -> subprocess.Popen[str]:
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
            str(count),
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
    for name in (REMOTE_A, REMOTE_B, MANAGED, HOST, LAN):
        add_namespace(name)

    add_veth(REMOTE_A, A_REMOTE_IF, MANAGED, A_MANAGED_IF)
    add_veth(REMOTE_B, B_REMOTE_IF, MANAGED, B_MANAGED_IF)
    add_veth(MANAGED, MANAGED_BOUNDARY, HOST, HOST_BOUNDARY)
    add_veth(HOST, HOST_LAN, LAN, LAN_IF)

    addr_up(REMOTE_A, A_REMOTE_IF, f"{A_LINK_REMOTE}/30")
    addr_up(MANAGED, A_MANAGED_IF, f"{A_LINK_MANAGED}/30")
    addr_up(REMOTE_B, B_REMOTE_IF, f"{B_LINK_REMOTE}/30")
    addr_up(MANAGED, B_MANAGED_IF, f"{B_LINK_MANAGED}/30")
    addr_up(MANAGED, MANAGED_BOUNDARY, f"{MANAGED_BOUNDARY_IP}/30")
    addr_up(HOST, HOST_BOUNDARY, f"{HOST_BOUNDARY_IP}/30")
    addr_up(HOST, HOST_LAN, f"{HOST_LAN_IP}/24")
    addr_up(LAN, LAN_IF, f"{LAN_IP}/24")

    ns(REMOTE_A, "ip", "addr", "add", f"{A_SOURCE}/32", "dev", "lo")
    ns(REMOTE_A, "ip", "addr", "add", f"{BAD_SOURCE}/32", "dev", "lo")
    ns(REMOTE_B, "ip", "addr", "add", f"{B_SOURCE}/32", "dev", "lo")

    ns(
        REMOTE_A,
        "ip",
        "route",
        "add",
        "default",
        "via",
        A_LINK_MANAGED,
        "dev",
        A_REMOTE_IF,
    )
    ns(
        REMOTE_B,
        "ip",
        "route",
        "add",
        "default",
        "via",
        B_LINK_MANAGED,
        "dev",
        B_REMOTE_IF,
    )

    ns(
        MANAGED,
        "ip",
        "route",
        "add",
        f"{A_SOURCE}/32",
        "via",
        A_LINK_REMOTE,
        "dev",
        A_MANAGED_IF,
    )
    ns(
        MANAGED,
        "ip",
        "route",
        "add",
        f"{B_SOURCE}/32",
        "via",
        B_LINK_REMOTE,
        "dev",
        B_MANAGED_IF,
    )
    ns(
        MANAGED,
        "ip",
        "route",
        "add",
        f"{BAD_SOURCE}/32",
        "via",
        A_LINK_REMOTE,
        "dev",
        A_MANAGED_IF,
    )
    ns(
        MANAGED,
        "ip",
        "route",
        "add",
        "default",
        "via",
        HOST_BOUNDARY_IP,
        "dev",
        MANAGED_BOUNDARY,
    )

    ns(
        HOST,
        "ip",
        "route",
        "add",
        REMOTE_PREFIX,
        "via",
        MANAGED_BOUNDARY_IP,
        "dev",
        HOST_BOUNDARY,
    )
    ns(
        HOST,
        "ip",
        "route",
        "add",
        f"{BAD_SOURCE}/32",
        "via",
        MANAGED_BOUNDARY_IP,
        "dev",
        HOST_BOUNDARY,
    )
    ns(
        LAN,
        "ip",
        "route",
        "add",
        REMOTE_PREFIX,
        "via",
        HOST_LAN_IP,
        "dev",
        LAN_IF,
    )

    ns(MANAGED, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")
    ns(HOST, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")

    # The priority-0 chain emulates the already accepted managed fail-closed
    # Profile permission. Both Profiles intentionally own the same remote prefix;
    # current ingress path is what distinguishes the selected Profile.
    nft(
        MANAGED,
        f"""
table ip exp053_managed {{
    chain payload_forward {{
        type filter hook forward priority 0; policy drop;
        iifname "{A_MANAGED_IF}" oifname "{MANAGED_BOUNDARY}" ip saddr {REMOTE_PREFIX} ct state new accept comment "exp053-profile-a-new"
        iifname "{B_MANAGED_IF}" oifname "{MANAGED_BOUNDARY}" ip saddr {REMOTE_PREFIX} ct state new accept comment "exp053-profile-b-new"
        iifname "{MANAGED_BOUNDARY}" oifname "{A_MANAGED_IF}" ip daddr {A_SOURCE} ct state established,related accept comment "exp053-profile-a-return"
        iifname "{MANAGED_BOUNDARY}" oifname "{B_MANAGED_IF}" ip daddr {B_SOURCE} ct state established,related accept comment "exp053-profile-b-return"
    }}

    chain boundary_profile_association {{
        type filter hook forward priority 10; policy accept;
        iifname "{A_MANAGED_IF}" oifname "{MANAGED_BOUNDARY}" ip saddr {REMOTE_PREFIX} meta mark set {PROFILE_A_MARK} comment "exp053-assoc-a"
        iifname "{B_MANAGED_IF}" oifname "{MANAGED_BOUNDARY}" ip saddr {REMOTE_PREFIX} meta mark set {PROFILE_B_MARK} comment "exp053-assoc-b"
    }}
}}
""",
    )

    # Host rules never inspect the remote source prefix. They consume only the
    # association carried across the common boundary. Only Profile A requests NAT.
    nft(
        HOST,
        f"""
table ip exp053_host {{
    chain association_observe {{
        type filter hook prerouting priority -150; policy accept;
        iifname "{HOST_BOUNDARY}" meta mark {PROFILE_A_MARK} counter comment "exp053-seen-a"
        iifname "{HOST_BOUNDARY}" meta mark {PROFILE_B_MARK} counter comment "exp053-seen-b"
    }}

    chain profile_gateway_nat {{
        type nat hook postrouting priority srcnat; policy accept;
        iifname "{HOST_BOUNDARY}" oifname "{HOST_LAN}" meta mark {PROFILE_A_MARK} masquerade comment "exp053-snat-a"
    }}
}}
""",
    )


def rule_counter(namespace: str, comment: str) -> int:
    raw = ns(namespace, "nft", "-j", "list", "ruleset").stdout
    root = json.loads(raw)
    for row in root.get("nftables", []):
        rule = row.get("rule") if isinstance(row, dict) else None
        if not isinstance(rule, dict) or rule.get("comment") != comment:
            continue
        for expr in rule.get("expr", []):
            counter = expr.get("counter") if isinstance(expr, dict) else None
            if isinstance(counter, dict):
                packets = counter.get("packets")
                if type(packets) is int:
                    return packets
    raise AssertionError(f"counter for {comment!r} not found")


def main() -> int:
    servers: list[subprocess.Popen[str]] = []
    try:
        setup()

        # One unaccepted source is routed to the same managed ingress but falls
        # outside both Profile remote-prefix permissions.
        blocked = ns(
            REMOTE_A,
            "python3",
            "-c",
            UDP_BLOCKED,
            BAD_SOURCE,
            LAN_IP,
            str(LAN_PORT),
        )
        assert "BLOCKED=1" in blocked.stdout
        assert rule_counter(HOST, "exp053-seen-a") == 0
        assert rule_counter(HOST, "exp053-seen-b") == 0
        print("EXP053_ACCEPTED_ONLY_ASSOCIATION=PASS")

        lan = start_udp_server(LAN, LAN_IP, LAN_PORT, 2, "LAN")
        servers.append(lan)

        a_out = client(
            REMOTE_A,
            A_SOURCE,
            LAN_IP,
            LAN_PORT,
            "profile-a",
        )
        assert f"PEER={LAN_IP}:{LAN_PORT}" in a_out
        print("EXP053_PROFILE_A_REPLY=PASS")

        b_out = client(
            REMOTE_B,
            B_SOURCE,
            LAN_IP,
            LAN_PORT,
            "profile-b",
        )
        assert f"PEER={LAN_IP}:{LAN_PORT}" in b_out
        print("EXP053_PROFILE_B_REPLY=PASS")

        lan_out = finish_server(lan, "LAN")
        servers.remove(lan)
        assert f"LAN_PEER0={HOST_LAN_IP}:" in lan_out, lan_out
        assert f"LAN_DATA0=profile-a" in lan_out, lan_out
        assert f"LAN_PEER1={B_SOURCE}:" in lan_out, lan_out
        assert f"LAN_DATA1=profile-b" in lan_out, lan_out
        print("EXP053_PROFILE_A_SNAT_ONLY=PASS")
        print("EXP053_PROFILE_B_UNTRANSLATED=PASS")

        seen_a = rule_counter(HOST, "exp053-seen-a")
        seen_b = rule_counter(HOST, "exp053-seen-b")
        assert seen_a == 1, seen_a
        assert seen_b == 1, seen_b
        print("EXP053_MARK_CROSSES_BOUNDARY=PASS")

        host_local = start_udp_server(
            HOST,
            HOST_BOUNDARY_IP,
            HOST_LOCAL_PORT,
            1,
            "HOST",
        )
        servers.append(host_local)
        host_reply = client(
            REMOTE_A,
            A_SOURCE,
            HOST_BOUNDARY_IP,
            HOST_LOCAL_PORT,
            "host-local",
        )
        assert f"PEER={HOST_BOUNDARY_IP}:{HOST_LOCAL_PORT}" in host_reply
        host_out = finish_server(host_local, "HOST")
        servers.remove(host_local)
        assert f"HOST_PEER0={A_SOURCE}:" in host_out, host_out
        print("EXP053_HOST_LOCAL_NOT_SNAT=PASS")

        # Host-local Profile-A traffic still crosses the boundary with the mark,
        # but cannot hit host postrouting NAT because it terminates locally.
        assert rule_counter(HOST, "exp053-seen-a") == 2

        unrelated = start_udp_server(
            LAN,
            LAN_IP,
            HOST_ORIGIN_PORT,
            1,
            "UNRELATED",
        )
        servers.append(unrelated)
        unrelated_out = client(
            HOST,
            HOST_LAN_IP,
            LAN_IP,
            HOST_ORIGIN_PORT,
            "ordinary-host",
        )
        assert f"PEER={LAN_IP}:{HOST_ORIGIN_PORT}" in unrelated_out
        unrelated_server = finish_server(unrelated, "UNRELATED")
        servers.remove(unrelated)
        assert f"UNRELATED_PEER0={HOST_LAN_IP}:" in unrelated_server
        print("EXP053_UNRELATED_HOST_TRAFFIC=PASS")

        assert rule_counter(HOST, "exp053-seen-b") == 1
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
        for name in (LAN, HOST, MANAGED, REMOTE_B, REMOTE_A):
            delete_namespace(name)


if __name__ == "__main__":
    raise SystemExit(main())
