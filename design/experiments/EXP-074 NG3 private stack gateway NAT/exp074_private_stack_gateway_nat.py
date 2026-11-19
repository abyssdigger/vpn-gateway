#!/usr/bin/env python3
"""EXP-074: private Profile gateway NAT entirely inside STACK."""

from __future__ import annotations

import os
import subprocess
import textwrap

PID=os.getpid()
HOST=f"v74h-{PID}"
STACK=f"v74s-{PID}"
LAN=f"v74l-{PID}"
RA=f"v74a-{PID}"
RB=f"v74b-{PID}"
RC=f"v74c-{PID}"

BH="vpng0"; BS="stack0"
HL="lan0"; LH="lanpeer0"
SA="pa0"; AS="ra0"
SB="pb0"; BR="rb0"
SC="pc0"; CR="rc0"

SERVICE="198.19.74.2"
HOST_LAN="192.0.2.1"
LAN_IP="192.0.2.2"
A_IP="10.74.0.2"
B_IP="10.75.0.2"
C_IP="10.74.4.2"

def run(*args, input_text=None, check=True):
    return subprocess.run(args,input=input_text,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check)

def ns(name,*args,input_text=None,check=True):
    return run("ip","netns","exec",name,*args,input_text=input_text,check=check)

def add_ns(name):
    run("ip","netns","add",name)
    ns(name,"ip","link","set","lo","up")

def pair(a,b,na,nb):
    run("ip","link","add",a,"type","veth","peer","name",b)
    run("ip","link","set",a,"netns",na)
    run("ip","link","set",b,"netns",nb)

def cleanup():
    for name in (RC,RB,RA,LAN,STACK,HOST):
        run("ip","netns","del",name,check=False)

def setup():
    for name in (HOST,STACK,LAN,RA,RB,RC): add_ns(name)
    pair(BH,BS,HOST,STACK)
    pair(HL,LH,HOST,LAN)
    pair(SA,AS,STACK,RA)
    pair(SB,BR,STACK,RB)
    pair(SC,CR,STACK,RC)

    ns(STACK,"ip","addr","add",f"{SERVICE}/32","dev",BS)
    ns(HOST,"ip","addr","add",f"{HOST_LAN}/24","dev",HL)
    ns(LAN,"ip","addr","add",f"{LAN_IP}/24","dev",LH)

    ns(STACK,"ip","addr","add","172.31.74.1/30","dev",SA)
    ns(RA,"ip","addr","add","172.31.74.2/30","dev",AS)
    ns(RA,"ip","addr","add",f"{A_IP}/32","dev","lo")

    ns(STACK,"ip","addr","add","172.31.75.1/30","dev",SB)
    ns(RB,"ip","addr","add","172.31.75.2/30","dev",BR)
    ns(RB,"ip","addr","add",f"{B_IP}/32","dev","lo")

    ns(STACK,"ip","addr","add","172.31.76.1/30","dev",SC)
    ns(RC,"ip","addr","add","172.31.76.2/30","dev",CR)
    ns(RC,"ip","addr","add",f"{C_IP}/32","dev","lo")

    for name,ifs in (
        (HOST,(BH,HL)),(STACK,(BS,SA,SB,SC)),(LAN,(LH,)),
        (RA,(AS,)),(RB,(BR,)),(RC,(CR,))
    ):
        for iface in ifs: ns(name,"ip","link","set",iface,"up")

    for name in (HOST,STACK):
        ns(name,"sysctl","-qw","net.ipv4.ip_forward=1")
        ns(name,"sysctl","-qw","net.ipv4.conf.all.rp_filter=0")
        ns(name,"sysctl","-qw","net.ipv4.conf.default.rp_filter=0")
    ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{BH}.rp_filter=0")
    ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{BS}.rp_filter=0")
    ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{BH}.proxy_arp=1")
    ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{BS}.proxy_arp=1")

    ns(HOST,"ip","route","replace",f"{SERVICE}/32","dev",BH)
    ns(STACK,"ip","route","replace","default","dev",BS)
    ns(LAN,"ip","route","replace","default","via",HOST_LAN,"dev",LH)

    ns(STACK,"ip","route","replace",f"{A_IP}/32","via","172.31.74.2","dev",SA)
    ns(STACK,"ip","route","replace",f"{B_IP}/32","via","172.31.75.2","dev",SB)
    ns(STACK,"ip","route","replace",f"{C_IP}/32","via","172.31.76.2","dev",SC)
    for name,via,dev,src in (
        (RA,"172.31.74.1",AS,A_IP),
        (RB,"172.31.75.1",BR,B_IP),
        (RC,"172.31.76.1",CR,C_IP),
    ):
        ns(name,"ip","route","replace","default","via",via,"dev",dev,"src",src)

    # Only route-return support on the VPN-GATE host itself; LAN learns nothing.
    ns(HOST,"ip","route","replace","10.74.0.0/16","dev",BH)
    ns(HOST,"ip","route","replace","10.75.0.0/16","dev",BH)

    nft=textwrap.dedent(f"""
    table ip exp074 {{
      chain forward {{
        type filter hook forward priority filter; policy accept;
      }}
      chain postrouting {{
        type nat hook postrouting priority srcnat; policy accept;

        # Host-local destination exclusion: +snat is gateway forwarding behavior,
        # not host-local behavior.
        oifname "{BS}" ip daddr {HOST_LAN} return comment "exp074-host-local-exclude"

        # C is a more-specific no-NAT exception inside A's broad source domain.
        oifname "{BS}" iifname "{SC}" ip saddr {C_IP} return comment "exp074-c-no-nat"

        oifname "{BS}" iifname "{SA}" ip saddr {A_IP} counter masquerade comment "exp074-a-nat"
        oifname "{BS}" iifname "{SB}" ip saddr {B_IP} counter masquerade comment "exp074-b-nat"
      }}
    }}
    """)
    ns(STACK,"nft","-f","-",input_text=nft)

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
src=sys.argv[1]; dst=sys.argv[2]; port=int(sys.argv[3]); payload=sys.argv[4].encode()
s=socket.socket(); s.settimeout(5); s.bind((src,0)); s.connect((dst,port)); s.sendall(payload)
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
    out,err=p.communicate(timeout=8)
    assert p.returncode==0,(out,err)
    assert marker in out,out
    return out

