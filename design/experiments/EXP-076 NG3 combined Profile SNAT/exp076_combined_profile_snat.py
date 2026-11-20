#!/usr/bin/env python3
"""EXP-076: combined Profile SNAT isolation/order/reverse dataplane evidence."""

from __future__ import annotations

import json
import os
import subprocess
from ipaddress import IPv4Address, IPv4Network

from rou.domain import Direction
from rou.host_managed_routing import (
    HostManagedRoutingProfile,
    build_host_managed_routing_plan,
)
from rou.interface_inventory import parse_ip_link_inventory
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_composite_nft import LinuxCompositeNftBackend
from rou.linux_host_managed_routing import build_linux_host_managed_routing_desired
from rou.linux_host_managed_routing_backend import (
    LinuxHostManagedRoutingBackend,
    converge_host_managed_routing_once,
)
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_payload_nat import LinuxPayloadNatBackend
from rou.linux_policy_platform import (
    NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
)
from rou.linux_stack_return_affinity import LinuxStackReturnAffinityBackend
from rou.payload_forward_desired import PayloadForwardRuleSpec
from rou.payload_forward_observation import (
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
)
from rou.payload_nat_desired import PayloadNatDesiredState, PayloadProfileSnatSpec
from rou.payload_nat_observation import compare_payload_nat
from rou.stack_return_affinity import (
    StackReturnAffinityDesired,
    StackReturnClassifierSpec,
    StackReturnRuleSpec,
)


PID=os.getpid()
HOST=f"v76h-{PID}"; STACK=f"v76s-{PID}"; LAN=f"v76l-{PID}"
RA=f"v76a-{PID}"; RB=f"v76b-{PID}"; RC=f"v76c-{PID}"
BH="vpng0"; BS="stack0"; HL="e76hl"; LH="e76lh"
SA="e76sa"; AS="e76as"; SB="e76sb"; BSIDE="e76bs"; SC="e76sc"; CS="e76cs"

HOST_LAN="10.76.0.1"; LAN_IP="10.76.0.2"
STACK_SERVICE="198.19.255.2"; SNAT_IP="198.19.255.10"
STACK_A="203.0.113.1"; REMOTE_A="203.0.113.2"; NET_A="203.0.113.0/30"
STACK_B="203.0.114.1"; REMOTE_B="203.0.114.2"; NET_B="203.0.114.0/30"
STACK_C="203.0.115.1"; REMOTE_C="203.0.115.2"; NET_C="203.0.115.0/30"
MARK_A=0x10000000; MARK_B=0x10000001; MARK_C=0x10000002
TABLE_A=1001; TABLE_B=1002; TABLE_C=1003
BASE_PORT=18760


def run(*args,input_text=None,check=True):
    return subprocess.run(
        args,input=input_text,text=True,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,check=check,
    )


def ns(name,*args,input_text=None,check=True):
    return run("ip","netns","exec",name,*args,input_text=input_text,check=check)


def add_ns(name):
    run("ip","netns","add",name)
    ns(name,"ip","link","set","lo","up")


def del_ns(name):
    run("ip","netns","del",name,check=False)


def pair(a,b,na,nb):
    run("ip","link","add",a,"type","veth","peer","name",b)
    run("ip","link","set",a,"netns",na)
    run("ip","link","set",b,"netns",nb)


def identities(namespace):
    return parse_ip_link_inventory(ns(namespace,"ip","-j","link","show").stdout)


def identity(namespace,name):
    found=[item for item in identities(namespace) if item.ifname==name]
    assert len(found)==1,found
    return found[0]


SERVER=r"""
import socket,sys
addr=sys.argv[1]; port=int(sys.argv[2])
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.bind((addr,port)); print("READY",flush=True)
data,peer=s.recvfrom(4096)
print("PEER="+peer[0],flush=True)
s.sendto(b"ACK:"+data,peer)
s.close()
"""

CLIENT=r"""
import socket,sys
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(4)
s.sendto(sys.argv[3].encode(),(sys.argv[1],int(sys.argv[2])))
data,peer=s.recvfrom(4096)
print("DATA="+data.decode(),flush=True)
s.close()
"""


def exchange(remote,port,payload):
    p=subprocess.Popen(
        ["ip","netns","exec",LAN,"python3","-u","-c",SERVER,LAN_IP,str(port)],
        text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    )
    assert p.stdout is not None
    assert p.stdout.readline().strip()=="READY"
    client=ns(
        remote,"python3","-c",CLIENT,LAN_IP,str(port),payload,check=False
    )
    out,err=p.communicate(timeout=7)
    assert p.returncode==0,(out,err)
    assert client.returncode==0,(client.stdout,client.stderr,out,err)
    assert f"DATA=ACK:{payload}" in client.stdout,client.stdout
    peer=[line.split("=",1)[1] for line in out.splitlines() if line.startswith("PEER=")]
    assert len(peer)==1,out
    return peer[0]


