#!/usr/bin/env python3
"""EXP-052: host-side nftables DNAT for NG3 server publication."""

from __future__ import annotations

import os
import subprocess
from ipaddress import IPv4Address

from rou.host_publication_policy import (
    HostPublicationDesiredState,
    HostPublicationMappingIntent,
    HostPublicationSelectorKind,
    build_host_publication_desired,
)
from rou.linux_host_publication import (
    LinuxHostPublicationBackend,
    converge_host_publication_once,
)
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.local_publication_policy import PublicationProtocol


PID = os.getpid()
HOST = f"vng52h-{PID}"
CLIENT = f"vng52c-{PID}"
ALT = f"vng52a-{PID}"
MANAGED = f"vng52m-{PID}"

EXT_CLIENT = "e52c"
EXT_HOST = "e52he"
ALT_CLIENT = "e52a"
ALT_HOST = "e52ha"
INNER_HOST = "e52hi"
INNER_MANAGED = "e52m"

HOST_PRIMARY = "198.51.100.1"
HOST_SECONDARY = "198.51.100.5"
CLIENT_IP = "198.51.100.2"
ALT_HOST_IP = "203.0.113.1"
ALT_CLIENT_IP = "203.0.113.2"
MANAGED_IP = "192.0.2.2"
HOST_INNER_IP = "192.0.2.1"



