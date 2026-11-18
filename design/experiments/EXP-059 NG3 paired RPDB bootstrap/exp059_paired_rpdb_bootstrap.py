#!/usr/bin/env python3
"""EXP-059: paired RPDB bootstrap using suppress_prefixlength."""

from __future__ import annotations

import json
import os
import subprocess

PID=os.getpid()
HOST=f"v59h-{PID}"; STACK=f"v59s-{PID}"; GW=f"v59g-{PID}"; LAN=f"v59l-{PID}"; STATIC=f"v59x-{PID}"
HS="e59hs"; SH="e59sh"; HU="e59hu"; GU="e59gu"; HL="e59hl"; LH="e59lh"; HX="e59hx"; XH="e59xh"
HOST_STACK="10.255.0.1"; STACK_IP="10.255.0.2"
HOST_UP="192.0.2.1"; GW_IP="192.0.2.2"; ENDPOINT="198.51.100.10"
HOST_LAN="10.0.0.1"; LAN_IP="10.0.0.2"
HOST_STATIC="172.16.0.1"; STATIC_GW="172.16.0.2"
STATIC_TARGET="203.0.113.9"; DYNAMIC_TARGET="198.18.0.9"; NESTED_MANAGED="203.0.113.129"
TABLE="2059"
BYPASS=900
P32_PRESERVE=1000; P32_BOOT=1001
P25_PRESERVE=1010; P25_BOOT=1011
P0_PRESERVE=1020; P0_BOOT=1021

def run(*args,check=True):
    return subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check)

def ns(name,*args,check=True):
    return run("ip","netns","exec",name,*args,check=check)

def add_ns(name):
    run("ip","netns","add",name); ns(name,"ip","link","set","lo","up")

def delete_ns(name):
    run("ip","netns","del",name,check=False)

def route_get(address,*extra):
    raw=ns(HOST,"ip","-j","-4","route","get",address,*extra).stdout
    rows=json.loads(raw); assert len(rows)==1,raw
    return rows[0]

def setup():
    for name in (HOST,STACK,GW,LAN,STATIC): add_ns(name)
    for a,b,na,nb in (
        (HS,SH,HOST,STACK),(HU,GU,HOST,GW),(HL,LH,HOST,LAN),(HX,XH,HOST,STATIC)
    ):
        run("ip","link","add",a,"type","veth","peer","name",b)
        run("ip","link","set",a,"netns",na); run("ip","link","set",b,"netns",nb)
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

    # Managed prefixes: exact ENDPOINT/32, nested 203.0.113.128/25, and full tunnel /0.
    ns(HOST,"ip","route","add","table",TABLE,f"{ENDPOINT}/32","via",STACK_IP,"dev",HS,"proto","203")
    ns(HOST,"ip","route","add","table",TABLE,"203.0.113.128/25","via",STACK_IP,"dev",HS,"proto","203")
    ns(HOST,"ip","route","add","table",TABLE,"default","via",STACK_IP,"dev",HS,"proto","203")

    ns(HOST,"ip","rule","add","priority",str(BYPASS),"iif",HS,"lookup","main")
    for priority,prefix,length in (
        (P32_PRESERVE,f"{ENDPOINT}/32","32"),
        (P32_BOOT,f"{ENDPOINT}/32",None),
        (P25_PRESERVE,"203.0.113.128/25","25"),
        (P25_BOOT,"203.0.113.128/25",None),
        (P0_PRESERVE,"0.0.0.0/0","0"),
        (P0_BOOT,"0.0.0.0/0",None),
    ):
        argv=["ip","rule","add","priority",str(priority),"to",prefix,"lookup"]
        if length is None:
            argv.append(TABLE)
        else:
            argv.extend(("main","suppress_prefixlength",length))
        ns(HOST,*argv)

def main():
    try:
        setup()
        main_before=json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)
        assert not any(row.get("protocol") in (203,"203") for row in main_before)
        print("EXP059_MAIN_UNTOUCHED=PASS")

        external=route_get("8.8.8.8")
        assert external.get("dev")==HS and external.get("gateway")==STACK_IP,external
        print("EXP059_FULL_TUNNEL_EXTERNAL_CAPTURE=PASS")

        lan=route_get(LAN_IP)
        assert lan.get("dev")==HL,lan
        uplink=route_get(GW_IP)
        assert uplink.get("dev")==HU,uplink
        print("EXP059_CONNECTED_ORDINARY_ROUTES_PRESERVED=PASS")

        static=route_get(STATIC_TARGET)
        assert static.get("dev")==HX and static.get("gateway")==STATIC_GW,static
        print("EXP059_MORE_SPECIFIC_MAIN_STATIC_PRESERVED=PASS")

        nested=route_get(NESTED_MANAGED)
        assert nested.get("dev")==HS and nested.get("gateway")==STACK_IP,nested
        print("EXP059_NESTED_MANAGED_ROUTE_WINS=PASS")

        # New main route after activation must win immediately under /0 without any
        # VPN-GATE throw/pin/rule update.
        ns(HOST,"ip","route","add",f"{DYNAMIC_TARGET}/32","via",GW_IP,"dev",HU)
        dynamic=route_get(DYNAMIC_TARGET)
        assert dynamic.get("dev")==HU and dynamic.get("gateway")==GW_IP,dynamic
        print("EXP059_DYNAMIC_MAIN_ROUTE_PRESERVED_IMMEDIATELY=PASS")

        exact=route_get(ENDPOINT)
        exact_stack=route_get(ENDPOINT,"from",STACK_IP,"iif",HS)
        assert exact.get("dev")==HS,exact
        assert exact_stack.get("dev")==HU and exact_stack.get("gateway")==GW_IP,exact_stack
        assert ns(STACK,"ping","-c","1","-W","1",ENDPOINT,check=False).returncode==0
        print("EXP059_EXACT_ENDPOINT_DIRECTION_DISAMBIGUATION=PASS")

        for priority in (BYPASS,P32_PRESERVE,P32_BOOT,P25_PRESERVE,P25_BOOT,P0_PRESERVE,P0_BOOT):
            ns(HOST,"ip","rule","del","priority",str(priority),check=False)
        ns(HOST,"ip","route","flush","table",TABLE)
        # Remove the deliberately added administrator route before comparing original main.
        ns(HOST,"ip","route","del",f"{DYNAMIC_TARGET}/32","via",GW_IP,"dev",HU)
        main_after=json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)
        assert main_after==main_before,(main_before,main_after)
        print("EXP059_CLEANUP_MAIN_IDENTICAL=PASS")
        print("EXP059_RESULT=PASS")
        return 0
    finally:
        for name in (STATIC,LAN,GW,STACK,HOST): delete_ns(name)

if __name__=="__main__":
    raise SystemExit(main())
