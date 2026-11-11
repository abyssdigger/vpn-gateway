#!/usr/bin/env python3
"""VPN-GATE NG1 ROU v0 executable reference appliance.

Deliberately narrow: one namespace, one OUTBOUND profile, one ocserv PREFIX binding,
one protected route and one published TCP/UDP endpoint. No generic config parser yet.
"""
from __future__ import annotations

import argparse
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Iterable

# --- v0 model ---------------------------------------------------------------
NS = "vpn-gate-rou0"
HOST_IF = "rouvpn0"
ROU_IF = "host0"
HOST_ADDR = "192.0.2.1"
ROU_ADDR = "192.0.2.2"
LINK_PREFIX = 30

OCSERV_CONFIG = Path("/etc/ocserv/ocserv.conf")
OCSERV_PORT = 44443
BINDING_PREFIX = "vpns"
BINDING_NETWORK = ipaddress.IPv4Network("172.20.130.0/29")
BINDING_CAPACITY = 2

PROFILE_TABLE = 100
PROFILE_RULE_PRIORITY = 100
PROFILE_TARGET = "172.21.201.19/32"
FIRST_UNICAST_METRIC = 10
METRIC_STEP = 10
BLACKHOLE_METRIC = 65536
ROUTE_PROTO_UNICAST = 202
ROUTE_PROTO_BLACKHOLE = 201
RECONCILE_INTERVAL = 1.0

RUNTIME_DIR = Path("/run/vpn-gateway-rou-v0")
LOCK_FILE = Path("/run/vpn-gateway-rou-v0.lock")
STATE_FILE = RUNTIME_DIR / "state.json"
DERIVED_CONFIG = RUNTIME_DIR / "ocserv.conf"
OCSERV_SOCKET = RUNTIME_DIR / "ocserv.sock"
OCCTL_SOCKET = RUNTIME_DIR / "occtl.sock"
OCSERV_PIDFILE = RUNTIME_DIR / "ocserv.pid"
LOG_DIR = Path("/var/tmp/vpn-gateway-rou-v0")
SCRIPT_DIR = Path(__file__).resolve().parent
RELAY = SCRIPT_DIR / "rou_v0_relay.py"


class RouError(RuntimeError):
    pass


@dataclass(frozen=True, order=True)
class BindingId:
    ifname: str
    ifindex: int


@dataclass(frozen=True)
class Assignment:
    identity: BindingId
    metric: int


@dataclass(frozen=True)
class Projection:
    admitted: tuple[Assignment, ...]
    overflow: tuple[BindingId, ...]
    next_cursor: int


