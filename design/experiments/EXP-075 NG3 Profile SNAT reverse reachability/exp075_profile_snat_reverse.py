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
STACK_SERVICE="198.19.255.2"
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
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.bind((addr,port)); print("READY",flush=True)
data,peer=s.recvfrom(4096)
print("PEER="+peer[0],flush=True)
s.sendto(b"ACK:"+data,peer)
s.close()
"""

CLIENT=r"""
import socket,sys
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(3)
s.sendto(b"probe",(sys.argv[1],int(sys.argv[2])))
try:
    data,peer=s.recvfrom(4096)
    print("DATA="+data.decode(),flush=True)
except Exception as exc:
    print("RECV_ERROR="+type(exc).__name__+":"+str(exc),flush=True)
    raise
finally:
    s.close()
"""


def start_server(port):
    p=subprocess.Popen(
        ["ip","netns","exec",LAN,"python3","-u","-c",SERVER,LAN_IP,str(port)],
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
    ns(STACK,"ip","addr","add",f"{STACK_SERVICE}/32","dev",BS)
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
    ns(HOST,"ip","route","add",f"{STACK_SERVICE}/32","dev",BH)
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

        server=start_server(PORT)
        client=ns(
            REMOTE,"python3","-c",CLIENT,LAN_IP,str(PORT),check=False
        )
        out,err=server.communicate(timeout=6)
        server=None
        combined=out+err
        assert f"PEER={SNAT_IP}" in combined,(combined,client.stdout,client.stderr)
        print("EXP075_FORWARD_SNAT_IDENTITY=PASS",flush=True)

        # Current architecture is expected to fail here: HOST ARPs for the
        # translated identity itself, while STACK owns no route/address for it.
        assert client.returncode!=0 and "DATA=ACK:probe" not in client.stdout,(
            "baseline unexpectedly returned",
            client.stdout,
            client.stderr,
        )
        neigh=ns(HOST,"ip","neigh","show","dev",BH,check=False).stdout
        print("EXP075_BASELINE_REPLY_FAILED=PASS",flush=True)
        print("EXP075_BASELINE_HOST_NEIGH="+repr(neigh),flush=True)

        # Candidate: keep remote prefixes device-only, but send only the SNAT
        # identity through the already-owned stack service /32 as an onlink
        # next hop. No extra stack-local identity address/proxy-neighbour exists.
        table=str(NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION.table)
        ns(
            HOST,"ip","route","replace","table",table,f"{SNAT_IP}/32",
            "via",STACK_SERVICE,"dev",BH,"onlink",
            "proto",str(NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION.route_protocol),
        )
        ns(HOST,"ip","neigh","flush","dev",BH,check=False)
        candidate=ns(HOST,"ip","-j","-4","route","get",SNAT_IP).stdout
        assert STACK_SERVICE in candidate and BH in candidate,candidate
        print("EXP075_GATEWAY_ROUTE_SELECTED=PASS",flush=True)

        second_port=PORT+1
        server=start_server(second_port)
        client=ns(
            REMOTE,"python3","-c",CLIENT,LAN_IP,str(second_port),check=False
        )
        out,err=server.communicate(timeout=6)
        server=None
        combined=out+err
        assert f"PEER={SNAT_IP}" in combined,(combined,client.stdout,client.stderr)
        assert client.returncode==0 and "DATA=ACK:probe" in client.stdout,(
            client.stdout,client.stderr
        )
        print("EXP075_GATEWAY_REVERSE_SNAT_REPLY=PASS",flush=True)
        print("EXP075_RESULT=PASS baseline=device-only-failed candidate=stack-service-gateway",flush=True)
        return 0
    finally:
        if server is not None and server.poll() is None:
            server.kill()
            try: server.communicate(timeout=1)
            except Exception: pass
        for name in (REMOTE,LAN,STACK,HOST): del_ns(name)


if __name__=="__main__":
    raise SystemExit(main())
