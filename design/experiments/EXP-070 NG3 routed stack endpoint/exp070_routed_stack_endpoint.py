#!/usr/bin/env python3
"""EXP-070: routed managed-stack endpoint candidates (ipvlan L3S / netkit L3)."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time


PID = os.getpid()
HOST = f"vng70h-{PID}"
STACK = f"vng70s-{PID}"
LAN = f"vng70l-{PID}"
REMOTE = f"vng70r-{PID}"

H_UP, L_H = "e70hu", "e70lh"
S_R, R_S = "e70sr", "e70rs"
IPVL = "e70ipvl"
IPVHOST = "e70ivh"
NK_HOST = "e70nkh"
NK_STACK = "e70nks"
RV_HOST = "vpng0"
RV_STACK = "e70rvs"

HOST_LAN = "192.0.2.1"
LAN_IP = "192.0.2.2"
STACK_TRANSIT = "198.51.100.1"
REMOTE_TRANSIT = "198.51.100.2"
REMOTE_IP = "10.70.0.2"
REMOTE_NO_NAT_IP = "10.70.0.3"
STACK_IPVL_IP = "198.18.70.2"
HOST_IPVL_IP = "198.18.70.1"
STACK_NETKIT_IP = "198.18.71.2"
RV_HOST_IP = "169.254.70.1"
RV_STACK_IP = "169.254.70.2"
MARK = "0x70010001"


def run(*args: str, check: bool = True, input_text: str | None = None, timeout: float | None = None):
    return subprocess.run(
        args,
        check=check,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def ns(name: str, *args: str, check: bool = True, input_text: str | None = None, timeout: float | None = None):
    return run("ip", "netns", "exec", name, *args, check=check, input_text=input_text, timeout=timeout)


def add_ns(name: str):
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def del_ns(name: str):
    run("ip", "netns", "del", name, check=False)


def pair(left_ns: str, left_if: str, right_ns: str, right_if: str):
    run("ip", "link", "add", left_if, "type", "veth", "peer", "name", right_if)
    run("ip", "link", "set", left_if, "netns", left_ns)
    run("ip", "link", "set", right_if, "netns", right_ns)


def addr(name: str, interface: str, cidr: str):
    ns(name, "ip", "addr", "add", cidr, "dev", interface)
    ns(name, "ip", "link", "set", interface, "up")


def require_tools():
    if os.geteuid() != 0:
        raise RuntimeError("EXP-070 requires root")
    for tool in ("ip", "nft", "python3", "ping"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"missing tool: {tool}")


def setup_base():
    for name in (HOST, STACK, LAN, REMOTE):
        add_ns(name)

    pair(HOST, H_UP, LAN, L_H)
    pair(STACK, S_R, REMOTE, R_S)

    addr(HOST, H_UP, f"{HOST_LAN}/24")
    addr(LAN, L_H, f"{LAN_IP}/24")
    addr(STACK, S_R, f"{STACK_TRANSIT}/30")
    addr(REMOTE, R_S, f"{REMOTE_TRANSIT}/30")
    ns(REMOTE, "ip", "addr", "add", f"{REMOTE_IP}/32", "dev", "lo")
    ns(REMOTE, "ip", "addr", "add", f"{REMOTE_NO_NAT_IP}/32", "dev", "lo")

    ns(HOST, "sysctl", "-qw", "net.ipv4.ip_forward=1")
    ns(STACK, "sysctl", "-qw", "net.ipv4.ip_forward=1")
    for name, ifaces in ((HOST, ("all", "default", H_UP)), (STACK, ("all", "default", S_R))):
        for iface in ifaces:
            ns(name, "sysctl", "-qw", f"net.ipv4.conf.{iface}.rp_filter=0")

    ns(STACK, "ip", "route", "add", "10.70.0.0/24", "via", REMOTE_TRANSIT, "dev", S_R)
    ns(REMOTE, "ip", "route", "add", "192.0.2.0/24", "via", STACK_TRANSIT, "dev", R_S)
    ns(REMOTE, "ip", "route", "add", f"{HOST_IPVL_IP}/32", "via", STACK_TRANSIT, "dev", R_S)
    ns(REMOTE, "ip", "route", "add", f"{HOST_LAN}/32", "via", STACK_TRANSIT, "dev", R_S)


SERVER = r"""
import socket,sys
addr=sys.argv[1]; port=int(sys.argv[2]); count=int(sys.argv[3])
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((addr,port)); s.listen(count)
print("READY", flush=True)
for _ in range(count):
    c,p=s.accept(); c.settimeout(3)
    data=c.recv(64)
    print("PEER="+p[0], flush=True)
    c.sendall(b"ACK:"+data)
    c.close()