def run(*args: str, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def ns(namespace: str, *args: str, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("ip", "netns", "exec", namespace, *args, input_text=input_text, check=check)


def add_namespace(name: str) -> None:
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def delete_namespace(name: str) -> None:
    run("ip", "netns", "del", name, check=False)


def start_python(namespace: str, code: str, *args: str) -> subprocess.Popen[str]:
    proc = subprocess.Popen(
        ["ip", "netns", "exec", namespace, "python3", "-u", "-c", code, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    ready = proc.stdout.readline().strip()
    if ready != "READY":
        out, err = proc.communicate(timeout=3)
        raise AssertionError(
            f"server in {namespace} did not become ready: first={ready!r} out={out!r} err={err!r}"
        )
    return proc


TCP_SERVER = r"""
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
tag = sys.argv[3]
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((addr, port))
s.listen(4)
print("READY", flush=True)
conn, peer = s.accept()
conn.settimeout(3)
data = conn.recv(4096)
print(f"{tag}_PEER={peer[0]}:{peer[1]}", flush=True)
conn.sendall(b"ACK:" + data)
conn.close()
s.close()
"""

UDP_SERVER = r"""
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
tag = sys.argv[3]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((addr, port))
s.settimeout(5)
print("READY", flush=True)
data, peer = s.recvfrom(4096)
print(f"{tag}_PEER={peer[0]}:{peer[1]}", flush=True)
s.sendto(b"ACK:" + data, peer)
s.close()
"""

TCP_CLIENT = r"""
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
payload = sys.argv[3].encode()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(3)
s.connect((addr, port))
s.sendall(payload)
data = s.recv(4096)
peer = s.getpeername()
print(f"PEER={peer[0]}:{peer[1]}")
print("DATA=" + data.decode())
assert data == b"ACK:" + payload
s.close()
"""

TCP_BLOCKED = r"""
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1.5)
rc = s.connect_ex((addr, port))
print(f"CONNECT_EX={rc}")
assert rc != 0
s.close()
"""

UDP_CLIENT = r"""
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
payload = sys.argv[3].encode()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", 0))
s.settimeout(3)
s.sendto(payload, (addr, port))
data, peer = s.recvfrom(4096)
print(f"PEER={peer[0]}:{peer[1]}")
print("DATA=" + data.decode())
assert data == b"ACK:" + payload
assert peer == (addr, port), (peer, (addr, port))
s.close()
"""

UDP_BLOCKED = r"""
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(1.0)
s.connect((addr, port))
try:
    s.send(b"must-not-arrive")
    data = s.recv(4096)
except (TimeoutError, ConnectionRefusedError, OSError):
    print("BLOCKED=1")
else:
    raise AssertionError(f"unexpected UDP response: {data!r}")
finally:
    s.close()
"""


def finish_server(proc: subprocess.Popen[str], marker: str) -> str:
    out, err = proc.communicate(timeout=5)
    if proc.returncode != 0:
        raise AssertionError(f"{marker} server failed rc={proc.returncode}: {err}")
    text = out.strip()
    if marker not in text:
        raise AssertionError(f"{marker} evidence missing: {text!r}")
    return text


def setup() -> None:
    for name in (HOST, CLIENT, ALT, MANAGED):
        add_namespace(name)

    run("ip", "link", "add", EXT_CLIENT, "type", "veth", "peer", "name", EXT_HOST)
    run("ip", "link", "set", EXT_CLIENT, "netns", CLIENT)
    run("ip", "link", "set", EXT_HOST, "netns", HOST)

    run("ip", "link", "add", ALT_CLIENT, "type", "veth", "peer", "name", ALT_HOST)
    run("ip", "link", "set", ALT_CLIENT, "netns", ALT)
    run("ip", "link", "set", ALT_HOST, "netns", HOST)

    run("ip", "link", "add", INNER_HOST, "type", "veth", "peer", "name", INNER_MANAGED)
    run("ip", "link", "set", INNER_HOST, "netns", HOST)
    run("ip", "link", "set", INNER_MANAGED, "netns", MANAGED)

    ns(CLIENT, "ip", "addr", "add", f"{CLIENT_IP}/29", "dev", EXT_CLIENT)
    ns(CLIENT, "ip", "link", "set", EXT_CLIENT, "up")

    ns(HOST, "ip", "addr", "add", f"{HOST_PRIMARY}/29", "dev", EXT_HOST)
    ns(HOST, "ip", "addr", "add", f"{HOST_SECONDARY}/32", "dev", EXT_HOST)
    ns(HOST, "ip", "link", "set", EXT_HOST, "up")

    ns(ALT, "ip", "addr", "add", f"{ALT_CLIENT_IP}/30", "dev", ALT_CLIENT)
    ns(ALT, "ip", "link", "set", ALT_CLIENT, "up")
    ns(ALT, "ip", "route", "add", f"{HOST_PRIMARY}/32", "via", ALT_HOST_IP)
    ns(ALT, "ip", "route", "add", "198.51.100.0/29", "via", ALT_HOST_IP)
    ns(CLIENT, "ip", "route", "add", f"{ALT_CLIENT_IP}/32", "via", HOST_PRIMARY)

    ns(HOST, "ip", "addr", "add", f"{ALT_HOST_IP}/30", "dev", ALT_HOST)
    ns(HOST, "ip", "link", "set", ALT_HOST, "up")

    ns(HOST, "ip", "addr", "add", f"{HOST_INNER_IP}/30", "dev", INNER_HOST)
    ns(HOST, "ip", "link", "set", INNER_HOST, "up")

    ns(MANAGED, "ip", "addr", "add", f"{MANAGED_IP}/30", "dev", INNER_MANAGED)
    ns(MANAGED, "ip", "link", "set", INNER_MANAGED, "up")
    ns(MANAGED, "ip", "route", "add", "default", "via", HOST_INNER_IP)

    ns(HOST, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")


def publication_desired() -> HostPublicationDesiredState:
    address = IPv4Address(MANAGED_IP)
    return build_host_publication_desired(
        (
            HostPublicationMappingIntent(
                device_id="exp052",
                protocol=PublicationProtocol.TCP,
                selector_kind=HostPublicationSelectorKind.INTERFACE,
                selector_value=EXT_HOST,
                host_port=44443,
                internal_address=address,
                internal_port=8443,
            ),
            HostPublicationMappingIntent(
                device_id="exp052",
                protocol=PublicationProtocol.UDP,
                selector_kind=HostPublicationSelectorKind.IPV4,
                selector_value=IPv4Address(HOST_PRIMARY),
                host_port=44444,
                internal_address=address,
                internal_port=8444,
            ),
            HostPublicationMappingIntent(
                device_id="exp052",
                protocol=PublicationProtocol.TCP,
                selector_kind=HostPublicationSelectorKind.ANY,
                selector_value=None,
                host_port=44445,
                internal_address=address,
                internal_port=8445,
            ),
        )
    )


def publication_backend() -> LinuxHostPublicationBackend:
    return LinuxHostPublicationBackend(
        SubprocessNftRunner(),
        network_namespace=HOST,
    )


def assert_inventory(
    backend: LinuxHostPublicationBackend,
    desired: HostPublicationDesiredState,
) -> None:
    observed = backend.observe()
    assert observed.table_present, observed
    assert observed.conflict_free, observed.conflicts
    assert observed.rules == desired.rules, (observed.rules, desired.rules)
    assert observed.forwarding_enabled
    print("EXP052_OWNER_INVENTORY=PASS")


def main() -> int:
    servers: list[subprocess.Popen[str]] = []
    try:
        setup()
        backend = publication_backend()
        desired = publication_desired()
        convergence = converge_host_publication_once(backend, desired)
        assert convergence.confirmed, convergence
        print("EXP052_REFERENCE_BACKEND_CONVERGENCE=PASS")

        tcp_if = start_python(MANAGED, TCP_SERVER, MANAGED_IP, "8443", "TCP_IF")
        servers.append(tcp_if)

        # H1 negative first: same destination through the wrong ingress interface.
        blocked = ns(ALT, "python3", "-c", TCP_BLOCKED, HOST_PRIMARY, "44443")
        assert "CONNECT_EX=" in blocked.stdout
        print("EXP052_INTERFACE_SELECTOR_NEGATIVE=PASS")

        transit_if = start_python(ALT, TCP_SERVER, ALT_CLIENT_IP, "44443", "TRANSIT_IF")
        servers.append(transit_if)
        transit_if_out = ns(
            CLIENT, "python3", "-c", TCP_CLIENT, ALT_CLIENT_IP, "44443", "transit-if"
        )
        assert f"PEER={ALT_CLIENT_IP}:44443" in transit_if_out.stdout
        transit_if_server = finish_server(transit_if, "TRANSIT_IF_PEER")
        assert f"TRANSIT_IF_PEER={CLIENT_IP}:" in transit_if_server, transit_if_server
        servers.remove(transit_if)
        print("EXP052_INTERFACE_SELECTOR_TRANSIT_UNTOUCHED=PASS")

        ok = ns(CLIENT, "python3", "-c", TCP_CLIENT, HOST_PRIMARY, "44443", "tcp-if")
        assert f"PEER={HOST_PRIMARY}:44443" in ok.stdout
        server_out = finish_server(tcp_if, "TCP_IF_PEER")
        assert f"TCP_IF_PEER={CLIENT_IP}:" in server_out, server_out
        servers.remove(tcp_if)
        print("EXP052_INTERFACE_SELECTOR_TCP=PASS")

        udp_ip = start_python(MANAGED, UDP_SERVER, MANAGED_IP, "8444", "UDP_IP")
        servers.append(udp_ip)

        # H2 negative first: same port on a host address not selected by the rule.
        blocked_udp = ns(CLIENT, "python3", "-c", UDP_BLOCKED, HOST_SECONDARY, "44444")
        assert "BLOCKED=1" in blocked_udp.stdout
        print("EXP052_IPV4_SELECTOR_NEGATIVE=PASS")

        udp = ns(CLIENT, "python3", "-c", UDP_CLIENT, HOST_PRIMARY, "44444", "udp-ip")
        assert f"PEER={HOST_PRIMARY}:44444" in udp.stdout
        udp_server_out = finish_server(udp_ip, "UDP_IP_PEER")
        assert f"UDP_IP_PEER={CLIENT_IP}:" in udp_server_out, udp_server_out
        servers.remove(udp_ip)
        print("EXP052_IPV4_SELECTOR_UDP=PASS")

        transit_any = start_python(ALT, TCP_SERVER, ALT_CLIENT_IP, "44445", "TRANSIT_ANY")
        servers.append(transit_any)
        transit_any_out = ns(
            CLIENT, "python3", "-c", TCP_CLIENT, ALT_CLIENT_IP, "44445", "transit-any"
        )
        assert f"PEER={ALT_CLIENT_IP}:44445" in transit_any_out.stdout
        transit_any_server = finish_server(transit_any, "TRANSIT_ANY_PEER")
        assert f"TRANSIT_ANY_PEER={CLIENT_IP}:" in transit_any_server, transit_any_server
        servers.remove(transit_any)
        print("EXP052_ANY_SELECTOR_TRANSIT_UNTOUCHED=PASS")

        tcp_any = start_python(MANAGED, TCP_SERVER, MANAGED_IP, "8445", "TCP_ANY")
        servers.append(tcp_any)
        any_out = ns(CLIENT, "python3", "-c", TCP_CLIENT, HOST_SECONDARY, "44445", "tcp-any")
        assert f"PEER={HOST_SECONDARY}:44445" in any_out.stdout
        any_server_out = finish_server(tcp_any, "TCP_ANY_PEER")
        assert f"TCP_ANY_PEER={CLIENT_IP}:" in any_server_out, any_server_out
        servers.remove(tcp_any)
        print("EXP052_ANY_SELECTOR_TCP=PASS")

        host_local = start_python(HOST, TCP_SERVER, HOST_PRIMARY, "45555", "HOST_LOCAL")
        servers.append(host_local)
        local_out = ns(CLIENT, "python3", "-c", TCP_CLIENT, HOST_PRIMARY, "45555", "host-local")
        assert f"PEER={HOST_PRIMARY}:45555" in local_out.stdout
        local_server_out = finish_server(host_local, "HOST_LOCAL_PEER")
        assert f"HOST_LOCAL_PEER={CLIENT_IP}:" in local_server_out, local_server_out
        servers.remove(host_local)
        print("EXP052_UNRELATED_HOST_LOCAL=PASS")

        assert_inventory(backend, desired)

        cleanup = converge_host_publication_once(
            backend,
            HostPublicationDesiredState(()),
        )
        assert cleanup.confirmed, cleanup
        assert not backend.observe().table_present
        print("EXP052_OWNER_CLEANUP=PASS")

        print("EXP052_RESULT=PASS")
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
        for name in (MANAGED, ALT, CLIENT, HOST):
            delete_namespace(name)


if __name__ == "__main__":
    raise SystemExit(main())
