#!/usr/bin/env python3
"""EXP-058: dedicated bootstrap table + throw routes preserve main LPM semantics."""

from __future__ import annotations

import json
import os
import subprocess

PID=os.getpid()
HOST=f"v58h-{PID}"; STACK=f"v58s-{PID}"; GW=f"v58g-{PID}"; LAN=f"v58l-{PID}"; STATIC=f"v58x-{PID}"
HS="e58hs"; SH="e58sh"; HU="e58hu"; GU="e58gu"; HL="e58hl"; LH="e58lh"; HX="e58hx"; XH="e58xh"
HOST_STACK="10.255.0.1"; STACK_IP="10.255.0.2"
HOST_UP="192.0.2.1"; GW_IP="192.0.2.2"; ENDPOINT="198.51.100.10"
HOST_LAN="10.0.0.1"; LAN_IP="10.0.0.2"
HOST_STATIC="172.16.0.1"; STATIC_GW="172.16.0.2"
STATIC_TARGET="203.0.113.9"; NESTED_MANAGED="203.0.113.128"
TABLE="2058"; RULE_PRIO="1000"; MARK="0x58"

def run(*args,check=True,input_text=None):
    return subprocess.run(args,input=input_text,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check)

def ns(name,*args,check=True,input_text=None):
    return run("ip","netns","exec",name,*args,check=check,input_text=input_text)

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

    ns(HOST,"ip","route","add","table",TABLE,"throw","10.0.0.0/24","proto","203")
    ns(HOST,"ip","route","add","table",TABLE,"throw","192.0.2.0/30","proto","203")
    ns(HOST,"ip","route","add","table",TABLE,"throw","172.16.0.0/30","proto","203")
    ns(HOST,"ip","route","add","table",TABLE,"throw","203.0.113.0/24","proto","203")
    ns(HOST,"ip","route","add","table",TABLE,"203.0.113.128/25","via",STACK_IP,"dev",HS,"proto","203")
    ns(HOST,"ip","route","add","table",TABLE,"default","via",STACK_IP,"dev",HS,"proto","203")
    ns(HOST,"ip","rule","add","priority",RULE_PRIO,"fwmark",MARK,"lookup",TABLE)

    nft=f"""
table inet exp058 {{
  chain prerouting {{
    type filter hook prerouting priority mangle; policy accept;
    iifname != "{HS}" meta mark set {MARK}
  }}
  chain output {{
    type route hook output priority mangle; policy accept;
    meta mark set {MARK}
  }}
}}
"""
    ns(HOST,"nft","-f","-",input_text=nft)

def main():
    try:
        setup()
        main_before=json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)
        assert not any(row.get("protocol") in (203,"203") for row in main_before)
        print("EXP058_MAIN_UNTOUCHED=PASS")

        external=route_get(ENDPOINT,"mark",MARK)
        assert external.get("dev")==HS and external.get("gateway")==STACK_IP,external
        print("EXP058_FULL_TUNNEL_EXTERNAL_CAPTURE=PASS")

        lan=route_get(LAN_IP,"mark",MARK)
        assert lan.get("dev")==HL,lan
        print("EXP058_CONNECTED_LAN_PRESERVED=PASS")

        uplink=route_get(GW_IP,"mark",MARK)
        assert uplink.get("dev")==HU,uplink
        print("EXP058_CONNECTED_UPLINK_PRESERVED=PASS")

        static=route_get(STATIC_TARGET,"mark",MARK)
        assert static.get("dev")==HX and static.get("gateway")==STATIC_GW,static
        print("EXP058_MORE_SPECIFIC_MAIN_STATIC_PRESERVED=PASS")

        nested=route_get(NESTED_MANAGED,"mark",MARK)
        assert nested.get("dev")==HS and nested.get("gateway")==STACK_IP,nested
        print("EXP058_NESTED_MANAGED_ROUTE_WINS=PASS")

        stack_external=route_get(ENDPOINT,"from",STACK_IP,"iif",HS)
        assert stack_external.get("dev")==HU and stack_external.get("gateway")==GW_IP,stack_external
        assert ns(STACK,"ping","-c","1","-W","1",ENDPOINT,check=False).returncode==0
        print("EXP058_STACK_INGRESS_BYPASS=PASS")

        ns(HOST,"ip","route","add","table",TABLE,f"{ENDPOINT}/32","via",STACK_IP,"dev",HS,"proto","203")
        exact_managed=route_get(ENDPOINT,"mark",MARK)
        exact_stack=route_get(ENDPOINT,"from",STACK_IP,"iif",HS)
        assert exact_managed.get("dev")==HS,exact_managed
        assert exact_stack.get("dev")==HU and exact_stack.get("gateway")==GW_IP,exact_stack
        print("EXP058_EXACT_ENDPOINT_DIRECTION_DISAMBIGUATION=PASS")

        ns(HOST,"nft","delete","table","inet","exp058")
        ns(HOST,"ip","rule","del","priority",RULE_PRIO)
        ns(HOST,"ip","route","flush","table",TABLE)
        ordinary=route_get(ENDPOINT)
        assert ordinary.get("dev")==HU and ordinary.get("gateway")==GW_IP,ordinary
        main_after=json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)
        assert main_after==main_before,(main_before,main_after)
        print("EXP058_CLEANUP_MAIN_IDENTICAL=PASS")
        print("EXP058_RESULT=PASS")
        return 0
    finally:
        for name in (STATIC,LAN,GW,STACK,HOST): delete_ns(name)

if __name__=="__main__":
    raise SystemExit(main())
