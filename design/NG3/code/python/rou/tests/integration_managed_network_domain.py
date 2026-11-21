from __future__ import annotations

from ipaddress import IPv4Interface
import json
import os
import subprocess
import sys

from rou.forwarding_gate import ForwardingGateState
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.managed_network_domain import (
    ManagedNetworkDomainError,
    ManagedNetworkDomainSpec,
    cleanup_ordinary_side_portal,
    destroy_managed_l3_boundary,
    destroy_managed_network_environment,
    ensure_managed_l3_boundary,
    ensure_managed_network_environment,
    ensure_ordinary_side_portal,
    observe_ordinary_side_portal,
    verify_managed_l3_boundary,
    verify_managed_network_environment,
)


def raw_run(*argv: str, check: bool = True):
    return subprocess.run(
        argv,
        check=check,
        text=True,
        capture_output=True,
    )



def ensure_lifecycle(spec, runner):
    environment = ensure_managed_network_environment(spec, runner)
    boundary = ensure_managed_l3_boundary(spec, runner)
    portal = ensure_ordinary_side_portal(spec, runner)
    assert environment.confirmed
    assert boundary.confirmed
    assert portal.confirmed
    return environment, boundary, portal


def destroy_lifecycle(spec, runner):
    cleanup_ordinary_side_portal(spec, runner)
    destroy_managed_l3_boundary(spec, runner)
    destroy_managed_network_environment(spec, runner)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit(
            "integration_managed_network_domain must run as root"
        )

    suffix = str(os.getpid())[-6:]
    namespace = f"vg-ng3-domain-{suffix}"
    host_interface = f"vgd{suffix}"
    spec = ManagedNetworkDomainSpec(
        namespace=namespace,
        host_interface=host_interface,
        inner_interface="host0",
        inner_address=IPv4Interface("198.18.255.2/32"),
    )
    runner = SubprocessNftRunner()

    def cleanup() -> None:
        raw_run("ip", "netns", "del", namespace, check=False)
        raw_run("ip", "link", "del", host_interface, check=False)

    cleanup()
    try:
        environment, boundary, portal = ensure_lifecycle(spec, runner)
        assert environment.created
        assert boundary.created
        assert boundary.verification.private_boundary is not None
        assert (
            boundary.verification.private_boundary.ifname
            == spec.inner_interface
        )
        assert (
            LinuxForwardingGateBackend(
                runner,
                namespace,
            ).observe_forwarding_gate()
            is ForwardingGateState.DISABLED
        )

        nft = json.loads(
            runner.run(
                (
                    "ip", "netns", "exec", namespace,
                    "nft", "-j", "list", "tables",
                )
            )
        )
        tables = [
            item["table"]
            for item in nft.get("nftables", ())
            if isinstance(item, dict) and "table" in item
        ]
        assert tables == [], tables
        print("MANAGED_DOMAIN_FRESH_CREATE_NO_POLICY=PASS")
        host_addr = json.loads(
            runner.run(
                ("ip", "-j", "-4", "addr", "show", "dev", host_interface)
            )
        )
        assert not host_addr or not host_addr[0].get("addr_info"), host_addr
        host_service_route = runner.run(
            (
                "ip", "-4", "route", "show",
                spec.inner_address.network.with_prefixlen,
            )
        )
        assert f"dev {host_interface}" in host_service_route
        assert " via " not in host_service_route
        stack_default = runner.run(
            (
                "ip", "-n", namespace,
                "-4", "route", "show", "default",
            )
        )
        assert f"dev {spec.inner_interface}" in stack_default
        assert " via " not in stack_default
        assert raw_run(
            "sysctl", "-n", f"net.ipv4.conf.{host_interface}.proxy_arp"
        ).stdout.strip() == "1"
        assert raw_run(
            "ip", "netns", "exec", namespace,
            "sysctl", "-n", f"net.ipv4.conf.{spec.inner_interface}.proxy_arp"
        ).stdout.strip() == "1"
        print("MANAGED_DOMAIN_ROUTED_PRIMARY=PASS")


        raw_run(
            "ip", "netns", "exec", namespace,
            "sysctl", "-q", "-w", "net.ipv4.ip_forward=1",
        )
        restarted_environment, restarted_boundary, restarted_portal = ensure_lifecycle(spec, runner)
        assert not restarted_environment.created
        assert not restarted_boundary.created
        assert restarted_portal.confirmed
        assert (
            LinuxForwardingGateBackend(
                runner,
                namespace,
            ).observe_forwarding_gate()
            is ForwardingGateState.DISABLED
        )
        print("MANAGED_DOMAIN_RESTART_CONTAINMENT=PASS")

        raw_run(
            "ip", "-n", namespace,
            "-4", "route", "del", "default",
        )
        raw_run(
            "ip", "netns", "exec", namespace,
            "sysctl", "-q", "-w", "net.ipv4.ip_forward=1",
        )
        repaired_environment, repaired_boundary, repaired_portal = ensure_lifecycle(spec, runner)
        assert not repaired_environment.created
        assert not repaired_boundary.created
        assert repaired_portal.confirmed
        assert (
            LinuxForwardingGateBackend(
                runner,
                namespace,
            ).observe_forwarding_gate()
            is ForwardingGateState.DISABLED
        )
        repaired_default = runner.run(
            (
                "ip", "-n", namespace,
                "-4", "route", "show", "default",
            )
        )
        assert f"dev {spec.inner_interface}" in repaired_default
        print("MANAGED_DOMAIN_PORTAL_DRIFT_REPAIRED_FAIL_CLOSED=PASS")

        raw_run("ip", "-n", namespace, "link", "set", "lo", "down")
        raw_run("ip", "link", "set", host_interface, "down")
        raw_run(
            "sysctl", "-q", "-w",
            f"net.ipv4.conf.{host_interface}.proxy_arp=0",
        )
        raw_run(
            "ip", "addr", "add", "192.0.2.1/32", "dev", host_interface,
        )
        drift_environment, drift_boundary, _ = ensure_lifecycle(spec, runner)
        assert drift_environment.confirmed
        assert drift_boundary.confirmed
        host_address_rows = json.loads(
            runner.run(("ip", "-j", "-4", "addr", "show", "dev", host_interface))
        )
        assert not host_address_rows or not host_address_rows[0].get("addr_info")
        print("MANAGED_OWNED_LIFECYCLE_DRIFT_REPAIRED=PASS")

        destroy_lifecycle(spec, runner)
        assert not verify_managed_network_environment(spec, runner).confirmed
        assert not verify_managed_l3_boundary(spec, runner).confirmed
        assert not observe_ordinary_side_portal(spec, runner).confirmed
        assert namespace not in runner.run(("ip", "netns", "list"))
        links = json.loads(runner.run(("ip", "-j", "link", "show")))
        assert not any(
            row.get("ifname") == host_interface
            for row in links
        )
        print("MANAGED_DOMAIN_DESTROY=PASS")

        raw_run("ip", "netns", "add", namespace)
        raw_run("ip", "-n", namespace, "link", "set", "lo", "up")
        raw_run(
            "ip", "netns", "exec", namespace,
            "sysctl", "-q", "-w", "net.ipv4.ip_forward=1",
        )
        recovered_environment, recovered_boundary, recovered_portal = ensure_lifecycle(spec, runner)
        assert not recovered_environment.created
        assert recovered_boundary.created
        assert recovered_portal.confirmed
        assert recovered_boundary.verification.private_boundary is not None
        assert (
            LinuxForwardingGateBackend(
                runner,
                namespace,
            ).observe_forwarding_gate()
            is ForwardingGateState.DISABLED
        )
        print("MANAGED_ENVIRONMENT_WITHOUT_TRANSITION_RECOVERED=PASS")

        print("NG3 managed network domain lifecycle integration: PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
