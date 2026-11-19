#!/usr/bin/env python3
"""EXP-069: cross-netns stack -> managed-tambour metadata carrier survival."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import shutil
import subprocess
import time
from typing import Optional


PID = os.getpid()
REMOTE = f"vng69r-{PID}"
STACK = f"vng69s-{PID}"
HOST = f"vng69h-{PID}"
LAN = f"vng69l-{PID}"

R_S, S_R = "e69rs", "e69sr"
S_H, H_S = "e69sh", "e69hs"
H_L, L_H = "e69hl", "e69lh"

REMOTE_TRANSIT = "198.18.69.2"
STACK_REMOTE = "198.18.69.1"
STACK_HOST = "198.18.70.1"
HOST_STACK = "198.18.70.2"
HOST_LAN = "192.0.2.1"
LAN_IP = "192.0.2.2"
REMOTE_PAYLOAD = "10.69.0.2"

BASELINE_PORT = 16900
SURVIVAL_PORT = 16901
NEGATIVE_PORT = 16902
NAT_PORT_BASE = 16920
NAT_CONTROL_PORT_BASE = 17020
NAT_CLASS = "0x69f00001"


@dataclass(frozen=True)
class Candidate:
    name: str
    scope: str
    setter: str
    matcher: str
    phase_a_clear: Optional[str]
    phase_b_consume: Optional[str]
    setter_hook: str = "postrouting"
    setter_priority: int = -150
    on_wire: bool = False
    known_result: Optional[str] = None


CANDIDATES = (
    Candidate(
        "meta_mark", "packet-local",
        "meta mark set 0x69010001", "meta mark 0x69010001",
        "meta mark set 0", f"ct mark set {NAT_CLASS} meta mark set 0",
        known_result="EXP-063 known negative",
    ),
    Candidate(
        "meta_priority", "packet-local",
        "meta priority set 0x6902", "meta priority 0x6902",
        "meta priority set 0", f"ct mark set {NAT_CLASS} meta priority set 0",
    ),
    Candidate(
        "meta_pkttype", "packet-local-derived",
        "meta pkttype set broadcast", "meta pkttype broadcast",
        "meta pkttype set host", f"ct mark set {NAT_CLASS} meta pkttype set host",
    ),
    Candidate(
        "meta_secmark", "packet-local",
        "meta secmark set 0x6903", "meta secmark 0x6903",
        "meta secmark set 0", f"ct mark set {NAT_CLASS} meta secmark set 0",
    ),
    Candidate(
        "meta_nftrace", "packet-local",
        "meta nftrace set 1", "meta nftrace 1",
        "meta nftrace set 0", f"ct mark set {NAT_CLASS} meta nftrace set 0",
    ),
    Candidate(
        "ct_mark", "conntrack-local",
        "ct mark set 0x69040001", "ct mark 0x69040001",
        "ct mark set 0", f"ct mark set {NAT_CLASS}",
    ),
    Candidate(
        "ct_label", "conntrack-local",
        "ct label set 69", "ct label 69",
        None, None,
    ),
    Candidate(
        "ct_secmark", "conntrack-local",
        "ct secmark set 0x6906", "ct secmark 0x6906",
        "ct secmark set 0", f"ct mark set {NAT_CLASS} ct secmark set 0",
    ),
    Candidate(
        "ct_zone", "conntrack-domain",
        "ct zone set 105", "ct zone 105",
        None, None, setter_hook="prerouting", setter_priority=-300,
    ),
    Candidate(
        "ipv4_dscp", "on-wire-control",
        "ip dscp set 0x2e", "ip dscp 0x2e",
        "ip dscp set 0", f"ct mark set {NAT_CLASS} ip dscp set 0",
        on_wire=True,
    ),
)


def run(*args: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        args, check=check, input=input_text, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def ns(name: str, *args: str, check: bool = True, input_text: str | None = None):
    return run("ip", "netns", "exec", name, *args, check=check, input_text=input_text)


def nft(name: str, text: str, check: bool = True):
    return ns(name, "nft", "-f", "-", check=check, input_text=text)


def add_ns(name: str):
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def del_ns(name: str):
    run("ip", "netns", "del", name, check=False)


def pair(left_ns: str, left_if: str, right_ns: str, right_if: str):
    run("ip", "link", "add", left_if, "type", "veth", "peer", "name", right_if)
    run("ip", "link", "set", left_if, "netns", left_ns)
    run("ip", "link", "set", right_if, "netns", right_ns)


def addr(name: str, interface: str, cidr: str):
    ns(name, "ip", "addr", "add", cidr, "dev", interface)
    ns(name, "ip", "link", "set", interface, "up")


def require_tools():
    for tool in ("ip", "nft", "python3"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"required command not found: {tool}")
    if os.geteuid() != 0:
        raise RuntimeError("EXP-069 must run as root")


def setup():
    for name in (REMOTE, STACK, HOST, LAN):
        add_ns(name)

    pair(REMOTE, R_S, STACK, S_R)
    pair(STACK, S_H, HOST, H_S)
    pair(HOST, H_L, LAN, L_H)

    addr(REMOTE, R_S, f"{REMOTE_TRANSIT}/30")
    addr(STACK, S_R, f"{STACK_REMOTE}/30")
    addr(STACK, S_H, f"{STACK_HOST}/30")
    addr(HOST, H_S, f"{HOST_STACK}/30")
    addr(HOST, H_L, f"{HOST_LAN}/30")
    addr(LAN, L_H, f"{LAN_IP}/30")
    ns(REMOTE, "ip", "addr", "add", f"{REMOTE_PAYLOAD}/32", "dev", "lo")

    ns(REMOTE, "ip", "route", "add", "192.0.2.0/30", "via", STACK_REMOTE, "dev", R_S, "src", REMOTE_PAYLOAD)
    ns(STACK, "ip", "route", "add", f"{REMOTE_PAYLOAD}/32", "via", REMOTE_TRANSIT, "dev", S_R)
    ns(STACK, "ip", "route", "add", "192.0.2.0/30", "via", HOST_STACK, "dev", S_H)
    ns(HOST, "ip", "route", "add", f"{REMOTE_PAYLOAD}/32", "via", STACK_HOST, "dev", H_S)
    ns(LAN, "ip", "route", "add", f"{REMOTE_PAYLOAD}/32", "via", HOST_LAN, "dev", L_H)

    for name in (STACK, HOST):
        ns(name, "sysctl", "-qw", "net.ipv4.ip_forward=1")
    for name, interfaces in (
        (STACK, ("all", "default", S_R, S_H)),
        (HOST, ("all", "default", H_S, H_L)),
    ):
        for interface in interfaces:
            ns(name, "sysctl", "-qw", f"net.ipv4.conf.{interface}.rp_filter=0")


SERVER = r"""
import socket,sys
addr=sys.argv[1]; port=int(sys.argv[2])
s=socket.socket()
s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((addr,port)); s.listen(1)
print("READY", flush=True)
c,p=s.accept(); c.settimeout(5)
print("PEER="+p[0], flush=True)
for _ in range(3):
    data=c.recv(256)
    if not data:
        raise SystemExit("unexpected EOF")
    c.sendall(b"ACK:"+data)
