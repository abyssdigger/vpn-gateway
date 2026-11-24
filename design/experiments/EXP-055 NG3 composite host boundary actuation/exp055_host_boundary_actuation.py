#!/usr/bin/env python3
"""EXP-055: production-shaped composite host-boundary actuation."""

from __future__ import annotations

import json
import os
import subprocess
from ipaddress import IPv4Address

from rou.host_boundary_convergence import (
    cleanup_host_boundary_once,
    converge_host_boundary_once,
)
from rou.host_boundary_prepare import prepare_linux_host_boundary_desired
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_policy_platform import NG3_HOST_BOUNDARY_LINUX_ALLOCATION
from rou.linux_host_boundary_routes import LinuxHostBoundaryRouteBackend
from rou.linux_host_return_nft import LinuxHostReturnNftBackend
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.release1_config import parse_release1_config


PID = os.getpid()
ALLOC = NG3_HOST_BOUNDARY_LINUX_ALLOCATION


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check
    )


def ns(name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("ip", "netns", "exec", name, *args, check=check)


def add_ns(name: str) -> None:
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def del_ns(name: str) -> None:
    run("ip", "netns", "del", name, check=False)


def route_get(name: str, address: str) -> dict:
    raw = ns(name, "ip", "-j", "-4", "route", "get", address).stdout
    rows = json.loads(raw)
    assert isinstance(rows, list) and len(rows) == 1, raw
    return rows[0]


def backends(host: str):
    return (
        LinuxHostBoundaryRouteBackend(
            SubprocessCommandRunner(),
            network_namespace=host,
        ),
        LinuxHostReturnNftBackend(
            SubprocessNftRunner(),
            network_namespace=host,
        ),
    )


def full_tunnel_case() -> None:
    host=f"v55fh-{PID}"
    gw=f"v55fg-{PID}"
    stack=f"v55fs-{PID}"
    hu="e55fhu"; gu="e55fgu"; hs="e55fhs"; sh="e55fsh"
    endpoint="198.51.100.10"
    try:
        for name in (host,gw,stack): add_ns(name)
        run("ip","link","add",hu,"type","veth","peer","name",gu)
        run("ip","link","set",hu,"netns",host); run("ip","link","set",gu,"netns",gw)
        run("ip","link","add",hs,"type","veth","peer","name",sh)
        run("ip","link","set",hs,"netns",host); run("ip","link","set",sh,"netns",stack)
        ns(host,"ip","addr","add","192.0.2.1/30","dev",hu); ns(host,"ip","link","set",hu,"up")
        ns(gw,"ip","addr","add","192.0.2.2/30","dev",gu); ns(gw,"ip","link","set",gu,"up")
        ns(gw,"ip","addr","add",f"{endpoint}/32","dev","lo")
        ns(host,"ip","addr","add","10.255.0.1/30","dev",hs); ns(host,"ip","link","set",hs,"up")
        ns(stack,"ip","addr","add","10.255.0.2/30","dev",sh); ns(stack,"ip","link","set",sh,"up")
        ns(host,"ip","route","add","default","via","192.0.2.2","dev",hu)

        config=parse_release1_config(f"""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false
allow_vpn_client = "udp>{endpoint}:51820"

[profile.full]
enabled = true
direction = "outbound"
destinations = ["0.0.0.0/0"]
device_order = ["wg"]
""")
        route_backend,nft_backend=backends(host)
        desired=prepare_linux_host_boundary_desired(
            config,
            route_backend=route_backend,
            host_interface=hs,
            inner_gateway=IPv4Address("10.255.0.2"),
            allocation=ALLOC,
        )
        assert [x.destination.with_prefixlen for x in desired.bootstrap_routes] == [
            "0.0.0.0/1","128.0.0.0/1"
        ]
        converge_host_boundary_once(route_backend,nft_backend,desired)
        ep=route_get(host,endpoint)
        assert ep.get("gateway")=="192.0.2.2" and ep.get("dev")==hu,ep
        captured=route_get(host,"203.0.113.77")
        assert captured.get("gateway")=="10.255.0.2" and captured.get("dev")==hs,captured
        assert ns(host,"ping","-c","1","-W","1",endpoint,check=False).returncode==0
        print("EXP055_FULL_TUNNEL_COMPOSITE=PASS")

        cleanup_host_boundary_once(route_backend,nft_backend,desired)
        restored=route_get(host,endpoint)
        assert restored.get("gateway")=="192.0.2.2" and restored.get("dev")==hu,restored
        owner=ns(host,"ip","-j","-4","route","show","proto","203").stdout
        assert json.loads(owner)==[],owner
        print("EXP055_FULL_TUNNEL_CLEANUP=PASS")
    finally:
        for name in (stack,gw,host): del_ns(name)


TCP_SERVER=r"""
import socket,sys
a=sys.argv[1]; p=int(sys.argv[2])
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((a,p)); s.listen(1); print("READY",flush=True)
c,peer=s.accept(); c.settimeout(5); data=c.recv(128); c.sendall(b"ACK:"+data)
print("PEER="+peer[0],flush=True); c.close(); s.close()
"""
TCP_CLIENT=r"""
import socket,sys
s=socket.socket(); s.settimeout(5); s.connect((sys.argv[1],int(sys.argv[2])))
s.sendall(b"stateful"); data=s.recv(128); print(data.decode()); assert data==b"ACK:stateful"; s.close()
"""


def start_server(name: str, address: str, port: int):
    p=subprocess.Popen(
        ["ip","netns","exec",name,"python3","-u","-c",TCP_SERVER,address,str(port)],
        text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    )
    assert p.stdout is not None
    assert p.stdout.readline().strip()=="READY"
    return p


def inbound_case() -> None:
    host=f"v55ih-{PID}"; stack=f"v55is-{PID}"; remote=f"v55ir-{PID}"; lan=f"v55il-{PID}"
    hs="e55ihs"; sh="e55ish"; sr="e55isr"; rs="e55irs"; hl="e55ihl"; lh="e55ilh"
    server=None
    try:
        for name in (host,stack,remote,lan): add_ns(name)
        for a,b,na,nb in ((hs,sh,host,stack),(sr,rs,stack,remote),(hl,lh,host,lan)):
            run("ip","link","add",a,"type","veth","peer","name",b)
            run("ip","link","set",a,"netns",na); run("ip","link","set",b,"netns",nb)
        ns(host,"ip","addr","add","192.0.2.1/30","dev",hs); ns(host,"ip","link","set",hs,"up")
        ns(stack,"ip","addr","add","192.0.2.2/30","dev",sh); ns(stack,"ip","link","set",sh,"up")
        ns(stack,"ip","addr","add","203.0.113.1/24","dev",sr); ns(stack,"ip","link","set",sr,"up")
        ns(remote,"ip","addr","add","203.0.113.2/24","dev",rs); ns(remote,"ip","link","set",rs,"up")
        ns(host,"ip","addr","add","10.0.0.1/24","dev",hl); ns(host,"ip","link","set",hl,"up")
        ns(lan,"ip","addr","add","10.0.0.2/24","dev",lh); ns(lan,"ip","link","set",lh,"up")
        ns(remote,"ip","route","add","default","via","203.0.113.1")
        ns(stack,"ip","route","add","10.0.0.0/24","via","192.0.2.1")
        ns(lan,"ip","route","add","default","via","10.0.0.1")
        # Deliberately wrong unmarked default for remote replies.
        ns(host,"ip","route","add","default","via","10.0.0.2","dev",hl)
        ns(host,"sysctl","-q","-w","net.ipv4.ip_forward=1")
        ns(stack,"sysctl","-q","-w","net.ipv4.ip_forward=1")

        config=parse_release1_config("""
[device.server]
enabled = true
expected_interfaces = ["vpn0"]

[profile.in]
enabled = true
direction = "inbound"
destinations = ["203.0.113.0/24"]
device_order = ["server"]
""")
        route_backend,nft_backend=backends(host)
        desired=prepare_linux_host_boundary_desired(
            config,
            route_backend=route_backend,
            host_interface=hs,
            inner_gateway=IPv4Address("192.0.2.2"),
            allocation=ALLOC,
        )
        assert desired.bootstrap_routes==()
        converge_host_boundary_once(route_backend,nft_backend,desired)

        server=start_server(lan,"10.0.0.2",18555)
        client=ns(remote,"python3","-c",TCP_CLIENT,"10.0.0.2","18555")
        assert "ACK:stateful" in client.stdout,client.stdout
        out,err=server.communicate(timeout=5)
        assert server.returncode==0,(out,err)
        assert "PEER=203.0.113.2" in out,out
        server=None
        print("EXP055_INBOUND_STATEFUL_COMPOSITE=PASS")

        cleanup_host_boundary_once(route_backend,nft_backend,desired)
        rules=ns(host,"ip","-j","-4","rule","show").stdout
        assert all(
            row.get("priority") != ALLOC.return_rule_priority
            for row in json.loads(rules)
        )
        tables=ns(host,"nft","list","table","inet","vpn_gate_host_return",check=False)
        assert tables.returncode!=0
        print("EXP055_INBOUND_CLEANUP=PASS")
    finally:
        if server is not None:
            server.terminate()
            try: server.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                server.kill(); server.communicate()
        for name in (lan,remote,stack,host): del_ns(name)


def main() -> int:
    full_tunnel_case()
    inbound_case()
    print("EXP055_RESULT=PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
