#!/usr/bin/env python3
"""EXP-072: device-only selected host bootstrap over managed-L3 endpoint backends."""

from __future__ import annotations

import json
import os
import subprocess
from ipaddress import IPv4Network

from rou.domain import Direction
from rou.host_boundary_policy import HostBoundaryProfileIntent, build_host_boundary_policy
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_host_bootstrap import build_linux_host_bootstrap_desired
from rou.linux_host_bootstrap_backend import (
    LinuxHostBootstrapBackend,
    cleanup_host_bootstrap_once,
    converge_host_bootstrap_once,
)
from rou.linux_policy_platform import NG3_HOST_BOOTSTRAP_LINUX_ALLOCATION


PID=os.getpid()
HOST=f"v72h-{PID}"; STACK=f"v72s-{PID}"; LAN=f"v72l-{PID}"
REMOTE=f"v72r-{PID}"; GW=f"v72g-{PID}"; STATIC=f"v72x-{PID}"
BH="vpng0"; BS="stack0"
HL="e72hl"; LH="e72lh"; SR="e72sr"; RS="e72rs"
HU="e72hu"; GU="e72gu"; HX="e72hx"; XH="e72xh"
HOST_LAN="10.0.0.1"; LAN_IP="10.0.0.2"
STACK_REMOTE="198.18.72.1"; REMOTE_LINK="198.18.72.2"
HOST_UP="192.0.2.1"; GW_IP="192.0.2.2"
HOST_STATIC="172.16.0.1"; STATIC_GW="172.16.0.2"
FULL_TARGET="8.8.8.8"
STATIC_TARGET="203.0.113.9"
NESTED_TARGET="203.0.113.129"
DYNAMIC_TARGET="198.18.0.9"


def run(*args,check=True):
    return subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check)


def ns(name,*args,check=True):
    return run("ip","netns","exec",name,*args,check=check)


def add_ns(name):
    run("ip","netns","add",name)
    ns(name,"ip","link","set","lo","up")


def delete_ns(name):
    run("ip","netns","del",name,check=False)


def pair(a,b,na,nb):
    run("ip","link","add",a,"type","veth","peer","name",b)
    run("ip","link","set",a,"netns",na)
    run("ip","link","set",b,"netns",nb)


def route_get(address,*extra):
    raw=ns(HOST,"ip","-j","-4","route","get",address,*extra).stdout
    rows=json.loads(raw)
    assert len(rows)==1,raw
    return rows[0]


def base_setup():
    for name in (HOST,STACK,LAN,REMOTE,GW,STATIC):
        add_ns(name)
    for a,b,na,nb in (
        (HL,LH,HOST,LAN),(SR,RS,STACK,REMOTE),(HU,GU,HOST,GW),(HX,XH,HOST,STATIC)
    ):
        pair(a,b,na,nb)

    ns(HOST,"ip","addr","add",f"{HOST_LAN}/24","dev",HL); ns(HOST,"ip","link","set",HL,"up")
    ns(LAN,"ip","addr","add",f"{LAN_IP}/24","dev",LH); ns(LAN,"ip","link","set",LH,"up")
    ns(STACK,"ip","addr","add",f"{STACK_REMOTE}/30","dev",SR); ns(STACK,"ip","link","set",SR,"up")
    ns(REMOTE,"ip","addr","add",f"{REMOTE_LINK}/30","dev",RS); ns(REMOTE,"ip","link","set",RS,"up")
    ns(HOST,"ip","addr","add",f"{HOST_UP}/30","dev",HU); ns(HOST,"ip","link","set",HU,"up")
    ns(GW,"ip","addr","add",f"{GW_IP}/30","dev",GU); ns(GW,"ip","link","set",GU,"up")
    ns(HOST,"ip","addr","add",f"{HOST_STATIC}/30","dev",HX); ns(HOST,"ip","link","set",HX,"up")
    ns(STATIC,"ip","addr","add",f"{STATIC_GW}/30","dev",XH); ns(STATIC,"ip","link","set",XH,"up")

    for target in (FULL_TARGET,NESTED_TARGET):
        ns(REMOTE,"ip","addr","add",f"{target}/32","dev","lo")
    ns(GW,"ip","addr","add",f"{DYNAMIC_TARGET}/32","dev","lo")
    ns(STATIC,"ip","addr","add",f"{STATIC_TARGET}/32","dev","lo")

    ns(HOST,"ip","route","add","default","via",GW_IP,"dev",HU)
    ns(HOST,"ip","route","add","203.0.113.0/24","via",STATIC_GW,"dev",HX)
    ns(LAN,"ip","route","add","default","via",HOST_LAN)
    ns(REMOTE,"ip","route","add","10.0.0.0/24","via",STACK_REMOTE,"dev",RS)
    ns(GW,"ip","route","add","10.0.0.0/24","via",HOST_UP,"dev",GU)
    ns(STATIC,"ip","route","add","10.0.0.0/24","via",HOST_STATIC,"dev",XH)

    ns(STACK,"ip","route","add",f"{FULL_TARGET}/32","via",REMOTE_LINK,"dev",SR)
    ns(STACK,"ip","route","add","203.0.113.128/25","via",REMOTE_LINK,"dev",SR)
    ns(STACK,"ip","route","add","10.0.0.0/24","dev",BS,check=False)

    for name in (HOST,STACK):
        ns(name,"sysctl","-qw","net.ipv4.ip_forward=1")
        ns(name,"sysctl","-qw","net.ipv4.conf.all.rp_filter=0")
        ns(name,"sysctl","-qw","net.ipv4.conf.default.rp_filter=0")