c.close(); s.close()
"""

CLIENT = r"""
import socket,sys
src=sys.argv[1]; dst=sys.argv[2]; port=int(sys.argv[3]); tag=sys.argv[4]
s=socket.socket(); s.settimeout(5); s.bind((src,0)); s.connect((dst,port))
for i in range(3):
    payload=(tag+":"+str(i)).encode()
    s.sendall(payload)
    data=s.recv(512)
    assert data==b"ACK:"+payload, (data,payload)
s.close()
print("OK")
"""


def start_server(port: int):
    p = subprocess.Popen(
        ["ip", "netns", "exec", LAN, "python3", "-u", "-c", SERVER, LAN_IP, str(port)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert p.stdout is not None
    first = p.stdout.readline().strip()
    if first != "READY":
        out, err = p.communicate(timeout=2)
        raise AssertionError((first, out, err))
    return p


def flow(port: int, tag: str) -> str:
    server = start_server(port)
    try:
        result = ns(
            REMOTE, "python3", "-c", CLIENT,
            REMOTE_PAYLOAD, LAN_IP, str(port), tag, check=False,
        )
        if result.returncode != 0 or "OK" not in result.stdout:
            raise AssertionError(
                f"client failed rc={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        assert server.stdout is not None
        peer_line = server.stdout.readline().strip()
        if not peer_line.startswith("PEER="):
            raise AssertionError(peer_line)
        peer = peer_line.split("=", 1)[1]
        out, err = server.communicate(timeout=5)
        if server.returncode != 0:
            raise AssertionError((out, err))
        return peer
    finally:
        if server.poll() is None:
            server.kill()
            server.communicate(timeout=1)


def table_delete(namespace: str, family: str, table: str):
    ns(namespace, "nft", "delete", "table", family, table, check=False)


def probe_fragment(candidate: Candidate, kind: str, expr: str, hook: str, priority: int) -> tuple[bool, str]:
    namespace = STACK if kind.startswith("stack") else HOST
    table = f"e69_probe_{candidate.name}_{kind}".replace("-", "_")
    payload = f"""
