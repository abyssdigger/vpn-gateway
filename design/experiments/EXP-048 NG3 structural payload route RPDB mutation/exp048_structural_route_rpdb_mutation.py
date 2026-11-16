from __future__ import annotations

import json
import os
import subprocess
import sys
import time


PAYLOAD_TABLE = 0x80000000
PAYLOAD_RULE = 0x4000
PATH_PROTO = 202
GUARD_PROTO = 201
GUARD_METRIC = 0xFFFFFFFF
TARGET = "203.0.113.48"
PORT = 48048


def run(*argv: str, check: bool = True):
    return subprocess.run(
        argv,
        check=check,
        text=True,
        capture_output=True,
    )


def ns(name: str, *argv: str, check: bool = True):
    return run("ip", "netns", "exec", name, *argv, check=check)


def start_udp(namespace: str, bind_ip: str, payload: str) -> subprocess.Popen:
    code = r"""
import socket, sys
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((sys.argv[1], int(sys.argv[2])))
reply = sys.argv[3].encode()
print("READY", flush=True)
while True:
    data, peer = sock.recvfrom(2048)
    sock.sendto(reply, peer)
"""
    return subprocess.Popen(
        [
            "ip", "netns", "exec", namespace,
            "python3", "-u", "-c", code,
            bind_ip, str(PORT), payload,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def udp_probe(namespace: str) -> str | None:
    code = r"""
import socket, sys
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.8)
sock.sendto(b"probe", (sys.argv[1], int(sys.argv[2])))
try:
    data, _ = sock.recvfrom(128)
except OSError:
    raise SystemExit(1)
sys.stdout.write(data.decode())
"""
    result = ns(
        namespace,
        "python3", "-c", code, TARGET, str(PORT),
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def route_rows(namespace: str, table: int) -> list[dict]:
    value = json.loads(
        ns(
            namespace,
            "ip", "-j", "-N", "-4",
            "route", "show", "table", str(table),
        ).stdout
    )
    assert isinstance(value, list)
    return value


def rule_rows(namespace: str) -> list[dict]:
    value = json.loads(
        ns(
            namespace,
            "ip", "-j", "-N", "-4",
            "rule", "show",
        ).stdout
    )
    assert isinstance(value, list)
    return value


def guard_command(namespace: str, action: str) -> tuple[str, ...]:
    return (
        "ip", "-n", namespace, "-4", "route", action,
        "blackhole", "default",
        "table", str(PAYLOAD_TABLE),
        "proto", str(GUARD_PROTO),
        "metric", str(GUARD_METRIC),
    )


def path_command(namespace: str, action: str, dev: str) -> tuple[str, ...]:
    return (
        "ip", "-n", namespace, "-4", "route", action,
        "unicast", f"{TARGET}/32",
        "table", str(PAYLOAD_TABLE),
        "proto", str(PATH_PROTO),
        "metric", "1",
        "via", "10.48.2.2",
        "dev", dev,
    )


def rule_command(namespace: str, action: str, ingress: str) -> tuple[str, ...]:
    return (
        "ip", "-n", namespace, "-4", "rule", action,
        "priority", str(PAYLOAD_RULE),
        "iif", ingress,
        "to", f"{TARGET}/32",
        "lookup", str(PAYLOAD_TABLE),
    )


def payload_guard_present(namespace: str) -> bool:
    return any(
        str(row.get("protocol")) == str(GUARD_PROTO)
        and row.get("metric") == GUARD_METRIC
        and str(row.get("type")) in {"6", "blackhole"}
        for row in route_rows(namespace, PAYLOAD_TABLE)
    )


def payload_path_present(namespace: str, dev: str) -> bool:
    return any(
        str(row.get("protocol")) == str(PATH_PROTO)
        and row.get("metric") == 1
        and row.get("dev") == dev
        and row.get("dst") == TARGET
        for row in route_rows(namespace, PAYLOAD_TABLE)
    )


def payload_rule_present(namespace: str, ingress: str) -> bool:
    return any(
        row.get("priority") == PAYLOAD_RULE
        and str(row.get("table")) == str(PAYLOAD_TABLE)
        and row.get("iif") == ingress
        and row.get("dst") == TARGET
        and row.get("dstlen") == 32
        for row in rule_rows(namespace)
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-048 must run as root")

    suffix = str(os.getpid())
    host = f"e48-h-{suffix}"
    managed = f"e48-m-{suffix}"
    vpn = f"e48-v-{suffix}"
    alt = f"e48-a-{suffix}"
    created: list[str] = []
    servers: list[subprocess.Popen] = []

    h_if = f"e48h-{suffix}"
    mh_if = f"e48mh-{suffix}"
    mv_if = f"e48mv-{suffix}"
    v_if = f"e48v-{suffix}"
    ma_if = f"e48ma-{suffix}"
    a_if = f"e48a-{suffix}"

    try:
        for name in (host, managed, vpn, alt):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        for left, right, left_ns, right_ns in (
            (h_if, mh_if, host, managed),
            (mv_if, v_if, managed, vpn),
            (ma_if, a_if, managed, alt),
        ):
            run("ip", "link", "add", left, "type", "veth", "peer", "name", right)
            run("ip", "link", "set", left, "netns", left_ns)
            run("ip", "link", "set", right, "netns", right_ns)

        addresses = (
            (host, h_if, "10.48.1.2/30"),
            (managed, mh_if, "10.48.1.1/30"),
            (managed, mv_if, "10.48.2.1/30"),
            (vpn, v_if, "10.48.2.2/30"),
            (managed, ma_if, "10.48.3.1/30"),
            (alt, a_if, "10.48.3.2/30"),
        )
        for namespace, interface, address in addresses:
            ns(namespace, "ip", "addr", "add", address, "dev", interface)
            ns(namespace, "ip", "link", "set", interface, "up")

        for peer in (vpn, alt):
            ns(peer, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")

        ns(host, "ip", "route", "add", f"{TARGET}/32", "via", "10.48.1.1")
        ns(vpn, "ip", "route", "add", "10.48.1.0/30", "via", "10.48.2.1")
        ns(alt, "ip", "route", "add", "10.48.1.0/30", "via", "10.48.3.1")
        ns(
            managed,
            "ip", "route", "add", f"{TARGET}/32",
            "via", "10.48.3.2", "dev", ma_if,
        )
        ns(managed, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")

        # Unrelated route/rule state must survive exact managed cleanup.
        run(
            "ip", "-n", managed, "-4", "route", "add", "192.0.2.0/24",
            "table", "100", "proto", "99", "metric", "9",
            "via", "10.48.3.2", "dev", ma_if,
        )
        run(
            "ip", "-n", managed, "-4", "rule", "add",
            "priority", "30000", "to", "192.0.2.0/24", "lookup", "100",
        )
        unrelated_route_before = route_rows(managed, 100)
        unrelated_rule_before = [
            row for row in rule_rows(managed)
            if row.get("priority") == 30000
        ]
        assert len(unrelated_route_before) == 1
        assert len(unrelated_rule_before) == 1

        servers.append(start_udp(vpn, TARGET, "vpn"))
        servers.append(start_udp(alt, TARGET, "alt"))
        time.sleep(0.25)
        for server in servers:
            if server.poll() is not None:
                stdout, stderr = server.communicate()
                raise AssertionError(
                    f"UDP server failed rc={server.returncode} "
                    f"stdout={stdout!r} stderr={stderr!r}"
                )

        assert udp_probe(host) == "alt", "main route baseline is not ALT"

        run(*guard_command(managed, "add"))
        assert payload_guard_present(managed)
        assert udp_probe(host) == "alt", "guarded table activated without RPDB"

        run(*path_command(managed, "add", mv_if))
        assert payload_path_present(managed, mv_if)
        assert udp_probe(host) == "alt", "prepared path table activated without RPDB"

        run(*rule_command(managed, "add", mh_if))
        current_rules = rule_rows(managed)
        assert payload_rule_present(managed, mh_if), current_rules
        assert udp_probe(host) == "vpn", "RPDB dispatch did not switch to prepared VPN table"

        run(*path_command(managed, "del", mv_if))
        assert not payload_path_present(managed, mv_if)
        assert payload_guard_present(managed), "exact path delete removed terminal guard"
        assert udp_probe(host) is None, "terminal guard allowed ambient/main fallback"

        run(*path_command(managed, "add", mv_if))
        assert udp_probe(host) == "vpn"

        run(*rule_command(managed, "del", mh_if))
        assert not payload_rule_present(managed, mh_if)
        assert udp_probe(host) == "alt", "RPDB delete did not restore main routing"

        run(*path_command(managed, "del", mv_if))
        assert payload_guard_present(managed)
        run(*guard_command(managed, "del"))
        assert route_rows(managed, PAYLOAD_TABLE) == []

        assert route_rows(managed, 100) == unrelated_route_before
        assert [
            row for row in rule_rows(managed)
            if row.get("priority") == 30000
        ] == unrelated_rule_before

        print("EXP048_TABLE_PREP_UNREACHABLE=1")
        print("EXP048_RPDB_ACTIVATES_PREPARED_TABLE=1")
        print("EXP048_TERMINAL_GUARD_BLOCKS_FALLBACK=1")
        print("EXP048_EXACT_RULE_DELETE_RESTORES_MAIN=1")
        print("EXP048_EXACT_CLEANUP_PRESERVES_UNRELATED=1")
        print("EXP-048 structural payload route/RPDB mutation: PASS")
        return 0
    finally:
        for server in servers:
            if server.poll() is None:
                server.terminate()
        for server in servers:
            try:
                server.wait(timeout=2)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=2)
        for name in reversed(created):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
