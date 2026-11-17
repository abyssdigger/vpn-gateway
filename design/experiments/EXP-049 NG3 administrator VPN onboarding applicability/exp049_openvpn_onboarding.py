#!/usr/bin/env python3
"""EXP-049: real OpenVPN endpoint onboarding through the current NG3 stack."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Interface
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from rou.binding import DeviceBindingState, LogicalPathId, project_device_bindings
from rou.config import parse_structural_config
from rou.controller_startup import ControllerStartupStatus, start_controller_once
from rou.controller_stop import ControllerStopStatus, stop_controller_once
from rou.device_policy import (
    DeviceFirewallPolicyIntent,
    DeviceNatPolicyIntent,
    NatIntent,
)
from rou.direct_device_route import realize_direct_device_path_routes
from rou.instance_lock import InstanceLockSpec
from rou.interface_inventory import parse_ip_link_inventory
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.managed_network_domain import (
    ManagedNetworkDomainSpec,
    destroy_managed_network_domain,
    ensure_managed_network_domain,
)
from rou.network_policy_layout import allocate_network_policy_layout
from rou.payload_network_policy_desired import (
    PayloadNetworkPolicyDesiredState,
    build_payload_network_policy_desired_state,
)
from rou.payload_profile import build_payload_profile_requests


MANAGED = "e49-managed"
HOST_BOUNDARY = "e49host"
INNER_BOUNDARY = "host0"
SERVER_NS = "e49-server"
SERVER_HOST = "e49srvh"
SERVER_INNER = "srv0"
VPN_IF = "vpn0"
SERVER_TUN = "tun-srv"

HOST_ADDR = IPv4Interface("198.19.255.1/30")
INNER_ADDR = IPv4Interface("198.19.255.2/30")
SERVER_HOST_CIDR = "198.19.254.1/30"
SERVER_ADDR_CIDR = "198.19.254.2/30"
SERVER_UNDERLAY = "198.19.254.2"
VPN_SERVER_ADDR = "10.253.0.1"
VPN_CLIENT_ADDR = "10.253.0.2"
OPENVPN_PORT = 11940

STRUCTURAL_CONFIG = f"""
[device.ovpn]
enabled = true
expected_interfaces = ["{VPN_IF}"]

[profile.exp049]
enabled = true
direction = "outbound"
destinations = ["{VPN_SERVER_ADDR}/32"]
device_order = ["ovpn"]
"""


def command(argv, *, check=True, capture=True, input_text=None):
    completed = subprocess.run(
        tuple(str(item) for item in argv),
        check=False,
        text=True,
        input=input_text,
        capture_output=capture,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed rc={completed.returncode}: {' '.join(map(str, argv))}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


def ns_command(namespace, *argv, check=True):
    return command(("ip", "netns", "exec", namespace, *argv), check=check)


def wait_until(description, predicate, timeout=15.0, interval=0.1):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception as exc:  # evidence polling; retain final failure context
            last_error = exc
        time.sleep(interval)
    raise RuntimeError(
        f"timeout waiting for {description}"
        + (f": last error {last_error}" if last_error else "")
    )


def interface_exists(namespace, ifname):
    return (
        command(
            ("ip", "-n", namespace, "link", "show", "dev", ifname),
            check=False,
        ).returncode
        == 0
    )


def ping(namespace, address, *, count=2):
    return (
        ns_command(
            namespace,
            "ping",
            "-c",
            str(count),
            "-W",
            "1",
            address,
            check=False,
        ).returncode
        == 0
    )


def host_ping(address):
    return (
        command(
            ("ping", "-c", "2", "-W", "1", address),
            check=False,
        ).returncode
        == 0
    )


def generate_pki(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    command(
        (
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", root / "ca.key",
            "-out", root / "ca.crt",
            "-days", "1",
            "-subj", "/CN=EXP049-CA",
        )
    )
    for name in ("server", "client"):
        command(
            (
                "openssl", "req", "-newkey", "rsa:2048", "-nodes",
                "-keyout", root / f"{name}.key",
                "-out", root / f"{name}.csr",
                "-subj", f"/CN=EXP049-{name}",
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


def write_openvpn_configs(root: Path) -> tuple[Path, Path]:
    server = root / "server.conf"
    client = root / "client.conf"
    server.write_text(
        f"""dev {SERVER_TUN}
