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
HOST_ADDR = "198.19.255.1"

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
    command(("ip", "netns", "del", MANAGED), check=False)
    command(("ip", "link", "del", HOST_BOUNDARY), check=False)
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
        f"""[device.ovpn]
enabled = true
expected_interfaces = ["{VPN_IF}"]

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["{VPN_SERVER_ADDR}/32"]
device_order = ["ovpn"]

[integration.openvpn-alpha]
device = "ovpn"
protocol = "udp"
remote_ipv4 = "{SERVER_UNDERLAY}"
remote_port = {OPENVPN_PORT}
local_port = {OPENVPN_LOCAL_PORT}
""",
        encoding="utf-8",
    )
    return server


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
    original_forward = command(("sysctl", "-n", "net.ipv4.ip_forward")).stdout.strip()

    cleanup()
    try:
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
        print("EXP051_ALPHA_CONTROLLER_READY=PASS")

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
        command(
            (
                "ip", "route", "replace", f"{VPN_SERVER_ADDR}/32",
                "via", INNER_ADDR, "dev", HOST_BOUNDARY,
            )
        )

        wait_until(
            "alpha periodic reconciliation and controlled payload",
            lambda: host_ping(VPN_SERVER_ADDR),
            timeout=30.0,
        )
        print("EXP051_FIRST_PAYLOAD=PASS")

        first_ifindex = json.loads(
            command(
                ("ip", "-n", MANAGED, "-j", "link", "show", "dev", VPN_IF)
            ).stdout
        )[0]["ifindex"]

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
        cleanup()
        terminate(server_proc, server_log)
        command(("sysctl", "-w", f"net.ipv4.ip_forward={original_forward}"), check=False)


if __name__ == "__main__":
    sys.exit(main())