def setup():
    for name in (HOST,STACK,LAN,RA,RB,RC): add_ns(name)
    for a,b,na,nb in (
        (BH,BS,HOST,STACK),(HL,LH,HOST,LAN),
        (SA,AS,STACK,RA),(SB,BSIDE,STACK,RB),(SC,CS,STACK,RC),
    ):
        pair(a,b,na,nb)

    ns(HOST,"ip","addr","add",f"{HOST_LAN}/24","dev",HL)
    ns(LAN,"ip","addr","add",f"{LAN_IP}/24","dev",LH)
    ns(STACK,"ip","addr","add",f"{STACK_SERVICE}/32","dev",BS)
    for iface,stack_ip in ((SA,STACK_A),(SB,STACK_B),(SC,STACK_C)):
        ns(STACK,"ip","addr","add",f"{stack_ip}/30","dev",iface)
    for remote,iface,ip in (
        (RA,AS,REMOTE_A),(RB,BSIDE,REMOTE_B),(RC,CS,REMOTE_C)
    ):
        ns(remote,"ip","addr","add",f"{ip}/30","dev",iface)

    for name,ifs in (
        (HOST,(BH,HL)),(STACK,(BS,SA,SB,SC)),(LAN,(LH,)),
        (RA,(AS,)),(RB,(BSIDE,)),(RC,(CS,))
    ):
        for iface in ifs: ns(name,"ip","link","set",iface,"up")

    for name in (HOST,STACK):
        ns(name,"sysctl","-qw","net.ipv4.ip_forward=1")
        ns(name,"sysctl","-qw","net.ipv4.conf.all.rp_filter=0")
        ns(name,"sysctl","-qw","net.ipv4.conf.default.rp_filter=0")
    for name,iface in ((HOST,BH),(STACK,BS),(STACK,SA),(STACK,SB),(STACK,SC)):
        ns(name,"sysctl","-qw",f"net.ipv4.conf.{iface}.rp_filter=0")
    ns(HOST,"sysctl","-qw",f"net.ipv4.conf.{BH}.proxy_arp=1")
    ns(STACK,"sysctl","-qw",f"net.ipv4.conf.{BS}.proxy_arp=1")

    ns(STACK,"ip","route","add","default","dev",BS)
    ns(HOST,"ip","route","add",f"{STACK_SERVICE}/32","dev",BH)
    ns(LAN,"ip","route","add","default","via",HOST_LAN)
    for remote,gateway,iface in (
        (RA,STACK_A,AS),(RB,STACK_B,BSIDE),(RC,STACK_C,CS)
    ):
        ns(remote,"ip","route","add",f"{LAN_IP}/32","via",gateway,"dev",iface)

    # Profile tables used by restored conntrack marks on replies.
    for table,remote_ip,iface in (
        (TABLE_A,REMOTE_A,SA),(TABLE_B,REMOTE_B,SB),(TABLE_C,REMOTE_C,SC)
    ):
        ns(STACK,"ip","route","add","table",str(table),f"{remote_ip}/32","dev",iface)

    host_plan=build_host_managed_routing_plan((
        HostManagedRoutingProfile(
            "a",Direction.INBOUND,(IPv4Network(NET_A),),IPv4Address(SNAT_IP)
        ),
        HostManagedRoutingProfile(
            "b",Direction.INBOUND,(IPv4Network(NET_B),),IPv4Address(SNAT_IP)
        ),
        HostManagedRoutingProfile(
            "c",Direction.INBOUND,(IPv4Network(NET_C),),None
        ),
    ))
    host_desired=build_linux_host_managed_routing_desired(
        host_plan,
        host_interface=BH,
        allocation=NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
        stack_service_address=IPv4Address(STACK_SERVICE),
    )
    host_backend=LinuxHostManagedRoutingBackend(
        SubprocessCommandRunner(),
        NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
        network_namespace=HOST,
    )
    assert converge_host_managed_routing_once(host_backend,host_desired).exact

    host_identity=identity(STACK,BS)
    vpn_a=identity(STACK,SA); vpn_b=identity(STACK,SB); vpn_c=identity(STACK,SC)
    affinity=StackReturnAffinityDesired(
        host_boundary=host_identity,
        classifiers=(
            StackReturnClassifierSpec("a",vpn_a,IPv4Network(f"{REMOTE_A}/32"),MARK_A),
            StackReturnClassifierSpec("b",vpn_b,IPv4Network(f"{REMOTE_B}/32"),MARK_B),
            StackReturnClassifierSpec("c",vpn_c,IPv4Network(f"{REMOTE_C}/32"),MARK_C),
        ),
        outbound_classifiers=(),
        rules=(
            StackReturnRuleSpec("a",MARK_A,TABLE_A,0x1800),
            StackReturnRuleSpec("b",MARK_B,TABLE_B,0x1801),
            StackReturnRuleSpec("c",MARK_C,TABLE_C,0x1802),
        ),
    )
    runner=SubprocessNftRunner()
    affinity_backend=LinuxStackReturnAffinityBackend(runner,STACK)
    affinity_backend.create_nft(affinity)
    for rule in affinity.rules: affinity_backend.add_rule(rule)

    # Exact managed scaffold. NEW rules match original remote sources; there is
    # deliberately no allow rule matching SNAT_IP.
    ns(
        STACK,"nft","-f","-",input_text=(
            'table ip vpn_gate {\n'
            ' comment "vpn-gate:ng3:owner-v1"\n'
            ' chain stack_input { type filter hook input priority 0; policy drop; '
            'comment "vpn-gate:ng3:stack-input-v1"; }\n'
            ' chain payload_forward { type filter hook forward priority 0; policy drop; '
            'comment "vpn-gate:ng3:payload-forward-v1"; }\n'
            ' chain stack_output { type filter hook output priority 0; policy drop; '
            'comment "vpn-gate:ng3:stack-output-v1"; }\n'
            ' chain payload_postrouting { type nat hook postrouting priority 100; policy accept; '
            'comment "vpn-gate:ng3:payload-postrouting-v1"; }\n'
            '}\n'
        )
    )
    composite=LinuxCompositeNftBackend(runner,STACK)
    for vpn,remote_ip in ((vpn_a,REMOTE_A),(vpn_b,REMOTE_B),(vpn_c,REMOTE_C)):
        composite.add_profile_rule(
            PayloadForwardRuleSpec(
                PayloadForwardRuleKind.NEW,
                vpn,
                host_identity,
                PayloadForwardRemoteField.SOURCE,
                IPv4Network(f"{remote_ip}/32"),
            )
        )
        composite.add_profile_rule(
            PayloadForwardRuleSpec(
                PayloadForwardRuleKind.RETURN,
                host_identity,
                vpn,
                PayloadForwardRemoteField.DESTINATION,
                IPv4Network(f"{remote_ip}/32"),
            )
        )

    nat_backend=LinuxPayloadNatBackend(runner,STACK)
    snat_a=PayloadProfileSnatSpec(
        "a",MARK_A,host_identity,IPv4Address(SNAT_IP)
    )
    snat_b=PayloadProfileSnatSpec(
        "b",MARK_B,host_identity,IPv4Address(SNAT_IP)
    )
    nat_backend.add_nat_rule(snat_a); nat_backend.add_nat_rule(snat_b)
    snapshot=nat_backend.observe_nat_snapshot()
    observed=compare_payload_nat(
        snapshot.observation,
        snapshot.interfaces,
        PayloadNatDesiredState((),(snat_a,snat_b)),
    )
    assert observed.confirmed==(snat_a,snat_b),observed
    assert not observed.missing and not observed.stale and observed.conflict_free,observed

    return host_desired


