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
BUNDLE_README = None
BUNDLE_DEPLOYMENT = None


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


def document_text(path):
    return Path(path).read_text(encoding="utf-8")


def require_documentation(section, *snippets):
    assert BUNDLE_DEPLOYMENT is not None
    text = document_text(BUNDLE_DEPLOYMENT)
    assert section in text, f"missing documented section: {section}"
    for snippet in snippets:
        assert snippet in text, f"missing documented instruction in {section}: {snippet!r}"


def doc_pass(step):
    print(f"DOC_WALKTHROUGH_{step}=PASS", flush=True)


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


def write_controller_config(ifname, allow, destination):
    require_documentation(
        "## Common integration procedure for any VPN",
        'log_level = "info"',
        'helper_routing_interfaces = ":local"',
        '[device.corp]',
        '[profile.corp]',
    )
    Path("/etc/vpn-gate-alpha").mkdir(parents=True, exist_ok=True)
    Path("/etc/vpn-gate-alpha/config.toml").write_text(
        f"""log_level = "info"
helper_routing_interfaces = ":local"
helper_routing_policy = "peaceful"

[device.corp]
enabled = true
expected_interfaces = ["{ifname}"]
use_outbound_nat = true
allow_vpn_client = "{allow}"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["{destination}/32"]
device_order = ["corp"]
""",
        encoding="utf-8",
    )
    doc_pass("CONFIG")


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


def install_packages(*packages):
    command(("apt-get", "update"))
    command(("env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", *packages))


def verify_admin_diagnostics(stack, ifname):
    require_documentation(
        "## Operational checks",
        "systemctl --no-pager --full status vpn-gate-alpha.service",
        "cat /run/vpn-gate-alpha/status.txt",
        "journalctl -u vpn-gate-alpha.service -p warning --no-pager",
        "ip netns exec vpn-gate-alpha ip -br link",
    )
    systemctl("--no-pager", "--full", "status", CONTROLLER)
    first = command(("head", "-1", STATUS_TEXT)).stdout.strip()
    assert first == f"VPN-GATE {VERSION}", first
    human = command(("cat", STATUS_TEXT)).stdout
    assert ifname in human, human
    machine = command(("python3", "-m", "json.tool", STATUS_JSON)).stdout
    assert ifname in machine, machine
    command(("journalctl", "-u", CONTROLLER, "-p", "warning", "--no-pager"))
    links = ns(MANAGED, "ip", "-br", "link").stdout
    assert ifname in links, links
    doc_pass(f"{stack}_DIAGNOSTICS")


def install_bundle():
    global BUNDLE_README, BUNDLE_DEPLOYMENT
    root = Path(tempfile.mkdtemp(prefix="vpn-gate-release-qa-"))
    archive = Path(f"/work/dist/vpn-gate-{VERSION}.tar.gz")
    assert archive.is_file(), archive
    command(("tar", "-xzf", archive, "-C", root))
    bundle = root / f"vpn-gate-{VERSION}"
    BUNDLE_README = bundle / "README.md"
    BUNDLE_DEPLOYMENT = bundle / "DEPLOYMENT.md"
    assert BUNDLE_README.is_file()
    assert BUNDLE_DEPLOYMENT.is_file()
    readme_text = document_text(BUNDLE_README)
    assert "tar -xzf vpn-gate-0.1.0.tar.gz" in readme_text
    assert "./install.sh" in readme_text
    doc_pass("BUNDLE_EXTRACT")

    require_documentation(
        "## Supported deployment boundary",
        "apt-get update",
        "apt-get install -y python3 iproute2 iputils-ping nftables procps",
    )
    command(("apt-get", "update"))
    command((
        "env", "DEBIAN_FRONTEND=noninteractive",
        "apt-get", "install", "-y",
        "python3", "iproute2", "iputils-ping", "nftables", "procps",
    ))
    doc_pass("BASE_PREREQUISITES")

    command((bundle / "install.sh",))
    installed = Path("/usr/lib/vpn-gate-alpha/VERSION").read_text(encoding="ascii").strip()
    assert installed == VERSION, installed
    assert Path("/usr/share/doc/vpn-gate/README.md").read_bytes() == BUNDLE_README.read_bytes()
    assert Path("/usr/share/doc/vpn-gate/DEPLOYMENT.md").read_bytes() == BUNDLE_DEPLOYMENT.read_bytes()
    print(
        "DOC_WALKTHROUGH_README_SHA256="
        + hashlib.sha256(BUNDLE_README.read_bytes()).hexdigest(),
        flush=True,
    )
    print(
        "DOC_WALKTHROUGH_DEPLOYMENT_SHA256="
        + hashlib.sha256(BUNDLE_DEPLOYMENT.read_bytes()).hexdigest(),
        flush=True,
    )
    doc_pass("BUNDLE_INSTALL")
    print("RELEASE_QA_BUNDLE_INSTALL=PASS")
    return root


