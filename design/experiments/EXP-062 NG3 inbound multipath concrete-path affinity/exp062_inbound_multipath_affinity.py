#!/usr/bin/env python3
"""EXP-062: concrete-path affinity for one established inbound multi-path flow."""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import time


PID = os.getpid()
A1 = f"vng62a1-{PID}"
A2 = f"vng62a2-{PID}"
STACK = f"vng62s-{PID}"
ORD = f"vng62o-{PID}"

A1_IF, S_A1 = "e62a1", "e62sa1"
A2_IF, S_A2 = "e62a2", "e62sa2"
O_IF, S_O = "e62o", "e62so"

REMOTE = "10.0.0.2"
ORD_IP = "192.0.2.2"
PORT = 24620
PROFILE_TABLE = "2062"
PIN_TABLE = "2162"
PROFILE_RULE_PRIO = "4062"
PIN_RULE_PRIO = "3062"
PIN_FAIL_RULE_PRIO = "3063"
PIN_MARK = "0x62a2"


def run(*args: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def ns(name: str, *args: str, check: bool = True, input_text: str | None = None):
    return run("ip", "netns", "exec", name, *args, check=check, input_text=input_text)


def add_ns(name: str):
    run("ip", "netns", "add", name)
    ns(name, "ip", "link", "set", "lo", "up")


def del_ns(name: str):
    run("ip", "netns", "del", name, check=False)


def veth(left_ns: str, left_if: str, right_ns: str, right_if: str):
    run("ip", "link", "add", left_if, "type", "veth", "peer", "name", right_if)
    run("ip", "link", "set", left_if, "netns", left_ns)
    run("ip", "link", "set", right_if, "netns", right_ns)


def addr(name: str, interface: str, cidr: str):
    ns(name, "ip", "addr", "add", cidr, "dev", interface)
    ns(name, "ip", "link", "set", interface, "up")


def setup():
    for name in (A1, A2, STACK, ORD):
        add_ns(name)

    veth(A1, A1_IF, STACK, S_A1)
    veth(A2, A2_IF, STACK, S_A2)
    veth(ORD, O_IF, STACK, S_O)

    addr(A1, A1_IF, "172.16.1.2/30")
    addr(STACK, S_A1, "172.16.1.1/30")
    addr(A2, A2_IF, "172.16.2.2/30")
    addr(STACK, S_A2, "172.16.2.1/30")
    ns(A2, "ip", "addr", "add", f"{REMOTE}/32", "dev", "lo")
    addr(ORD, O_IF, "192.0.2.2/30")
    addr(STACK, S_O, "192.0.2.1/30")

    ns(STACK, "sysctl", "-qw", "net.ipv4.ip_forward=1")
    for interface in ("all", "default", S_A1, S_A2, S_O):
        ns(STACK, "sysctl", "-qw", f"net.ipv4.conf.{interface}.rp_filter=0")

    ns(A2, "ip", "route", "add", "192.0.2.0/30", "via", "172.16.2.1", "dev", A2_IF, "src", REMOTE)
    ns(ORD, "ip", "route", "add", "10.0.0.0/16", "via", "192.0.2.1", "dev", O_IF)

    ns(STACK, "ip", "rule", "add", "priority", PROFILE_RULE_PRIO, "to", "10.0.0.0/16", "lookup", PROFILE_TABLE)
    observe = f"""
table ip exp062_observe {{
  chain forward {{
    type filter hook forward priority filter; policy accept;
    oifname "{S_A1}" ip daddr 10.0.0.0/16 counter comment "exp062-a1-remote"
  }}
}}
"""
    completed = ns(STACK, "nft", "-f", "-", check=False, input_text=observe)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    prefer_a2()


def flush_profile_table():
    ns(STACK, "ip", "route", "flush", "table", PROFILE_TABLE, check=False)


def prefer_a2():
    flush_profile_table()
    ns(STACK, "ip", "route", "add", "10.0.0.0/16", "via", "172.16.2.2", "dev", S_A2, "metric", "10", "table", PROFILE_TABLE)
    ns(STACK, "ip", "route", "add", "10.0.0.0/16", "via", "172.16.1.2", "dev", S_A1, "metric", "20", "table", PROFILE_TABLE)


def prefer_a1():
    flush_profile_table()
    ns(STACK, "ip", "route", "add", "10.0.0.0/16", "via", "172.16.1.2", "dev", S_A1, "metric", "10", "table", PROFILE_TABLE)
    ns(STACK, "ip", "route", "add", "10.0.0.0/16", "via", "172.16.2.2", "dev", S_A2, "metric", "20", "table", PROFILE_TABLE)


def flush_conntrack():
    ns(STACK, "conntrack", "-F", check=False)


def a1_remote_packets() -> int:
    payload = json.loads(
        ns(STACK, "nft", "-j", "list", "table", "ip", "exp062_observe").stdout
    )
    packets = []
    for item in payload.get("nftables", []):
        rule = item.get("rule") if isinstance(item, dict) else None
        if not isinstance(rule, dict) or rule.get("comment") != "exp062-a1-remote":
            continue
        for expr in rule.get("expr", []):
            counter = expr.get("counter") if isinstance(expr, dict) else None
            if isinstance(counter, dict) and type(counter.get("packets")) is int:
                packets.append(counter["packets"])
    if len(packets) != 1:
        raise AssertionError(f"unexpected A1 observer state: {payload!r}")
    return packets[0]


def install_affinity():
    ns(STACK, "ip", "route", "flush", "table", PIN_TABLE, check=False)
    ns(STACK, "ip", "route", "add", "10.0.0.0/16", "via", "172.16.2.2", "dev", S_A2, "metric", "10", "table", PIN_TABLE)
    ns(STACK, "ip", "route", "add", "unreachable", "10.0.0.0/16", "metric", "1000", "table", PIN_TABLE)
    ns(STACK, "ip", "rule", "add", "priority", PIN_RULE_PRIO, "fwmark", PIN_MARK, "lookup", PIN_TABLE)
    ns(STACK, "ip", "rule", "add", "priority", PIN_FAIL_RULE_PRIO, "fwmark", PIN_MARK, "type", "unreachable")
    nft = f"""
table ip exp062_affinity {{
  chain prerouting {{
    type filter hook prerouting priority mangle; policy accept;
    iifname "{S_A2}" ip saddr 10.0.0.0/16 ct state new ct mark set {PIN_MARK}
    iifname "{S_O}" ct mark {PIN_MARK} meta mark set ct mark
  }}
}}
"""
    completed = ns(STACK, "nft", "-f", "-", check=False, input_text=nft)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)


