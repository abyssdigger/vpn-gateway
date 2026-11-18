#!/usr/bin/env python3
"""EXP-063: Profile association handoff for ordinary-side gateway NAT."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time


PID = os.getpid()
STACK = f"vng63s-{PID}"
HOST = f"vng63h-{PID}"
RA = f"vng63a-{PID}"
RB = f"vng63b-{PID}"
LAN = f"vng63l-{PID}"

S_A, A_S = "e63sa", "e63as"
S_B, B_S = "e63sb", "e63bs"
S_H, H_S = "e63sh", "e63hs"
H_L, L_H = "e63hl", "e63lh"

A_TRANSIT_STACK = "172.16.10.1"
A_TRANSIT_REMOTE = "172.16.10.2"
B_TRANSIT_STACK = "172.16.20.1"
B_TRANSIT_REMOTE = "172.16.20.2"
STACK_HOST_IP = "198.18.63.2"
HOST_STACK_IP = "198.18.63.1"
HOST_LAN_IP = "192.0.2.1"
LAN_IP = "192.0.2.2"
REMOTE_A = "10.0.0.2"
REMOTE_B = "10.0.0.3"

STACK_CT_A = "0x6301"
STACK_CT_B = "0x6302"
TRANS_A = "0x63010001"
TRANS_B = "0x63020001"
HOST_CT_A = "0x63a1"
HOST_CT_B = "0x63b1"
RETURN_MARK = "0x6353"

TABLE_A = "6301"
TABLE_B = "6302"
HOST_RETURN_TABLE = "6353"
HOST_POISON_TABLE = "6363"


def run(*args: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        args,
        check=check,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def ns(name: str, *args: str, check: bool = True, input_text: str | None = None):
    return run("ip", "netns", "exec", name, *args, check=check, input_text=input_text)


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


def setup():
    for name in (STACK, HOST, RA, RB, LAN):
        add_ns(name)

    pair(STACK, S_A, RA, A_S)
    pair(STACK, S_B, RB, B_S)
    pair(STACK, S_H, HOST, H_S)
    pair(HOST, H_L, LAN, L_H)

    addr(STACK, S_A, f"{A_TRANSIT_STACK}/30")
    addr(RA, A_S, f"{A_TRANSIT_REMOTE}/30")
    addr(STACK, S_B, f"{B_TRANSIT_STACK}/30")
    addr(RB, B_S, f"{B_TRANSIT_REMOTE}/30")
    addr(STACK, S_H, f"{STACK_HOST_IP}/30")
    addr(HOST, H_S, f"{HOST_STACK_IP}/30")
    addr(HOST, H_L, f"{HOST_LAN_IP}/30")
    addr(LAN, L_H, f"{LAN_IP}/30")

    ns(RA, "ip", "addr", "add", f"{REMOTE_A}/32", "dev", "lo")
    ns(RB, "ip", "addr", "add", f"{REMOTE_B}/32", "dev", "lo")

    ns(RA, "ip", "route", "add", "192.0.2.0/30", "via", A_TRANSIT_STACK, "dev", A_S, "src", REMOTE_A)
    ns(RA, "ip", "route", "add", f"{HOST_STACK_IP}/32", "via", A_TRANSIT_STACK, "dev", A_S, "src", REMOTE_A)
    ns(RB, "ip", "route", "add", "192.0.2.0/30", "via", B_TRANSIT_STACK, "dev", B_S, "src", REMOTE_B)

    ns(LAN, "ip", "route", "add", "10.0.0.0/24", "via", HOST_LAN_IP, "dev", L_H)

    ns(STACK, "ip", "route", "add", "192.0.2.0/30", "via", HOST_STACK_IP, "dev", S_H)
    ns(STACK, "ip", "route", "add", f"{HOST_STACK_IP}/32", "via", HOST_STACK_IP, "dev", S_H)

    ns(STACK, "ip", "route", "add", "10.0.0.0/16", "via", A_TRANSIT_REMOTE, "dev", S_A, "table", TABLE_A)
    ns(STACK, "ip", "route", "add", "10.0.0.0/24", "via", B_TRANSIT_REMOTE, "dev", S_B, "table", TABLE_B)
    ns(STACK, "ip", "rule", "add", "priority", "6301", "fwmark", STACK_CT_A, "lookup", TABLE_A)
    ns(STACK, "ip", "rule", "add", "priority", "6302", "fwmark", STACK_CT_B, "lookup", TABLE_B)

    ns(HOST, "ip", "route", "add", "default", "via", STACK_HOST_IP, "dev", H_S, "table", HOST_RETURN_TABLE)
    ns(HOST, "ip", "rule", "add", "priority", "100", "fwmark", RETURN_MARK, "lookup", HOST_RETURN_TABLE)

    # If the transient association tag survives host prerouting, this route decision kills it.
    ns(HOST, "ip", "route", "add", "blackhole", "default", "table", HOST_POISON_TABLE)
    ns(HOST, "ip", "rule", "add", "priority", "90", "fwmark", TRANS_A, "lookup", HOST_POISON_TABLE)
    ns(HOST, "ip", "rule", "add", "priority", "91", "fwmark", TRANS_B, "lookup", HOST_POISON_TABLE)

    ns(STACK, "sysctl", "-qw", "net.ipv4.ip_forward=1")
    ns(HOST, "sysctl", "-qw", "net.ipv4.ip_forward=1")
    for name, interfaces in (
        (STACK, ("all", "default", S_A, S_B, S_H)),
        (HOST, ("all", "default", H_S, H_L)),
    ):
        for interface in interfaces:
            ns(name, "sysctl", "-qw", f"net.ipv4.conf.{interface}.rp_filter=0")

    stack_nft = f"""
