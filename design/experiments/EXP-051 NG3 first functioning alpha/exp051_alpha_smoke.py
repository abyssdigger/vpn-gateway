#!/usr/bin/env python3
"""EXP-051: actual installed systemd alpha + OpenVPN end-to-end smoke."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


ALPHA_UNIT = "vpn-gate-alpha.service"
VPN_UNIT = "vpn-gate-alpha-openvpn.service"
MANAGED = "vpn-gate-alpha"
HOST_BOUNDARY = "vnga-host0"
INNER_BOUNDARY = "vnga-inner0"
INNER_ADDR = "198.19.255.2"
HOST_ADDR = "198.19.255.1"  # test-only ordinary host-local /32, not boundary addressing
STATUS_PATH = Path("/run/vpn-gate-alpha/status.json")
STATUS_TEXT_PATH = Path("/run/vpn-gate-alpha/status.txt")

SERVER_NS = "alpha-srv"
SERVER_HOST = "alpha-srv-host"
SERVER_INNER = "alpha-srv0"
SERVER_HOST_CIDR = "198.19.254.1/30"
SERVER_ADDR_CIDR = "198.19.254.2/30"
SERVER_UNDERLAY = "198.19.254.2"

VPN_IF = "vpn0"
SERVER_TUN = "tun-srv"
VPN_CLIENT_ADDR = "10.253.0.2"
VPN_SERVER_ADDR = "10.253.0.1"
OPENVPN_PORT = 11940
OPENVPN_LOCAL_PORT = 11941
PUBLICATION_HOST_PORT = 14443
PUBLICATION_INTERNAL_PORT = 24443


def command(argv, *, check=True):
    result = subprocess.run(
        tuple(str(item) for item in argv),
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed {argv!r}: rc={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    return result


def ns_command(namespace, *argv, check=True):
    return command(("ip", "netns", "exec", namespace, *argv), check=check)


def systemctl(*argv, check=True):
    return command(("systemctl", *argv), check=check)


def active(unit):
    return systemctl("is-active", "--quiet", unit, check=False).returncode == 0


def main_pid(unit):
    value = systemctl("show", "--property=MainPID", "--value", unit).stdout.strip()
    if not value.isdecimal() or int(value) <= 0:
        raise RuntimeError(f"{unit} has no positive MainPID: {value!r}")
    return int(value)


def wait_until(description, predicate, *, timeout=25.0, interval=0.2):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception as exc:
            last = exc
        time.sleep(interval)
    raise RuntimeError(
        f"timeout waiting for {description}"
        + (f": last={last!r}" if last is not None else "")
    )


def interface_exists(namespace, ifname):
    return command(
        ("ip", "-n", namespace, "link", "show", "dev", ifname),
        check=False,
    ).returncode == 0


def runtime_status():
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def runtime_status_text():
    return STATUS_TEXT_PATH.read_text(encoding="utf-8")


def host_ping(address):
    return command(
        ("ping", "-c", "2", "-W", "1", address),
        check=False,
    ).returncode == 0


def generate_pki(root):
    command(
        (
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", root / "ca.key",
            "-out", root / "ca.crt",
            "-days", "1",
            "-subj", "/CN=EXP051-CA",
        )
    )
    for name in ("server", "client"):
        command(
            (
                "openssl", "req", "-newkey", "rsa:2048", "-nodes",
                "-keyout", root / f"{name}.key",
                "-out", root / f"{name}.csr",
                "-subj", f"/CN=EXP051-{name}",
            )
        )
        ext = root / f"{name}.ext"
        ext.write_text(
            (
                "basicConstraints=CA:FALSE\n"
                "keyUsage=digitalSignature,keyEncipherment\n"
                + (
                    "extendedKeyUsage=serverAuth\n"
                    if name == "server"
                    else "extendedKeyUsage=clientAuth\n"
                )
            ),
            encoding="utf-8",
        )
        command(
            (
                "openssl", "x509", "-req",
                "-in", root / f"{name}.csr",
                "-CA", root / "ca.crt",
                "-CAkey", root / "ca.key",
                "-CAcreateserial",
                "-out", root / f"{name}.crt",
                "-days", "1",
                "-sha256",
                "-extfile", ext,
            )
        )


def setup_server_namespace():
    command(("ip", "netns", "del", SERVER_NS), check=False)
    command(("ip", "link", "del", SERVER_HOST), check=False)
    command(("ip", "netns", "add", SERVER_NS))
    command(
        (
            "ip", "link", "add", SERVER_HOST,
            "type", "veth", "peer", "name", SERVER_INNER,
        )
    )
    command(("ip", "link", "set", SERVER_INNER, "netns", SERVER_NS))
    command(("ip", "addr", "add", SERVER_HOST_CIDR, "dev", SERVER_HOST))
    command(("ip", "link", "set", SERVER_HOST, "up"))
    command(("ip", "-n", SERVER_NS, "link", "set", "lo", "up"))
    command(
        ("ip", "-n", SERVER_NS, "addr", "add", SERVER_ADDR_CIDR, "dev", SERVER_INNER)
    )
    command(("ip", "-n", SERVER_NS, "link", "set", SERVER_INNER, "up"))
    command(
        (
            "ip", "-n", SERVER_NS, "route", "replace", "default",
            "via", "198.19.254.1", "dev", SERVER_INNER,
        )
    )


def cleanup():
    systemctl("stop", VPN_UNIT, check=False)
    systemctl("stop", ALPHA_UNIT, check=False)
    command(("nft", "delete", "table", "ip", "vpn_gate_publication"), check=False)
    command(("ip", "netns", "del", MANAGED), check=False)
    command(("ip", "link", "del", HOST_BOUNDARY), check=False)
    command(("ip", "addr", "del", f"{HOST_ADDR}/32", "dev", "lo"), check=False)
    command(("ip", "netns", "del", SERVER_NS), check=False)
    command(("ip", "link", "del", SERVER_HOST), check=False)


def write_configs(root):
    server = root / "server.conf"
    server.write_text(
        f"""dev {SERVER_TUN}