def remove_affinity():
    ns(STACK, "nft", "delete", "table", "ip", "exp062_affinity", check=False)
    ns(STACK, "ip", "rule", "del", "priority", PIN_FAIL_RULE_PRIO, "fwmark", PIN_MARK, "type", "unreachable", check=False)
    ns(STACK, "ip", "rule", "del", "priority", PIN_RULE_PRIO, "fwmark", PIN_MARK, "lookup", PIN_TABLE, check=False)
    ns(STACK, "ip", "route", "flush", "table", PIN_TABLE, check=False)


SERVER = r"""
import socket
s=socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("192.0.2.2", 24620))
s.listen(4)
while True:
    c,_=s.accept()
    c.settimeout(5)
    try:
        while True:
            b=c.recv(1)
            if not b: break
            c.sendall(b)
    except Exception:
        pass
    c.close()
"""

CLIENT = r"""
import socket,sys
s=socket.socket()
s.settimeout(2)
s.bind(("10.0.0.2",0))
s.connect(("192.0.2.2",24620))
s.sendall(b"A")
assert s.recv(1)==b"A"
print("FIRST_OK", flush=True)
sys.stdin.readline()
s.sendall(b"B")
try:
    b=s.recv(1)
    print("SECOND_OK" if b==b"B" else "SECOND_BAD", flush=True)
except Exception:
    print("SECOND_FAIL", flush=True)
sys.stdin.readline()
try:
    s.sendall(b"C")
    b=s.recv(1)
    print("THIRD_OK" if b==b"C" else "THIRD_BAD", flush=True)
except Exception:
    print("THIRD_FAIL", flush=True)
s.close()
"""