table ip exp063_stack {{
  chain prerouting {{
    type filter hook prerouting priority mangle; policy accept;
    iifname "{S_A}" ip saddr 10.0.0.0/16 ct state new ct mark set {STACK_CT_A}
    iifname "{S_B}" ip saddr 10.0.0.0/24 ct state new ct mark set {STACK_CT_B}
    iifname "{S_H}" ct mark {STACK_CT_A} meta mark set ct mark
    iifname "{S_H}" ct mark {STACK_CT_B} meta mark set ct mark
  }}
  chain postrouting {{
    type filter hook postrouting priority mangle; policy accept;
    oifname "{S_H}" ct mark {STACK_CT_A} counter meta mark set {TRANS_A} comment "exp063-export-a"
    oifname "{S_H}" ct mark {STACK_CT_B} counter meta mark set {TRANS_B} comment "exp063-export-b"
  }}
}}
"""
    ns(STACK, "nft", "-f", "-", input_text=stack_nft)

    host_nft = f"""
table inet exp063_host {{
  chain prerouting {{
    type filter hook prerouting priority mangle; policy accept;
    iifname "{H_S}" meta mark {TRANS_A} counter ct mark set {HOST_CT_A} meta mark set 0 comment "exp063-consume-a"
    iifname "{H_S}" meta mark {TRANS_B} counter ct mark set {HOST_CT_B} meta mark set 0 comment "exp063-consume-b"
    iifname != "{H_S}" ct mark {HOST_CT_A} counter meta mark set {RETURN_MARK} comment "exp063-return-a"
    iifname != "{H_S}" ct mark {HOST_CT_B} counter meta mark set {RETURN_MARK} comment "exp063-return-b"
  }}
  chain output {{
    type route hook output priority mangle; policy accept;
    ct mark {HOST_CT_A} meta mark set {RETURN_MARK}
    ct mark {HOST_CT_B} meta mark set {RETURN_MARK}
  }}
  chain postrouting {{
    type nat hook postrouting priority srcnat; policy accept;
    oifname "{H_L}" ct mark {HOST_CT_A} counter masquerade comment "exp063-profile-a-nat"
  }}
}}
"""
    ns(HOST, "nft", "-f", "-", input_text=host_nft)


SERVER = r"""
import socket,sys
addr=sys.argv[1]; port=int(sys.argv[2]); count=int(sys.argv[3])
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((addr,port)); s.listen(count)
print("READY", flush=True)
for _ in range(count):
    c,p=s.accept(); c.settimeout(5)
    data=c.recv(32)
    print("PEER="+p[0], flush=True)
    c.sendall(b"ACK:"+data)
    c.close()