def test_wireguard():
    require_documentation(
        "## WireGuard / wg-quick example",
        "apt-get install -y wireguard-tools",
        "Table = off",
        "NetworkNamespacePath=/run/netns/vpn-gate-alpha",
        'expected_interfaces = ["wg-corp"]',
    )
    install_packages("wireguard-tools")
    command(("modprobe", "wireguard"), check=False)
    doc_pass("WIREGUARD_PREREQUISITES")
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

        Path("/etc/wireguard").mkdir(parents=True, exist_ok=True)
        server_key = Path("/etc/wireguard/qa-server.key")
        server_key.write_text(server_private + "\n", encoding="ascii")
        server_key.chmod(0o600)
        ns(namespace, "ip", "link", "add", "wg-server", "type", "wireguard")
        ns(namespace, "ip", "addr", "add", "10.70.0.1/32", "dev", "wg-server")
        ns(
            namespace,
            "wg", "set", "wg-server",
            "private-key", str(server_key),
            "listen-port", "51820",
            "peer", client_public,
            "allowed-ips", "10.70.0.2/32",
        )
        ns(namespace, "ip", "link", "set", "wg-server", "up")
        ns(namespace, "ip", "route", "replace", "10.70.0.2/32", "dev", "wg-server")


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
Description=VPN-GATE WireGuard %i
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
Type=oneshot
RemainAfterExit=yes
NetworkNamespacePath=/run/netns/vpn-gate-alpha
ExecStart=/usr/bin/wg-quick up %i
ExecStop=/usr/bin/wg-quick down %i

[Install]
WantedBy=multi-user.target
""",
        )
        write_controller_config(
            "wg-corp", "udp:51821>198.19.254.2:51820", "10.70.0.1"
        )
        controller_start()
        systemctl("start", unit)
        wait_path("wg-corp")
        verify_admin_diagnostics("WIREGUARD", "wg-corp")
        wait_ping("10.70.0.1")
        doc_pass("WIREGUARD_PAYLOAD")
        print("RELEASE_QA_WIREGUARD_PAYLOAD=PASS")

        systemctl("stop", unit)
        wait_no_path()
        assert active(CONTROLLER)
        doc_pass("WIREGUARD_STOP_STATUS")
        systemctl("start", unit)
        wait_path("wg-corp")
        verify_admin_diagnostics("WIREGUARD_RESTART", "wg-corp")
        wait_ping("10.70.0.1")
        doc_pass("WIREGUARD_RESTART_PAYLOAD")

        systemctl("stop", unit)
        wait_no_path()
        controller_stop()
        print("RELEASE_QA_WIREGUARD_LIFECYCLE=PASS")
    finally:
        systemctl("stop", unit, check=False)
        controller_stop()
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
    require_documentation(
        "## OpenConnect example",
        "apt-get install -y openconnect",
        "VPN_GATE_OC_SERVER=",
        "VPN_GATE_OC_USER=",
        "VPN_GATE_OC_PASSWORD=",
        "VPN_GATE_OC_SERVERCERT=",
        "NetworkNamespacePath=/run/netns/vpn-gate-alpha",
    )
    install_packages("openconnect")
    # Remote ocserv and certificate generation are QA-harness-only peer setup.
    install_packages("ocserv", "openssl")
    doc_pass("OPENCONNECT_PREREQUISITES")
    namespace = "qa-oc-srv"
    host_if, remote_if = "qoc-h", "qoc-r"
    unit = "vpn-gate-openconnect-qa.service"
    setup_remote(namespace, host_if, remote_if, "198.19.253.1/30", "198.19.253.2/30")
    root = Path(tempfile.mkdtemp(prefix="qa-oc-"))
    root.chmod(0o755)
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
        env = Path("/etc/vpn-gate-alpha/openconnect-corp.env")
        env.write_text(
            "VPN_GATE_OC_SERVER=https://198.19.253.2:4443/\n"
            "VPN_GATE_OC_USER=qa\n"
            "VPN_GATE_OC_PASSWORD=qa\n"
            f"VPN_GATE_OC_SERVERCERT={pin}\n",
            encoding="utf-8",
        )
        env.chmod(0o600)
        Path("/etc/vpn-gate-alpha/openconnect-corp.conf").write_text(
            "no-dtls\n",
            encoding="utf-8",
        )
        write_unit(
            "vpn-gate-openconnect@.service",
            """[Unit]