dev-type tun
proto udp4
local {SERVER_UNDERLAY}
port {OPENVPN_PORT}
ifconfig {VPN_SERVER_ADDR} {VPN_CLIENT_ADDR}
tls-server
float
remote-cert-tls client
ca {root / 'ca.crt'}
cert {root / 'server.crt'}
key {root / 'server.key'}
dh none
data-ciphers AES-256-GCM:AES-128-GCM
auth SHA256
keepalive 10 60
verb 3
""",
        encoding="utf-8",
    )

    etc = Path("/etc/vpn-gate-alpha")
    etc.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "ca.crt", etc / "ca.crt")
    shutil.copy2(root / "client.crt", etc / "client.crt")
    shutil.copy2(root / "client.key", etc / "client.key")

    (etc / "openvpn.conf").write_text(
        f"""dev {VPN_IF}
dev-type tun
proto udp4
remote {SERVER_UNDERLAY} {OPENVPN_PORT}
lport {OPENVPN_LOCAL_PORT}
route-noexec
ifconfig {VPN_CLIENT_ADDR} {VPN_SERVER_ADDR}
tls-client
remote-cert-tls server
ca {etc / 'ca.crt'}
cert {etc / 'client.crt'}
key {etc / 'client.key'}
data-ciphers AES-256-GCM:AES-128-GCM
auth SHA256
ping 10
ping-restart 60
verb 3
""",
        encoding="utf-8",
    )

    (etc / "config.toml").write_text(
        f"""helper_routing_interfaces = ":local"
helper_routing_policy = "peaceful"

[device.ovpn]
enabled = true
expected_interfaces = ["{VPN_IF}"]
use_outbound_nat = false
allow_vpn_client = "udp:{OPENVPN_LOCAL_PORT}>{SERVER_UNDERLAY}:{OPENVPN_PORT}"
publish_vpn_server = "tcp/{SERVER_HOST}:{PUBLICATION_HOST_PORT}>{PUBLICATION_INTERNAL_PORT}"