s.close()
"""

CLIENT = r"""
import socket,sys
src=sys.argv[1]; dst=sys.argv[2]; port=int(sys.argv[3]); payload=sys.argv[4].encode()
s=socket.socket(); s.settimeout(5); s.bind((src,0)); s.connect((dst,port))
s.sendall(payload); data=s.recv(64)
assert data==b"ACK:"+payload, data
print("OK")
s.close()
"""


def start_server(namespace: str, addr_: str, port: int, count: int):
    p=subprocess.Popen(
        ["ip","netns","exec",namespace,"python3","-u","-c",SERVER,addr_,str(port),str(count)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert p.stdout is not None
    if p.stdout.readline().strip() != "READY":
        out,err=p.communicate(timeout=3)
        raise AssertionError((out,err))
    return p


def client(namespace: str, src: str, dst: str, port: int, payload: str):
    r=ns(namespace,"python3","-c",CLIENT,src,dst,str(port),payload,check=False)
    if r.returncode != 0 or "OK" not in r.stdout:
        print("EXP063_CLIENT_STDOUT=" + repr(r.stdout), flush=True)
        print("EXP063_CLIENT_STDERR=" + repr(r.stderr), flush=True)
        dump_diagnostics()
        raise AssertionError(f"client failed rc={r.returncode}")


def read_peer(server) -> str:
    assert server.stdout is not None
    line=server.stdout.readline().strip()
    if not line.startswith("PEER="):
        raise AssertionError(line)
    return line.split("=",1)[1]


def rule_counter(namespace: str, family: str, table: str, comment: str) -> int:
    doc=json.loads(ns(namespace,"nft","-j","list","table",family,table).stdout)
    for row in doc.get("nftables",[]):
        rule=row.get("rule") if isinstance(row,dict) else None
        if not isinstance(rule,dict) or rule.get("comment")!=comment:
            continue
        for expr in rule.get("expr",[]):
            counter=expr.get("counter") if isinstance(expr,dict) else None
            if isinstance(counter,dict):
                return int(counter.get("packets",0))
    return -1


def dump_diagnostics():
    for namespace, family, table, comment in (
        (STACK,"ip","exp063_stack","exp063-export-a"),
        (HOST,"inet","exp063_host","exp063-host-ingress"),
        (HOST,"inet","exp063_host","exp063-host-zero-tag"),
        (HOST,"inet","exp063_host","exp063-consume-a"),
        (HOST,"inet","exp063_host","exp063-profile-a-nat"),
        (HOST,"inet","exp063_host","exp063-return-a"),
    ):
        try:
            print(
                "EXP063_DIAG_COUNTER "
                + comment
                + "="
                + str(rule_counter(namespace,family,table,comment)),
                flush=True,
            )
        except Exception as exc:
            print("EXP063_DIAG_COUNTER_ERROR " + comment + "=" + repr(exc), flush=True)
    for namespace, dst, mark in (
        (HOST,LAN_IP,TRANS_A),
        (HOST,LAN_IP,"0"),
        (HOST,REMOTE_A,RETURN_MARK),
        (STACK,REMOTE_A,STACK_CT_A),
    ):
        try:
            result=ns(namespace,"ip","-4","route","get",dst,"mark",mark,check=False)
            print(
                f"EXP063_DIAG_ROUTE ns={namespace} dst={dst} mark={mark} "
                f"rc={result.returncode} out={result.stdout!r} err={result.stderr!r}",
                flush=True,
            )
        except Exception as exc:
            print("EXP063_DIAG_ROUTE_ERROR=" + repr(exc), flush=True)


def nat_counter() -> int:
    doc=json.loads(ns(HOST,"nft","-j","list","table","inet","exp063_host").stdout)
    for row in doc.get("nftables",[]):
        rule=row.get("rule") if isinstance(row,dict) else None
        if not isinstance(rule,dict) or rule.get("comment")!="exp063-profile-a-nat":
            continue
        for expr in rule.get("expr",[]):
            counter=expr.get("counter") if isinstance(expr,dict) else None
            if isinstance(counter,dict):
                return int(counter.get("packets",0))
    raise AssertionError("NAT counter not found")


def main():
    servers=[]
    try:
        setup()
        time.sleep(0.1)

        lan_server=start_server(LAN,LAN_IP,18631,3)
        servers.append(lan_server)

        before=nat_counter()
        client(RA,REMOTE_A,LAN_IP,18631,"A")
        peer_a=read_peer(lan_server)
        after_a=nat_counter()
        if peer_a != HOST_LAN_IP or after_a <= before:
            raise AssertionError((peer_a,before,after_a))
        print("EXP063_PROFILE_A_ASSOCIATION=PASS")
        print("EXP063_PROFILE_A_GATEWAY_NAT=PASS")
        print("EXP063_TRANSIENT_TAG_CLEARED_BEFORE_ROUTING=PASS")
        print("EXP063_REVERSE_RETURN=PASS")

        client(RB,REMOTE_B,LAN_IP,18631,"B")
        peer_b=read_peer(lan_server)
        after_b=nat_counter()
        if peer_b != REMOTE_B or after_b != after_a:
            raise AssertionError((peer_b,after_a,after_b))
        print("EXP063_PROFILE_B_NO_GATEWAY_NAT=PASS")

        # Unrelated host-origin traffic must not enter the Profile NAT owner.
        client(HOST,HOST_LAN_IP,LAN_IP,18631,"H")
        peer_h=read_peer(lan_server)
        after_h=nat_counter()
        if peer_h != HOST_LAN_IP or after_h != after_b:
            raise AssertionError((peer_h,after_b,after_h))
        print("EXP063_UNRELATED_HOST_UNTOUCHED=PASS")

        out,err=lan_server.communicate(timeout=3)
        if lan_server.returncode != 0:
            raise AssertionError(err)
        servers.remove(lan_server)

        host_server=start_server(HOST,HOST_STACK_IP,18632,1)
        servers.append(host_server)
        before_local=nat_counter()
        client(RA,REMOTE_A,HOST_STACK_IP,18632,"LOCAL")
        peer_local=read_peer(host_server)
        after_local=nat_counter()
        if peer_local != REMOTE_A or after_local != before_local:
            raise AssertionError((peer_local,before_local,after_local))
        print("EXP063_HOST_LOCAL_NOT_GATEWAY_NATED=PASS")
        out,err=host_server.communicate(timeout=3)
        if host_server.returncode != 0:
            raise AssertionError(err)
        servers.remove(host_server)

        print("EXP063_RESULT=PASS")
        return 0
    finally:
        for p in servers:
            if p.poll() is None:
                p.kill()
            try:
                p.communicate(timeout=1)
            except Exception:
                pass
        for name in (LAN,RB,RA,HOST,STACK):
            del_ns(name)


if __name__ == "__main__":
    raise SystemExit(main())
