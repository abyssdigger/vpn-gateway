#!/usr/bin/env python3
"""EXP-064: fixed host-boundary behavior lanes for remote-initiated flows."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time


PID=os.getpid()
STACK=f"vng64s-{PID}"
HOST=f"vng64h-{PID}"
LAN=f"vng64l-{PID}"
REMOTES=[f"vng64r{i}-{PID}" for i in range(4)]

PATH_STACK=[f"e64s{i}" for i in range(4)]
PATH_REMOTE=[f"e64r{i}" for i in range(4)]
LAN_H="e64hl"; LAN_L="e64lh"

# behavior order: S0, S1, R0, R1
LANE_STACK=[f"e64bs{i}" for i in range(4)]
LANE_HOST=[f"e64bh{i}" for i in range(4)]

REMOTE_IP=["10.0.0.2","10.0.0.3","10.0.0.4","10.0.0.5"]
REMOTE_PREFIX=["10.0.0.0/16","10.0.0.0/24","10.0.0.0/25","10.0.0.0/26"]
PATH_STACK_IP=["172.16.10.1","172.16.20.1","172.16.30.1","172.16.40.1"]
PATH_REMOTE_IP=["172.16.10.2","172.16.20.2","172.16.30.2","172.16.40.2"]

LAN_HOST_IP="192.0.2.1"
LAN_IP="192.0.2.2"

LANE_NET=[
    ("198.18.64.1","198.18.64.2"),
    ("198.18.64.5","198.18.64.6"),
    ("198.18.64.9","198.18.64.10"),
    ("198.18.64.13","198.18.64.14"),
]
# tuple is host, stack
PROFILE_MARK=[0x6401,0x6402,0x6403,0x6404]
PROFILE_TABLE=[6401,6402,6403,6404]
HOST_CLASS=[0x6410,0x6420,0x6430,0x6440]
RETURN_MARK=0x6453
RETURN_TABLE=6453

STATEFUL={0,1}
NAT={1,3}
ROUTE_RETURN={2,3}


def run(*args:str,check:bool=True,input_text:str|None=None):
    return subprocess.run(
        args,check=check,input=input_text,text=True,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    )


def ns(name:str,*args:str,check:bool=True,input_text:str|None=None):
    return run("ip","netns","exec",name,*args,check=check,input_text=input_text)


def add_ns(name:str):
    run("ip","netns","add",name)
    ns(name,"ip","link","set","lo","up")


def del_ns(name:str):
    run("ip","netns","del",name,check=False)


def pair(a_ns:str,a_if:str,b_ns:str,b_if:str):
    run("ip","link","add",a_if,"type","veth","peer","name",b_if)
    run("ip","link","set",a_if,"netns",a_ns)
    run("ip","link","set",b_if,"netns",b_ns)


def addr(name:str,interface:str,cidr:str):
    ns(name,"ip","addr","add",cidr,"dev",interface)
    ns(name,"ip","link","set",interface,"up")


def setup():
    for name in [STACK,HOST,LAN,*REMOTES]:
        add_ns(name)

    for i in range(4):
        pair(STACK,PATH_STACK[i],REMOTES[i],PATH_REMOTE[i])
        addr(STACK,PATH_STACK[i],PATH_STACK_IP[i]+"/30")
        addr(REMOTES[i],PATH_REMOTE[i],PATH_REMOTE_IP[i]+"/30")
        ns(REMOTES[i],"ip","addr","add",REMOTE_IP[i]+"/32","dev","lo")
        ns(
            REMOTES[i],"ip","route","add","192.0.2.0/30",
            "via",PATH_STACK_IP[i],"dev",PATH_REMOTE[i],"src",REMOTE_IP[i]
        )

    for i in range(4):
        pair(STACK,LANE_STACK[i],HOST,LANE_HOST[i])
        host_ip,stack_ip=LANE_NET[i]
        addr(HOST,LANE_HOST[i],host_ip+"/30")
        addr(STACK,LANE_STACK[i],stack_ip+"/30")

    # Host-local evidence target is one VPN-GATE host-boundary address.
    ns(
        REMOTES[1],"ip","route","add",LANE_NET[1][0]+"/32",
        "via",PATH_STACK_IP[1],"dev",PATH_REMOTE[1],"src",REMOTE_IP[1]
    )

    pair(HOST,LAN_H,LAN,LAN_L)
    addr(HOST,LAN_H,LAN_HOST_IP+"/30")
    addr(LAN,LAN_L,LAN_IP+"/30")
    ns(LAN,"ip","route","add","10.0.0.0/24","via",LAN_HOST_IP,"dev",LAN_L)

    # Host-local reply generation needs an ordinary initial route before the
    # type-route OUTPUT owner can reroute stateful replies. Deliberately point
    # that ordinary default away from the managed stack, as in EXP-053.
    ns(HOST,"ip","route","add","default","via",LAN_IP,"dev",LAN_H)

    ns(STACK,"sysctl","-qw","net.ipv4.ip_forward=1")
    ns(HOST,"sysctl","-qw","net.ipv4.ip_forward=1")
    for name,interfaces in (
        (STACK,("all","default",*PATH_STACK,*LANE_STACK)),
        (HOST,("all","default",*LANE_HOST,LAN_H)),
    ):
        for interface in interfaces:
            ns(name,"sysctl","-qw",f"net.ipv4.conf.{interface}.rp_filter=0")

    # Each Profile table owns both its remote route and its ordinary-side behavior lane.
    for i in range(4):
        host_ip,_stack_ip=LANE_NET[i]
        ns(
            STACK,"ip","route","add",REMOTE_PREFIX[i],
            "via",PATH_REMOTE_IP[i],"dev",PATH_STACK[i],
            "table",str(PROFILE_TABLE[i])
        )
        ns(
            STACK,"ip","route","add","default",
            "via",host_ip,"dev",LANE_STACK[i],
            "table",str(PROFILE_TABLE[i])
        )
        ns(
            STACK,"ip","rule","add","priority",str(6400+i),
            "fwmark",hex(PROFILE_MARK[i]),"lookup",str(PROFILE_TABLE[i])
        )

    # Stateful host return uses one common lane (S0) and does not need a remote main route.
    _host0,stack0=LANE_NET[0]
    ns(
        HOST,"ip","route","add","default",
        "via",stack0,"dev",LANE_HOST[0],"table",str(RETURN_TABLE)
    )
    ns(
        HOST,"ip","rule","add","priority","100",
        "fwmark",hex(RETURN_MARK),"lookup",str(RETURN_TABLE)
    )

    # Route-return classes deliberately use ordinary destination routing.
    for i in sorted(ROUTE_RETURN):
        _host0,stack0=LANE_NET[0]
        ns(
            HOST,"ip","route","add",REMOTE_IP[i]+"/32",
            "via",stack0,"dev",LANE_HOST[0]
        )

    # Stack Profile association: actual ingress decides Profile despite overlapping sources.
    stack_lines=[
        "table ip exp064_stack {",
        "  chain prerouting {",
        "    type filter hook prerouting priority mangle; policy accept;",
    ]
    for i in range(4):
        stack_lines.append(
            f'    iifname "{PATH_STACK[i]}" ip saddr {REMOTE_PREFIX[i]} '
            f'ct state new ct mark set {hex(PROFILE_MARK[i])}'
        )
        stack_lines.append(
            f'    ct mark {hex(PROFILE_MARK[i])} counter meta mark set ct mark '
            f'comment "exp064-stack-restore-{i}"'
        )
    stack_lines.extend(["  }","}",""])
    ns(STACK,"nft","-f","-",input_text="\n".join(stack_lines))

    host_lines=[
        "table inet exp064_host {",
        "  chain prerouting {",
        "    type filter hook prerouting priority mangle; policy accept;",
    ]
    for i in range(4):
        host_lines.append(
            f'    iifname "{LANE_HOST[i]}" ct state new '
            f'ct mark set {hex(HOST_CLASS[i])} '
            f'counter comment "exp064-class-{i}"'
        )
    for i in sorted(STATEFUL):
        host_lines.append(
            f'    iifname "{LAN_H}" ct mark {hex(HOST_CLASS[i])} '
            f'meta mark set {hex(RETURN_MARK)} '
            f'counter comment "exp064-return-{i}"'
        )
    host_lines.extend([
        "  }",
        "  chain output {",
        "    type route hook output priority mangle; policy accept;",
    ])
    for i in sorted(STATEFUL):
        host_lines.append(
            f'    ct mark {hex(HOST_CLASS[i])} counter meta mark set {hex(RETURN_MARK)} '
            f'comment "exp064-output-return-{i}"'
        )
    host_lines.extend([
        "  }",
        "  chain postrouting {",
        "    type nat hook postrouting priority srcnat; policy accept;",
    ])
    for i in sorted(NAT):
        host_lines.append(
            f'    oifname "{LAN_H}" ct mark {hex(HOST_CLASS[i])} '
            f'counter masquerade comment "exp064-nat-{i}"'
        )
    host_lines.extend(["  }","}",""])
    ns(HOST,"nft","-f","-",input_text="\n".join(host_lines))


SERVER=r"""
import socket,sys
addr=sys.argv[1]; port=int(sys.argv[2]); count=int(sys.argv[3])
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((addr,port)); s.listen(count)
print("READY",flush=True)
for _ in range(count):
    c,p=s.accept(); c.settimeout(5)
    data=c.recv(64)
    print("PEER="+p[0],flush=True)
    c.sendall(b"ACK:"+data)
    c.close()
