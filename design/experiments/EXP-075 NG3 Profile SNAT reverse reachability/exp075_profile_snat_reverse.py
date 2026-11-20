#!/usr/bin/env python3
"""EXP-075: reverse reachability of a stack-side Profile SNAT identity."""

from __future__ import annotations

import os
import subprocess
from ipaddress import IPv4Address, IPv4Network

from rou.domain import Direction
from rou.host_managed_routing import (
    HostManagedRoutingProfile,
    build_host_managed_routing_plan,
)
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_host_managed_routing import build_linux_host_managed_routing_desired
from rou.linux_host_managed_routing_backend import (
    LinuxHostManagedRoutingBackend,
    converge_host_managed_routing_once,
)
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_payload_nat import LinuxPayloadNatBackend
from rou.linux_policy_platform import NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION
from rou.payload_nat_desired import PayloadProfileSnatSpec


PID=os.getpid()
HOST=f"v75h-{PID}"; STACK=f"v75s-{PID}"; LAN=f"v75l-{PID}"; REMOTE=f"v75r-{PID}"
BH="vpng0"; BS="stack0"; HL="e75hl"; LH="e75lh"; SV="e75sv"; VR="e75vr"
HOST_LAN="10.75.0.1"; LAN_IP="10.75.0.2"
STACK_VPN="203.0.113.1"; REMOTE_IP="203.0.113.2"
SNAT_IP="198.19.255.10"
MARK=0x10000000
PORT=18750


def run(*args,input_text=None,check=True):
    return subprocess.run(
        args,input=input_text,text=True,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,check=check,
    )


def ns(name,*args,input_text=None,check=True):
    return run("ip","netns","exec",name,*args,input_text=input_text,check=check)


def add_ns(name):
    run("ip","netns","add",name)
    ns(name,"ip","link","set","lo","up")


def del_ns(name):
    run("ip","netns","del",name,check=False)


def pair(a,b,na,nb):
    run("ip","link","add",a,"type","veth","peer","name",b)
    run("ip","link","set",a,"netns",na)
    run("ip","link","set",b,"netns",nb)


SERVER=r"""
import socket,sys
addr=sys.argv[1]; port=int(sys.argv[2])
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((addr,port)); s.listen(1); print("READY",flush=True)
c,peer=s.accept(); c.settimeout(3)
print("PEER="+peer[0],flush=True)
data=c.recv(4096)
try:
    c.sendall(b"ACK:"+data)
except OSError as exc:
    print("SEND_ERROR="+repr(exc),flush=True)
c.close(); s.close()
"""

CLIENT=r"""
import socket,sys
s=socket.socket(); s.settimeout(3)
s.connect((sys.argv[1],int(sys.argv[2])))
s.sendall(b"probe")
try:
    data=s.recv(4096)
    print("DATA="+data.decode(),flush=True)
except Exception as exc:
    print("RECV_ERROR="+type(exc).__name__+":"+str(exc),flush=True)
    raise
finally:
    s.close()
"""


def start_server():
    p=subprocess.Popen(
        ["ip","netns","exec",LAN,"python3","-u","-c",SERVER,LAN_IP,str(PORT)],
        text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    )
    assert p.stdout is not None
    first=p.stdout.readline().strip()
    assert first=="READY",(first,p.stderr.read() if p.stderr else "")
    return p


