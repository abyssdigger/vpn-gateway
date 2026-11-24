#!/usr/bin/env python3
from __future__ import annotations
import json, os, subprocess

PID=os.getpid()
H=f"v80h-{PID}"; A=f"v80a-{PID}"; B=f"v80b-{PID}"; M=f"v80m-{PID}"; X=f"v80x-{PID}"; S=f"v80s-{PID}"
HA,AH="e80ha","e80ah"; HB,BH="e80hb","e80bh"; HM,MH="e80hm","e80mh"; HX,XH="e80hx","e80xh"; HS,SH="vpng0","stack0"
LAN_A="10.80.1.2"; LAN_B="10.80.2.2"; MAIN_GW="192.0.2.2"; ALT_GW="198.51.100.2"; TARGET="203.0.113.80"
HELPER=0x7FFF0004; ADMIN=180; PRESERVE=0x6003; DISPATCH=0x6004; ADMIN_PRIO=0x6500; EXIT=0x7000; PROTO=204

def run(*a,check=True): return subprocess.run(a,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check)
def ns(n,*a,check=True): return run("ip","netns","exec",n,*a,check=check)
def addns(n): run("ip","netns","add",n); ns(n,"ip","link","set","lo","up")
def pair(a,b,na,nb):
    run("ip","link","add",a,"type","veth","peer","name",b); run("ip","link","set",a,"netns",na); run("ip","link","set",b,"netns",nb)
def get(src,iif):
    rows=json.loads(ns(H,"ip","-j","-4","route","get",TARGET,"from",src,"iif",iif).stdout); assert len(rows)==1; return rows[0]
def clear():
    for p in (DISPATCH,PRESERVE): ns(H,"ip","rule","del","priority",str(p),"protocol",str(PROTO),check=False)

def setup():
    for n in (H,A,B,M,X,S): addns(n)
    for a,b,na,nb in ((HA,AH,H,A),(HB,BH,H,B),(HM,MH,H,M),(HX,XH,H,X),(HS,SH,H,S)): pair(a,b,na,nb)
    for n,addr,pfx,dev in ((H,"10.80.1.1",24,HA),(A,LAN_A,24,AH),(H,"10.80.2.1",24,HB),(B,LAN_B,24,BH),(H,"192.0.2.1",30,HM),(M,MAIN_GW,30,MH),(H,"198.51.100.1",30,HX),(X,ALT_GW,30,XH)):
        ns(n,"ip","addr","add",f"{addr}/{pfx}","dev",dev)
    for n,ifs in ((H,(HA,HB,HM,HX,HS)),(A,(AH,)),(B,(BH,)),(M,(MH,)),(X,(XH,)),(S,(SH,))):
        for d in ifs: ns(n,"ip","link","set",d,"up")
    ns(H,"ip","route","add",f"{TARGET}/32","via",MAIN_GW,"dev",HM)
    ns(H,"ip","route","add","table",str(ADMIN),f"{TARGET}/32","via",ALT_GW,"dev",HX)
    ns(H,"ip","rule","add","priority",str(ADMIN_PRIO),"iif",HB,"lookup",str(ADMIN))
    ns(H,"ip","route","add","table",str(HELPER),"default","dev",HS,"proto",str(PROTO))
    ns(H,"ip","rule","add","priority",str(EXIT),"protocol",str(PROTO),"type","nop")

def main():
    if os.geteuid()!=0: print("EXP080_RESULT=SKIP root required"); return 77
    try:
        setup()
        before=json.loads(ns(H,"ip","-j","-4","route","show","table","main").stdout)
        ns(H,"ip","rule","add","priority",str(PRESERVE),"protocol",str(PROTO),"lookup","main","suppress_prefixlength","0")
        ns(H,"ip","rule","add","priority",str(DISPATCH),"protocol",str(PROTO),"iif",HA,"lookup",str(HELPER))
        r=get(LAN_B,HB); assert r.get("dev")==HM and r.get("gateway")==MAIN_GW,r
        print("EXP080_GLOBAL_PRESERVE_INTERFERES=PASS",flush=True); clear()
        ns(H,"ip","rule","add","priority",str(PRESERVE),"protocol",str(PROTO),"iif",HA,"lookup","main","suppress_prefixlength","0")
        ns(H,"ip","rule","add","priority",str(DISPATCH),"protocol",str(PROTO),"iif",HA,"lookup",str(HELPER))
        r=get(LAN_B,HB); assert r.get("dev")==HX and r.get("gateway")==ALT_GW,r
        print("EXP080_UNSELECTED_ADMIN_POLICY_PRESERVED=PASS",flush=True)
        r=get(LAN_A,HA); assert r.get("dev")==HM and r.get("gateway")==MAIN_GW,r
        print("EXP080_SELECTED_MAIN_NONDEFAULT_WINS=PASS",flush=True)
        after=json.loads(ns(H,"ip","-j","-4","route","show","table","main").stdout); assert before==after
        print("EXP080_MAIN_UNTOUCHED=PASS",flush=True); print("EXP080_RESULT=PASS",flush=True); return 0
    finally:
        for n in (S,X,M,B,A,H): run("ip","netns","del",n,check=False)
if __name__=="__main__": raise SystemExit(main())