s.close()
"""

CLIENT = r"""
import socket,sys
src=sys.argv[1]
dst=sys.argv[2]; port=int(sys.argv[3]); payload=sys.argv[4].encode()
s=socket.socket(); s.settimeout(3)
if src != "-":
    s.bind((src,0))
s.connect((dst,port)); s.sendall(payload)
data=s.recv(128)
assert data==b"ACK:"+payload, data
print("OK")
s.close()
"""


def start_server(namespace: str, ip: str, port: int, count: int = 1):
    p = subprocess.Popen(
        ["ip", "netns", "exec", namespace, "python3", "-u", "-c", SERVER, ip, str(port), str(count)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert p.stdout is not None
    if p.stdout.readline().strip() != "READY":
        out, err = p.communicate(timeout=2)
        raise AssertionError((out, err))
    return p


def client(namespace: str, src: str, dst: str, port: int, payload: str) -> bool:
    r = ns(namespace, "python3", "-c", CLIENT, src, dst, str(port), payload, check=False, timeout=6)
    return r.returncode == 0 and "OK" in r.stdout


def read_peer(server) -> str:
    assert server.stdout is not None
    line = server.stdout.readline().strip()
    if not line.startswith("PEER="):
        raise AssertionError(line)
    peer = line.split("=", 1)[1]
    out, err = server.communicate(timeout=4)
    if server.returncode != 0:
        raise AssertionError((out, err))
    return peer


def probe_ipvlan_l3s() -> tuple[bool, str]:
    r = ns(HOST, "ip", "link", "add", "e70probe", "link", H_UP, "type", "ipvlan", "mode", "l3s", "bridge", check=False)
    if r.returncode == 0:
        ns(HOST, "ip", "link", "del", "e70probe", check=False)
        return True, ""
    return False, (r.stderr or r.stdout).strip()


def setup_ipvlan():
    r = ns(HOST, "ip", "link", "add", IPVL, "link", H_UP, "type", "ipvlan", "mode", "l3s", "bridge", check=False)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    ns(HOST, "ip", "link", "set", IPVL, "netns", STACK)
    addr(STACK, IPVL, f"{STACK_IPVL_IP}/32")
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{IPVL}.rp_filter=0")
    ns(STACK, "ip", "route", "add", "192.0.2.0/24", "dev", IPVL)

    # External ordinary network knows only that the stack-owned address is routed by HOST.
    ns(LAN, "ip", "route", "add", f"{STACK_IPVL_IP}/32", "via", HOST_LAN, "dev", L_H)


def phase_ipvlan_external_reachability() -> bool:
    server = start_server(STACK, STACK_IPVL_IP, 17001)
    ok = client(LAN, LAN_IP, STACK_IPVL_IP, 17001, "IPVLAN-IN")
    if not ok:
        if server.poll() is None:
            server.kill(); server.communicate(timeout=1)
        print("EXP070_IPVLAN_EXTERNAL_TO_STACK=FAIL", flush=True)
        return False
    peer = read_peer(server)
    good = peer == LAN_IP
    print(f"EXP070_IPVLAN_EXTERNAL_TO_STACK={'PASS' if good else 'FAIL'} peer={peer}", flush=True)
    return good


def phase_ipvlan_stack_nat() -> bool:
    nft = f"""