Description=VPN-GATE OpenConnect %i
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
Type=simple
NetworkNamespacePath=/run/netns/vpn-gate-alpha
EnvironmentFile=/etc/vpn-gate-alpha/openconnect-%i.env
ExecStart=/bin/sh -c 'printf "%%s\\n" "$VPN_GATE_OC_PASSWORD" | exec /usr/sbin/openconnect --non-inter --passwd-on-stdin --user="$VPN_GATE_OC_USER" --interface=vpn-%i --script=/usr/lib/vpn-gate-alpha/openconnect-policy-neutral.sh --config=/etc/vpn-gate-alpha/openconnect-%i.conf --servercert="$VPN_GATE_OC_SERVERCERT" "$VPN_GATE_OC_SERVER"'
Restart=no

[Install]
WantedBy=multi-user.target
""",
        )
        unit = "vpn-gate-openconnect@corp.service"
        write_controller_config("vpn-corp", "tcp>198.19.253.2:4443", "10.72.0.1")
        controller_start()
        systemctl("start", unit)
        try:
            wait_path("vpn-corp")
        except Exception:
            print("RELEASE_QA_OPENCONNECT_SYSTEMD=" + systemctl(
                "status", unit, "--no-pager", "--full", check=False
            ).stdout.replace("\n", "\\n"))
            print("RELEASE_QA_OPENCONNECT_JOURNAL=" + command(
                ("journalctl", "-u", unit, "--no-pager", "-n", "200"),
                check=False,
            ).stdout.replace("\n", "\\n"))
            print("RELEASE_QA_OPENCONNECT_LINKS=" + ns(
                MANAGED, "ip", "-br", "link", check=False
            ).stdout.replace("\n", "\\n"))
            print("RELEASE_QA_OCSERV_LOG=" + (
                root / "ocserv.log"
            ).read_text(encoding="utf-8", errors="replace").replace("\n", "\\n"))
            raise
        verify_admin_diagnostics("OPENCONNECT", "vpn-corp")
        wait_ping("10.72.0.1")
        doc_pass("OPENCONNECT_PAYLOAD")
        print("RELEASE_QA_OPENCONNECT_PAYLOAD=PASS")

        systemctl("stop", unit)
        wait_no_path()
        assert active(CONTROLLER)
        doc_pass("OPENCONNECT_STOP_STATUS")
        systemctl("start", unit)
        wait_path("vpn-corp")
        verify_admin_diagnostics("OPENCONNECT_RESTART", "vpn-corp")
        wait_ping("10.72.0.1")
        doc_pass("OPENCONNECT_RESTART_PAYLOAD")

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
    require_documentation(
        "## L2TP client integration",
        "apt-get install -y xl2tpd ppp",
        "/etc/ppp/options.vpn-gate-corp",
        "/etc/xl2tpd/xl2tpd-vpn-gate-corp.conf",
        "NetworkNamespacePath=/run/netns/vpn-gate-alpha",
        "connect-lac corp",
    )
    install_packages("xl2tpd", "ppp")
    command(("modprobe", "ppp_generic"), check=False)
    command(("modprobe", "pppol2tp"), check=False)
    doc_pass("L2TP_PREREQUISITES")
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
        Path("/etc/ppp").mkdir(parents=True, exist_ok=True)
        client_ppp = Path("/etc/ppp/options.vpn-gate-corp")
        client_ppp.write_text(
            common + "ipcp-accept-local\nipcp-accept-remote\n",
            encoding="utf-8",
        )
        Path("/etc/xl2tpd").mkdir(parents=True, exist_ok=True)
        client_conf = Path("/etc/xl2tpd/xl2tpd-vpn-gate-corp.conf")
        client_conf.write_text(
            f"""[global]
