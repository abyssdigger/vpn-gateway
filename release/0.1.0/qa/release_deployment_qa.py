#!/usr/bin/env python3
"""VPN-GATE 0.1.0 release-bundle deployment QA on Debian 13/systemd."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


VERSION = "0.1.0"
CONTROLLER = "vpn-gate-alpha.service"
MANAGED = "vpn-gate-alpha"
STATUS_JSON = Path("/run/vpn-gate-alpha/status.json")
STATUS_TEXT = Path("/run/vpn-gate-alpha/status.txt")
HOST_TEST_ADDR = "198.19.255.1"


def command(argv, *, check=True, input_text=None):
    result = subprocess.run(
        tuple(str(item) for item in argv),
        text=True,
        input=input_text,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed {argv!r}: rc={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    return result


def ns(namespace, *argv, check=True):
    return command(("ip", "netns", "exec", namespace, *argv), check=check)


def systemctl(*argv, check=True):
    return command(("systemctl", *argv), check=check)


def active(unit):
    return systemctl("is-active", "--quiet", unit, check=False).returncode == 0


def wait_until(description, predicate, *, timeout=35.0, interval=0.25):
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


def status():
    return json.loads(STATUS_JSON.read_text(encoding="utf-8"))


def current_path():
    value = status()
    if value.get("version") != VERSION:
        return None
    effective = value.get("confirmed_effective_state")
    if not effective:
        return None
    paths = effective[0].get("ordered_paths", [])
    return paths[0] if len(paths) == 1 else None


def wait_path(ifname):
    wait_until(
        f"current path {ifname}",
        lambda: (path := current_path()) is not None and path.get("ifname") == ifname,
    )
    text = STATUS_TEXT.read_text(encoding="utf-8")
    assert text.startswith(f"VPN-GATE {VERSION}\n"), text


def wait_no_path():
    def predicate():
        value = status()
        if value.get("version") != VERSION:
            return False
        effective = value.get("confirmed_effective_state")
        return bool(effective) and effective[0].get("ordered_paths") == []
    wait_until("zero current paths", predicate)


def ping(address):
    return command(("ping", "-c", "2", "-W", "1", address), check=False).returncode == 0


def wait_ping(address):
    wait_until(f"payload ping {address}", lambda: ping(address), timeout=45.0)


def write_controller_config(device, ifname, allow, destination):
    Path("/etc/vpn-gate-alpha").mkdir(parents=True, exist_ok=True)
    Path("/etc/vpn-gate-alpha/config.toml").write_text(
        f"""log_level = "debug"
helper_routing_interfaces = ":local"
helper_routing_policy = "peaceful"

[device.{device}]
enabled = true
expected_interfaces = ["{ifname}"]
use_outbound_nat = true
allow_vpn_client = "{allow}"