def flow(remote,src,dst,port,tag):
    server_ns = LAN if dst==LAN_IP else HOST
    p=start_server(server_ns,dst,port,tag)
    c=ns(remote,"python3","-c",TCP_CLIENT,src,dst,str(port),tag.lower())
    assert f"DATA=ACK:{tag.lower()}" in c.stdout,c.stdout
    return finish_server(p,f"{tag}_PEER")

def counter(comment):
    raw=ns(STACK,"nft","list","chain","ip","exp074","postrouting").stdout
    for line in raw.splitlines():
        if f'comment "{comment}"' in line and "counter packets" in line:
            return int(line.split("counter packets ",1)[1].split()[0])
    raise AssertionError((comment,raw))

def main():
    if os.geteuid()!=0:
        print("EXP074_RESULT=SKIP root required"); return 77
    cleanup()
    try:
        setup()
        lan_routes=ns(LAN,"ip","-4","route","show").stdout
        assert "default via 192.0.2.1" in lan_routes,lan_routes
        assert SERVICE not in lan_routes and "10.74." not in lan_routes and "10.75." not in lan_routes,lan_routes
        print("EXP074_LAN_NO_SPECIAL_RETURN_ROUTE=PASS",flush=True)

        a=flow(RA,A_IP,LAN_IP,18741,"A")
        assert f"A_PEER={SERVICE}:" in a,a
        print("EXP074_PROFILE_A_STACK_SNAT=PASS",flush=True)

        b=flow(RB,B_IP,LAN_IP,18742,"B")
        assert f"B_PEER={SERVICE}:" in b,b
        print("EXP074_PROFILE_B_STACK_SNAT=PASS",flush=True)

        ca=counter("exp074-a-nat"); cb=counter("exp074-b-nat")
        assert ca==1 and cb==1,(ca,cb)

        c_before=(counter("exp074-a-nat"),counter("exp074-b-nat"))
        c=flow(RC,C_IP,LAN_IP,18743,"C")
        assert f"C_PEER={C_IP}:" in c,c
        c_after=(counter("exp074-a-nat"),counter("exp074-b-nat"))
        assert c_before==c_after,(c_before,c_after)
        print("EXP074_PROFILE_C_NO_SNAT=PASS",flush=True)

        before=counter("exp074-a-nat")
        h=flow(RA,A_IP,HOST_LAN,18744,"HOST")
        assert f"HOST_PEER={A_IP}:" in h,h
        after=counter("exp074-a-nat")
        assert before==after,(before,after)
        print("EXP074_HOST_LOCAL_NOT_SNAT=PASS",flush=True)

        print("EXP074_RESULT=PASS",flush=True)
        return 0
    finally:
        cleanup()

if __name__=="__main__":
    raise SystemExit(main())
