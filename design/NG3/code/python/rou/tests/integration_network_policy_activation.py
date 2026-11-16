from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import os
import subprocess
import sys
import time

from rou.binding import LogicalPathId
from rou.composite_nft_policy import CompositeNftDesiredState
from rou.device_firewall_desired import DeviceFirewallDesiredState
from rou.forwarding_gate import ForwardingGateState
from rou.interface_inventory import parse_ip_link_inventory
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import LinuxNftScaffoldBackend, SubprocessNftRunner
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.linux_structural_policy import LinuxStructuralPolicyBackend
from rou.local_publication_policy import LocalPublicationDesiredState
from rou.network_policy_activation import (
    NetworkPolicyActivationStatus,
    activate_network_policy,
)
from rou.payload_forward_desired import (
    PayloadForwardDesiredState,
    PayloadForwardRuleSpec,
)
from rou.payload_forward_observation import (
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
)
from rou.payload_nat_desired import PayloadNatDesiredState
from rou.payload_routing_desired import (
    ManagedRouteSpec,
    ManagedRouteType,
    ManagedRuleSpec,
    PayloadRoutingDesiredState,
)


TARGET = IPv4Address("203.0.113.58")
TARGET_NET = IPv4Network(f"{TARGET}/32")
PORT = 58058
TABLE = 0x80000000
RULE_PRIORITY = 0x4000


def raw_run(*argv: str, check: bool = True):
    return subprocess.run(
        argv,
        check=check,
        text=True,
        capture_output=True,
    )


def ns(name: str, *argv: str, check: bool = True):
    return raw_run("ip", "netns", "exec", name, *argv, check=check)