dev-type tun
proto udp4
local {SERVER_UNDERLAY}
port {OPENVPN_PORT}
ifconfig {VPN_SERVER_ADDR} {VPN_CLIENT_ADDR}
tls-server
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
    client.write_text(
        f"""dev {VPN_IF}
dev-type tun
proto udp4
remote {SERVER_UNDERLAY} {OPENVPN_PORT}
nobind
ifconfig {VPN_CLIENT_ADDR} {VPN_SERVER_ADDR}
tls-client
remote-cert-tls server
ca {root / 'ca.crt'}
cert {root / 'client.crt'}
key {root / 'client.key'}
data-ciphers AES-256-GCM:AES-128-GCM
auth SHA256
ping 10
ping-restart 60
verb 3
""",
        encoding="utf-8",
    )
    return server, client


def spawn_openvpn(namespace: str, config: Path, log_path: Path):
    log = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        ("ip", "netns", "exec", namespace, "openvpn", "--config", str(config)),
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return process, log


def terminate_process(process, log) -> None:
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if log is not None:
        log.close()


def setup_server_namespace() -> None:
    command(("ip", "netns", "del", SERVER_NS), check=False)
    command(("ip", "link", "del", SERVER_HOST), check=False)
    command(("ip", "netns", "add", SERVER_NS))
    command(("ip", "link", "add", SERVER_HOST, "type", "veth", "peer", "name", SERVER_INNER))
    command(("ip", "link", "set", SERVER_INNER, "netns", SERVER_NS))
    command(("ip", "addr", "add", SERVER_HOST_CIDR, "dev", SERVER_HOST))
    command(("ip", "link", "set", SERVER_HOST, "up"))
    command(("ip", "-n", SERVER_NS, "link", "set", "lo", "up"))
    command(("ip", "-n", SERVER_NS, "addr", "add", SERVER_ADDR_CIDR, "dev", SERVER_INNER))
    command(("ip", "-n", SERVER_NS, "link", "set", SERVER_INNER, "up"))
    command(
        (
            "ip", "-n", SERVER_NS, "route", "replace", "default",
            "via", "198.19.254.1", "dev", SERVER_INNER,
        )
    )


def teardown_server_namespace() -> None:
    command(("ip", "netns", "del", SERVER_NS), check=False)
    command(("ip", "link", "del", SERVER_HOST), check=False)


@dataclass
class PreparedPolicy:
    config_text: str
    observed_binding: object | None = None
    observed_interfaces: tuple | None = None
    desired: PayloadNetworkPolicyDesiredState | None = None

    def build_current(self, host_boundary, interfaces):
        cfg = parse_structural_config(self.config_text)
        binding = project_device_bindings(
            cfg.device_binding_intents,
            DeviceBindingState.empty(),
            interfaces,
        )
        expected_path = LogicalPathId("ovpn", 0, 0)
        if len(binding.bindings) != 1:
            raise AssertionError(f"expected exactly one binding, got {binding.bindings!r}")
        if binding.bindings[0].path_id != expected_path:
            raise AssertionError(binding.bindings[0])
        if binding.bindings[0].endpoint.ifname != VPN_IF:
            raise AssertionError(binding.bindings[0])

        profiles = build_payload_profile_requests(
            cfg.profiles.values(),
            binding.bindings,
        )
        path_routes = realize_direct_device_path_routes(binding.bindings)
        layout = allocate_network_policy_layout(
            profiles,
            (),
            NG3_LINUX_POLICY_PLATFORM,
        )
        desired = build_payload_network_policy_desired_state(
            profiles,
            layout,
            path_routes,
            host_boundary,
            (DeviceNatPolicyIntent("ovpn", NatIntent.MASQUERADE),),
            (DeviceFirewallPolicyIntent("ovpn", rules=None),),
            (),
        )

        self.observed_binding = binding
        self.observed_interfaces = tuple(interfaces)
        self.desired = desired
        return desired


def cleanup_managed(domain_spec, runner) -> None:
    try:
        destroy_managed_network_domain(domain_spec, runner)
    except Exception as exc:
        print(f"EXP049_CLEANUP_MANAGED_FALLBACK={type(exc).__name__}:{exc}")
        command(("ip", "netns", "del", MANAGED), check=False)
        command(("ip", "link", "del", HOST_BOUNDARY), check=False)