table ip {table} {{
  chain c {{
    type filter hook {hook} priority {priority}; policy accept;
    {expr}
  }}
}}
"""
    result = nft(namespace, payload, check=False)
    table_delete(namespace, "ip", table)
    if result.returncode == 0:
        return True, ""
    msg = (result.stderr or result.stdout).strip().replace("\n", " ")
    return False, msg[:300]


def probe_candidate(candidate: Candidate) -> tuple[bool, bool, str]:
    checks = [
        ("stack_set", candidate.setter, candidate.setter_hook, candidate.setter_priority),
        ("stack_match", f"{candidate.matcher} counter", "postrouting", -130),
        ("host_match", f"{candidate.matcher} counter", "prerouting", -150),
    ]
    clear_supported = candidate.phase_a_clear is not None
    if candidate.phase_a_clear is not None:
        checks.append(("host_clear", f"{candidate.matcher} {candidate.phase_a_clear}", "prerouting", -140))
    errors = []
    for kind, expr, hook, priority in checks:
        ok, error = probe_fragment(candidate, kind, expr, hook, priority)
        if not ok:
            errors.append(f"{kind}: {error}")
            if kind == "host_clear":
                clear_supported = False
            else:
                return False, clear_supported, "; ".join(errors)
    return True, clear_supported, "; ".join(errors)


def rule_counter(namespace: str, family: str, table: str, comment: str) -> int:
    doc = json.loads(ns(namespace, "nft", "-j", "list", "table", family, table).stdout)
    for row in doc.get("nftables", []):
        rule = row.get("rule") if isinstance(row, dict) else None
        if not isinstance(rule, dict) or rule.get("comment") != comment:
            continue
        for expr in rule.get("expr", []):
            counter = expr.get("counter") if isinstance(expr, dict) else None
            if isinstance(counter, dict):
                return int(counter.get("packets", 0))
    raise AssertionError(f"counter not found: {namespace} {family} {table} {comment}")


def install_phase_a(supported: list[Candidate], clearable: set[str]):
    raw_setters = []
    normal_setters = []
    source_observers = []
    host_observers = []
    host_clears = []

    for c in supported:
        setter = f"ip saddr {REMOTE_PAYLOAD} ip daddr {LAN_IP} tcp dport {SURVIVAL_PORT} {c.setter}"
        (raw_setters if c.setter_hook == "prerouting" else normal_setters).append(setter)
        source_observers.append(
            f'ip saddr {REMOTE_PAYLOAD} ip daddr {LAN_IP} tcp dport {SURVIVAL_PORT} '
            f'{c.matcher} counter comment "e69-src-{c.name}"'
        )
        host_observers.append(
            f'iifname "{H_S}" ip saddr {REMOTE_PAYLOAD} ip daddr {LAN_IP} tcp dport {SURVIVAL_PORT} '
            f'{c.matcher} counter comment "e69-host-{c.name}"'
        )
        if c.name in clearable and c.phase_a_clear is not None:
            host_clears.append(
                f'iifname "{H_S}" ip saddr {REMOTE_PAYLOAD} ip daddr {LAN_IP} tcp dport {SURVIVAL_PORT} '
                f'{c.matcher} {c.phase_a_clear}'
            )

    stack_payload = f"""
table ip e69_stack {{
  chain raw_pre {{
    type filter hook prerouting priority -300; policy accept;
    {"\n    ".join(raw_setters)}
  }}
  chain stamp {{
    type filter hook postrouting priority -150; policy accept;
    {"\n    ".join(normal_setters)}
  }}
  chain observe {{
    type filter hook postrouting priority -130; policy accept;
    {"\n    ".join(source_observers)}
  }}
}}
"""
    host_payload = f"""