[profile.alpha]
enabled = true
direction = "bidirectional"
destinations = ["{VPN_SERVER_ADDR}/32"]
device_order = ["ovpn"]
""",
        encoding="utf-8",
    )
    return server


PUBLICATION_SERVER = r'''
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((addr, port))
s.listen(1)
print('READY', flush=True)
conn, peer = s.accept()
conn.settimeout(5)
data = conn.recv(4096)
print(f'PEER={peer[0]}:{peer[1]}', flush=True)
conn.sendall(b'PUBACK:' + data)
conn.close()
s.close()
'''

PUBLICATION_CLIENT = r'''
import socket, sys
addr = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
s.connect((addr, port))
s.sendall(b'publication-e2e')
data = s.recv(4096)
peer = s.getpeername()
print(f'PEER={peer[0]}:{peer[1]}')
print('DATA=' + data.decode())
assert data == b'PUBACK:publication-e2e'
s.close()
'''


def spawn_publication_listener():
    proc = subprocess.Popen(
        (
            'ip', 'netns', 'exec', MANAGED,
            'python3', '-u', '-c', PUBLICATION_SERVER,
            INNER_ADDR, str(PUBLICATION_INTERNAL_PORT),
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    ready = proc.stdout.readline().strip()
    if ready != 'READY':
        out, err = proc.communicate(timeout=3)
        raise RuntimeError(
            f'publication listener did not become ready: {ready!r} {out!r} {err!r}'
        )
    return proc


def publication_probe():
    return ns_command(
        SERVER_NS,
        'python3', '-c', PUBLICATION_CLIENT,
        SERVER_HOST_CIDR.split('/')[0],
        str(PUBLICATION_HOST_PORT),
    )

def spawn_server(config, log_path):
    log = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        ("ip", "netns", "exec", SERVER_NS, "openvpn", "--config", str(config)),
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, log


def terminate(proc, log):
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    if log is not None:
        log.close()


def journal(unit):
    return command(
        ("journalctl", "-u", unit, "--no-pager", "-n", "200"),
        check=False,
    ).stdout


def same_netns(pid):
    process_ns = os.readlink(f"/proc/{pid}/ns/net")
    managed_ns = ns_command(MANAGED, "readlink", "/proc/self/ns/net").stdout.strip()
    return process_ns == managed_ns


def main():
    if os.geteuid() != 0:
        raise SystemExit("EXP-051 must run as root under systemd")

    root = Path(tempfile.mkdtemp(prefix="exp051-alpha-"))
    server_proc = None
    server_log = None
    publication_proc = None
    original_forward = command(("sysctl", "-n", "net.ipv4.ip_forward")).stdout.strip()

    cleanup()
    try:
        command(("ip", "addr", "add", f"{HOST_ADDR}/32", "dev", "lo"))
        generate_pki(root)
        setup_server_namespace()
        server_config = write_configs(root)

        # Install actual deployment files/code from the checked-out repository.
        command(("sh", "design/NG3/deployment/alpha/install.sh"))
        shutil.copy2(
            "design/NG3/deployment/alpha/vpn-gate-alpha-openvpn.service.example",
            "/etc/systemd/system/vpn-gate-alpha-openvpn.service",
        )
        systemctl("daemon-reload")

        command(("sysctl", "-w", "net.ipv4.ip_forward=1"))

        server_proc, server_log = spawn_server(
            server_config,
            root / "server.log",
        )
        wait_until(
            "OpenVPN server TUN",
            lambda: interface_exists(SERVER_NS, SERVER_TUN),
        )

        systemctl("start", ALPHA_UNIT)
        assert active(ALPHA_UNIT)
        assert Path(f"/run/netns/{MANAGED}").exists()
        assert interface_exists(MANAGED, INNER_BOUNDARY)
        status = runtime_status()
        assert status["readiness"] == "ready", status
        assert status["blocking_problems"] == [], status
        assert status["unknown_or_unconfirmed_fields"] == [], status
        assert status["configured_intent"]["profiles"][0]["profile_id"] == "alpha", status
        assert status["confirmed_effective_state"][0]["profile_id"] == "alpha", status
        assert status["confirmed_effective_state"][0]["ordered_paths"] == [], status
        assert status["availability_state"][0]["state"] == "disabled", status
        assert runtime_status_text() == """Devices
    ovpn: not discovered
Profiles
    alpha
