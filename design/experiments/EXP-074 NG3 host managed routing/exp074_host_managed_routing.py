#!/usr/bin/env python3
"""EXP-074: current host managed-destination routing over routed L3 boundary."""

from __future__ import annotations

import json
import os
import subprocess
from ipaddress import IPv4Network

from rou.domain import Direction
from rou.host_managed_routing import (
    HostManagedRoutingProfile,
    build_host_managed_routing_plan,
)
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_host_managed_routing import build_linux_host_managed_routing_desired
from rou.linux_host_managed_routing_backend import (
    LinuxHostManagedRoutingBackend,
    cleanup_host_managed_routing_once,
    converge_host_managed_routing_once,
)
from rou.linux_policy_platform import NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION


PID=os.getpid()
HOST=f"v74h-{PID}"; STACK=f"v74s-{PID}"; LAN=f"v74l-{PID}"
REMOTE=f"v74r-{PID}"; GW=f"v74g-{PID}"; STATIC=f"v74x-{PID}"
BH="vpng0"; BS="stack0"
HL="e74hl"; LH="e74lh"; SR="e74sr"; RS="e74rs"
HU="e74hu"; GU="e74gu"; HX="e74hx"; XH="e74xh"

HOST_LAN="10.0.0.1"; LAN_IP="10.0.0.2"
STACK_REMOTE="198.18.74.1"; REMOTE_LINK="198.18.74.2"
HOST_UP="192.0.2.1"; GW_IP="192.0.2.2"
HOST_STATIC="172.16.0.1"; STATIC_GW="172.16.0.2"
FULL_TARGET="8.8.8.8"
STATIC_TARGET="203.0.113.9"
NESTED_TARGET="203.0.113.129"
DYNAMIC_TARGET="198.51.100.9"


def run(*args,check=True):
    return subprocess.run(
        args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check
    )


def ns(name,*args,check=True):
    return run("ip","netns","exec",name,*args,check=check)


def add_ns(name):
    run("ip","netns","add",name)
    ns(name,"ip","link","set","lo","up")


def del_ns(name):
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


def setup():
    for name in (HOST,STACK,LAN,REMOTE,GW,STATIC):
        add_ns(name)
    for a,b,na,nb in (
        (BH,BS,HOST,STACK),
        (HL,LH,HOST,LAN),
        (SR,RS,STACK,REMOTE),
        (HU,GU,HOST,GW),
        (HX,XH,HOST,STATIC),
    ):
        pair(a,b,na,nb)

    ns(HOST,"ip","addr","add",f"{HOST_LAN}/24","dev",HL)
    ns(LAN,"ip","addr","add",f"{LAN_IP}/24","dev",LH)
    ns(STACK,"ip","addr","add",f"{STACK_REMOTE}/30","dev",SR)
    ns(REMOTE,"ip","addr","add",f"{REMOTE_LINK}/30","dev",RS)
    ns(HOST,"ip","addr","add",f"{HOST_UP}/30","dev",HU)
    ns(GW,"ip","addr","add",f"{GW_IP}/30","dev",GU)
    ns(HOST,"ip","addr","add",f"{HOST_STATIC}/30","dev",HX)
    ns(STATIC,"ip","addr","add",f"{STATIC_GW}/30","dev",XH)

    for name,ifs in (
        (HOST,(BH,HL,HU,HX)),(STACK,(BS,SR)),(LAN,(LH,)),
        (REMOTE,(RS,)),(GW,(GU,)),(STATIC,(XH,))
    ):
        for iface in ifs:
            ns(name,"ip","link","set",iface,"up")

    for target in (FULL_TARGET,STATIC_TARGET,NESTED_TARGET,DYNAMIC_TARGET):
        ns(REMOTE,"ip","addr","add",f"{target}/32","dev","lo")

    # Ordinary host routes deliberately conflict with managed 0/0.
    ns(HOST,"ip","route","add","default","via",GW_IP,"dev",HU)
    ns(HOST,"ip","route","add","203.0.113.0/24","via",STATIC_GW,"dev",HX)
    ns(LAN,"ip","route","add","default","via",HOST_LAN)
    ns(GW,"ip","route","add","10.0.0.0/24","via",HOST_UP,"dev",GU)
    ns(STATIC,"ip","route","add","10.0.0.0/24","via",HOST_STATIC,"dev",XH)

    # STACK has an ordinary route to the remote test router and a return route
    # to LAN through the routed, addressless managed boundary.
    ns(STACK,"ip","route","add","default","via",REMOTE_LINK,"dev",SR)
    ns(STACK,"ip","route","add","10.0.0.0/24","dev",BS)
    ns(REMOTE,"ip","route","add","10.0.0.0/24","via",STACK_REMOTE,"dev",RS)

    for name in (HOST,STACK):
        ns(name,"sysctl","-qw","net.ipv4.ip_forward=1")
        ns(name,"sysctl","-qw","net.ipv4.conf.all.rp_filter=0")
        ns(name,"sysctl","-qw","net.ipv4.conf.default.rp_filter=0")
    ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{BH}.proxy_arp=1")
    ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{BS}.proxy_arp=1")
    ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{BH}.rp_filter=0")
    ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{BS}.rp_filter=0")