[profile.qa]
enabled = true
direction = "outbound"
destinations = ["{destination}/32"]
device_order = ["{device}"]
""",
        encoding="utf-8",
    )


def setup_remote(namespace, host_if, remote_if, host_cidr, remote_cidr):
    cleanup_remote(namespace, host_if)
    command(("ip", "netns", "add", namespace))
    command(("ip", "link", "add", host_if, "type", "veth", "peer", "name", remote_if))
    command(("ip", "link", "set", remote_if, "netns", namespace))
    command(("ip", "addr", "add", host_cidr, "dev", host_if))
    command(("ip", "link", "set", host_if, "up"))
    command(("ip", "-n", namespace, "link", "set", "lo", "up"))
    command(("ip", "-n", namespace, "addr", "add", remote_cidr, "dev", remote_if))
    command(("ip", "-n", namespace, "link", "set", remote_if, "up"))
    host_ip = host_cidr.split("/")[0]
    command(("ip", "-n", namespace, "route", "replace", "default", "via", host_ip, "dev", remote_if))


def cleanup_remote(namespace, host_if):
    command(("ip", "netns", "del", namespace), check=False)
    command(("ip", "link", "del", host_if), check=False)


def controller_start():
    systemctl("start", CONTROLLER)
    assert active(CONTROLLER)
    wait_until("release status", STATUS_JSON.exists)
    value = status()
    assert value["version"] == VERSION, value
    assert STATUS_TEXT.read_text(encoding="utf-8").startswith(f"VPN-GATE {VERSION}\n")


def controller_stop():
    systemctl("stop", CONTROLLER, check=False)
    wait_until("controller stop", lambda: not active(CONTROLLER))
    wait_until("managed namespace removal", lambda: not Path(f"/run/netns/{MANAGED}").exists())


def write_unit(name, body):
    path = Path("/etc/systemd/system") / name
    path.write_text(body, encoding="utf-8")
    systemctl("daemon-reload")
    return path


def install_bundle():
    root = Path(tempfile.mkdtemp(prefix="vpn-gate-release-qa-"))
    archive = Path(f"/work/dist/vpn-gate-{VERSION}.tar.gz")
    assert archive.is_file(), archive
    command(("tar", "-xzf", archive, "-C", root))
    bundle = root / f"vpn-gate-{VERSION}"
    command((bundle / "install.sh",))
    installed = Path("/usr/lib/vpn-gate-alpha/VERSION").read_text(encoding="ascii").strip()
    assert installed == VERSION, installed
    print("RELEASE_QA_BUNDLE_INSTALL=PASS")
    return root


def test_wireguard():
    namespace = "qa-wg-srv"
    host_if, remote_if = "qwg-h", "qwg-r"
    unit = "vpn-gate-wg@wg-corp.service"
    setup_remote(namespace, host_if, remote_if, "198.19.254.1/30", "198.19.254.2/30")
    root = Path(tempfile.mkdtemp(prefix="qa-wg-"))
    try:
        server_private = command(("wg", "genkey")).stdout.strip()
        server_public = command(("wg", "pubkey"), input_text=server_private + "\n").stdout.strip()
        client_private = command(("wg", "genkey")).stdout.strip()
        client_public = command(("wg", "pubkey"), input_text=client_private + "\n").stdout.strip()

        server_conf = root / "wg-server.conf"
        server_conf.write_text(
            f"""[Interface]
PrivateKey = {server_private}
Address = 10.70.0.1/32
ListenPort = 51820

[Peer]
PublicKey = {client_public}
AllowedIPs = 10.70.0.2/32
""",
            encoding="utf-8",
        )
        server_conf.chmod(0o600)
        ns(namespace, "wg-quick", "up", str(server_conf))

        Path("/etc/wireguard").mkdir(parents=True, exist_ok=True)
        client_conf = Path("/etc/wireguard/wg-corp.conf")
        client_conf.write_text(
            f"""[Interface]
PrivateKey = {client_private}
Address = 10.70.0.2/32
ListenPort = 51821
Table = off

[Peer]
PublicKey = {server_public}
Endpoint = 198.19.254.2:51820
AllowedIPs = 10.70.0.1/32
PersistentKeepalive = 5
""",
            encoding="utf-8",
        )
        client_conf.chmod(0o600)

        write_unit(
            "vpn-gate-wg@.service",
            """[Unit]
Description=VPN-GATE QA WireGuard %i
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
Type=oneshot
RemainAfterExit=yes
NetworkNamespacePath=/run/netns/vpn-gate-alpha
ExecStart=/usr/bin/wg-quick up %i
ExecStop=/usr/bin/wg-quick down %i
""",
        )
        write_controller_config(
            "wg", "wg-corp", "udp:51821>198.19.254.2:51820", "10.70.0.1"
        )
        controller_start()
        systemctl("start", unit)
        wait_path("wg-corp")
        wait_ping("10.70.0.1")
        print("RELEASE_QA_WIREGUARD_PAYLOAD=PASS")
        systemctl("stop", unit)
        wait_no_path()
        controller_stop()
        print("RELEASE_QA_WIREGUARD_LIFECYCLE=PASS")
    finally:
        systemctl("stop", unit, check=False)
        controller_stop()
        ns(namespace, "wg-quick", "down", str(root / "wg-server.conf"), check=False)
        cleanup_remote(namespace, host_if)
        shutil.rmtree(root, ignore_errors=True)


def cert_pin(cert):
    pub = command(("openssl", "x509", "-in", cert, "-pubkey", "-noout")).stdout
    der = subprocess.run(
        ("openssl", "pkey", "-pubin", "-outform", "DER"),
        input=pub.encode(),
        capture_output=True,
        check=True,
    ).stdout
    return "pin-sha256:" + base64.b64encode(hashlib.sha256(der).digest()).decode()


def test_openconnect():
    namespace = "qa-oc-srv"
    host_if, remote_if = "qoc-h", "qoc-r"
    unit = "vpn-gate-openconnect-qa.service"
    setup_remote(namespace, host_if, remote_if, "198.19.253.1/30", "198.19.253.2/30")
    root = Path(tempfile.mkdtemp(prefix="qa-oc-"))
    server = None
    try:
        cert = root / "server.pem"
        key = root / "server.key"
        command((
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", key, "-out", cert, "-days", "1",
            "-subj", "/CN=198.19.253.2",
        ))
        passwd = root / "passwd"
        command(("ocpasswd", "-c", passwd, "qa"), input_text="qa\nqa\n")
        config = root / "ocserv.conf"
        config.write_text(
            f"""auth = "plain[passwd={passwd}]"
