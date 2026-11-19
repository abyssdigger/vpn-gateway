#!/usr/bin/env python3
"""EXP-073: stateful host return over routed managed-L3 endpoint."""

from __future__ import annotations

import os
import subprocess
from ipaddress import IPv4Network

from rou.domain import Direction
from rou.host_boundary_policy import HostBoundaryProfileIntent, build_host_boundary_policy
from rou.host_boundary_route_convergence import prepare_host_boundary_route_dependencies_once
from rou.linux_host_boundary_policy import build_linux_host_boundary_desired
from rou.linux_host_boundary_routes import LinuxHostBoundaryRouteBackend
from rou.linux_host_return_nft import LinuxHostReturnNftBackend, converge_host_return_nft_once
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_policy_platform import NG3_HOST_BOUNDARY_LINUX_ALLOCATION

PID=os.getpid()
HOST=f"v73h-{PID}"; STACK=f"v73s-{PID}"; REMOTE=f"v73r-{PID}"; LAN=f"v73l-{PID}"
H_STACK="vpng0"; S_HOST="stack0"; S_REMOTE="e73sr"; R_STACK="e73rs"; H_LAN="e73hl"; L_HOST="e73lh"
STACK_SERVICE="198.19.255.2"; HOST_LOCAL="198.19.255.1"
STACK_REMOTE="203.0.113.1"; REMOTE_IP="203.0.113.2"
HOST_LAN="10.0.0.1"; LAN_IP="10.0.0.2"


def run(*args, input_text=None, check=True):
    return subprocess.run(args,input=input_text,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check)

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

def setup():
    for name in (HOST,STACK,REMOTE,LAN): add_ns(name)
    pair(H_STACK,S_HOST,HOST,STACK)
    pair(S_REMOTE,R_STACK,STACK,REMOTE)
    pair(H_LAN,L_HOST,HOST,LAN)

    ns(STACK,"ip","addr","add",f"{STACK_SERVICE}/32","dev",S_HOST)
    ns(STACK,"ip","addr","add",f"{STACK_REMOTE}/24","dev",S_REMOTE)
    ns(REMOTE,"ip","addr","add",f"{REMOTE_IP}/24","dev",R_STACK)
    ns(HOST,"ip","addr","add",f"{HOST_LAN}/24","dev",H_LAN)
    ns(HOST,"ip","addr","add",f"{HOST_LOCAL}/32","dev","lo")
    ns(LAN,"ip","addr","add",f"{LAN_IP}/24","dev",L_HOST)

    for name,ifs in ((HOST,(H_STACK,H_LAN)),(STACK,(S_HOST,S_REMOTE)),(REMOTE,(R_STACK,)),(LAN,(L_HOST,))):
        for iface in ifs: ns(name,"ip","link","set",iface,"up")

    for name in (HOST,STACK):
        ns(name,"sysctl","-qw","net.ipv4.ip_forward=1")
        ns(name,"sysctl","-qw","net.ipv4.conf.all.rp_filter=0")
        ns(name,"sysctl","-qw","net.ipv4.conf.default.rp_filter=0")
    ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{H_STACK}.rp_filter=0")
    ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{S_HOST}.rp_filter=0")
    ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{H_STACK}.proxy_arp=1")
    ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{S_HOST}.proxy_arp=1")

    ns(STACK,"ip","route","replace","default","dev",S_HOST)
    ns(HOST,"ip","route","replace",f"{STACK_SERVICE}/32","dev",H_STACK)
    ns(REMOTE,"ip","route","replace","default","via",STACK_REMOTE,"dev",R_STACK)
    ns(LAN,"ip","route","replace","default","via",HOST_LAN,"dev",L_HOST)

    # Deliberately wrong ordinary route for REMOTE unless the return mark wins.
    ns(HOST,"ip","route","replace","default","via",LAN_IP,"dev",H_LAN)


TCP_SERVER=r"""
import socket,sys
addr=sys.argv[1]; port=int(sys.argv[2]); tag=sys.argv[3]
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((addr,port)); s.listen(1); print("READY",flush=True)
c,peer=s.accept(); c.settimeout(5); data=c.recv(4096)
print(f"{tag}_PEER={peer[0]}:{peer[1]}",flush=True)
c.sendall(b"ACK:"+data); c.close(); s.close()
"""

