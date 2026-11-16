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
from rou.linux_composite_nft import LinuxCompositeNftBackend
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import LinuxNftScaffoldBackend, SubprocessNftRunner
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.linux_structural_policy import LinuxStructuralPolicyBackend
from rou.linux_structural_routing import LinuxStructuralRoutingBackend
from rou.local_publication_policy import LocalPublicationDesiredState
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
from rou.structural_policy_mutation import (
    StructuralPolicyMutationStatus,
    converge_structural_policy_step_once,
)
from rou.structural_policy_plan import StructuralPolicyStepKind


TARGET = IPv4Address("203.0.113.57")
TARGET_NET = IPv4Network(f"{TARGET}/32")
PORT = 57057
NEW_TABLE = 0x80000000
OLD_TABLE = 0x80000001
NEW_RULE = 0x4000
OLD_RULE = 0x4001


def raw_run(*argv: str, check: bool = True):
    return subprocess.run(
        argv,
        check=check,
        text=True,
        capture_output=True,
    )


class FaultAfterSuccessRunner:
    def __init__(self):
        self.delegate = SubprocessNftRunner()
        self.failed = False

    def run(self, argv):
        command = tuple(argv)
        stdout = self.delegate.run(command)
        if (
            not self.failed
            and "rule" in command
            and "add" in command
            and "priority" in command
            and str(NEW_RULE) in command
        ):
            self.failed = True
            raise RuntimeError(
                "synthetic transport error after successful desired RPDB add"
            )
        return stdout

    def run_script(self, argv, script):
        return self.delegate.run_script(argv, script)


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