table ip e69_host {{
  chain observe {{
    type filter hook prerouting priority -150; policy accept;
    {"\n    ".join(host_observers)}
  }}
  chain consume {{
    type filter hook prerouting priority -140; policy accept;
    {"\n    ".join(host_clears)}
  }}
}}
"""
    nft(STACK, stack_payload)
    nft(HOST, host_payload)


def phase_a(supported: list[Candidate], clearable: set[str]):
    install_phase_a(supported, clearable)
    peer = flow(SURVIVAL_PORT, "SURVIVAL")
    if peer != REMOTE_PAYLOAD:
        raise AssertionError(f"survival flow unexpectedly translated: {peer}")

    verdicts: dict[str, str] = {}
    for c in supported:
        src = rule_counter(STACK, "ip", "e69_stack", f"e69-src-{c.name}")
        host = rule_counter(HOST, "ip", "e69_host", f"e69-host-{c.name}")
        if src <= 0:
            verdict = "INCONCLUSIVE_SOURCE_NOT_OBSERVED"
        elif host > 0:
            verdict = "SURVIVED"
        else:
            verdict = "LOST"
        verdicts[c.name] = verdict
        print(
            f"EXP069_SURVIVAL candidate={c.name} source_packets={src} "
            f"tambour_packets={host} verdict={verdict}",
            flush=True,
        )

    if verdicts.get("ipv4_dscp") != "SURVIVED":
        raise AssertionError(f"positive control did not survive: {verdicts.get('ipv4_dscp')}")

    before = {
        c.name: rule_counter(HOST, "ip", "e69_host", f"e69-host-{c.name}")
        for c in supported
    }
    peer = flow(NEGATIVE_PORT, "NEGATIVE")
    if peer != REMOTE_PAYLOAD:
        raise AssertionError(f"negative flow unexpectedly translated: {peer}")
    after = {
        c.name: rule_counter(HOST, "ip", "e69_host", f"e69-host-{c.name}")
        for c in supported
    }
    changed = [name for name in before if after[name] != before[name]]
    if changed:
        raise AssertionError(f"negative control acquired candidate markers: {changed}")
    print("EXP069_NEGATIVE_CONTROL=PASS", flush=True)
    return verdicts


def install_phase_b(candidate: Candidate, mark_port: int):
    table_delete(STACK, "ip", "e69_b_stack")
    table_delete(HOST, "ip", "e69_b_host")

    setter_rule = (
        f"ip saddr {REMOTE_PAYLOAD} ip daddr {LAN_IP} tcp dport {mark_port} {candidate.setter}"
    )
    raw = setter_rule if candidate.setter_hook == "prerouting" else ""
    post = "" if candidate.setter_hook == "prerouting" else setter_rule

    stack_payload = f"""
table ip e69_b_stack {{
  chain raw_pre {{
    type filter hook prerouting priority -300; policy accept;
    {raw}
  }}
  chain stamp {{
    type filter hook postrouting priority -150; policy accept;
    {post}
  }}
}}
"""
    assert candidate.phase_b_consume is not None
    host_payload = f"""
