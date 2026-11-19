#!/usr/bin/env python3
import json
import os
import statistics
import subprocess
import sys
import time

H="e71h"; S="e71s"; A="e71a"; B="e71b"
HA="e71ha"; AH="e71ah"; SB="e71sb"; BS="e71bs"
BH="vpng0"; BSIDE="stack0"
SRC="192.0.2.2"; HIP="192.0.2.1"; SIP="198.51.100.1"; DST="198.51.100.2"
P_H="169.254.71.1"; P_S="169.254.71.2"

def run(*args, check=True, capture=True):
    return subprocess.run(args, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)

def ns(n,*args,check=True,capture=True):
    return run("ip","netns","exec",n,*args,check=check,capture=capture)

def cleanup():
    for n in (B,A,S,H):
        run("ip","netns","del",n,check=False)

def pair(n1,if1,n2,if2):
    run("ip","link","add",if1,"type","veth","peer","name",if2)
    run("ip","link","set",if1,"netns",n1)
    run("ip","link","set",if2,"netns",n2)

def base():
    cleanup()
    for n in (H,S,A,B):
        run("ip","netns","add",n)
        ns(n,"ip","link","set","lo","up")
    pair(H,HA,A,AH)
    pair(S,SB,B,BS)
    ns(H,"ip","addr","add",f"{HIP}/24","dev",HA)
    ns(A,"ip","addr","add",f"{SRC}/24","dev",AH)
    ns(S,"ip","addr","add",f"{SIP}/24","dev",SB)
    ns(B,"ip","addr","add",f"{DST}/24","dev",BS)
    for n,i in ((H,HA),(A,AH),(S,SB),(B,BS)):
        ns(n,"ip","link","set",i,"up")
    ns(H,"sysctl","-qw","net.ipv4.ip_forward=1")
    ns(S,"sysctl","-qw","net.ipv4.ip_forward=1")
    for n,i in ((H,"all"),(H,"default"),(H,HA),(S,"all"),(S,"default"),(S,SB)):
        ns(n,"sysctl","-qw",f"net.ipv4.conf.{i}.rp_filter=0")
    ns(A,"ip","route","replace","198.51.100.0/24","via",HIP,"dev",AH)
    ns(B,"ip","route","replace","192.0.2.0/24","via",SIP,"dev",BS)

def setup_boundary(kind):
    if kind == "netkit":
        r=ns(H,"ip","link","add",BH,"type","netkit","mode","l3","forward","peer","forward",BSIDE,check=False)
        if r.returncode:
            raise RuntimeError("netkit unsupported: "+(r.stderr or r.stdout).strip())
        ns(H,"ip","link","set",BSIDE,"netns",S)
        ns(H,"ip","link","set",BH,"up")
        ns(S,"ip","link","set",BSIDE,"up")
        ns(H,"ip","route","replace","198.51.100.0/24","dev",BH)
        ns(S,"ip","route","replace","192.0.2.0/24","dev",BSIDE)
    elif kind in ("veth_proxy","veth_via"):
        pair(H,BH,S,BSIDE)
        ns(H,"ip","link","set",BH,"up")
        ns(S,"ip","link","set",BSIDE,"up")
        for n,i in ((H,BH),(S,BSIDE)):
            ns(n,"sysctl","-qw",f"net.ipv4.conf.{i}.rp_filter=0")
        if kind == "veth_proxy":
            ns(H,"sysctl","-qw",f"net.ipv4.conf.{BH}.proxy_arp=1")
            ns(S,"sysctl","-qw",f"net.ipv4.conf.{BSIDE}.proxy_arp=1")
            ns(H,"ip","route","replace","198.51.100.0/24","dev",BH)
            ns(S,"ip","route","replace","192.0.2.0/24","dev",BSIDE)
        else:
            ns(H,"ip","addr","add",f"{P_H}/30","dev",BH)
            ns(S,"ip","addr","add",f"{P_S}/30","dev",BSIDE)
            ns(H,"ip","route","replace","198.51.100.0/24","via",P_S,"dev",BH)
            ns(S,"ip","route","replace","192.0.2.0/24","via",P_H,"dev",BSIDE)
    else:
        raise ValueError(kind)

def ping():
    r=ns(A,"ping","-n","-c","2","-W","2",DST,check=False)
    return r.returncode == 0

def procstat():
    with open("/proc/stat") as f:
        p=f.readline().split()[1:]
    nums=list(map(int,p))
    idle=nums[3]+nums[4]
    total=sum(nums)
    return total,idle