port = 1701

[lac corp]
lns = 198.19.252.2
pppoptfile = {client_ppp}
autodial = no
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

        unit = "vpn-gate-l2tp-corp.service"
        write_unit(
            unit,
            """[Unit]
Description=VPN-GATE L2TP corp
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
Type=simple
NetworkNamespacePath=/run/netns/vpn-gate-alpha
ExecStart=/usr/sbin/xl2tpd -D -c /etc/xl2tpd/xl2tpd-vpn-gate-corp.conf -p /run/vpn-gate-l2tp-corp.pid -C /run/vpn-gate-l2tp-corp-control
Restart=no
""",
        )
        write_controller_config(
            "ppp0", "udp>198.19.252.2:1701", "10.73.0.1"
        )
        controller_start()
        systemctl("start", unit)
        wait_until(
            "L2TP control socket",
            lambda: Path("/run/vpn-gate-l2tp-corp-control").exists(),
        )
        ns(
            MANAGED,
            "xl2tpd-control",
            "-c", "/run/vpn-gate-l2tp-corp-control",
            "connect-lac", "corp",
        )
        try:
            wait_path("ppp0")
        except Exception:
            print("RELEASE_QA_L2TP_SYSTEMD=" + systemctl(
                "status", unit, "--no-pager", "--full", check=False
            ).stdout.replace("\n", "\\n"))
            print("RELEASE_QA_L2TP_JOURNAL=" + command(
                ("journalctl", "-u", unit, "--no-pager", "-n", "200"),
                check=False,
            ).stdout.replace("\n", "\\n"))
            print("RELEASE_QA_L2TP_LINKS=" + ns(
                MANAGED, "ip", "-br", "link", check=False
            ).stdout.replace("\n", "\\n"))
            print("RELEASE_QA_L2TP_SERVER_LOG=" + (
                root / "server.log"
            ).read_text(encoding="utf-8", errors="replace").replace("\n", "\\n"))
            raise
        verify_admin_diagnostics("L2TP", "ppp0")
        wait_ping("10.73.0.1")
        doc_pass("L2TP_PAYLOAD")
        print("RELEASE_QA_L2TP_PAYLOAD=PASS")

        systemctl("stop", unit)
        wait_no_path()
        assert active(CONTROLLER)
        doc_pass("L2TP_STOP_STATUS")
        systemctl("start", unit)
        wait_until(
            "L2TP control socket after restart",
            lambda: Path("/run/vpn-gate-l2tp-corp-control").exists(),
        )
        ns(
            MANAGED,
            "xl2tpd-control",
            "-c", "/run/vpn-gate-l2tp-corp-control",
            "connect-lac", "corp",
        )
        wait_path("ppp0")
        verify_admin_diagnostics("L2TP_RESTART", "ppp0")
        wait_ping("10.73.0.1")
        doc_pass("L2TP_RESTART_PAYLOAD")

        test_documented_protective("10.73.0.1", "ppp0")
        test_protective_negative("10.73.0.1")

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


