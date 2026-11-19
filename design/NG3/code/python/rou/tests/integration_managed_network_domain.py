from __future__ import annotations

from ipaddress import IPv4Interface
import json
import os
import subprocess
import sys

from rou.forwarding_gate import ForwardingGateState
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.managed_l3_boundary import ManagedL3BoundaryBackend
from rou.managed_network_domain import (
    ManagedBoundaryLinkSpec,
    ManagedNetworkDomainError,
    ManagedNetworkDomainSpec,
    destroy_managed_network_domain,
    ensure_managed_network_domain,
    verify_managed_network_domain,
)


def raw_run(*argv: str, check: bool = True):
    return subprocess.run(
        argv,
        check=check,
        text=True,
        capture_output=True,
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit(
            "integration_managed_network_domain must run as root"
        )

    suffix = str(os.getpid())[-6:]
    namespace = f"vg-ng3-domain-{suffix}"
    host_interface = f"vgd{suffix}"
    extra_host_interface = f"vge{suffix}"
    spec = ManagedNetworkDomainSpec(
        namespace=namespace,
        host_interface=host_interface,
        inner_interface="host0",
        host_address=None,
        inner_address=IPv4Interface("198.18.255.2/32"),
        primary_backend=ManagedL3BoundaryBackend.ROUTED_VETH_PROXY_ARP,
        additional_boundaries=(
            ManagedBoundaryLinkSpec(
                host_interface=extra_host_interface,
                inner_interface="host1",
                host_address=IPv4Interface("198.18.255.5/30"),
                inner_address=IPv4Interface("198.18.255.6/30"),
            ),
        ),
    )
    runner = SubprocessNftRunner()

    def cleanup() -> None:
        raw_run("ip", "netns", "del", namespace, check=False)
        raw_run("ip", "link", "del", host_interface, check=False)
        raw_run("ip", "link", "del", extra_host_interface, check=False)

    cleanup()
    try:
        created = ensure_managed_network_domain(spec, runner)
        assert created.confirmed
        assert created.created
        assert created.verification.host_boundary is not None
        assert (
            created.verification.host_boundary.ifname
            == spec.inner_interface
        )
        assert tuple(
            item.ifname
            for item in created.verification.boundary_interfaces
        ) == ("host0", "host1")
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
        restarted = ensure_managed_network_domain(spec, runner)
        assert restarted.confirmed
        assert not restarted.created
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
        try:
            ensure_managed_network_domain(spec, runner)
        except ManagedNetworkDomainError as exc:
            assert "default route" in str(exc), str(exc)
        else:
            raise AssertionError(
                "divergent existing domain was silently repaired/adopted"
            )
        assert (
            LinuxForwardingGateBackend(
                runner,
                namespace,
            ).observe_forwarding_gate()
            is ForwardingGateState.DISABLED
        )
        print("MANAGED_DOMAIN_DRIFT_REFUSED_FAIL_CLOSED=PASS")

        destroy_managed_network_domain(spec, runner)
        assert not verify_managed_network_domain(spec, runner).confirmed
        assert namespace not in runner.run(("ip", "netns", "list"))
        links = json.loads(runner.run(("ip", "-j", "link", "show")))
        assert not any(
            row.get("ifname") in {host_interface, extra_host_interface}
            for row in links
        )
        print("MANAGED_DOMAIN_DESTROY=PASS")

        raw_run("ip", "netns", "add", namespace)
        raw_run(
            "ip", "netns", "exec", namespace,
            "sysctl", "-q", "-w", "net.ipv4.ip_forward=1",
        )
        try:
            ensure_managed_network_domain(spec, runner)
        except ManagedNetworkDomainError as exc:
            assert "partially present" in str(exc), str(exc)
        else:
            raise AssertionError("partial namespace-only state was adopted")
        assert (
            LinuxForwardingGateBackend(
                runner,
                namespace,
            ).observe_forwarding_gate()
            is ForwardingGateState.DISABLED
        )
        print("MANAGED_DOMAIN_PARTIAL_STATE_REFUSED=PASS")

        print("NG3 managed network domain lifecycle integration: PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