def create_boundary(kind):
    if kind=="veth":
        pair(BH,BS,HOST,STACK)
        ns(HOST,"ip","link","set",BH,"up")
        ns(STACK,"ip","link","set",BS,"up")
        ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{BH}.rp_filter=0")
        ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{BS}.rp_filter=0")
        ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{BH}.proxy_arp=1")
        ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{BS}.proxy_arp=1")
        return True
    if kind=="netkit":
        r=ns(HOST,"ip","link","add",BH,"type","netkit","mode","l3","forward","peer","forward",BS,check=False)
        if r.returncode!=0:
            print("EXP072_NETKIT_SUPPORT=UNSUPPORTED detail="+repr((r.stderr or r.stdout).strip()),flush=True)
            return False
        ns(HOST,"ip","link","set",BS,"netns",STACK)
        ns(HOST,"ip","link","set",BH,"up")
        ns(STACK,"ip","link","set",BS,"up")
        print("EXP072_NETKIT_SUPPORT=SUPPORTED",flush=True)
        return True
    raise ValueError(kind)


def bootstrap_desired():
    plan=build_host_boundary_policy((
        HostBoundaryProfileIntent(
            profile_id="full",direction=Direction.OUTBOUND,
            destinations=(IPv4Network("0.0.0.0/0"),),
        ),
        HostBoundaryProfileIntent(
            profile_id="nested",direction=Direction.OUTBOUND,
            destinations=(IPv4Network("203.0.113.128/25"),),
        ),
    ))
    return build_linux_host_bootstrap_desired(
        plan,host_interface=BH,inner_gateway=None,
        allocation=NG3_HOST_BOOTSTRAP_LINUX_ALLOCATION,
    )


def ping_from_lan(target):
    return ns(LAN,"ping","-n","-c","1","-W","2",target,check=False).returncode==0


def phase(kind):
    if not create_boundary(kind):
        return None

    # Boundary-dependent stack return route is installed only after the endpoint exists.
    ns(STACK,"ip","route","replace","10.0.0.0/24","dev",BS)

    desired=bootstrap_desired()
    backend=LinuxHostBootstrapBackend(
        SubprocessCommandRunner(),NG3_HOST_BOOTSTRAP_LINUX_ALLOCATION,network_namespace=HOST,
    )
    main_before=json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)
    result=converge_host_bootstrap_once(backend,desired)
    assert result.exact,result

    full=route_get(FULL_TARGET)
    assert full.get("dev")==BH and "gateway" not in full,full
    assert ping_from_lan(FULL_TARGET),("full payload failed",kind)
    print(f"EXP072_{kind.upper()}_FULL_CAPTURE=PASS",flush=True)

    static=route_get(STATIC_TARGET)
    assert static.get("dev")==HX and static.get("gateway")==STATIC_GW,static
    assert ping_from_lan(STATIC_TARGET),("static payload failed",kind)
    print(f"EXP072_{kind.upper()}_MORE_SPECIFIC_MAIN=PASS",flush=True)

    nested=route_get(NESTED_TARGET)
    assert nested.get("dev")==BH and "gateway" not in nested,nested
    assert ping_from_lan(NESTED_TARGET),("nested payload failed",kind)
    print(f"EXP072_{kind.upper()}_NESTED_MANAGED=PASS",flush=True)

    ns(HOST,"ip","route","add",f"{DYNAMIC_TARGET}/32","via",GW_IP,"dev",HU)
    dynamic=route_get(DYNAMIC_TARGET)
    assert dynamic.get("dev")==HU and dynamic.get("gateway")==GW_IP,dynamic
    assert ping_from_lan(DYNAMIC_TARGET),("dynamic main payload failed",kind)
    print(f"EXP072_{kind.upper()}_DYNAMIC_MAIN=PASS",flush=True)

    # Return traffic from STACK must hit the iif bypass and use ordinary main, not bootstrap.
    bypass=route_get(LAN_IP,"from",FULL_TARGET,"iif",BH)
    assert bypass.get("dev")==HL,bypass
    print(f"EXP072_{kind.upper()}_STACK_BYPASS=PASS",flush=True)

    cleanup=cleanup_host_bootstrap_once(backend,desired)
    assert not cleanup.routes and not cleanup.rule_priorities,cleanup
    ns(HOST,"ip","route","del",f"{DYNAMIC_TARGET}/32","via",GW_IP,"dev",HU)
    main_after=json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)
    assert main_after==main_before,(main_before,main_after)
    print(f"EXP072_{kind.upper()}_CLEANUP_MAIN_IDENTICAL=PASS",flush=True)
    return True


def reset():
    for name in (STATIC,GW,REMOTE,LAN,STACK,HOST):
        delete_ns(name)


def main():
    if os.geteuid()!=0:
        print("EXP072_RESULT=SKIP root required")
        return 77
    print("EXP072_PREFLIGHT kernel="+run("uname","-r").stdout.strip(),flush=True)
    print("EXP072_PREFLIGHT ip="+run("ip","-V").stdout.strip(),flush=True)
    netkit=None
    try:
        base_setup(); veth=phase("veth")
        reset()
        base_setup(); netkit=phase("netkit")
        if not veth:
            raise RuntimeError("routed-veth backend did not complete")
        print(f"EXP072_RESULT=PASS netkit={netkit}",flush=True)
        return 0
    except Exception as exc:
        print("EXP072_RESULT=FAIL",flush=True)
        print("EXP072_ERROR="+repr(exc),flush=True)
        raise
    finally:
        reset()


if __name__=="__main__":
    raise SystemExit(main())