def log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def run(argv: list[str], *, ns: bool = False, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    cmd = ["ip", "netns", "exec", NS, *argv] if ns else argv
    p = subprocess.run(cmd, text=True, input=input_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RouError(f"command failed ({p.returncode}): {' '.join(cmd)}\nstdout: {p.stdout}\nstderr: {p.stderr}")
    return p


def require_environment() -> None:
    if os.geteuid() != 0:
        raise RouError("ROU v0 requires root")
    for name in ("ip", "sysctl", "ss", "ocserv", "iptables-legacy", "iptables-legacy-restore", "iptables-legacy-save", "python3"):
        if shutil.which(name) is None:
            raise RouError(f"missing required command: {name}")
    if not OCSERV_CONFIG.is_file():
        raise RouError(f"missing source ocserv config: {OCSERV_CONFIG}")
    if not RELAY.is_file():
        raise RouError(f"missing relay: {RELAY}")


def acquire_lock():
    fh = LOCK_FILE.open("w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as e:
        raise RouError("another ROU v0 controller holds the lock") from e
    fh.write(str(os.getpid()) + "\n"); fh.flush()
    return fh


def ns_exists() -> bool:
    p = run(["ip", "netns", "list"], check=False)
    return any(line.split(maxsplit=1)[0] == NS for line in p.stdout.splitlines() if line.strip())


def host_link_exists() -> bool:
    return run(["ip", "link", "show", "dev", HOST_IF], check=False).returncode == 0


def port_free() -> bool:
    t = run(["ss", "-H", "-ltn", f"sport = :{OCSERV_PORT}"], check=False).stdout.strip()
    u = run(["ss", "-H", "-lun", f"sport = :{OCSERV_PORT}"], check=False).stdout.strip()
    return not t and not u


def prepare_runtime() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(RUNTIME_DIR, 0o700)
    LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)


def derive_ocserv_config() -> None:
    repl = {
        "tcp-port": str(OCSERV_PORT),
        "udp-port": str(OCSERV_PORT),
        "listen-host": ROU_ADDR,
        "udp-listen-host": ROU_ADDR,
        "socket-file": str(OCSERV_SOCKET),
        "occtl-socket-file": str(OCCTL_SOCKET),
        "pid-file": str(OCSERV_PIDFILE),
    }
    seen: set[str] = set(); out: list[str] = []
    rx = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=")
    for raw in OCSERV_CONFIG.read_text().splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            out.append(raw); continue
        m = rx.match(raw)
        if m and m.group(1) in repl:
            k = m.group(1)
            if k in seen:
                out.append("# ROU-v0 disabled duplicate: " + raw)
            else:
                out.append(f"{k} = {repl[k]}"); seen.add(k)
        else:
            out.append(raw)
    for k, v in repl.items():
        if k not in seen:
            out.append(f"{k} = {v}")
    DERIVED_CONFIG.write_text("\n".join(out) + "\n")
    os.chmod(DERIVED_CONFIG, 0o600)


def set_forwarding(enabled: bool) -> None:
    if ns_exists():
        run(["sysctl", "-q", "-w", f"net.ipv4.ip_forward={1 if enabled else 0}"], ns=True)


def forwarding() -> int:
    return int(run(["sysctl", "-n", "net.ipv4.ip_forward"], ns=True).stdout.strip())


def create_namespace() -> None:
    if ns_exists() or host_link_exists():
        raise RouError("refusing to reuse existing ROU namespace/veth")
    if not port_free():
        raise RouError(f"TCP/UDP {OCSERV_PORT} is busy; stop normal ocserv first")
    run(["ip", "netns", "add", NS])
    try:
        run(["ip", "link", "add", HOST_IF, "type", "veth", "peer", "name", ROU_IF])
        run(["ip", "link", "set", ROU_IF, "netns", NS])
        run(["ip", "addr", "add", f"{HOST_ADDR}/{LINK_PREFIX}", "dev", HOST_IF])
        run(["ip", "link", "set", HOST_IF, "up"])
        run(["ip", "link", "set", "lo", "up"], ns=True)
        run(["ip", "addr", "add", f"{ROU_ADDR}/{LINK_PREFIX}", "dev", ROU_IF], ns=True)
        run(["ip", "link", "set", ROU_IF, "up"], ns=True)
        run(["ip", "route", "replace", "default", "via", HOST_ADDR, "dev", ROU_IF], ns=True)
        set_forwarding(False)
        run(["sysctl", "-q", "-w", "net.ipv6.conf.all.forwarding=0"], ns=True)
        run(["sysctl", "-q", "-w", "net.ipv6.conf.default.forwarding=0"], ns=True)
    except Exception:
        destroy_namespace(); raise


def destroy_namespace() -> None:
    if ns_exists():
        run(["ip", "netns", "del", NS], check=False)
    if host_link_exists():
        run(["ip", "link", "del", HOST_IF], check=False)


def observe_bindings() -> list[BindingId]:
    links = json.loads(run(["ip", "-j", "addr", "show"], ns=True).stdout)
    out: list[BindingId] = []
    for link in links:
        name = link.get("ifname", "")
        if not name.startswith(BINDING_PREFIX):
            continue
        good = False
        for a in link.get("addr_info", []):
            if a.get("family") == "inet" and a.get("local"):
                if ipaddress.IPv4Address(a["local"]) in BINDING_NETWORK:
                    good = True; break
        if good:
            out.append(BindingId(name, int(link["ifindex"])))
    return out


def slots() -> tuple[int, ...]:
    return tuple(FIRST_UNICAST_METRIC + i * METRIC_STEP for i in range(BINDING_CAPACITY))


def project_bindings(observed: Iterable[BindingId], committed: tuple[Assignment, ...], cursor: int) -> Projection:
    observed_list = list(observed)
    observed_ids = set(observed_list)
    survivors = [a for a in committed if a.identity in observed_ids]
    committed_ids = {a.identity for a in committed}
    newcomers = [i for i in observed_list if i not in committed_ids]
    reserved = {a.metric for a in committed}  # missing committed metrics stay reserved until this verified transition commits
    assigned = list(survivors); overflow: list[BindingId] = []
    pool = slots(); next_cursor = cursor
    for ident in newcomers:
        picked = None
        for off in range(len(pool)):
            idx = (next_cursor + off) % len(pool)
            if pool[idx] not in reserved:
                picked = (idx, pool[idx]); break
        if picked is None:
            overflow.append(ident); continue
        idx, metric = picked
        assigned.append(Assignment(ident, metric)); reserved.add(metric)
        next_cursor = (idx + 1) % len(pool)
    return Projection(tuple(assigned), tuple(overflow), next_cursor)


def desired_routes(admitted: tuple[Assignment, ...]) -> list[list[str]]:
    routes: list[list[str]] = []
    for a in admitted:
        routes.append(["ip", "route", "replace", "table", str(PROFILE_TABLE), PROFILE_TARGET,
                       "dev", a.identity.ifname, "proto", str(ROUTE_PROTO_UNICAST), "metric", str(a.metric)])
    routes.append(["ip", "route", "replace", "table", str(PROFILE_TABLE), "blackhole", PROFILE_TARGET,
                   "proto", str(ROUTE_PROTO_BLACKHOLE), "metric", str(BLACKHOLE_METRIC)])
    routes.append(["ip", "route", "replace", "table", str(PROFILE_TABLE), "blackhole", "default",
                   "proto", str(ROUTE_PROTO_BLACKHOLE), "metric", str(BLACKHOLE_METRIC)])
    return routes


def firewall_restore(admitted: tuple[Assignment, ...]) -> str:
    fwd = [
        "*filter",
        ":INPUT ACCEPT [0:0]",
        ":FORWARD DROP [0:0]",
        ":OUTPUT ACCEPT [0:0]",
        "-A FORWARD -m conntrack --ctstate INVALID -j DROP",
    ]
    for a in admitted:
        fwd.append(f"-A FORWARD -i {ROU_IF} -o {a.identity.ifname} -m conntrack --ctstate NEW,ESTABLISHED,RELATED -j ACCEPT")
        fwd.append(f"-A FORWARD -i {a.identity.ifname} -o {ROU_IF} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT")
    fwd += ["COMMIT", "*nat", ":PREROUTING ACCEPT [0:0]", ":INPUT ACCEPT [0:0]", ":OUTPUT ACCEPT [0:0]", ":POSTROUTING ACCEPT [0:0]"]
    for a in admitted:
        fwd.append(f"-A POSTROUTING -o {a.identity.ifname} -m addrtype ! --dst-type LOCAL -j MASQUERADE")
    fwd += ["COMMIT", ""]
    return "\n".join(fwd)


def normalize_save(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("# Generated by") or line.startswith("# Completed on"):
            continue
        # zero counters so verification does not depend on traffic
        line = re.sub(r"\[[0-9]+:[0-9]+\]", "[0:0]", line)
        lines.append(line)
    return "\n".join(lines).strip()


def flush_profile_table() -> None:
    p = run(["ip", "route", "flush", "table", str(PROFILE_TABLE)], ns=True, check=False)
    if p.returncode == 0:
        return
    if p.returncode == 2 and "FIB table does not exist" in p.stderr:
        return
    raise RouError(
        f"command failed ({p.returncode}): ip netns exec {NS} ip route flush table {PROFILE_TABLE}"
        f"\nstdout: {p.stdout}\nstderr: {p.stderr}"
    )


def install_full_state(admitted: tuple[Assignment, ...]) -> None:
    # On a brand-new namespace the dedicated table does not exist until its first route
    # is installed. That specific absence is a valid empty baseline; every other flush
    # failure remains fatal.
    flush_profile_table()
    for cmd in desired_routes(admitted):
        run(cmd, ns=True)
    run(["ip", "rule", "del", "priority", str(PROFILE_RULE_PRIORITY)], ns=True, check=False)
    run(["ip", "rule", "add", "priority", str(PROFILE_RULE_PRIORITY), "iif", ROU_IF,
         "to", PROFILE_TARGET, "lookup", str(PROFILE_TABLE)], ns=True)
    run(["iptables-legacy-restore"], ns=True, input_text=firewall_restore(admitted))


def firewall_snapshot() -> str:
    # Only filter+nat belong to the ROU routing policy in v0. Do not adopt unrelated
    # raw/mangle state into the committed verifier baseline.
    filt = run(["iptables-legacy-save", "-c", "-t", "filter"], ns=True).stdout
    nat = run(["iptables-legacy-save", "-c", "-t", "nat"], ns=True).stdout
    return normalize_save(filt + "\n" + nat)


def route_snapshot() -> list[dict]:
    return json.loads(run(["ip", "-j", "route", "show", "table", str(PROFILE_TABLE)], ns=True).stdout)


def norm_prefix(value: str) -> str:
    if value == "default":
        return value
    return ipaddress.ip_network(value, strict=False).with_prefixlen


def expected_route_semantics(admitted: tuple[Assignment, ...]) -> list[tuple]:
    out: list[tuple] = []
    for a in admitted:
        out.append(("unicast", PROFILE_TARGET, a.identity.ifname, str(ROUTE_PROTO_UNICAST), a.metric))
    out.append(("blackhole", PROFILE_TARGET, None, str(ROUTE_PROTO_BLACKHOLE), BLACKHOLE_METRIC))
    out.append(("blackhole", "default", None, str(ROUTE_PROTO_BLACKHOLE), BLACKHOLE_METRIC))
    return sorted(out)


def actual_route_semantics() -> list[tuple]:
    out: list[tuple] = []
    for item in route_snapshot():
        typ = item.get("type", "unicast")
        dst = norm_prefix(item.get("dst", "default"))
        dev = item.get("dev")
        proto = str(item.get("protocol", item.get("proto", "")))
        metric = int(item.get("metric", 0))
        out.append((typ, dst, dev, proto, metric))
    return sorted(out)


def rule_semantically_present() -> tuple[bool, str]:
    rules = json.loads(run(["ip", "-j", "rule", "show"], ns=True).stdout)
    managed = [r for r in rules if int(r.get("priority", -1)) == PROFILE_RULE_PRIORITY]
    if len(managed) != 1:
        return False, f"managed rule count={len(managed)} rules={managed!r}"
    r = managed[0]
    table = str(r.get("table", ""))
    raw_dst = r.get("dst", "all")
    dst = norm_prefix(raw_dst) if raw_dst != "all" else raw_dst
    iif = r.get("iif") or r.get("iifname")
    if table != str(PROFILE_TABLE) or dst != PROFILE_TARGET or iif != ROU_IF:
        return False, f"managed rule mismatch={r!r}"
    foreign_custom = [
        x for x in rules
        if int(x.get("priority", -1)) not in (0, PROFILE_RULE_PRIORITY, 32766, 32767)
    ]
    if foreign_custom:
        return False, f"foreign RPDB rules={foreign_custom!r}"
    return True, "ok"


def verify_infrastructure() -> tuple[bool, str]:
    if not ns_exists():
        return False, "namespace missing"
    if not host_link_exists():
        return False, f"host link {HOST_IF} missing"

    host = json.loads(run(["ip", "-j", "addr", "show", "dev", HOST_IF]).stdout)
    if len(host) != 1:
        return False, "host link snapshot invalid"
    host_addrs = {a.get("local") for a in host[0].get("addr_info", []) if a.get("family") == "inet"}
    if HOST_ADDR not in host_addrs:
        return False, f"host address {HOST_ADDR} missing"

    inner_p = run(["ip", "-j", "addr", "show", "dev", ROU_IF], ns=True, check=False)
    if inner_p.returncode != 0:
        return False, f"internal link {ROU_IF} missing"
    inner = json.loads(inner_p.stdout)
    if len(inner) != 1:
        return False, "internal link snapshot invalid"
    inner_addrs = {a.get("local") for a in inner[0].get("addr_info", []) if a.get("family") == "inet"}
    if ROU_ADDR not in inner_addrs:
        return False, f"internal address {ROU_ADDR} missing"

    main = json.loads(run(["ip", "-j", "route", "show", "table", "main"], ns=True).stdout)
    default_ok = any(
        x.get("dst", "default") == "default"
        and x.get("gateway") == HOST_ADDR
        and x.get("dev") == ROU_IF
        for x in main
    )
    if not default_ok:
        return False, "underlay default route missing"
    return True, "ok"


def verify_state(admitted: tuple[Assignment, ...], expected_firewall: str) -> tuple[bool, str]:
    infra_ok, infra_why = verify_infrastructure()
    if not infra_ok:
        return False, "INFRA:" + infra_why
    if actual_route_semantics() != expected_route_semantics(admitted):
        return False, f"route mismatch actual={actual_route_semantics()!r} expected={expected_route_semantics(admitted)!r}"
    rule_ok, rule_why = rule_semantically_present()
    if not rule_ok:
        return False, rule_why
    actual_fw = firewall_snapshot()
    if actual_fw != expected_firewall:
        return False, "iptables mismatch"
    return True, "ok"

def reconcile(
    committed: tuple[Assignment, ...],
    cursor: int,
    expected_firewall: str,
) -> tuple[tuple[Assignment, ...], int, tuple[BindingId, ...], str]:
    infra_ok, infra_why = verify_infrastructure()
    if not infra_ok:
        set_forwarding(False)
        raise RouError(f"structural appliance integrity failure: {infra_why}")

    observed = observe_bindings()
    p = project_bindings(observed, committed, cursor)
    binding_changed = p.admitted != committed
    if not binding_changed:
        ok, why = verify_state(committed, expected_firewall)
        if ok:
            return committed, cursor, p.overflow, expected_firewall
        if why.startswith("INFRA:"):
            set_forwarding(False)
            raise RouError(f"structural appliance integrity failure: {why[6:]}")
        reason = why
    else:
        reason = "binding-change"

    log(f"RECONCILE barrier reason={reason}")
    set_forwarding(False)
    install_full_state(p.admitted)
    new_firewall = firewall_snapshot()
    ok, why = verify_state(p.admitted, new_firewall)
    if not ok:
        raise RouError(f"post-apply verification failed: {why}")
    set_forwarding(True)
    ok, why = verify_state(p.admitted, new_firewall)
    if not ok or forwarding() != 1:
        set_forwarding(False)
        raise RouError(f"post-enable verification failed: {why}")
    log(f"RECONCILE committed admitted={[a.identity.ifname for a in p.admitted]} overflow={[x.ifname for x in p.overflow]}")
    return p.admitted, p.next_cursor, p.overflow, new_firewall

def start_processes() -> tuple[subprocess.Popen[str], subprocess.Popen[str], object, object]:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    oc_log = (LOG_DIR / f"ocserv-{stamp}.log").open("a", buffering=1)
    relay_log = (LOG_DIR / f"relay-{stamp}.log").open("a", buffering=1)
    oc = subprocess.Popen(["ip", "netns", "exec", NS, "ocserv", "-f", "-c", str(DERIVED_CONFIG)], stdout=oc_log, stderr=subprocess.STDOUT, text=True)
    time.sleep(0.8)
    if oc.poll() is not None:
        raise RouError(f"ocserv exited during startup rc={oc.returncode}; see {oc_log.name}")
    relay = subprocess.Popen([sys.executable, str(RELAY), "--listen-address", "0.0.0.0", "--internal-source-address", HOST_ADDR,
                              "--target-address", ROU_ADDR, "--port", str(OCSERV_PORT)], stdout=relay_log, stderr=subprocess.STDOUT, text=True)
    time.sleep(0.5)
    if relay.poll() is not None:
        oc.terminate(); oc.wait(timeout=5)
        raise RouError(f"relay exited during startup; see {relay_log.name}")
    return oc, relay, oc_log, relay_log


def stop_process(p: subprocess.Popen[str] | None) -> None:
    if p is None or p.poll() is not None:
        return
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill(); p.wait(timeout=5)


def write_state(admitted: tuple[Assignment, ...], cursor: int, overflow: tuple[BindingId, ...]) -> None:
    STATE_FILE.write_text(json.dumps({
        "state": "READY",
        "namespace": NS,
        "host_interface": HOST_IF,
        "profile_target": PROFILE_TARGET,
        "admitted": [{"ifname": a.identity.ifname, "ifindex": a.identity.ifindex, "metric": a.metric} for a in admitted],
        "overflow": [{"ifname": x.ifname, "ifindex": x.ifindex} for x in overflow],
        "cursor": cursor,
    }, indent=2) + "\n")


def controller() -> int:
    require_environment(); _lock = acquire_lock(); prepare_runtime(); derive_ocserv_config(); create_namespace()
    oc = relay = None; oc_log = relay_log = None
    stopping = False
    def on_signal(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGINT, on_signal); signal.signal(signal.SIGTERM, on_signal)
    committed: tuple[Assignment, ...] = (); cursor = 0; overflow: tuple[BindingId, ...] = ()
    try:
        # Fail closed before transport comes alive.
        install_full_state(committed)
        expected_firewall = firewall_snapshot()
        ok, why = verify_state(committed, expected_firewall)
        if not ok:
            raise RouError(f"initial fail-closed verification failed: {why}")
        oc, relay, oc_log, relay_log = start_processes()
        log(f"ROU_V0_STARTED ns={NS} publication={OCSERV_PORT}/tcp+udp")
        while not stopping:
            if oc.poll() is not None:
                raise RouError(f"ocserv exited rc={oc.returncode}")
            if relay.poll() is not None:
                raise RouError(f"relay exited rc={relay.returncode}")
            committed, cursor, overflow, expected_firewall = reconcile(committed, cursor, expected_firewall)
            write_state(committed, cursor, overflow)
            time.sleep(RECONCILE_INTERVAL)
        return 0
    finally:
        log("ROU_V0_STOPPING")
        try: set_forwarding(False)
        except Exception: pass
        stop_process(relay); stop_process(oc)
        if relay_log: relay_log.close()
        if oc_log: oc_log.close()
        destroy_namespace()
        try: STATE_FILE.unlink()
        except FileNotFoundError: pass
        shutil.rmtree(RUNTIME_DIR, ignore_errors=True)
        log("ROU_V0_STOPPED")


def show() -> int:
    if STATE_FILE.exists():
        print(STATE_FILE.read_text(), end="")
        return 0
    print(json.dumps({"state": "DOWN", "namespace_present": ns_exists(), "host_interface_present": host_link_exists()}, indent=2))
    return 0


def check() -> int:
    require_environment()
    print("ROU v0 environment: OK")
    print(f"namespace={NS} host_if={HOST_IF} internal={ROU_ADDR}:{OCSERV_PORT} profile={PROFILE_TARGET}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("run", "show", "check"))
    a = p.parse_args()
    try:
        if a.command == "run": return controller()
        if a.command == "show": return show()
        return check()
    except RouError as e:
        print(f"ROU_V0_ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