def start_server():
    return subprocess.Popen(
        ("ip", "netns", "exec", ORD, sys.executable, "-c", SERVER),
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def start_client():
    return subprocess.Popen(
        ("ip", "netns", "exec", A2, sys.executable, "-c", CLIENT),
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )


def read_line(proc, timeout=5):
    assert proc.stdout is not None
    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    if not ready:
        raise AssertionError("timed out waiting for client phase")
    line = proc.stdout.readline().strip()
    if not line:
        err = proc.stderr.read() if proc.stderr is not None else ""
        raise AssertionError(f"client exited without phase marker: {err}")
    return line


def run_control(server):
    remove_affinity()
    flush_conntrack()
    prefer_a2()
    client = start_client()
    try:
        first = read_line(client)
        if first != "FIRST_OK":
            raise AssertionError(first)
        print("EXP062_INITIAL_A2_FLOW=PASS")

        prefer_a1()
        a1_before = a1_remote_packets()
        assert client.stdin is not None
        client.stdin.write("\n")
        client.stdin.flush()
        second = read_line(client)
        if second != "SECOND_FAIL":
            raise AssertionError(f"control flow unexpectedly survived preference switch: {second}")
        a1_after = a1_remote_packets()
        if a1_after <= a1_before:
            raise AssertionError("control reply failed without any A1 egress")
        print("EXP062_CONTROL_PREFERENCE_SWITCH_BREAKS_FLOW=PASS")
        client.stdin.write("\n")
        client.stdin.flush()
        client.wait(timeout=5)
    finally:
        client.kill()
        client.wait()


def run_affinity(server):
    flush_conntrack()
    prefer_a2()
    install_affinity()

    marked = ns(STACK, "ip", "-4", "route", "get", REMOTE, "mark", PIN_MARK).stdout
    if S_A2 not in marked or "172.16.2.2" not in marked:
        raise AssertionError(f"marked lookup did not select A2: {marked!r}")
    print("EXP062_MARKED_LOOKUP_SELECTS_A2=PASS")

    client = start_client()
    try:
        first = read_line(client)
        if first != "FIRST_OK":
            raise AssertionError(first)

        prefer_a1()
        assert client.stdin is not None
        a1_before_affinity = a1_remote_packets()
        client.stdin.write("\n")
        client.stdin.flush()
        second = read_line(client)
        if second != "SECOND_OK":
            raise AssertionError(f"affinity flow did not survive preference switch: {second}")
        a1_after_affinity = a1_remote_packets()
        if a1_after_affinity != a1_before_affinity:
            raise AssertionError("affinity reply leaked through currently preferred A1")
        print("EXP062_AFFINITY_SURVIVES_PREFERENCE_SWITCH=PASS")

        # Remove only the pinned concrete path. A1 remains up and preferred.
        ns(STACK, "ip", "link", "set", S_A2, "down")
        a1_before_loss = a1_remote_packets()
        client.stdin.write("\n")
        client.stdin.flush()
        third = read_line(client)
        if third != "THIRD_FAIL":
            raise AssertionError(f"pinned-path loss silently migrated flow: {third}")
        a1_after_loss = a1_remote_packets()
        if a1_after_loss != a1_before_loss:
            raise AssertionError("pinned-path loss fell through to alternate A1")
        print("EXP062_PINNED_PATH_LOSS_FAILS_CLOSED=PASS")
        client.wait(timeout=5)
    finally:
        client.kill()
        client.wait()
        ns(STACK, "ip", "link", "set", S_A2, "up", check=False)
        remove_affinity()


def main():
    server = None
    try:
        setup()
        server = start_server()
        time.sleep(0.2)
        run_control(server)
        run_affinity(server)
        print("EXP062_RESULT=PASS")
        return 0
    finally:
        if server is not None:
            server.kill()
            server.wait()
        for name in (ORD, STACK, A2, A1):
            del_ns(name)


if __name__ == "__main__":
    raise SystemExit(main())