def iperf_once(streams, reverse):
    server=subprocess.Popen(["ip","netns","exec",B,"iperf3","-s","-1","-J"],
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    time.sleep(0.15)
    cmd=["ip","netns","exec",A,"iperf3","-c",DST,"-t","3","-O","1","-P",str(streams),"-J"]
    if reverse:
        cmd.append("-R")
    t0,i0=procstat()
    cp=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    t1,i1=procstat()
    sout,serr=server.communicate(timeout=10)
    if cp.returncode:
        raise RuntimeError("iperf client failed: "+cp.stderr)
    doc=json.loads(cp.stdout)
    end=doc["end"]
    summary=end.get("sum_received") or end.get("sum") or end.get("sum_sent")
    bps=float(summary["bits_per_second"])
    cpu=end.get("cpu_utilization_percent",{})
    dt=t1-t0; di=i1-i0
    system_busy=100.0*(dt-di)/dt if dt else 0.0
    return {
        "bps":bps,
        "gbps":bps/1e9,
        "client_cpu":float(cpu.get("host_total",0.0)),
        "remote_cpu":float(cpu.get("remote_total",0.0)),
        "system_busy":system_busy,
    }

def run_case(kind,streams,reverse,rep):
    base()
    setup_boundary(kind)
    if not ping():
        raise RuntimeError(f"{kind}: warm-up reachability failed")
    x=iperf_once(streams,reverse)
    print("EXP071_SAMPLE "
          f"backend={kind} streams={streams} reverse={int(reverse)} rep={rep} "
          f"gbps={x['gbps']:.3f} client_cpu={x['client_cpu']:.2f} "
          f"remote_cpu={x['remote_cpu']:.2f} system_busy={x['system_busy']:.2f}",
          flush=True)
    cleanup()
    return x

def main():
    if os.geteuid()!=0:
        print("EXP071_RESULT=SKIP root required")
        return 77
    print("EXP071_PREFLIGHT kernel="+run("uname","-r").stdout.strip(),flush=True)
    print("EXP071_PREFLIGHT ip="+run("ip","-V").stdout.strip(),flush=True)
    print("EXP071_PREFLIGHT iperf3="+run("iperf3","--version").stdout.splitlines()[0],flush=True)

    backends=["netkit","veth_proxy","veth_via"]
    results={}
    try:
        # Alternating order reduces monotonic runner/thermal bias.
        orders=[backends,list(reversed(backends)),backends]
        for streams in (1,4):
            for reverse in (False,True):
                for rep,order in enumerate(orders,1):
                    for kind in order:
                        results.setdefault((kind,streams,reverse),[]).append(
                            run_case(kind,streams,reverse,rep)
                        )

        for (kind,streams,reverse),vals in sorted(results.items()):
            med_g=statistics.median(v["gbps"] for v in vals)
            med_cc=statistics.median(v["client_cpu"] for v in vals)
            med_rc=statistics.median(v["remote_cpu"] for v in vals)
            med_sb=statistics.median(v["system_busy"] for v in vals)
            spread=max(v["gbps"] for v in vals)-min(v["gbps"] for v in vals)
            print("EXP071_MEDIAN "
                  f"backend={kind} streams={streams} reverse={int(reverse)} "
                  f"gbps={med_g:.3f} spread_gbps={spread:.3f} "
                  f"client_cpu={med_cc:.2f} remote_cpu={med_rc:.2f} system_busy={med_sb:.2f}",
                  flush=True)

        # Ratios are paired only at the aggregate median level; CI noise remains explicit.
        for streams in (1,4):
            for reverse in (False,True):
                n=statistics.median(v["gbps"] for v in results[("netkit",streams,reverse)])
                p=statistics.median(v["gbps"] for v in results[("veth_proxy",streams,reverse)])
                v=statistics.median(v["gbps"] for v in results[("veth_via",streams,reverse)])
                print("EXP071_RATIO "
                      f"streams={streams} reverse={int(reverse)} "
                      f"netkit_over_proxy={n/p:.3f} netkit_over_via={n/v:.3f} "
                      f"proxy_over_via={p/v:.3f}",flush=True)

        print("EXP071_RESULT=PASS",flush=True)
        return 0
    except Exception as e:
        print("EXP071_RESULT=FAIL",flush=True)
        print("EXP071_ERROR="+repr(e),flush=True)
        return 1
    finally:
        cleanup()

if __name__=="__main__":
    sys.exit(main())