def desired():
    plan=build_host_managed_routing_plan((
        HostManagedRoutingProfile(
            profile_id="full",
            direction=Direction.OUTBOUND,
            destinations=(IPv4Network("0.0.0.0/0"),),
        ),
        HostManagedRoutingProfile(
            profile_id="nested",
            direction=Direction.INBOUND,
            destinations=(IPv4Network("203.0.113.128/25"),),
        ),
    ))
    return build_linux_host_managed_routing_desired(
        plan,
        host_interface=BH,
        allocation=NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
    )


def ping_from_lan(target):
    return ns(LAN,"ping","-n","-c","1","-W","2",target,check=False).returncode==0


def main():
    if os.geteuid()!=0:
        print("EXP074_RESULT=SKIP root required")
        return 77
    try:
        setup()
        target=desired()
        backend=LinuxHostManagedRoutingBackend(
            SubprocessCommandRunner(),
            NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
            network_namespace=HOST,
        )
        main_before=json.loads(
            ns(HOST,"ip","-j","-4","route","show","table","main").stdout
        )
        result=converge_host_managed_routing_once(backend,target)
        assert result.exact,result

        full=route_get(FULL_TARGET)
        assert full.get("dev")==BH and "gateway" not in full,full
        assert ping_from_lan(FULL_TARGET),full
        print("EXP074_FULL_CAPTURE=PASS",flush=True)

        # More-specific ordinary main route no longer escapes explicit managed /0.
        static=route_get(STATIC_TARGET)
        assert static.get("dev")==BH and "gateway" not in static,static
        assert ping_from_lan(STATIC_TARGET),static
        print("EXP074_MORE_SPECIFIC_MAIN_CAPTURED=PASS",flush=True)

        nested=route_get(NESTED_TARGET)
        assert nested.get("dev")==BH and "gateway" not in nested,nested
        assert ping_from_lan(NESTED_TARGET),nested
        print("EXP074_NESTED_MANAGED=PASS",flush=True)

        ns(HOST,"ip","route","add",f"{DYNAMIC_TARGET}/32","via",GW_IP,"dev",HU)
        dynamic=route_get(DYNAMIC_TARGET)
        assert dynamic.get("dev")==BH and "gateway" not in dynamic,dynamic
        assert ping_from_lan(DYNAMIC_TARGET),dynamic
        print("EXP074_DYNAMIC_MORE_SPECIFIC_MAIN_CAPTURED=PASS",flush=True)

        # A packet already emitted by STACK bypasses the managed table and uses
        # ordinary main even though managed /0 would otherwise match.
        bypass_static=route_get(
            STATIC_TARGET,"from",FULL_TARGET,"iif",BH
        )
        assert (
            bypass_static.get("dev")==HX
            and bypass_static.get("gateway")==STATIC_GW
        ),bypass_static
        bypass_dynamic=route_get(
            DYNAMIC_TARGET,"from",FULL_TARGET,"iif",BH
        )
        assert (
            bypass_dynamic.get("dev")==HU
            and bypass_dynamic.get("gateway")==GW_IP
        ),bypass_dynamic
        print("EXP074_STACK_ORIGIN_MAIN_BYPASS=PASS",flush=True)

        # Kernel local rule remains before both VPN-GATE rules.
        local=route_get(HOST_LAN)
        assert local.get("type")=="local" or local.get("dev")=="lo",local
        print("EXP074_LOCAL_DELIVERY_PRESERVED=PASS",flush=True)

        cleanup=cleanup_host_managed_routing_once(backend,target)
        assert not cleanup.routes and not cleanup.rule_priorities,cleanup
        ns(HOST,"ip","route","del",f"{DYNAMIC_TARGET}/32","via",GW_IP,"dev",HU)
        main_after=json.loads(
            ns(HOST,"ip","-j","-4","route","show","table","main").stdout
        )
        assert main_after==main_before,(main_before,main_after)
        print("EXP074_CLEANUP_MAIN_IDENTICAL=PASS",flush=True)
        print("EXP074_RESULT=PASS",flush=True)
        return 0
    finally:
        for name in (STATIC,GW,REMOTE,LAN,STACK,HOST):
            del_ns(name)


if __name__=="__main__":
    raise SystemExit(main())