def test_documented_protective(payload_address, ifname):
    require_documentation(
        "## Protective mode",
        "vpn-gate-control protective status",
        "vpn-gate-control protective enter",
        "vpn-gate-control protective leave",
        '"status": "inactive"',
        '"status": "active"',
    )
    control = ("/usr/sbin/vpn-gate-control", "protective")
    initial = json.loads(command((*control, "status")).stdout)
    assert initial["ok"] is True, initial
    assert initial["protective"]["status"] == "inactive", initial
    doc_pass("PROTECTIVE_INITIAL_STATUS")

    entered = json.loads(command((*control, "enter")).stdout)
    assert entered["ok"] is True, entered
    active_status = json.loads(command((*control, "status")).stdout)
    assert active_status["ok"] is True, active_status
    assert active_status["protective"]["status"] == "active", active_status
    wait_path(ifname)
    assert not ping(payload_address)
    doc_pass("PROTECTIVE_ENTER_STATUS_PAYLOAD")

    left = json.loads(command((*control, "leave")).stdout)
    assert left["ok"] is True, left
    inactive_status = json.loads(command((*control, "status")).stdout)
    assert inactive_status["ok"] is True, inactive_status
    assert inactive_status["protective"]["status"] == "inactive", inactive_status
    wait_path(ifname)
    wait_ping(payload_address)
    doc_pass("PROTECTIVE_LEAVE_STATUS_PAYLOAD")
    print("RELEASE_QA_PROTECTIVE_ENTER_BLOCK=PASS")
    print("RELEASE_QA_PROTECTIVE_SAFE_LEAVE=PASS")


def test_protective_negative(payload_address):
    control = ("/usr/sbin/vpn-gate-control", "protective")

    entered = json.loads(command((*control, "enter")).stdout)
    assert entered["ok"] is True, entered
    ns(MANAGED, "nft", "delete", "table", "inet", "vpn_gate_protective")
    wait_until(
        "Protective mode periodic gate repair",
        lambda: ns(
            MANAGED,
            "nft",
            "list",
            "table",
            "inet",
            "vpn_gate_protective",
            check=False,
        ).returncode == 0,
    )
    assert not ping(payload_address)
    print("RELEASE_QA_PROTECTIVE_PERIODIC_REPAIR=PASS")
    safe = json.loads(command((*control, "leave")).stdout)
    assert safe["ok"] is True, safe
    wait_ping(payload_address)

    reentered = json.loads(command((*control, "enter")).stdout)
    assert reentered["ok"] is True, reentered
    assert not ping(payload_address)
    ns(MANAGED, "nft", "delete", "table", "ip", "vpn_gate")
    ns(MANAGED, "nft", "add", "table", "ip", "vpn_gate")
    blocked_leave = command((*control, "leave"), check=False)
    assert blocked_leave.returncode != 0, blocked_leave
    blocked = json.loads(blocked_leave.stdout)
    assert blocked["ok"] is False, blocked
    assert blocked["action_status"] == "leave_blocked", blocked
    assert blocked["protective"]["status"] == "active", blocked
    assert not ping(payload_address)
    print("RELEASE_QA_PROTECTIVE_FAILED_LEAVE_RETAINS_BLOCK=PASS")

    ns(MANAGED, "nft", "delete", "table", "ip", "vpn_gate")
    wait_until(
        "Protective mode release after normal-state recovery",
        lambda: (
            json.loads(command((*control, "status")).stdout)
            ["protective"]["status"]
            == "inactive"
        ),
    )
    wait_ping(payload_address)
    print("RELEASE_QA_PROTECTIVE_RECOVERY_RELEASE=PASS")


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
    try:
        bundle_root = install_bundle()
        cleanup_global()
        original_forward = command(("sysctl", "-n", "net.ipv4.ip_forward")).stdout.strip()
        command(("sysctl", "-w", "net.ipv4.ip_forward=1"))
        command(("ip", "addr", "add", f"{HOST_TEST_ADDR}/32", "dev", "lo"))
        test_wireguard()
        test_openconnect()
        test_l2tp()
        doc_pass("ADMINISTRATOR_PROCEDURE")
        print("RELEASE_QA_DOCUMENTATION_WALKTHROUGH=PASS")
        print("RELEASE_QA_RESULT=PASS")
        return 0
    finally:
        if command(("command", "-v", "ip"), check=False).returncode == 0:
            cleanup_global()
        if "original_forward" in locals():
            command(("sysctl", "-w", f"net.ipv4.ip_forward={original_forward}"), check=False)
        if bundle_root is not None:
            shutil.rmtree(bundle_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