def forward_desired(host, path):
    return PayloadForwardDesiredState((
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


def nft_desired(host=None, path=None):
    return CompositeNftDesiredState(
        forward_desired(host, path)
        if host is not None and path is not None
        else PayloadForwardDesiredState(()),
        PayloadNatDesiredState(()),
        DeviceFirewallDesiredState(()),
        LocalPublicationDesiredState(()),
    )


def routing_desired(host, path=None):
    routes = [
        ManagedRouteSpec(
            table=NEW_TABLE,
            destination=IPv4Network("0.0.0.0/0"),
            route_type=ManagedRouteType.BLACKHOLE,
            protocol=201,
            metric=0xFFFFFFFF,
        )
    ]
    if path is not None:
        routes.append(
            ManagedRouteSpec(
                table=NEW_TABLE,
                destination=TARGET_NET,
                route_type=ManagedRouteType.UNICAST,
                protocol=202,
                metric=1,
                path_id=LogicalPathId("vpn", 0, 0),
                endpoint=path,
                gateway=IPv4Address("10.57.2.2"),
            )
        )
    return PayloadRoutingDesiredState(
        host_boundary=host,
        routes=tuple(routes),
        rules=(
            ManagedRuleSpec(
                priority=NEW_RULE,
                ingress=host,
                destination=TARGET_NET,
                table=NEW_TABLE,
            ),
        ),
    )


def converge(
    gate,
    backend,
    routing,
    nft,
    host_namespace: str,
    *,
    max_steps: int = 32,
):
    steps = []
    final = None
    for _ in range(max_steps):
        result = converge_structural_policy_step_once(
            gate,
            backend,
            routing,
            nft,
            NG3_LINUX_POLICY_PLATFORM,
        )
        if result.step is not None:
            steps.append(result.step.kind)

        if result.status is StructuralPolicyMutationStatus.STEP_APPLIED:
            assert (
                gate.observe_forwarding_gate()
                is ForwardingGateState.DISABLED
            )
            assert udp_probe(host_namespace) is None, (
                result.status,
                result.step,
            )
            continue

        if result.status is StructuralPolicyMutationStatus.CONFIRMED:
            assert result.confirmed
            final = result
            break

        raise AssertionError(
            f"structural convergence failed: {result.status} "
            f"{result.diagnostic}"
        )

    assert final is not None, steps
    return final, steps


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration_structural_policy_mutation must run as root")

    suffix = str(os.getpid())
    host_ns = f"sp-h-{suffix}"
    managed = f"sp-m-{suffix}"
    vpn_ns = f"sp-v-{suffix}"
    alt_ns = f"sp-a-{suffix}"
    created = []
    servers = []

    h_if = f"sph-{suffix}"
    mh_if = f"spmh-{suffix}"
    mv_if = f"spmv-{suffix}"
    v_if = f"spv-{suffix}"
    ma_if = f"spma-{suffix}"
    a_if = f"spa-{suffix}"

    runner = FaultAfterSuccessRunner()

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
            (host_ns, h_if, "10.57.1.2/30"),
            (managed, mh_if, "10.57.1.1/30"),
            (managed, mv_if, "10.57.2.1/30"),
            (vpn_ns, v_if, "10.57.2.2/30"),
            (managed, ma_if, "10.57.3.1/30"),
            (alt_ns, a_if, "10.57.3.2/30"),
        )
        for namespace, interface, address in addresses:
            ns(namespace, "ip", "addr", "add", address, "dev", interface)
            ns(namespace, "ip", "link", "set", interface, "up")

        for peer in (vpn_ns, alt_ns):
            ns(peer, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")
            ns(peer, "ip", "route", "add", "10.57.1.0/30", "via",
               "10.57.2.1" if peer == vpn_ns else "10.57.3.1")

        ns(host_ns, "ip", "route", "add", f"{TARGET}/32", "via", "10.57.1.1")
        ns(
            managed,
            "ip", "route", "add", f"{TARGET}/32",
            "via", "10.57.3.2", "dev", ma_if,
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

        host = current_identity(runner, managed, mh_if)
        vpn = current_identity(runner, managed, mv_if)
        alt = current_identity(runner, managed, ma_if)

        LinuxNftScaffoldBackend(runner, managed).create_payload_scaffold()
        nft_backend = LinuxCompositeNftBackend(runner, managed)
        old_forward = forward_desired(host, alt)
        for spec in old_forward.rules:
            nft_backend.add_profile_rule(spec)

        old_routing = LinuxStructuralRoutingBackend(runner, managed)
        old_routing.add_route(
            ManagedRouteSpec(
                table=OLD_TABLE,
                destination=IPv4Network("0.0.0.0/0"),
                route_type=ManagedRouteType.BLACKHOLE,
                protocol=201,
                metric=0xFFFFFFFF,
            )
        )
        old_routing.add_route(
            ManagedRouteSpec(
                table=OLD_TABLE,
                destination=TARGET_NET,
                route_type=ManagedRouteType.UNICAST,
                protocol=202,
                metric=1,
                path_id=LogicalPathId("old", 0, 0),
                endpoint=alt,
                gateway=IPv4Address("10.57.3.2"),
            )
        )
        old_routing.add_rule(
            ManagedRuleSpec(
                priority=OLD_RULE,
                ingress=host,
                destination=TARGET_NET,
                table=OLD_TABLE,
            )
        )

        assert udp_probe(host_ns) == "alt", "old accepted policy is not active"

        gate = LinuxForwardingGateBackend(runner, managed)
        backend = LinuxStructuralPolicyBackend(
            runner=runner,
            namespace=managed,
            platform=NG3_LINUX_POLICY_PLATFORM,
        )

        final, steps = converge(
            gate,
            backend,
            routing_desired(host, vpn),
            nft_desired(host, vpn),
            host_ns,
        )

        assert steps[:5] == [
            StructuralPolicyStepKind.ADD_GUARD_ROUTE,
            StructuralPolicyStepKind.DELETE_ROUTING_RULE,
            StructuralPolicyStepKind.DELETE_ROUTING_ROUTE,
            StructuralPolicyStepKind.DELETE_ROUTING_ROUTE,
            StructuralPolicyStepKind.ADD_PATH_ROUTE,
        ], steps
        assert steps[-1] is StructuralPolicyStepKind.ADD_ROUTING_RULE, steps
        assert steps.count(StructuralPolicyStepKind.APPLY_NFT_STEP) == 4, steps
        assert runner.failed, "synthetic post-success RPDB error was not exercised"
        assert final.diagnostic is not None
        assert "apply raised RuntimeError" in final.diagnostic
        assert gate.observe_forwarding_gate() is ForwardingGateState.ENABLED
        assert udp_probe(host_ns) == "vpn", "new exact policy did not activate VPN path"
        print("STRUCTURAL_CROSS_DOMAIN_NEW_POLICY=PASS")

        zero_final, zero_steps = converge(
            gate,
            backend,
            routing_desired(host, None),
            nft_desired(),
            host_ns,
        )
        assert zero_final.confirmed
        assert zero_steps[0] is StructuralPolicyStepKind.DELETE_ROUTING_ROUTE
        assert zero_steps.count(StructuralPolicyStepKind.APPLY_NFT_STEP) == 2
        assert gate.observe_forwarding_gate() is ForwardingGateState.ENABLED
        assert udp_probe(host_ns) is None, "zero-path Profile escaped to ambient/main"
        print("STRUCTURAL_CROSS_DOMAIN_ZERO_PATH_BLACKHOLE=PASS")

        old_vpn_ifindex = vpn.ifindex
        ns(managed, "ip", "link", "del", mv_if)
        raw_run("ip", "link", "add", mv_if, "type", "veth", "peer", "name", v_if)
        raw_run("ip", "link", "set", mv_if, "netns", managed)
        raw_run("ip", "link", "set", v_if, "netns", vpn_ns)
        ns(managed, "ip", "addr", "add", "10.57.2.1/30", "dev", mv_if)
        ns(vpn_ns, "ip", "addr", "add", "10.57.2.2/30", "dev", v_if)
        ns(managed, "ip", "link", "set", mv_if, "up")
        ns(vpn_ns, "ip", "link", "set", v_if, "up")
        ns(vpn_ns, "ip", "route", "replace", "10.57.1.0/30", "via", "10.57.2.1")
        ns(managed, "sysctl", "-q", "-w", f"net.ipv4.conf.{mv_if}.rp_filter=0")

        new_vpn = current_identity(runner, managed, mv_if)
        assert new_vpn.ifindex != old_vpn_ifindex

        drift = converge_structural_policy_step_once(
            gate,
            backend,
            routing_desired(host, vpn),
            nft_desired(host, vpn),
            NG3_LINUX_POLICY_PLATFORM,
        )
        assert (
            drift.status
            is StructuralPolicyMutationStatus.POSTCONDITION_FAILED
        ), (drift.status, drift.diagnostic)
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED
        assert udp_probe(host_ns) is None
        print("STRUCTURAL_CROSS_DOMAIN_SAME_NAME_NEW_IFINDEX_FAIL_CLOSED=PASS")

        print("NG3 cross-domain structural convergence integration: PASS")
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