def run_cycle(
    cycle: int,
    *,
    root: Path,
    server_config: Path,
    client_config: Path,
    runner,
    domain_spec,
    lock_spec,
) -> bool:
    server_proc = client_proc = None
    server_log = client_log = None
    startup = None

    print(f"EXP049_CYCLE_{cycle}_BEGIN")
    setup_server_namespace()

    try:
        ensured = ensure_managed_network_domain(domain_spec, runner)
        assert ensured.confirmed

        before_json = runner.run(("ip", "-n", MANAGED, "-j", "link", "show"))
        before = parse_ip_link_inventory(before_json)
        assert all(item.ifname != VPN_IF for item in before)
        print(f"EXP049_CYCLE_{cycle}_VPN_ENDPOINT_ABSENT=PASS")

        server_proc, server_log = spawn_openvpn(
            SERVER_NS,
            server_config,
            root / f"server-cycle-{cycle}.log",
        )
        wait_until(
            "OpenVPN server TUN",
            lambda: interface_exists(SERVER_NS, SERVER_TUN),
        )

        underlay_before = ping(MANAGED, SERVER_UNDERLAY, count=1)
        print(
            f"EXP049_CYCLE_{cycle}_UNDERLAY_BEFORE_CLIENT="
            + ("PASS" if underlay_before else "FAIL")
        )
        if not underlay_before:
            raise RuntimeError("managed-domain underlay cannot reach OpenVPN server")

        client_proc, client_log = spawn_openvpn(
            MANAGED,
            client_config,
            root / f"client-cycle-{cycle}.log",
        )
        try:
            wait_until(
                "OpenVPN client vpn0",
                lambda: interface_exists(MANAGED, VPN_IF),
            )
        except Exception:
            for label, path in (
                ("server", root / f"server-cycle-{cycle}.log"),
                ("client", root / f"client-cycle-{cycle}.log"),
            ):
                try:
                    tail = path.read_text(encoding="utf-8", errors="replace")[-12000:]
                except OSError as exc:
                    tail = f"<cannot read log: {exc}>"
                print(
                    f"EXP049_CYCLE_{cycle}_{label.upper()}_LOG_TAIL="
                    + json.dumps(tail)
                )
            raise
        wait_until(
            "pre-policy OpenVPN tunnel payload",
            lambda: ping(MANAGED, VPN_SERVER_ADDR, count=1),
        )
        print(f"EXP049_CYCLE_{cycle}_REAL_OPENVPN_TUNNEL_IN_MANAGED_DOMAIN=PASS")

        inventory_json = runner.run(("ip", "-n", MANAGED, "-j", "link", "show"))
        inventory = parse_ip_link_inventory(inventory_json)
        cfg = parse_structural_config(STRUCTURAL_CONFIG)
        binding = project_device_bindings(
            cfg.device_binding_intents,
            DeviceBindingState.empty(),
            inventory,
        )
        assert len(binding.bindings) == 1, binding
        assert binding.bindings[0].path_id == LogicalPathId("ovpn", 0, 0)
        assert binding.bindings[0].endpoint.ifname == VPN_IF
        print(
            f"EXP049_CYCLE_{cycle}_FRESH_BINDING=PASS:"
            f"{binding.bindings[0].path_id!r}->{binding.bindings[0].endpoint!r}"
        )

        holder = {}

        def load_policy():
            prepared = PreparedPolicy(STRUCTURAL_CONFIG)
            holder["prepared"] = prepared
            return prepared

        startup = start_controller_once(
            lock_spec,
            domain_spec,
            runner,
            NG3_LINUX_POLICY_PLATFORM,
            load_policy,
        )
        assert startup.status is ControllerStartupStatus.READY, (
            startup.status,
            startup.diagnostic,
        )
        assert startup.ready and startup.session is not None
        prepared = holder["prepared"]
        assert prepared.observed_binding is not None
        assert len(prepared.observed_binding.bindings) == 1
        assert prepared.observed_binding.bindings[0].endpoint.ifname == VPN_IF
        print(f"EXP049_CYCLE_{cycle}_PRODUCTION_STARTUP_BINDING_ACTIVATION=PASS")

        command(
            (
                "ip", "route", "replace", f"{VPN_SERVER_ADDR}/32",
                "via", str(INNER_ADDR.ip), "dev", HOST_BOUNDARY,
            )
        )

        stack_output = ns_command(
            MANAGED,
            "nft", "list", "chain", "ip", "vpn_gate", "stack_output",
        ).stdout
        print(
            f"EXP049_CYCLE_{cycle}_STACK_OUTPUT="
            + json.dumps(stack_output.strip())
        )

        payload_ok = host_ping(VPN_SERVER_ADDR)
        print(
            f"EXP049_CYCLE_{cycle}_CONTROLLED_PAYLOAD_THROUGH_ADMITTED_PATH="
            + ("PASS" if payload_ok else "FAIL")
        )

        underlay_after = ping(MANAGED, SERVER_UNDERLAY, count=1)
        print(
            f"EXP049_CYCLE_{cycle}_LOCAL_UNDERLAY_AFTER_ACTIVATION="
            + ("PASS" if underlay_after else "BLOCKED")
        )

        return payload_ok
    finally:
        terminate_process(client_proc, client_log)
        client_proc = client_log = None

        if interface_exists(MANAGED, VPN_IF) if command(
            ("ip", "netns", "list"), check=False
        ).stdout.find(MANAGED) >= 0 else False:
            print(f"EXP049_CYCLE_{cycle}_VPN_ENDPOINT_AFTER_CLIENT_STOP=PRESENT")
        else:
            print(f"EXP049_CYCLE_{cycle}_VPN_ENDPOINT_AFTER_CLIENT_STOP=ABSENT")

        if startup is not None and startup.session is not None:
            stopped = stop_controller_once(startup.session, domain_spec, runner)
            print(f"EXP049_CYCLE_{cycle}_CONTROLLER_STOP={stopped.status.value}")
            if stopped.status is not ControllerStopStatus.STOPPED:
                cleanup_managed(domain_spec, runner)
        else:
            cleanup_managed(domain_spec, runner)

        terminate_process(server_proc, server_log)
        teardown_server_namespace()

        namespaces = command(("ip", "netns", "list"), check=False).stdout
        host_link = command(
            ("ip", "link", "show", "dev", HOST_BOUNDARY),
            check=False,
        )
        assert MANAGED not in namespaces
        assert host_link.returncode != 0
        print(f"EXP049_CYCLE_{cycle}_MANAGED_DOMAIN_CLEAN=PASS")


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-049 must run as root")

    version = command(("openvpn", "--version")).stdout.splitlines()[0]
    os_release = Path("/etc/os-release").read_text(encoding="utf-8")
    print("EXP049_TARGET_OS=" + json.dumps(os_release.strip()))
    print("EXP049_OPENVPN=" + json.dumps(version))

    root = Path(tempfile.mkdtemp(prefix="exp049-openvpn-"))
    runner = SubprocessNftRunner()
    domain_spec = ManagedNetworkDomainSpec(
        namespace=MANAGED,
        host_interface=HOST_BOUNDARY,
        inner_interface=INNER_BOUNDARY,
        host_address=HOST_ADDR,
        inner_address=INNER_ADDR,
    )
    lock_spec = InstanceLockSpec(
        runtime_directory=root / "runtime",
        expected_owner_uid=os.getuid(),
    )

    original_forward = command(
        ("sysctl", "-n", "net.ipv4.ip_forward")
    ).stdout.strip()

    try:
        cleanup_managed(domain_spec, runner)
        teardown_server_namespace()
        command(("sysctl", "-w", "net.ipv4.ip_forward=1"))

        generate_pki(root)
        server_config, client_config = write_openvpn_configs(root)

        outcomes = []
        for cycle in (1, 2):
            outcomes.append(
                run_cycle(
                    cycle,
                    root=root,
                    server_config=server_config,
                    client_config=client_config,
                    runner=runner,
                    domain_spec=domain_spec,
                    lock_spec=lock_spec,
                )
            )

        if all(outcomes):
            print("EXP049_RESULT=PASS")
            return 0

        print("EXP049_RESULT=FAIL")
        print(
            "EXP049_FINDING=real OpenVPN endpoint onboarding/binding succeeds, "
            "but accepted NG3 activation blocks the VPN client's local underlay "
            "traffic through terminal stack_input/stack_output policy without a "
            "concrete supported-integration local/system allow contribution"
        )
        return 1
    finally:
        cleanup_managed(domain_spec, runner)
        teardown_server_namespace()
        command(
            ("sysctl", "-w", f"net.ipv4.ip_forward={original_forward}"),
            check=False,
        )
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