"""
        print("EXP051_RUNTIME_STATUS_ZERO_PATH=PASS")
        print("EXP051_RUNTIME_STATUS_TEXT_ZERO_PATH=PASS")
        print("EXP051_ALPHA_CONTROLLER_READY=PASS")

        host_boundary_addr = json.loads(
            command(
                ("ip", "-j", "-4", "addr", "show", "dev", HOST_BOUNDARY)
            ).stdout
        )
        assert not host_boundary_addr or not host_boundary_addr[0].get("addr_info"), host_boundary_addr
        inner_boundary_addr = json.loads(
            ns_command(
                MANAGED, "ip", "-j", "-4", "addr", "show", "dev", INNER_BOUNDARY
            ).stdout
        )
        assert any(
            item.get("local") == INNER_ADDR and item.get("prefixlen") == 32
            for item in inner_boundary_addr[0].get("addr_info", ())
        ), inner_boundary_addr
        service_route = json.loads(
            command(
                ("ip", "-j", "-4", "route", "show", f"{INNER_ADDR}/32")
            ).stdout
        )
        assert len(service_route) == 1, service_route
        assert service_route[0].get("dev") == HOST_BOUNDARY, service_route
        assert service_route[0].get("gateway") is None, service_route
        stack_default = json.loads(
            ns_command(
                MANAGED, "ip", "-j", "-4", "route", "show", "default"
            ).stdout
        )
        assert len(stack_default) == 1, stack_default
        assert stack_default[0].get("dev") == INNER_BOUNDARY, stack_default
        assert stack_default[0].get("gateway") is None, stack_default
        print("EXP051_ROUTED_MANAGED_L3_BOUNDARY=PASS")

        # Server publication is a Device transport property and must be complete
        # even before a concrete VPN endpoint appears. Prove both the ordinary
        # host DNAT owner and the managed local INPUT/OUTPUT admission.
        host_publication = command(
            ("nft", "list", "table", "ip", "vpn_gate_publication")
        ).stdout
        assert "host-publication-owner-v1" in host_publication
        assert f'tcp dport {PUBLICATION_HOST_PORT}' in host_publication
        assert f'dnat to {INNER_ADDR}:{PUBLICATION_INTERNAL_PORT}' in host_publication

        managed_input = ns_command(
            MANAGED,
            "nft", "list", "chain", "ip", "vpn_gate", "stack_input",
        ).stdout
        managed_output = ns_command(
            MANAGED,
            "nft", "list", "chain", "ip", "vpn_gate", "stack_output",
        ).stdout
        assert "local-publication-v1" in managed_input
        assert f"tcp dport {PUBLICATION_INTERNAL_PORT}" in managed_input
        assert "local-publication-v1" in managed_output
        assert f"tcp sport {PUBLICATION_INTERNAL_PORT}" in managed_output

        publication_proc = spawn_publication_listener()
        publication = publication_probe()
        assert (
            f"PEER={SERVER_HOST_CIDR.split('/')[0]}:{PUBLICATION_HOST_PORT}"
            in publication.stdout
        )
        assert "DATA=PUBACK:publication-e2e" in publication.stdout
        pub_out, pub_err = publication_proc.communicate(timeout=5)
        assert publication_proc.returncode == 0, pub_err
        assert f"PEER={SERVER_UNDERLAY}:" in pub_out, pub_out
        publication_proc = None
        print("EXP051_SERVER_PUBLICATION_E2E=PASS")

        # Before VPN start there is no payload path, but the exact transport
        # contribution must already be present so the VPN can establish.
        stack_output = ns_command(
            MANAGED,
            "nft", "list", "chain", "ip", "vpn_gate", "stack_output",
        ).stdout
        assert f"udp sport {OPENVPN_LOCAL_PORT}" in stack_output
        assert f"udp dport {OPENVPN_PORT}" in stack_output
        assert "local-integration-v1" in stack_output
        print("EXP051_ZERO_PATH_TRANSPORT_ALLOW=PASS")

        systemctl("start", VPN_UNIT)
        wait_until(
            "stack OpenVPN vpn0",
            lambda: interface_exists(MANAGED, VPN_IF),
        )
        first_pid = main_pid(VPN_UNIT)
        assert same_netns(first_pid)
        print(f"EXP051_VPN_SYSTEMD_NAMESPACE=PASS:pid={first_pid}")

        wait_until(
            "server tunnel initialization",
            lambda: "Initialization Sequence Completed" in journal(VPN_UNIT),
        )

        # NAT-free remote return path for host-generated payload.
        command(
            (
                "ip", "-n", SERVER_NS, "route", "replace",
                f"{HOST_ADDR}/32",
                "via", VPN_CLIENT_ADDR,
                "dev", SERVER_TUN,
            )
        )
        main_remote = command(
            ("ip", "-j", "-4", "route", "show", "table", "main", f"{VPN_SERVER_ADDR}/32")
        ).stdout
        assert json.loads(main_remote) == [], main_remote
        selected_route = json.loads(
            command(
                ("ip", "-j", "-4", "route", "get", VPN_SERVER_ADDR)
            ).stdout
        )[0]
        assert selected_route.get("dev") == HOST_BOUNDARY, selected_route
        assert selected_route.get("gateway") is None, selected_route
        print("EXP051_SELECTED_HOST_BOOTSTRAP_DEVICE_ONLY=PASS")

        # +route-return must not install the stateful host-return nft owner.
        assert command(
            ("nft", "list", "table", "inet", "vpn_gate_host_return"),
            check=False,
        ).returncode != 0
        print("EXP051_ROUTE_RETURN_STATEFUL_OWNER_ABSENT=PASS")

        wait_until(
            "alpha periodic reconciliation and controlled payload",
            lambda: host_ping(VPN_SERVER_ADDR),
            timeout=30.0,
        )
        first_alpha_journal = journal(ALPHA_UNIT)
        assert "VPNG_ALPHA_RECONCILE status=reconciled" in first_alpha_journal
        print("EXP051_FIRST_PAYLOAD=PASS")
        print("EXP051_FIRST_MANAGER_RECONCILE=PASS")

        first_ifindex = json.loads(
            command(
                ("ip", "-n", MANAGED, "-j", "link", "show", "dev", VPN_IF)
            ).stdout
        )[0]["ifindex"]
        first_status = runtime_status()
        assert first_status["readiness"] == "ready", first_status
        first_paths = first_status["confirmed_effective_state"][0]["ordered_paths"]
        assert len(first_paths) == 1, first_status
        assert first_paths[0]["ifname"] == VPN_IF, first_status
        assert first_paths[0]["ifindex"] == first_ifindex, first_status
        assert runtime_status_text() == f"""Devices
    ovpn: {VPN_IF}