listen-host = 198.19.253.2
tcp-port = 4443
udp-port = 4443
run-as-user = nobody
run-as-group = nogroup
socket-file = {root / "ocserv.sock"}
pid-file = {root / "ocserv.pid"}
server-cert = {cert}
server-key = {key}
isolate-workers = false
max-clients = 4
max-same-clients = 2
device = vpns
predictable-ips = true
ipv4-network = 10.71.0.0
ipv4-netmask = 255.255.255.0
route = 10.72.0.1/255.255.255.255
tunnel-all-dns = false
cisco-client-compat = true
""",
            encoding="utf-8",
        )
        command(("ip", "-n", namespace, "addr", "add", "10.72.0.1/32", "dev", "lo"))
        ns(namespace, "sysctl", "-w", "net.ipv4.ip_forward=1")
        log = (root / "ocserv.log").open("w", encoding="utf-8")
        server = subprocess.Popen(
            ("ip", "netns", "exec", namespace, "ocserv", "-f", "-c", str(config)),
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        wait_until(
            "ocserv TCP listener",
            lambda: ":4443" in ns(namespace, "ss", "-lnt").stdout,
        )

        pin = cert_pin(cert)
        env = Path("/etc/vpn-gate-alpha/openconnect-qa.env")
        env.write_text("QA_OC_PASSWORD=qa\n", encoding="utf-8")
        env.chmod(0o600)
        write_unit(
            unit,
            f"""[Unit]
Description=VPN-GATE QA OpenConnect
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
Type=simple
NetworkNamespacePath=/run/netns/vpn-gate-alpha
EnvironmentFile=/etc/vpn-gate-alpha/openconnect-qa.env
ExecStart=/bin/sh -c 'printf "%s\\n" "$QA_OC_PASSWORD" | exec /usr/sbin/openconnect --non-inter --passwd-on-stdin --user=qa --no-dtls --interface=vpn-corp --script=/usr/lib/vpn-gate-alpha/openconnect-policy-neutral.sh --servercert={pin} https://198.19.253.2:4443'
Restart=no
""",
        )
        write_controller_config("oc", "vpn-corp", "tcp>198.19.253.2:4443", "10.72.0.1")
        controller_start()
        systemctl("start", unit)
        wait_path("vpn-corp")
        wait_ping("10.72.0.1")
        print("RELEASE_QA_OPENCONNECT_PAYLOAD=PASS")
        systemctl("stop", unit)
        wait_no_path()
        controller_stop()
        print("RELEASE_QA_OPENCONNECT_LIFECYCLE=PASS")
    finally:
        systemctl("stop", unit, check=False)
        controller_stop()
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        cleanup_remote(namespace, host_if)
        shutil.rmtree(root, ignore_errors=True)


def test_l2tp():
    namespace = "qa-l2tp-srv"
    host_if, remote_if = "ql2-h", "ql2-r"
    unit = "vpn-gate-l2tp-qa.service"
    setup_remote(namespace, host_if, remote_if, "198.19.252.1/30", "198.19.252.2/30")
    root = Path(tempfile.mkdtemp(prefix="qa-l2tp-"))
    server = None
    try:
        server_ppp = root / "server.ppp"
        client_ppp = root / "client.ppp"
        common = """noauth