TCP_CLIENT=r"""
import socket,sys
addr=sys.argv[1]; port=int(sys.argv[2]); payload=sys.argv[3].encode()
s=socket.socket(); s.settimeout(5); s.connect((addr,port)); s.sendall(payload)
data=s.recv(4096); print("DATA="+data.decode()); assert data==b"ACK:"+payload; s.close()
"""

def start_server(namespace,addr,port,tag):
    p=subprocess.Popen(["ip","netns","exec",namespace,"python3","-u","-c",TCP_SERVER,addr,str(port),tag],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert p.stdout is not None
    first=p.stdout.readline().strip()
    if first!="READY":
        out,err=p.communicate(timeout=3); raise AssertionError((first,out,err))
    return p

def finish_server(p,marker):
    out,err=p.communicate(timeout=7)
    assert p.returncode==0,(out,err)
    assert marker in out,out
    return out

def main():
    servers=[]
    if os.geteuid()!=0:
        print("EXP073_RESULT=SKIP root required"); return 77
    try:
        setup()
        plan=build_host_boundary_policy((
            HostBoundaryProfileIntent(
                profile_id="p",direction=Direction.INBOUND,
                destinations=(IPv4Network("203.0.113.0/24"),),
            ),
        ))
        desired=build_linux_host_boundary_desired(
            plan,host_interface=H_STACK,inner_gateway=None,
            allocation=NG3_HOST_BOUNDARY_LINUX_ALLOCATION,
        )
        assert desired.return_route is not None and desired.return_route.via is None
        assert desired.return_nft is not None
        print("EXP073_DEVICE_ONLY_DESIRED=PASS",flush=True)

        runner=SubprocessNftRunner()
        route_backend=LinuxHostBoundaryRouteBackend(runner,network_namespace=HOST)
        nft_backend=LinuxHostReturnNftBackend(runner,network_namespace=HOST)
        result=prepare_host_boundary_route_dependencies_once(route_backend,desired)
        assert result.confirmed
        nft=converge_host_return_nft_once(nft_backend,desired.return_nft)
        assert nft.exact

        mark=hex(NG3_HOST_BOUNDARY_LINUX_ALLOCATION.mark)
        ordinary=ns(HOST,"ip","-j","-4","route","get",REMOTE_IP).stdout
        marked=ns(HOST,"ip","-j","-4","route","get",REMOTE_IP,"mark",mark).stdout
        assert H_LAN in ordinary,ordinary
        assert H_STACK in marked,marked
        assert "\"gateway\"" not in marked,marked
        print("EXP073_ROUTE_SPLIT=PASS",flush=True)

        main_routes=ns(HOST,"ip","-4","route","show","table","main").stdout
        assert "203.0.113.0/24" not in main_routes and REMOTE_IP not in main_routes,main_routes
        print("EXP073_NO_REMOTE_MAIN_ROUTE=PASS",flush=True)

        lan=start_server(LAN,LAN_IP,18731,"LAN"); servers.append(lan)
        client=ns(REMOTE,"python3","-c",TCP_CLIENT,LAN_IP,"18731","forwarded")
        assert "DATA=ACK:forwarded" in client.stdout,client.stdout
        out=finish_server(lan,"LAN_PEER"); servers.remove(lan)
        assert f"LAN_PEER={REMOTE_IP}:" in out,out
        print("EXP073_FORWARDED_REPLY=PASS",flush=True)

        host=start_server(HOST,HOST_LOCAL,18732,"HOST"); servers.append(host)
        client=ns(REMOTE,"python3","-c",TCP_CLIENT,HOST_LOCAL,"18732","host-local")
        assert "DATA=ACK:host-local" in client.stdout,client.stdout
        out=finish_server(host,"HOST_PEER"); servers.remove(host)
        assert f"HOST_PEER={REMOTE_IP}:" in out,out
        print("EXP073_HOST_LOCAL_REPLY=PASS",flush=True)

        print("EXP073_RESULT=PASS",flush=True)
        return 0
    finally:
        for p in servers:
            if p.poll() is None: p.kill()
            try: p.communicate(timeout=1)
            except Exception: pass
        for name in (LAN,REMOTE,STACK,HOST): del_ns(name)

if __name__=="__main__":
    raise SystemExit(main())
