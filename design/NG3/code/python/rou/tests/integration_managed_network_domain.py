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
        host_address=IPv4Interface("198.18.255.1/30"),
        inner_address=IPv4Interface("198.18.255.2/30"),
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
            row.get("ifname") == host_interface
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