def start_udp(namespace: str, payload: str) -> subprocess.Popen:
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
            str(TARGET), str(PORT), payload,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def udp_probe(namespace: str) -> str | None:
    code = r"""
import socket, sys
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.5)
sock.sendto(b"probe", (sys.argv[1], int(sys.argv[2])))
try:
    data, _ = sock.recvfrom(128)
except OSError:
    raise SystemExit(1)
sys.stdout.write(data.decode())
"""
    result = ns(
        namespace,
        "python3", "-c", code, str(TARGET), str(PORT),
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def current_identity(runner, namespace: str, ifname: str):
    values = parse_ip_link_inventory(
        runner.run(("ip", "-n", namespace, "-j", "link", "show"))
    )
    matches = [value for value in values if value.ifname == ifname]
    assert len(matches) == 1, (ifname, values)
    return matches[0]


def routing_desired(host, path=None):
    routes = [
        ManagedRouteSpec(
            table=TABLE,
            destination=IPv4Network("0.0.0.0/0"),
            route_type=ManagedRouteType.BLACKHOLE,
            protocol=201,
            metric=0xFFFFFFFF,
        )
    ]
    if path is not None:
        routes.append(
            ManagedRouteSpec(
                table=TABLE,
                destination=TARGET_NET,
                route_type=ManagedRouteType.UNICAST,
                protocol=202,
                metric=1,
                path_id=LogicalPathId("vpn", 0, 0),
                endpoint=path,
                gateway=IPv4Address("10.58.2.2"),
            )
        )

    return PayloadRoutingDesiredState(
        host_boundary=host,
        routes=tuple(routes),
        rules=(
            ManagedRuleSpec(
                priority=RULE_PRIORITY,
                ingress=host,
                destination=TARGET_NET,
                table=TABLE,
            ),
        ),
    )


def nft_desired(host=None, path=None):
    if host is None or path is None:
        forward = PayloadForwardDesiredState(())
    else:
        forward = PayloadForwardDesiredState((
            PayloadForwardRuleSpec(
                kind=PayloadForwardRuleKind.NEW,
                ingress=host,
                egress=path,
                remote_field=PayloadForwardRemoteField.DESTINATION,
                remote_prefix=TARGET_NET,
            ),
            PayloadForwardRuleSpec(
                kind=PayloadForwardRuleKind.RETURN,
                ingress=path,
                egress=host,
                remote_field=PayloadForwardRemoteField.SOURCE,
                remote_prefix=TARGET_NET,
            ),
        ))

    return CompositeNftDesiredState(
        forward,
        PayloadNatDesiredState(()),
        DeviceFirewallDesiredState(()),
        LocalPublicationDesiredState(()),
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit(
            "integration_network_policy_activation must run as root"
        )

    suffix = str(os.getpid())
    host_ns = f"na-h-{suffix}"
    managed = f"na-m-{suffix}"
    vpn_ns = f"na-v-{suffix}"
    alt_ns = f"na-a-{suffix}"
    created = []
    servers = []

    h_if = f"nah-{suffix}"
    mh_if = f"namh-{suffix}"
    mv_if = f"namv-{suffix}"
    v_if = f"nav-{suffix}"
    ma_if = f"nama-{suffix}"
    a_if = f"naa-{suffix}"

    runner = SubprocessNftRunner()

    try:
        for name in (host_ns, managed, vpn_ns, alt_ns):
            raw_run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        for left, right, left_ns, right_ns in (
            (h_if, mh_if, host_ns, managed),
            (mv_if, v_if, managed, vpn_ns),
            (ma_if, a_if, managed, alt_ns),
        ):
            raw_run("ip", "link", "add", left, "type", "veth", "peer", "name", right)
            raw_run("ip", "link", "set", left, "netns", left_ns)
            raw_run("ip", "link", "set", right, "netns", right_ns)

        addresses = (
            (host_ns, h_if, "10.58.1.2/30"),
            (managed, mh_if, "10.58.1.1/30"),
            (managed, mv_if, "10.58.2.1/30"),
            (vpn_ns, v_if, "10.58.2.2/30"),
            (managed, ma_if, "10.58.3.1/30"),
            (alt_ns, a_if, "10.58.3.2/30"),
        )
        for namespace, interface, address in addresses:
            ns(namespace, "ip", "addr", "add", address, "dev", interface)
            ns(namespace, "ip", "link", "set", interface, "up")

        ns(vpn_ns, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")
        ns(alt_ns, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")
        ns(vpn_ns, "ip", "route", "add", "10.58.1.0/30", "via", "10.58.2.1")
        ns(alt_ns, "ip", "route", "add", "10.58.1.0/30", "via", "10.58.3.1")
        ns(host_ns, "ip", "route", "add", f"{TARGET}/32", "via", "10.58.1.1")
        ns(
            managed,
            "ip", "route", "add", f"{TARGET}/32",
            "via", "10.58.3.2", "dev", ma_if,
        )

        ns(managed, "sysctl", "-q", "-w", "net.ipv4.ip_forward=1")
        for key in ("all", "default", mh_if, mv_if, ma_if):
            ns(
                managed,
                "sysctl", "-q", "-w",
                f"net.ipv4.conf.{key}.rp_filter=0",
            )

        servers.extend((
            start_udp(vpn_ns, "vpn"),
            start_udp(alt_ns, "alt"),
        ))
        time.sleep(0.25)
        for server in servers:
            if server.poll() is not None:
                out, err = server.communicate()
                raise AssertionError(
                    f"UDP server failed rc={server.returncode} "
                    f"stdout={out!r} stderr={err!r}"
                )

        assert udp_probe(host_ns) == "alt", (
            "ambient/main fallback route was not live before activation"
        )
        assert ns(
            managed,
            "nft", "list", "table", "ip", "vpn_gate",
            check=False,
        ).returncode != 0

        host = current_identity(runner, managed, mh_if)
        vpn = current_identity(runner, managed, mv_if)

        gate = LinuxForwardingGateBackend(runner, managed)
        scaffold = LinuxNftScaffoldBackend(runner, managed)
        structural = LinuxStructuralPolicyBackend(
            runner=runner,
            namespace=managed,
            platform=NG3_LINUX_POLICY_PLATFORM,
        )

        zero = activate_network_policy(
            gate,
            scaffold,
            structural,
            routing_desired(host, None),
            nft_desired(),
            NG3_LINUX_POLICY_PLATFORM,
        )
        assert zero.status is NetworkPolicyActivationStatus.READY, (
            zero.status,
            zero.diagnostic,
        )
        assert zero.ready
        assert zero.scaffold_prepare is not None
        assert zero.scaffold_prepare.confirmed
        assert gate.observe_forwarding_gate() is ForwardingGateState.ENABLED
        assert udp_probe(host_ns) is None, (
            "zero-path activation escaped through ambient/main route"
        )
        print("NETWORK_POLICY_ACTIVATION_ZERO_PATH_BOOTSTRAP=PASS")

        active = activate_network_policy(
            gate,
            scaffold,
            structural,
            routing_desired(host, vpn),
            nft_desired(host, vpn),
            NG3_LINUX_POLICY_PLATFORM,
        )
        assert active.status is NetworkPolicyActivationStatus.READY, (
            active.status,
            active.diagnostic,
        )
        assert active.ready
        assert active.scaffold_prepare is None, (
            "exact scaffold with existing policy must not be scaffold-repaired"
        )
        assert gate.observe_forwarding_gate() is ForwardingGateState.ENABLED
        assert udp_probe(host_ns) == "vpn"
        print("NETWORK_POLICY_ACTIVATION_CURRENT_PATH=PASS")

        print("NG3 network policy activation integration: PASS")
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
            raw_run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