def setup():
    for name in (HOST,STACK,LAN,REMOTE): add_ns(name)
    pair(BH,BS,HOST,STACK)
    pair(HL,LH,HOST,LAN)
    pair(SV,VR,STACK,REMOTE)

    ns(HOST,"ip","addr","add",f"{HOST_LAN}/24","dev",HL)
    ns(LAN,"ip","addr","add",f"{LAN_IP}/24","dev",LH)
    ns(STACK,"ip","addr","add",f"{STACK_VPN}/30","dev",SV)
    ns(REMOTE,"ip","addr","add",f"{REMOTE_IP}/30","dev",VR)
    for name,ifs in (
        (HOST,(BH,HL)),(STACK,(BS,SV)),(LAN,(LH,)),(REMOTE,(VR,))
    ):
        for iface in ifs: ns(name,"ip","link","set",iface,"up")

    for name in (HOST,STACK):
        ns(name,"sysctl","-qw","net.ipv4.ip_forward=1")
        ns(name,"sysctl","-qw","net.ipv4.conf.all.rp_filter=0")
        ns(name,"sysctl","-qw","net.ipv4.conf.default.rp_filter=0")
    ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{BH}.proxy_arp=1")
    ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{BS}.proxy_arp=1")
    ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{BH}.rp_filter=0")
    ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{BS}.rp_filter=0")

    # Current routed-L3 contract: addressless HOST endpoint, STACK default through it.
    ns(STACK,"ip","route","add","default","dev",BS)
    ns(LAN,"ip","route","add","default","via",HOST_LAN)
    ns(REMOTE,"ip","route","add",f"{LAN_IP}/32","via",STACK_VPN,"dev",VR)

    plan=build_host_managed_routing_plan((
        HostManagedRoutingProfile(
            profile_id="snat",
            direction=Direction.INBOUND,
            destinations=(IPv4Network("203.0.113.0/30"),),
            effective_snat_address=IPv4Address(SNAT_IP),
        ),
    ))
    desired=build_linux_host_managed_routing_desired(
        plan,
        host_interface=BH,
        allocation=NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
    )
    backend=LinuxHostManagedRoutingBackend(
        SubprocessCommandRunner(),
        NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
        network_namespace=HOST,
    )
    assert converge_host_managed_routing_once(backend,desired).exact

    # Minimal managed policy: classify original VPN source, allow forwarding, then
    # materialize the real Profile SNAT rule through the production Linux Driver.
    ns(
        STACK,"nft","-f","-",input_text=(
            'table ip vpn_gate_assoc {\n'
            ' chain prerouting { type filter hook prerouting priority mangle; policy accept;\n'
            f'  meta iif "{SV}" ip saddr {REMOTE_IP} ct state new ct mark set {hex(MARK)}\n'
            ' }\n'
            '}\n'
            'table ip vpn_gate {\n'
            ' comment "vpn-gate:ng3:owner-v1"\n'
            ' chain stack_input { type filter hook input priority 0; policy drop; '
            'comment "vpn-gate:ng3:stack-input-v1"; }\n'
            ' chain payload_forward { type filter hook forward priority 0; policy accept; '
            'comment "vpn-gate:ng3:payload-forward-v1"; }\n'
            ' chain stack_output { type filter hook output priority 0; policy drop; '
            'comment "vpn-gate:ng3:stack-output-v1"; }\n'
            ' chain payload_postrouting { type nat hook postrouting priority 100; policy accept; '
            'comment "vpn-gate:ng3:payload-postrouting-v1"; }\n'
            '}\n'
        )
    )
    inner_ifindex=int(ns(STACK,"cat",f"/sys/class/net/{BS}/ifindex").stdout.strip())
    LinuxPayloadNatBackend(
        SubprocessNftRunner(),STACK
    ).add_nat_rule(
        PayloadProfileSnatSpec(
            profile_id="snat",
            mark=MARK,
            egress=__import__("rou.interface_identity",fromlist=["InterfaceIdentity"]).InterfaceIdentity(BS,inner_ifindex),
            source_address=IPv4Address(SNAT_IP),
        )
    )


def main():
    server=None
    if os.geteuid()!=0:
        print("EXP075_RESULT=SKIP root required")
        return 77
    try:
        setup()
        route=ns(HOST,"ip","-j","-4","route","get",SNAT_IP).stdout
        assert BH in route and '"gateway"' not in route,route
        print("EXP075_HOST_SNAT_32_DEVICE_ROUTE=PASS",flush=True)

        server=start_server()
        client=ns(
            REMOTE,"python3","-c",CLIENT,LAN_IP,str(PORT),check=False
        )
        out,err=server.communicate(timeout=6)
        server=None
        combined=out+err
        assert f"PEER={SNAT_IP}" in combined,(combined,client.stdout,client.stderr)
        print("EXP075_FORWARD_SNAT_IDENTITY=PASS",flush=True)

        if client.returncode!=0 or "DATA=ACK:probe" not in client.stdout:
            neigh=ns(HOST,"ip","neigh","show","dev",BH,check=False).stdout
            stack_routes=ns(STACK,"ip","-4","route","show","table","main").stdout
            print("EXP075_REPLY_FAILED=YES",flush=True)
            print("EXP075_HOST_NEIGH="+repr(neigh),flush=True)
            print("EXP075_STACK_MAIN="+repr(stack_routes),flush=True)
            raise AssertionError(
                "reply to SNAT identity did not return across current routed boundary"
            )

        print("EXP075_REVERSE_SNAT_REPLY=PASS",flush=True)
        print("EXP075_RESULT=PASS",flush=True)
        return 0
    finally:
        if server is not None and server.poll() is None:
            server.kill()
            try: server.communicate(timeout=1)
            except Exception: pass
        for name in (REMOTE,LAN,STACK,HOST): del_ns(name)


if __name__=="__main__":
    raise SystemExit(main())