Profiles
    alpha
        01. {VPN_IF} unchecked
"""
        print("EXP051_RUNTIME_STATUS_FIRST_PATH=PASS")
        print("EXP051_RUNTIME_STATUS_TEXT_FIRST_PATH=PASS")
        # Remote-initiated host-local flow: the response must use the
        # selected route-based host bootstrap because +route-return opted out
        # of host conntrack return steering.
        command(
            (
                "ip", "-n", SERVER_NS, "route", "replace", f"{HOST_ADDR}/32",
                "via", VPN_CLIENT_ADDR, "dev", SERVER_TUN,
            )
        )
        remote_host = ns_command(
            SERVER_NS,
            "ping", "-c", "2", "-W", "1", HOST_ADDR,
            check=False,
        )
        if remote_host.returncode != 0:
            print(
                "EXP051_ROUTE_RETURN_DIAG_SERVER_ROUTE="
                + ns_command(
                    SERVER_NS,
                    "ip", "-j", "-4", "route", "get", HOST_ADDR,
                    check=False,
                ).stdout,
                flush=True,
            )
            print(
                "EXP051_ROUTE_RETURN_DIAG_HOST_ROUTE="
                + command(
                    ("ip", "-j", "-4", "route", "get", VPN_SERVER_ADDR),
                    check=False,
                ).stdout,
                flush=True,
            )
            print(
                "EXP051_ROUTE_RETURN_DIAG_FORWARD="
                + ns_command(
                    MANAGED,
                    "nft", "list", "chain", "ip", "vpn_gate", "payload_forward",
                    check=False,
                ).stdout,
                flush=True,
            )
            print(
                "EXP051_ROUTE_RETURN_DIAG_AFFINITY="
                + ns_command(
                    MANAGED,
                    "nft", "list", "table", "ip", "vpn_gate_return_affinity",
                    check=False,
                ).stdout,
                flush=True,
            )
            print(
                "EXP051_ROUTE_RETURN_DIAG_SERVER_PING="
                + remote_host.stdout
                + remote_host.stderr,
                flush=True,
            )
        assert remote_host.returncode == 0, remote_host.stderr
        print("EXP051_ROUTE_RETURN_HOST_LOCAL_REPLY=PASS")

        systemctl("restart", VPN_UNIT)
        wait_until(
            "new OpenVPN MainPID",
            lambda: active(VPN_UNIT) and main_pid(VPN_UNIT) != first_pid,
        )
        second_pid = main_pid(VPN_UNIT)
        assert same_netns(second_pid)
        wait_until(
            "recreated vpn0",
            lambda: interface_exists(MANAGED, VPN_IF),
        )
        second_ifindex = json.loads(
            command(
                ("ip", "-n", MANAGED, "-j", "link", "show", "dev", VPN_IF)
            ).stdout
        )[0]["ifindex"]
        assert second_ifindex != first_ifindex

        wait_until(
            "payload recovery after VPN-only restart",
            lambda: host_ping(VPN_SERVER_ADDR),
            timeout=30.0,
        )
        wait_until(
            "runtime status on recreated VPN generation",
            lambda: (
                (status := runtime_status()).get("readiness") == "ready"
                and len(
                    status.get("confirmed_effective_state", [{}])[0].get(
                        "ordered_paths", []
                    )
                ) == 1
                and status["confirmed_effective_state"][0]["ordered_paths"][0].get(
                    "ifindex"
                ) == second_ifindex
            ),
            timeout=30.0,
        )
        final_alpha_journal = journal(ALPHA_UNIT)
        reconcile_markers = final_alpha_journal.count(
            "VPNG_ALPHA_RECONCILE status=reconciled"
        )
        final_status = runtime_status()
        assert final_status["readiness"] == "ready", final_status
        final_paths = final_status["confirmed_effective_state"][0]["ordered_paths"]
        assert len(final_paths) == 1, final_status
        assert final_paths[0]["ifname"] == VPN_IF, final_status
        assert final_paths[0]["ifindex"] == second_ifindex, final_status
        assert final_paths[0]["ifindex"] != first_ifindex, final_status
        assert runtime_status_text() == f"""Devices
    ovpn: {VPN_IF}
