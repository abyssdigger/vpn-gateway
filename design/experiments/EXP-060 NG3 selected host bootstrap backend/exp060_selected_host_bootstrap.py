#!/usr/bin/env python3
"""EXP-060: production-shaped selected paired-RPDB host bootstrap backend."""

from __future__ import annotations

import json
import os
import subprocess
from ipaddress import IPv4Address

from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_host_bootstrap import build_linux_host_bootstrap_desired
from rou.linux_host_bootstrap_backend import (
    LinuxHostBootstrapBackend,
    cleanup_host_bootstrap_once,
    converge_host_bootstrap_once,
)
from rou.linux_policy_platform import NG3_HOST_BOOTSTRAP_LINUX_ALLOCATION
from rou.release1_config import parse_release1_config
from rou.release1_host_boundary import build_release1_host_boundary_plan


PID=os.getpid()
HOST=f"v60h-{PID}"; STACK=f"v60s-{PID}"; GW=f"v60g-{PID}"; LAN=f"v60l-{PID}"; STATIC=f"v60x-{PID}"
HS="e60hs"; SH="e60sh"; HU="e60hu"; GU="e60gu"; HL="e60hl"; LH="e60lh"; HX="e60hx"; XH="e60xh"
HOST_STACK="10.255.0.1"; STACK_IP="10.255.0.2"
HOST_UP="192.0.2.1"; GW_IP="192.0.2.2"; ENDPOINT="198.51.100.10"
HOST_LAN="10.0.0.1"; LAN_IP="10.0.0.2"
HOST_STATIC="172.16.0.1"; STATIC_GW="172.16.0.2"
STATIC_TARGET="203.0.113.9"; NESTED_MANAGED="203.0.113.129"; DYNAMIC_TARGET="198.18.0.9"


def run(*args,check=True):
    return subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check)


def ns(name,*args,check=True):
    return run("ip","netns","exec",name,*args,check=check)


def add_ns(name):
    run("ip","netns","add",name)
    ns(name,"ip","link","set","lo","up")


def delete_ns(name):
    run("ip","netns","del",name,check=False)


def route_get(address,*extra):
    raw=ns(HOST,"ip","-j","-4","route","get",address,*extra).stdout
    rows=json.loads(raw)
    assert len(rows)==1,raw
    return rows[0]


def setup():
    for name in (HOST,STACK,GW,LAN,STATIC):
        add_ns(name)
    for a,b,na,nb in (
        (HS,SH,HOST,STACK),(HU,GU,HOST,GW),(HL,LH,HOST,LAN),(HX,XH,HOST,STATIC)
    ):
        run("ip","link","add",a,"type","veth","peer","name",b)
        run("ip","link","set",a,"netns",na)
        run("ip","link","set",b,"netns",nb)

    ns(HOST,"ip","addr","add",f"{HOST_STACK}/30","dev",HS); ns(HOST,"ip","link","set",HS,"up")
    ns(STACK,"ip","addr","add",f"{STACK_IP}/30","dev",SH); ns(STACK,"ip","link","set",SH,"up")
    ns(HOST,"ip","addr","add",f"{HOST_UP}/30","dev",HU); ns(HOST,"ip","link","set",HU,"up")
    ns(GW,"ip","addr","add",f"{GW_IP}/30","dev",GU); ns(GW,"ip","link","set",GU,"up")
    ns(GW,"ip","addr","add",f"{ENDPOINT}/32","dev","lo")
    ns(GW,"ip","addr","add",f"{DYNAMIC_TARGET}/32","dev","lo")
    ns(HOST,"ip","addr","add",f"{HOST_LAN}/24","dev",HL); ns(HOST,"ip","link","set",HL,"up")
    ns(LAN,"ip","addr","add",f"{LAN_IP}/24","dev",LH); ns(LAN,"ip","link","set",LH,"up")
    ns(HOST,"ip","addr","add",f"{HOST_STATIC}/30","dev",HX); ns(HOST,"ip","link","set",HX,"up")
    ns(STATIC,"ip","addr","add",f"{STATIC_GW}/30","dev",XH); ns(STATIC,"ip","link","set",XH,"up")
    ns(STATIC,"ip","addr","add",f"{STATIC_TARGET}/24","dev","lo")

    ns(HOST,"ip","route","add","default","via",GW_IP,"dev",HU)
    ns(HOST,"ip","route","add","203.0.113.0/24","via",STATIC_GW,"dev",HX)
    ns(STACK,"ip","route","add","default","via",HOST_STACK)
    ns(LAN,"ip","route","add","default","via",HOST_LAN)
    ns(GW,"ip","route","add","10.255.0.0/30","via",HOST_UP)
    ns(STATIC,"ip","route","add","10.255.0.0/30","via",HOST_STATIC)
    ns(HOST,"sysctl","-q","-w","net.ipv4.ip_forward=1")
    ns(STACK,"sysctl","-q","-w","net.ipv4.ip_forward=1")