table ip e70nat {{
  chain postrouting {{
    type nat hook postrouting priority srcnat; policy accept;
    ip saddr {REMOTE_IP} oifname "{IPVL}" counter masquerade comment "e70-snat"
  }}
}}
"""
    ns(STACK, "nft", "-f", "-", input_text=nft)

    server = start_server(LAN, LAN_IP, 17002)
    ok = client(REMOTE, REMOTE_IP, LAN_IP, 17002, "NAT")
    if not ok:
        nat_count = nft_counter(STACK, "e70nat", "e70-snat")
        stack_route = ns(STACK, "ip", "-4", "route", "get", LAN_IP, "from", REMOTE_IP, check=False)
        host_route = ns(HOST, "ip", "-4", "route", "get", LAN_IP, check=False)
        stack_link = ns(STACK, "ip", "-s", "-j", "link", "show", "dev", IPVL, check=False)
        host_link = ns(HOST, "ip", "-s", "-j", "link", "show", "dev", H_UP, check=False)
        lan_link = ns(LAN, "ip", "-s", "-j", "link", "show", "dev", L_H, check=False)
        if server.poll() is None:
            server.kill(); server.communicate(timeout=1)
        print(
            "EXP070_IPVLAN_STACK_SNAT=FAIL "
            f"nat_packets={nat_count} "
            f"stack_route={stack_route.stdout.strip()!r} "
            f"host_route={host_route.stdout.strip()!r}",
            flush=True,
        )
        print("EXP070_IPVLAN_DIAG_STACK_LINK=" + stack_link.stdout.strip(), flush=True)
        print("EXP070_IPVLAN_DIAG_HOST_LINK=" + host_link.stdout.strip(), flush=True)
        print("EXP070_IPVLAN_DIAG_LAN_LINK=" + lan_link.stdout.strip(), flush=True)
        return False
    peer = read_peer(server)
    good = peer == STACK_IPVL_IP
    print(f"EXP070_IPVLAN_STACK_SNAT={'PASS' if good else 'FAIL'} peer={peer}", flush=True)
    return good


def setup_host_ipvlan_alias() -> bool:
    r = ns(HOST, "ip", "link", "add", IPVHOST, "link", H_UP, "type", "ipvlan", "mode", "l3s", "bridge", check=False)
    if r.returncode != 0:
        print("EXP070_IPVLAN_HOST_ALIAS=UNAVAILABLE detail=" + repr((r.stderr or r.stdout).strip()), flush=True)
        return False
    addr(HOST, IPVHOST, f"{HOST_IPVL_IP}/32")
    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{IPVHOST}.rp_filter=0")
    print("EXP070_IPVLAN_HOST_ALIAS=SUPPORTED", flush=True)
    return True


def ping(namespace: str, source: str, dest: str) -> bool:
    r = ns(namespace, "ping", "-n", "-c", "1", "-W", "1", "-I", source, dest, check=False, timeout=4)
    return r.returncode == 0


def phase_ipvlan_alias_routes() -> tuple[bool, bool]:
    # First prove sibling-ipvlan cross-talk itself.
    ns(HOST, "ip", "route", "replace", f"{STACK_IPVL_IP}/32", "dev", IPVHOST, "src", HOST_IPVL_IP)
    sibling = ping(HOST, HOST_IPVL_IP, STACK_IPVL_IP)
    print(f"EXP070_IPVLAN_ALIAS_TO_STACK_IP={'PASS' if sibling else 'FAIL'}", flush=True)

    # Then test the user's desired shape: a route to the network behind STACK by device only.
    ns(HOST, "ip", "route", "replace", f"{REMOTE_IP}/32", "dev", IPVHOST, "src", HOST_IPVL_IP)
    dev_only = ping(HOST, HOST_IPVL_IP, REMOTE_IP)
    print(f"EXP070_IPVLAN_ROUTE_DEV_ONLY={'PASS' if dev_only else 'FAIL'}", flush=True)

    # Compare with explicit next-hop via the stack-side ipvlan address.
    ns(HOST, "ip", "route", "replace", f"{REMOTE_IP}/32", "via", STACK_IPVL_IP, "dev", IPVHOST, "onlink", "src", HOST_IPVL_IP)
    via = ping(HOST, HOST_IPVL_IP, REMOTE_IP)
    print(f"EXP070_IPVLAN_ROUTE_VIA_STACK_IP={'PASS' if via else 'FAIL'}", flush=True)
    return dev_only, via


def probe_netkit() -> tuple[bool, str]:
    cmd = ["ip", "link", "add", "e70nkp", "type", "netkit", "mode", "l3", "forward", "peer", "forward", "e70nkq"]
    r = ns(HOST, *cmd, check=False)
    if r.returncode == 0:
        ns(HOST, "ip", "link", "del", "e70nkp", check=False)
        return True, ""
    return False, (r.stderr or r.stdout).strip()


def setup_netkit(scrub_none: bool = False):
    args = ["ip", "link", "add", NK_HOST, "type", "netkit", "mode", "l3"]
    if scrub_none:
        args += ["scrub", "none"]
    args += ["forward", "peer"]
    if scrub_none:
        args += ["scrub", "none"]
    args += ["forward", NK_STACK]
    r = ns(HOST, *args, check=False)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    ns(HOST, "ip", "link", "set", NK_STACK, "netns", STACK)
    ns(HOST, "ip", "link", "set", NK_HOST, "up")
    ns(STACK, "ip", "link", "set", NK_STACK, "up")


def cleanup_netkit():
    ns(HOST, "ip", "link", "del", NK_HOST, check=False)


def phase_netkit_dev_route() -> bool:
    ns(HOST, "ip", "route", "replace", f"{REMOTE_IP}/32", "dev", NK_HOST, "src", HOST_LAN)
    ns(STACK, "ip", "route", "replace", f"{HOST_LAN}/32", "dev", NK_STACK)
    good = ping(HOST, HOST_LAN, REMOTE_IP)
    print(f"EXP070_NETKIT_ROUTE_DEV_ONLY={'PASS' if good else 'FAIL'}", flush=True)
    return good


def nft_counter(namespace: str, table: str, comment: str) -> int:
    doc = json.loads(ns(namespace, "nft", "-j", "list", "table", "ip", table).stdout)
    for row in doc.get("nftables", []):
        rule = row.get("rule") if isinstance(row, dict) else None
        if not isinstance(rule, dict) or rule.get("comment") != comment:
            continue
        for expr in rule.get("expr", []):
            c = expr.get("counter") if isinstance(expr, dict) else None
            if isinstance(c, dict):
                return int(c.get("packets", 0))
    return -1


def phase_netkit_mark_survival() -> bool:
    stack_nft = f"""