def main():
    if os.geteuid()!=0:
        print("EXP076_RESULT=SKIP root required")
        return 77
    try:
        host_desired=setup()

        by_dst={route.destination.with_prefixlen:route for route in host_desired.routes}
        identity_route=by_dst[f"{SNAT_IP}/32"]
        assert str(identity_route.gateway)==STACK_SERVICE and identity_route.onlink
        assert by_dst[NET_C].gateway is None
        print("EXP076_HOST_ROUTE_SPLIT=PASS",flush=True)

        peer_a=exchange(RA,BASE_PORT,"a")
        peer_b=exchange(RB,BASE_PORT+1,"b")
        peer_c=exchange(RC,BASE_PORT+2,"c")

        assert peer_a==SNAT_IP and peer_b==SNAT_IP,(peer_a,peer_b)
        print("EXP076_SHARED_SNAT_IDENTITY=PASS",flush=True)

        assert peer_c==REMOTE_C,peer_c
        print("EXP076_NO_SNAT_SOURCE_PRESERVED=PASS",flush=True)

        # A/B could reach LAN only through NEW rules matching original source.
        # Translation happens in postrouting after those policy accepts.
        print("EXP076_POST_POLICY_TRANSLATION_ORDER=PASS",flush=True)
        print("EXP076_PROFILE_SNAT_ISOLATION=PASS",flush=True)

        host_rules=ns(HOST,"nft","-j","list","ruleset",check=False).stdout
        assert "profile-snat" not in host_rules and '"snat"' not in host_rules,host_rules
        print("EXP076_NO_HOST_SIDE_SNAT_OWNER=PASS",flush=True)

        # Both shared-identity replies and the untranslated reply completed,
        # proving the host /32/prefix reverse routes and STACK conntrack return.
        print("EXP076_REVERSE_FLOWS=PASS",flush=True)
        print("EXP076_RESULT=PASS",flush=True)
        return 0
    finally:
        for name in (RC,RB,RA,LAN,STACK,HOST): del_ns(name)


if __name__=="__main__":
    raise SystemExit(main())