def main():
    try:
        setup()
        config=parse_release1_config(f"""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false
allow_vpn_client = "udp>{ENDPOINT}:51820"

[profile.full]
enabled = true
direction = "outbound"
destinations = ["0.0.0.0/0", "203.0.113.128/25", "{ENDPOINT}/32"]
device_order = ["wg"]
""")
        plan=build_release1_host_boundary_plan(config)
        desired=build_linux_host_bootstrap_desired(
            plan,
            host_interface=HS,
            inner_gateway=IPv4Address(STACK_IP),
            allocation=NG3_HOST_BOOTSTRAP_LINUX_ALLOCATION,
        )
        backend=LinuxHostBootstrapBackend(
            SubprocessCommandRunner(),
            NG3_HOST_BOOTSTRAP_LINUX_ALLOCATION,
            network_namespace=HOST,
        )

        main_before=json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)
        try:
            result=converge_host_bootstrap_once(backend,desired)
        except Exception:
            observed=backend.observe(desired)
            print(f"EXP060_DIAG_DESIRED_ROUTES={desired.routes!r}",flush=True)
            print(f"EXP060_DIAG_DESIRED_BYPASS={desired.bypass!r}",flush=True)
            print(f"EXP060_DIAG_DESIRED_PAIRS={desired.pairs!r}",flush=True)
            print(f"EXP060_DIAG_OBSERVED={observed!r}",flush=True)
            print(
                "EXP060_DIAG_RAW_ROUTES="
                + ns(HOST,"ip","-j","-4","route","show","table","all").stdout,
                flush=True,
            )
            print(
                "EXP060_DIAG_RAW_RULES="
                + ns(HOST,"ip","-j","-4","rule","show").stdout,
                flush=True,
            )
            raise
        assert result.exact,result
        print("EXP060_BACKEND_CONVERGENCE=PASS")

        external=route_get("8.8.8.8")
        assert external.get("dev")==HS and external.get("gateway")==STACK_IP,external
        print("EXP060_FULL_TUNNEL_CAPTURE=PASS")

        assert route_get(LAN_IP).get("dev")==HL
        assert route_get(GW_IP).get("dev")==HU
        print("EXP060_CONNECTED_MAIN_PRESERVED=PASS")

        static=route_get(STATIC_TARGET)
        assert static.get("dev")==HX and static.get("gateway")==STATIC_GW,static
        nested=route_get(NESTED_MANAGED)
        assert nested.get("dev")==HS and nested.get("gateway")==STACK_IP,nested
        print("EXP060_MAIN_STATIC_AND_NESTED_MANAGED=PASS")

        ns(HOST,"ip","route","add",f"{DYNAMIC_TARGET}/32","via",GW_IP,"dev",HU)
        dynamic=route_get(DYNAMIC_TARGET)
        assert dynamic.get("dev")==HU and dynamic.get("gateway")==GW_IP,dynamic
        print("EXP060_DYNAMIC_MAIN_ROUTE_IMMEDIATE=PASS")

        exact=route_get(ENDPOINT)
        exact_stack=route_get(ENDPOINT,"from",STACK_IP,"iif",HS)
        assert exact.get("dev")==HS and exact.get("gateway")==STACK_IP,exact
        assert exact_stack.get("dev")==HU and exact_stack.get("gateway")==GW_IP,exact_stack
        assert ns(STACK,"ping","-c","1","-W","1",ENDPOINT,check=False).returncode==0
        print("EXP060_EXACT_ENDPOINT_DIRECTION_DISAMBIGUATION=PASS")

        cleanup=cleanup_host_bootstrap_once(backend,desired)
        assert not cleanup.routes and not cleanup.rule_priorities,cleanup
        ns(HOST,"ip","route","del",f"{DYNAMIC_TARGET}/32","via",GW_IP,"dev",HU)
        main_after=json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)
        assert main_after==main_before,(main_before,main_after)
        print("EXP060_CLEANUP_MAIN_IDENTICAL=PASS")
        print("EXP060_RESULT=PASS")
        return 0
    finally:
        for name in (STATIC,LAN,GW,STACK,HOST):
            delete_ns(name)


if __name__=="__main__":
    raise SystemExit(main())