nodefaultroute
noccp
nobsdcomp
nodeflate
nopcomp
noaccomp
mtu 1400
mru 1400
lcp-echo-interval 5
lcp-echo-failure 3
"""
        server_ppp.write_text(common, encoding="utf-8")
        client_ppp.write_text(
            common + "ipcp-accept-local\nipcp-accept-remote\n",
            encoding="utf-8",
        )
        server_conf = root / "server.conf"
        server_conf.write_text(
            f"""[global]
port = 1701

[lns default]
ip range = 10.73.0.2-10.73.0.2
local ip = 10.73.0.1
require authentication = no
pppoptfile = {server_ppp}
length bit = yes
""",
            encoding="utf-8",
        )
        client_conf = root / "client.conf"
        client_conf.write_text(
            f"""[global]
port = 1701

[lac qa]
lns = 198.19.252.2
pppoptfile = {client_ppp}
autodial = yes
redial = no
length bit = yes
""",
            encoding="utf-8",
        )
        server_ctl = root / "server-control"
        server_pid = root / "server.pid"
        server_log = (root / "server.log").open("w", encoding="utf-8")
        server = subprocess.Popen(
            (
                "ip", "netns", "exec", namespace,
                "xl2tpd", "-D", "-c", str(server_conf),
                "-p", str(server_pid), "-C", str(server_ctl),
            ),
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        time.sleep(1.0)
        if server.poll() is not None:
            raise RuntimeError((root / "server.log").read_text(encoding="utf-8"))

        write_unit(
            unit,
            f"""[Unit]
Description=VPN-GATE QA L2TP
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
Type=simple
NetworkNamespacePath=/run/netns/vpn-gate-alpha
ExecStart=/usr/sbin/xl2tpd -D -c {client_conf} -p /run/qa-l2tp.pid -C /run/qa-l2tp-control
Restart=no
""",
        )
        write_controller_config(
            "l2tp", "ppp0", "udp:1701>198.19.252.2:1701", "10.73.0.1"
        )
        controller_start()
        systemctl("start", unit)
        wait_path("ppp0")
        wait_ping("10.73.0.1")
        print("RELEASE_QA_L2TP_PAYLOAD=PASS")
        systemctl("stop", unit)
        wait_no_path()
        controller_stop()
        print("RELEASE_QA_L2TP_LIFECYCLE=PASS")
    finally:
        systemctl("stop", unit, check=False)
        controller_stop()
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        cleanup_remote(namespace, host_if)
        shutil.rmtree(root, ignore_errors=True)


def cleanup_global():
    for unit in (
        "vpn-gate-wg@wg-corp.service",
        "vpn-gate-openconnect-qa.service",
        "vpn-gate-l2tp-qa.service",
    ):
        systemctl("stop", unit, check=False)
    systemctl("stop", CONTROLLER, check=False)
    command(("ip", "netns", "del", MANAGED), check=False)
    command(("ip", "link", "del", "vnga-host0"), check=False)
    command(("ip", "addr", "del", f"{HOST_TEST_ADDR}/32", "dev", "lo"), check=False)
    for namespace, host_if in (
        ("qa-wg-srv", "qwg-h"),
        ("qa-oc-srv", "qoc-h"),
        ("qa-l2tp-srv", "ql2-h"),
    ):
        cleanup_remote(namespace, host_if)


def main():
    if os.geteuid() != 0:
        raise SystemExit("release deployment QA must run as root")
    os_release = Path("/etc/os-release").read_text(encoding="utf-8")
    assert 'VERSION_ID="13"' in os_release or "VERSION_ID=13" in os_release, os_release

    original_forward = command(("sysctl", "-n", "net.ipv4.ip_forward")).stdout.strip()
    bundle_root = None
    cleanup_global()
    try:
        command(("sysctl", "-w", "net.ipv4.ip_forward=1"))
        command(("ip", "addr", "add", f"{HOST_TEST_ADDR}/32", "dev", "lo"))
        bundle_root = install_bundle()
        test_wireguard()
        test_openconnect()
        test_l2tp()
        print("RELEASE_QA_RESULT=PASS")
        return 0
    finally:
        cleanup_global()
        command(("sysctl", "-w", f"net.ipv4.ip_forward={original_forward}"), check=False)
        if bundle_root is not None:
            shutil.rmtree(bundle_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
