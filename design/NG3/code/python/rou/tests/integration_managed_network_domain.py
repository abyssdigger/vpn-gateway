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
        created = ensure_managed_network_domain(spec, runner)
        assert created.confirmed
        assert created.created
        assert created.verification.host_boundary is not None
        assert (
            created.verification.host_boundary.ifname
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
        repaired = ensure_managed_network_domain(spec, runner)
        assert repaired.confirmed
        assert not repaired.created
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

        destroy_managed_network_domain(spec, runner)
        assert not verify_managed_network_domain(spec, runner).confirmed
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
        recovered = ensure_managed_network_domain(spec, runner)
        assert recovered.confirmed
        assert recovered.created
        assert recovered.verification.host_boundary is not None
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