Profiles
    alpha
        01. {VPN_IF} unchecked
"""
        print("EXP051_RUNTIME_STATUS_NEW_GENERATION=PASS")
        print("EXP051_RUNTIME_STATUS_TEXT_NEW_GENERATION=PASS")
        print(
            f"EXP051_MANAGER_RECONCILE_COUNT=PASS:{reconcile_markers}"
        )
        print(
            "EXP051_VPN_ONLY_RESTART_RECONCILED=PASS:"
            f"old_pid={first_pid}:new_pid={second_pid}:"
            f"old_ifindex={first_ifindex}:new_ifindex={second_ifindex}"
        )

        systemctl("stop", ALPHA_UNIT)
        wait_until(
            "bound OpenVPN stop",
            lambda: not active(VPN_UNIT),
        )
        assert not Path(f"/proc/{second_pid}").exists()
        assert not Path(f"/run/netns/{MANAGED}").exists()
        assert command(
            ("ip", "link", "show", "dev", HOST_BOUNDARY),
            check=False,
        ).returncode != 0
        assert command(
            ("nft", "list", "table", "ip", "vpn_gate_publication"),
            check=False,
        ).returncode != 0
        print("EXP051_SERVER_PUBLICATION_STOP_CLEAN=PASS")
        print("EXP051_STACK_STOP_CLEAN=PASS")
        print("EXP051_RESULT=PASS")
        return 0
    except Exception:
        print("EXP051_ALPHA_JOURNAL=" + json.dumps(journal(ALPHA_UNIT)[-12000:]))
        print("EXP051_VPN_JOURNAL=" + json.dumps(journal(VPN_UNIT)[-12000:]))
        try:
            tail = (root / "server.log").read_text(
                encoding="utf-8", errors="replace"
            )[-12000:]
        except OSError as exc:
            tail = f"<server log unavailable: {exc}>"
        print("EXP051_SERVER_LOG=" + json.dumps(tail))
        raise
    finally:
        if publication_proc is not None and publication_proc.poll() is None:
            publication_proc.terminate()
            try:
                publication_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                publication_proc.kill()
                publication_proc.wait(timeout=3)
        cleanup()
        terminate(server_proc, server_log)
        command(("sysctl", "-w", f"net.ipv4.ip_forward={original_forward}"), check=False)


if __name__ == "__main__":
    sys.exit(main())