table ip e69_b_host {{
  chain classify {{
    type filter hook prerouting priority -150; policy accept;
    iifname "{H_S}" {candidate.matcher} counter {candidate.phase_b_consume} comment "e69-b-classify"
  }}
  chain cleancheck {{
    type filter hook prerouting priority -130; policy accept;
    iifname "{H_S}" {candidate.matcher} counter comment "e69-b-leaked"
  }}
  chain nat {{
    type nat hook postrouting priority srcnat; policy accept;
    oifname "{H_L}" ct mark {NAT_CLASS} counter masquerade comment "e69-b-nat"
  }}
}}
"""
    nft(STACK, stack_payload)
    nft(HOST, host_payload)


def phase_b(candidate: Candidate, index: int):
    mark_port = NAT_PORT_BASE + index
    control_port = NAT_CONTROL_PORT_BASE + index
    install_phase_b(candidate, mark_port)

    peer = flow(mark_port, f"NAT-{candidate.name}")
    classify = rule_counter(HOST, "ip", "e69_b_host", "e69-b-classify")
    leaked = rule_counter(HOST, "ip", "e69_b_host", "e69-b-leaked")
    nat = rule_counter(HOST, "ip", "e69_b_host", "e69-b-nat")
    if peer != HOST_LAN or classify <= 0 or leaked != 0 or nat <= 0:
        raise AssertionError(
            f"phase-B marked flow failed for {candidate.name}: "
            f"peer={peer} classify={classify} leaked={leaked} nat={nat}"
        )

    before_nat = nat
    before_classify = classify
    peer_control = flow(control_port, f"CONTROL-{candidate.name}")
    after_nat = rule_counter(HOST, "ip", "e69_b_host", "e69-b-nat")
    after_classify = rule_counter(HOST, "ip", "e69_b_host", "e69-b-classify")
    if peer_control != REMOTE_PAYLOAD or after_nat != before_nat or after_classify != before_classify:
        raise AssertionError(
            f"phase-B negative control failed for {candidate.name}: "
            f"peer={peer_control} nat={before_nat}->{after_nat} "
            f"classify={before_classify}->{after_classify}"
        )
    print(
        f"EXP069_NAT_INTERACTION candidate={candidate.name} "
        f"classified_packets={classify} nat_packets={nat} leaked_marker_packets={leaked} PASS",
        flush=True,
    )


def preflight():
    require_tools()
    print("EXP069_PREFLIGHT", flush=True)
    print("  kernel=" + run("uname", "-r").stdout.strip(), flush=True)
    print("  ip=" + run("ip", "-V").stdout.strip(), flush=True)
    version = run("nft", "--version")
    print("  nft=" + (version.stdout or version.stderr).strip(), flush=True)


def main():
    try:
        preflight()
        setup()
        time.sleep(0.1)

        baseline_peer = flow(BASELINE_PORT, "BASELINE")
        if baseline_peer != REMOTE_PAYLOAD:
            raise AssertionError(f"baseline source mismatch: {baseline_peer}")
        print("EXP069_BASELINE_FLOW=PASS", flush=True)

        supported: list[Candidate] = []
        clearable: set[str] = set()
        for c in CANDIDATES:
            ok, can_clear, error = probe_candidate(c)
            if ok:
                supported.append(c)
                if can_clear:
                    clearable.add(c.name)
                known = f" known={c.known_result!r}" if c.known_result else ""
                print(
                    f"EXP069_CANDIDATE_SUPPORT candidate={c.name} status=SUPPORTED "
                    f"clearable={'yes' if can_clear else 'no'} scope={c.scope}{known}",
                    flush=True,
                )
            else:
                print(
                    f"EXP069_CANDIDATE_SUPPORT candidate={c.name} status=UNAVAILABLE "
                    f"scope={c.scope} detail={error!r}",
                    flush=True,
                )

        if "ipv4_dscp" not in {c.name for c in supported}:
            raise AssertionError("IPv4 DSCP positive control unavailable")

        verdicts = phase_a(supported, clearable)
        survivors = [c for c in supported if verdicts.get(c.name) == "SURVIVED"]
        local_survivors = [c.name for c in survivors if not c.on_wire]
        wire_survivors = [c.name for c in survivors if c.on_wire]
        print("EXP069_LOCAL_SURVIVORS=" + (",".join(local_survivors) if local_survivors else "none"), flush=True)
        print("EXP069_EXTERNAL_CONTROL_SURVIVORS=" + (",".join(wire_survivors) if wire_survivors else "none"), flush=True)

        phase_b_candidates = [
            c for c in survivors if c.phase_b_consume is not None and c.name in clearable
        ]
        for index, c in enumerate(phase_b_candidates):
            phase_b(c, index)

        not_tested = [c.name for c in survivors if c not in phase_b_candidates]
        if not_tested:
            print("EXP069_NAT_INTERACTION_NOT_TESTED=" + ",".join(not_tested), flush=True)

        print("EXP069_RESULT=PASS", flush=True)
        return 0
    except Exception as exc:
        print("EXP069_RESULT=FAIL", flush=True)
        print("EXP069_ERROR=" + repr(exc), flush=True)
        return 1
    finally:
        for namespace in (LAN, HOST, STACK, REMOTE):
            del_ns(namespace)


if __name__ == "__main__":
    raise SystemExit(main())