s.close()
"""

CLIENT=r"""
import socket,sys
src=sys.argv[1]; dst=sys.argv[2]; port=int(sys.argv[3]); data=sys.argv[4].encode()
s=socket.socket(); s.settimeout(5); s.bind((src,0)); s.connect((dst,port))
s.sendall(data); reply=s.recv(128)
assert reply==b"ACK:"+data,reply
print("OK")
s.close()
"""


def start_server(namespace:str,address:str,port:int,count:int):
    p=subprocess.Popen(
        ["ip","netns","exec",namespace,"python3","-u","-c",SERVER,address,str(port),str(count)],
        text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    )
    assert p.stdout is not None
    if p.stdout.readline().strip()!="READY":
        out,err=p.communicate(timeout=3)
        raise AssertionError((out,err))
    return p


def do_client(i:int,dst:str,port:int,payload:str):
    r=ns(
        REMOTES[i],"python3","-c",CLIENT,
        REMOTE_IP[i],dst,str(port),payload,check=False
    )
    if r.returncode!=0 or "OK" not in r.stdout:
        raise AssertionError(f"client {i} failed: {r.stdout!r} {r.stderr!r}")


def do_client_diagnostic(i:int,dst:str,port:int,payload:str):
    r=ns(
        REMOTES[i],"python3","-c",CLIENT,
        REMOTE_IP[i],dst,str(port),payload,check=False
    )
    if r.returncode!=0 or "OK" not in r.stdout:
        print("EXP064_LOCAL_CLIENT_STDERR="+repr(r.stderr),flush=True)
        for label,value in (
            ("host-classify",counter(f"exp064-class-{i}")),
            ("host-output-return",counter(f"exp064-output-return-{i}")),
            ("stack-profile-restore",table_counter(STACK,"ip","exp064_stack",f"exp064-stack-restore-{i}")),
        ):
            print(f"EXP064_LOCAL_DIAG {label}={value}",flush=True)
        route=ns(HOST,"ip","-4","route","get",REMOTE_IP[i],"mark",hex(RETURN_MARK),check=False)
        print("EXP064_LOCAL_DIAG host-return-route="+repr(route.stdout)+repr(route.stderr),flush=True)
        raise AssertionError(f"local client {i} failed")


def peer(server)->str:
    assert server.stdout is not None
    line=server.stdout.readline().strip()
    if not line.startswith("PEER="):
        raise AssertionError(line)
    return line.split("=",1)[1]


def table_counter(namespace:str,family:str,table:str,comment:str)->int:
    doc=json.loads(ns(namespace,"nft","-j","list","table",family,table).stdout)
    for row in doc.get("nftables",[]):
        rule=row.get("rule") if isinstance(row,dict) else None
        if not isinstance(rule,dict) or rule.get("comment")!=comment:
            continue
        for expr in rule.get("expr",[]):
            value=expr.get("counter") if isinstance(expr,dict) else None
            if isinstance(value,dict):
                return int(value.get("packets",0))
    return 0


def counter(comment:str)->int:
    return table_counter(HOST,"inet","exp064_host",comment)


def main():
    servers=[]
    try:
        setup()
        time.sleep(0.1)
        lan=start_server(LAN,LAN_IP,18641,5)
        servers.append(lan)

        expected_peer=[
            REMOTE_IP[0],
            LAN_HOST_IP,
            REMOTE_IP[2],
            LAN_HOST_IP,
        ]
        markers=[
            "EXP064_S0_STATEFUL_NO_NAT=PASS",
            "EXP064_S1_STATEFUL_NAT=PASS",
            "EXP064_R0_ROUTE_NO_NAT=PASS",
            "EXP064_R1_ROUTE_NAT=PASS",
        ]
        for i in range(4):
            do_client(i,LAN_IP,18641,f"P{i}")
            observed=peer(lan)
            if observed!=expected_peer[i]:
                raise AssertionError((i,observed,expected_peer[i]))
            print(markers[i])

        # All four completed end-to-end; the stack-side conntrack association therefore
        # returned each reply through its original actual Profile path.
        print("EXP064_STACK_RETURN_AFFINITY=PASS")

        before=sum(counter(f"exp064-nat-{i}") for i in NAT)
        r=ns(HOST,"python3","-c",CLIENT,LAN_HOST_IP,LAN_IP,"18641","HOST",check=False)
        if r.returncode!=0:
            raise AssertionError(r.stderr)
        observed=peer(lan)
        after=sum(counter(f"exp064-nat-{i}") for i in NAT)
        if observed!=LAN_HOST_IP or after!=before:
            raise AssertionError((observed,before,after))
        print("EXP064_UNRELATED_HOST_UNTOUCHED=PASS")

        out,err=lan.communicate(timeout=3)
        if lan.returncode!=0:
            raise AssertionError(err)
        servers.remove(lan)

        # Host-local destination for NAT-enabled stateful class: no gateway NAT applies.
        host_local=start_server(HOST,LANE_NET[1][0],18642,1)
        servers.append(host_local)
        before_local=counter("exp064-nat-1")
        do_client_diagnostic(1,LANE_NET[1][0],18642,"LOCAL")
        observed=peer(host_local)
        after_local=counter("exp064-nat-1")
        if observed!=REMOTE_IP[1] or after_local!=before_local:
            raise AssertionError((observed,before_local,after_local))
        print("EXP064_HOST_LOCAL_NOT_NATED=PASS")
        out,err=host_local.communicate(timeout=3)
        if host_local.returncode!=0:
            raise AssertionError(err)
        servers.remove(host_local)

        print("EXP064_RESULT=PASS")
        return 0
    finally:
        for p in servers:
            if p.poll() is None:
                p.kill()
            try:
                p.communicate(timeout=1)
            except Exception:
                pass
        for name in [LAN,*reversed(REMOTES),HOST,STACK]:
            del_ns(name)


if __name__=="__main__":
    raise SystemExit(main())