table ip e70nks {{
  chain out {{
    type filter hook postrouting priority mangle; policy accept;
    oifname "{NK_STACK}" meta mark set {MARK} counter comment "e70-set-mark"
  }}
}}
"""
    host_nft = f"""
table ip e70nkh {{
  chain in {{
    type filter hook prerouting priority mangle; policy accept;
    iifname "{NK_HOST}" meta mark {MARK} counter comment "e70-see-mark"
  }}
}}
"""
    ns(STACK, "nft", "-f", "-", input_text=stack_nft)
    ns(HOST, "nft", "-f", "-", input_text=host_nft)

    # One-way reachability is enough for carrier survival: the host-side observer must see
    # the exact mark on a packet emitted by STACK. Return routing is a separate question.
    ns(STACK, "ip", "route", "replace", f"{HOST_LAN}/32", "dev", NK_STACK)
    ping_ok = ping(STACK, NK_STACK, HOST_LAN)
    src = nft_counter(STACK, "e70nks", "e70-set-mark")
    dst = nft_counter(HOST, "e70nkh", "e70-see-mark")
    good = src > 0 and dst > 0
    print(
        f"EXP070_NETKIT_SCRUB_NONE_MARK={'PASS' if good else 'FAIL'} "
        f"source_packets={src} host_packets={dst} roundtrip={ping_ok}",
        flush=True,
    )
    return good


def phase_netkit_stack_nat() -> tuple[bool, bool]:
    # Present STACK as an L3 endpoint to HOST: every host-side route points only at
    # the host-visible netkit device, never at a gateway IP.
    ns(STACK, "ip", "addr", "add", f"{STACK_NETKIT_IP}/32", "dev", NK_STACK)
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{NK_STACK}.rp_filter=0")
    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{NK_HOST}.rp_filter=0")

    ns(HOST, "ip", "route", "replace", f"{STACK_NETKIT_IP}/32", "dev", NK_HOST)
    ns(HOST, "ip", "route", "replace", f"{REMOTE_IP}/32", "dev", NK_HOST)
    ns(HOST, "ip", "route", "replace", f"{REMOTE_NO_NAT_IP}/32", "dev", NK_HOST)
    ns(STACK, "ip", "route", "replace", "192.0.2.0/24", "dev", NK_STACK)
    ns(LAN, "ip", "route", "replace", f"{STACK_NETKIT_IP}/32", "via", HOST_LAN, "dev", L_H)
    ns(LAN, "ip", "route", "replace", f"{REMOTE_NO_NAT_IP}/32", "via", HOST_LAN, "dev", L_H)

    nat = f"""
