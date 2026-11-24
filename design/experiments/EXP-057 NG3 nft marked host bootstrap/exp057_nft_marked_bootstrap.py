#!/usr/bin/env python3
"""EXP-057: nft mark classifier + one host boundary table/rule."""

from __future__ import annotations

import json
import os
import subprocess


PID=os.getpid()
HOST=f"v57h-{PID}"; STACK=f"v57s-{PID}"; GW=f"v57g-{PID}"; LAN=f"v57l-{PID}"
HS="e57hs"; SH="e57sh"; HU="e57hu"; GU="e57gu"; HL="e57hl"; LH="e57lh"
HOST_STACK="10.255.0.1"; STACK_IP="10.255.0.2"
HOST_UP="192.0.2.1"; GW_IP="192.0.2.2"; ENDPOINT="198.51.100.10"
HOST_LAN="10.0.0.1"; LAN_IP="10.0.0.2"
TABLE="2057"; RULE_PRIO="1000"; MARK="0x57"


def run(*args,check=True,input_text=None):
    return subprocess.run(
        args,input=input_text,text=True,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check
    )


def ns(name,*args,check=True,input_text=None):
    return run("ip","netns","exec",name,*args,check=check,input_text=input_text)


def add_ns(name):
    run("ip","netns","add",name); ns(name,"ip","link","set","lo","up")


def delete_ns(name):
    run("ip","netns","del",name,check=False)


def link_packets(name,dev):
    rows=json.loads(ns(name,"ip","-s","-j","link","show","dev",dev).stdout)
    assert len(rows)==1
    stats=rows[0]["stats64"]
    return stats["rx"]["packets"],stats["tx"]["packets"]


def main_routes():
    return json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)


def setup():
    for name in (HOST,STACK,GW,LAN): add_ns(name)
    for a,b,na,nb in ((HS,SH,HOST,STACK),(HU,GU,HOST,GW),(HL,LH,HOST,LAN)):
        run("ip","link","add",a,"type","veth","peer","name",b)
        run("ip","link","set",a,"netns",na); run("ip","link","set",b,"netns",nb)
    ns(HOST,"ip","addr","add",f"{HOST_STACK}/30","dev",HS); ns(HOST,"ip","link","set",HS,"up")
    ns(STACK,"ip","addr","add",f"{STACK_IP}/30","dev",SH); ns(STACK,"ip","link","set",SH,"up")
    ns(HOST,"ip","addr","add",f"{HOST_UP}/30","dev",HU); ns(HOST,"ip","link","set",HU,"up")
    ns(GW,"ip","addr","add",f"{GW_IP}/30","dev",GU); ns(GW,"ip","link","set",GU,"up")
    ns(GW,"ip","addr","add",f"{ENDPOINT}/32","dev","lo")
    ns(HOST,"ip","addr","add",f"{HOST_LAN}/24","dev",HL); ns(HOST,"ip","link","set",HL,"up")
    ns(LAN,"ip","addr","add",f"{LAN_IP}/24","dev",LH); ns(LAN,"ip","link","set",LH,"up")

    ns(HOST,"ip","route","add","default","via",GW_IP,"dev",HU)
    ns(STACK,"ip","route","add","default","via",HOST_STACK)
    ns(LAN,"ip","route","add","default","via",HOST_LAN)
    ns(GW,"ip","route","add","10.255.0.0/30","via",HOST_UP)
    ns(GW,"ip","route","add","10.0.0.0/24","via",HOST_UP)
    ns(HOST,"sysctl","-q","-w","net.ipv4.ip_forward=1")
    ns(STACK,"sysctl","-q","-w","net.ipv4.ip_forward=1")

    ns(HOST,"ip","route","add","table",TABLE,"default","via",STACK_IP,"dev",HS,"proto","203")
    ns(HOST,"ip","rule","add","priority",RULE_PRIO,"fwmark",MARK,"lookup",TABLE)

    nft=f"""
table inet exp057 {{
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
        routes=main_routes()
        assert any(row.get("dst","default")=="default" and row.get("gateway")==GW_IP for row in routes)
        assert not any(row.get("protocol") in (203,"203") for row in routes)
        assert not any(row.get("dst") in (ENDPOINT,f"{ENDPOINT}/32") for row in routes)
        print("EXP057_MAIN_UNTOUCHED_NO_PIN=PASS")

        before=link_packets(STACK,SH)
        host_ping=ns(HOST,"ping","-c","1","-W","1",ENDPOINT,check=False)
        assert host_ping.returncode==0,(host_ping.stdout,host_ping.stderr)
        after=link_packets(STACK,SH)
        assert after[0]>before[0] and after[1]>before[1],(before,after)
        print("EXP057_HOST_LOCAL_CAPTURE_THROUGH_STACK=PASS")

        before=link_packets(STACK,SH)
        lan_ping=ns(LAN,"ping","-c","1","-W","1",ENDPOINT,check=False)
        assert lan_ping.returncode==0,(lan_ping.stdout,lan_ping.stderr)
        after=link_packets(STACK,SH)
        assert after[0]>before[0] and after[1]>before[1],(before,after)
        print("EXP057_ORDINARY_FORWARDED_CAPTURE_THROUGH_STACK=PASS")

        stack_ping=ns(STACK,"ping","-c","1","-W","1",ENDPOINT,check=False)
        assert stack_ping.returncode==0,(stack_ping.stdout,stack_ping.stderr)
        print("EXP057_STACK_UNDERLAY_BYPASS_WITHOUT_PIN=PASS")

        marked=json.loads(ns(HOST,"ip","-j","-4","route","get",ENDPOINT,"mark",MARK).stdout)[0]
        from_stack=json.loads(
            ns(HOST,"ip","-j","-4","route","get",ENDPOINT,"from",STACK_IP,"iif",HS).stdout
        )[0]
        assert marked.get("dev")==HS and marked.get("gateway")==STACK_IP,marked
        assert from_stack.get("dev")==HU and from_stack.get("gateway")==GW_IP,from_stack
        print("EXP057_EXACT_ENDPOINT_DIRECTION_DISAMBIGUATION=PASS")

        ns(HOST,"nft","delete","table","inet","exp057")
        ns(HOST,"ip","rule","del","priority",RULE_PRIO)
        ns(HOST,"ip","route","del","table",TABLE,"default","via",STACK_IP,"dev",HS,"proto","203")
        ordinary=json.loads(ns(HOST,"ip","-j","-4","route","get",ENDPOINT).stdout)[0]
        assert ordinary.get("dev")==HU and ordinary.get("gateway")==GW_IP,ordinary
        print("EXP057_CLEANUP_RESTORES_ORDINARY=PASS")

        print("EXP057_RESULT=PASS")
        return 0
    finally:
        for name in (LAN,GW,STACK,HOST): delete_ns(name)


if __name__=="__main__":
    raise SystemExit(main())
