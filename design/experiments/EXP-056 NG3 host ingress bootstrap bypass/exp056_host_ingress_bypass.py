#!/usr/bin/env python3
"""EXP-056: dedicated host bootstrap table with managed-ingress main bypass."""

from __future__ import annotations

import json
import os
import subprocess


PID=os.getpid()
HOST=f"v56h-{PID}"; STACK=f"v56s-{PID}"; GW=f"v56g-{PID}"; LAN=f"v56l-{PID}"
HS="e56hs"; SH="e56sh"; HU="e56hu"; GU="e56gu"; HL="e56hl"; LH="e56lh"
HOST_STACK="10.255.0.1"; STACK_IP="10.255.0.2"
HOST_UP="192.0.2.1"; GW_IP="192.0.2.2"; ENDPOINT="198.51.100.10"
HOST_LAN="10.0.0.1"; LAN_IP="10.0.0.2"
TABLE="2056"; BYPASS_PRIO="1000"; CAPTURE_PRIO="1100"


def run(*args,check=True):
    return subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check)


def ns(name,*args,check=True):
    return run("ip","netns","exec",name,*args,check=check)


def add_ns(name):
    run("ip","netns","add",name); ns(name,"ip","link","set","lo","up")


def delete_ns(name):
    run("ip","netns","del",name,check=False)


def lookup(*extra):
    raw=ns(HOST,"ip","-j","-4","route","get",ENDPOINT,*extra).stdout
    rows=json.loads(raw); assert len(rows)==1,raw
    return rows[0]


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
    ns(HOST,"sysctl","-q","-w","net.ipv4.ip_forward=1")

    ns(HOST,"ip","route","add","table",TABLE,"default","via",STACK_IP,"dev",HS,"proto","203")
    ns(HOST,"ip","rule","add","priority",BYPASS_PRIO,"iif",HS,"lookup","main")
    ns(HOST,"ip","rule","add","priority",CAPTURE_PRIO,"to","0.0.0.0/0","lookup",TABLE)


def main():
    try:
        setup()
        main_routes=json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)
        assert any(row.get("dst","default")=="default" and row.get("gateway")==GW_IP for row in main_routes)
        assert not any(row.get("protocol") in (203,"203") for row in main_routes)
        print("EXP056_MAIN_UNTOUCHED=PASS")

        local=lookup()
        assert local.get("dev")==HS and local.get("gateway")==STACK_IP,local
        print("EXP056_LOCAL_CAPTURE=PASS")

        forwarded=lookup("from",LAN_IP,"iif",HL)
        assert forwarded.get("dev")==HS and forwarded.get("gateway")==STACK_IP,forwarded
        print("EXP056_ORDINARY_FORWARDED_CAPTURE=PASS")

        from_stack=lookup("from",STACK_IP,"iif",HS)
        assert from_stack.get("dev")==HU and from_stack.get("gateway")==GW_IP,from_stack
        print("EXP056_STACK_INGRESS_BYPASS=PASS")

        exact=json.loads(ns(HOST,"ip","-j","-4","route","show","table","main").stdout)
        assert not any(row.get("dst") in (ENDPOINT,f"{ENDPOINT}/32") for row in exact)
        ping=ns(STACK,"ping","-c","1","-W","1",ENDPOINT,check=False)
        assert ping.returncode==0,(ping.stdout,ping.stderr)
        print("EXP056_DYNAMIC_UNDERLAY_REACHABLE_WITHOUT_PIN=PASS")

        # Exact /32 capture is still directionally disambiguated by the iif bypass.
        ns(HOST,"ip","rule","del","priority",CAPTURE_PRIO)
        ns(HOST,"ip","rule","add","priority",CAPTURE_PRIO,"to",f"{ENDPOINT}/32","lookup",TABLE)
        local_exact=lookup()
        stack_exact=lookup("from",STACK_IP,"iif",HS)
        assert local_exact.get("dev")==HS,local_exact
        assert stack_exact.get("dev")==HU and stack_exact.get("gateway")==GW_IP,stack_exact
        assert ns(STACK,"ping","-c","1","-W","1",ENDPOINT,check=False).returncode==0
        print("EXP056_EXACT_ENDPOINT_DIRECTION_DISAMBIGUATION=PASS")

        print("EXP056_RESULT=PASS")
        return 0
    finally:
        for name in (LAN,GW,STACK,HOST): delete_ns(name)


if __name__=="__main__":
    raise SystemExit(main())