table ip e70nknat {{
  chain postrouting {{
    type nat hook postrouting priority srcnat; policy accept;
    ip saddr {REMOTE_IP} oifname "{NK_STACK}" counter masquerade comment "e70-netkit-snat"
  }}
}}
"""
    ns(STACK, "nft", "-f", "-", input_text=nat)

    server_nat = start_server(LAN, LAN_IP, 17011)
    ok_nat = client(REMOTE, REMOTE_IP, LAN_IP, 17011, "NETKIT-NAT")
    peer_nat = None
    if ok_nat:
        peer_nat = read_peer(server_nat)
    else:
        if server_nat.poll() is None:
            server_nat.kill(); server_nat.communicate(timeout=1)
    nat_good = ok_nat and peer_nat == STACK_NETKIT_IP
    print(
        f"EXP070_NETKIT_STACK_SNAT={'PASS' if nat_good else 'FAIL'} peer={peer_nat}",
        flush=True,
    )

    server_plain = start_server(LAN, LAN_IP, 17012)
    ok_plain = client(REMOTE, REMOTE_NO_NAT_IP, LAN_IP, 17012, "NETKIT-PLAIN")
    peer_plain = None
    if ok_plain:
        peer_plain = read_peer(server_plain)
    else:
        if server_plain.poll() is None:
            server_plain.kill(); server_plain.communicate(timeout=1)
    plain_good = ok_plain and peer_plain == REMOTE_NO_NAT_IP
    print(
        f"EXP070_NETKIT_NO_SNAT={'PASS' if plain_good else 'FAIL'} peer={peer_plain}",
        flush=True,
    )
    return nat_good, plain_good



def setup_routed_veth(with_peer_ips: bool):
    pair(HOST, RV_HOST, STACK, RV_STACK)
    ns(HOST, "ip", "link", "set", RV_HOST, "up")
    ns(STACK, "ip", "link", "set", RV_STACK, "up")
    for name, iface in ((HOST, RV_HOST), (STACK, RV_STACK)):
        ns(name, "sysctl", "-qw", f"net.ipv4.conf.{iface}.rp_filter=0")
    if with_peer_ips:
        ns(HOST, "ip", "addr", "add", f"{RV_HOST_IP}/32", "peer", f"{RV_STACK_IP}/32", "dev", RV_HOST)
        ns(STACK, "ip", "addr", "add", f"{RV_STACK_IP}/32", "peer", f"{RV_HOST_IP}/32", "dev", RV_STACK)


def cleanup_routed_veth():
    ns(HOST, "ip", "link", "del", RV_HOST, check=False)


def routed_veth_flow(port: int, label: str) -> tuple[bool, str | None]:
    ns(LAN, "ip", "route", "replace", f"{REMOTE_IP}/32", "via", HOST_LAN, "dev", L_H)
    server = start_server(REMOTE, REMOTE_IP, port)
    ok = client(LAN, LAN_IP, REMOTE_IP, port, label)
    peer = None
    if ok:
        peer = read_peer(server)
    else:
        if server.poll() is None:
            server.kill(); server.communicate(timeout=1)
    return ok, peer


def phase_routed_veth_dev_only(with_peer_ips: bool) -> bool:
    ns(HOST, "ip", "route", "replace", f"{REMOTE_IP}/32", "dev", RV_HOST, "src", HOST_LAN)
    ns(STACK, "ip", "route", "replace", f"{LAN_IP}/32", "dev", RV_STACK)
    ok, peer = routed_veth_flow(17021 if not with_peer_ips else 17022, "RV-DEV")
    host_neigh = ns(HOST, "ip", "neigh", "show", "dev", RV_HOST, check=False).stdout.strip()
    stack_neigh = ns(STACK, "ip", "neigh", "show", "dev", RV_STACK, check=False).stdout.strip()
    good = ok and peer == LAN_IP
    suffix = "PEER32" if with_peer_ips else "UNNUMBERED"
    print(
        f"EXP070_ROUTED_VETH_DEV_ONLY_{suffix}={'PASS' if good else 'FAIL'} "
        f"peer={peer} host_neigh={host_neigh!r} stack_neigh={stack_neigh!r}",
        flush=True,
    )
    return good


def phase_routed_veth_via_peer() -> bool:
    ns(HOST, "ip", "route", "replace", f"{REMOTE_IP}/32", "via", RV_STACK_IP, "dev", RV_HOST, "src", HOST_LAN)
    ns(STACK, "ip", "route", "replace", f"{LAN_IP}/32", "via", RV_HOST_IP, "dev", RV_STACK)
    ok, peer = routed_veth_flow(17023, "RV-VIA")
    good = ok and peer == LAN_IP
    print(f"EXP070_ROUTED_VETH_VIA_PEER={'PASS' if good else 'FAIL'} peer={peer}", flush=True)
    return good


def phase_routed_veth_proxy_arp(with_peer_ips: bool) -> bool:
    # The host route contract remains device-only. Proxy ARP is enabled only on the
    # opposite endpoint so each side can answer neighbour resolution for routed prefixes
    # that actually live behind it.
    ns(HOST, "sysctl", "-qw", f"net.ipv4.conf.{RV_HOST}.proxy_arp=1")
    ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{RV_STACK}.proxy_arp=1")
    ns(HOST, "ip", "route", "replace", f"{REMOTE_IP}/32", "dev", RV_HOST, "src", HOST_LAN)
    ns(STACK, "ip", "route", "replace", f"{LAN_IP}/32", "dev", RV_STACK)

    ok, peer = routed_veth_flow(17024 if not with_peer_ips else 17025, "RV-PROXY")
    host_neigh = ns(HOST, "ip", "neigh", "show", "dev", RV_HOST, check=False).stdout.strip()
    stack_neigh = ns(STACK, "ip", "neigh", "show", "dev", RV_STACK, check=False).stdout.strip()
    good = ok and peer == LAN_IP
    suffix = "PEER32" if with_peer_ips else "UNNUMBERED"
    print(
        f"EXP070_ROUTED_VETH_PROXY_ARP_{suffix}={'PASS' if good else 'FAIL'} "
        f"peer={peer} host_neigh={host_neigh!r} stack_neigh={stack_neigh!r}",
        flush=True,
    )
    return good

def main():
    require_tools()
    print("EXP070_PREFLIGHT kernel=" + run("uname", "-r").stdout.strip(), flush=True)
    print("EXP070_PREFLIGHT ip=" + run("ip", "-V").stdout.strip(), flush=True)
    try:
        setup_base()

        ipv_ok, ipv_detail = probe_ipvlan_l3s()
        print(f"EXP070_IPVLAN_L3S_SUPPORT={'SUPPORTED' if ipv_ok else 'UNAVAILABLE'} detail={ipv_detail!r}", flush=True)
        ipv_external = ipv_nat = False
        dev_only = via = False
        if ipv_ok:
            setup_ipvlan()
            ipv_external = phase_ipvlan_external_reachability()
            ipv_nat = phase_ipvlan_stack_nat()
            if setup_host_ipvlan_alias():
                dev_only, via = phase_ipvlan_alias_routes()

        nk_ok, nk_detail = probe_netkit()
        print(f"EXP070_NETKIT_SUPPORT={'SUPPORTED' if nk_ok else 'UNAVAILABLE'} detail={nk_detail!r}", flush=True)
        nk_dev = nk_mark = nk_nat = nk_plain = False
        if nk_ok:
            setup_netkit(scrub_none=False)
            nk_dev = phase_netkit_dev_route()
            cleanup_netkit()

            # Recreate with explicit cross-netns metadata preservation.
            ns(HOST, "nft", "delete", "table", "ip", "e70nkh", check=False)
            ns(STACK, "nft", "delete", "table", "ip", "e70nks", check=False)
            setup_netkit(scrub_none=True)
            nk_mark = phase_netkit_mark_survival()
            cleanup_netkit()

            # Final production-shaped candidate: L3 device identity on HOST, Profile/NAT in STACK.
            ns(HOST, "nft", "delete", "table", "ip", "e70nkh", check=False)
            ns(STACK, "nft", "delete", "table", "ip", "e70nks", check=False)
            setup_netkit(scrub_none=False)
            nk_nat, nk_plain = phase_netkit_stack_nat()
            cleanup_netkit()

        rv_plain = rv_peer_dev = rv_via = rv_proxy_plain = rv_proxy_peer = False

        setup_routed_veth(with_peer_ips=False)
        rv_plain = phase_routed_veth_dev_only(with_peer_ips=False)
        cleanup_routed_veth()

        setup_routed_veth(with_peer_ips=True)
        rv_peer_dev = phase_routed_veth_dev_only(with_peer_ips=True)
        rv_via = phase_routed_veth_via_peer()
        cleanup_routed_veth()

        setup_routed_veth(with_peer_ips=False)
        rv_proxy_plain = phase_routed_veth_proxy_arp(with_peer_ips=False)
        cleanup_routed_veth()

        setup_routed_veth(with_peer_ips=True)
        rv_proxy_peer = phase_routed_veth_proxy_arp(with_peer_ips=True)
        cleanup_routed_veth()

        print(
            "EXP070_SUMMARY "
            f"ipvlan_external={ipv_external} ipvlan_stack_nat={ipv_nat} "
            f"ipvlan_dev_only={dev_only} ipvlan_via={via} "
            f"netkit_dev_only={nk_dev} netkit_mark={nk_mark} "
            f"netkit_stack_nat={nk_nat} netkit_no_snat={nk_plain} "
            f"routed_veth_plain={rv_plain} routed_veth_peer_dev={rv_peer_dev} "
            f"routed_veth_via={rv_via} routed_veth_proxy_plain={rv_proxy_plain} "
            f"routed_veth_proxy_peer={rv_proxy_peer}",
            flush=True,
        )
        print("EXP070_RESULT=PASS", flush=True)
        return 0
    except Exception as exc:
        print("EXP070_RESULT=FAIL", flush=True)
        print("EXP070_ERROR=" + repr(exc), flush=True)
        return 1
    finally:
        for name in (REMOTE, LAN, STACK, HOST):
            del_ns(name)


if __name__ == "__main__":
    raise SystemExit(main())
