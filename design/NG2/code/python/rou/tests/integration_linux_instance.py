from __future__ import annotations

from ipaddress import IPv4Interface
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.linux_driver import SubprocessLinuxRunner
from rou.linux_instance import (
    LinuxInstanceError,
    LinuxInstanceSpec,
    destroy_linux_instance,
    ensure_linux_instance,
    verify_linux_instance,
)
from rou.runtime_bootstrap import (
    bootstrap_linux_network_rules_adapter_for_instance,
)


NS = "vpng2-inst-ci"
HOST_IF = "vngi0"


def host(*argv: str, check: bool = True):
    return subprocess.run(
        argv,
        text=True,
        capture_output=True,
        check=check,
    )


def cleanup():
    host("ip", "netns", "del", NS, check=False)
    host("ip", "link", "del", HOST_IF, check=False)


def namespace_names() -> set[str]:
    return {
        line.split(maxsplit=1)[0]
        for line in host("ip", "netns", "list").stdout.splitlines()
        if line.strip()
    }


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration test must run as root")

    cleanup()
    runner = SubprocessLinuxRunner()
    spec = LinuxInstanceSpec(
        namespace=NS,
        host_interface=HOST_IF,
        host_address=IPv4Interface("192.0.2.1/30"),
        inner_address=IPv4Interface("192.0.2.2/30"),
    )

    try:
        bootstrapped = bootstrap_linux_network_rules_adapter_for_instance(
            spec,
            host_runner=runner,
        )
        if not bootstrapped.success or bootstrapped.adapter is None:
            raise RuntimeError(
                "full instance bootstrap failed: "
                f"{bootstrapped.diagnostic}"
            )

        verified = verify_linux_instance(spec, runner)
        if not verified.ok:
            raise RuntimeError(
                "fresh instance verification failed: "
                + "; ".join(verified.errors)
            )

        nft_tables = host(
            "ip", "netns", "exec", NS,
            "nft", "-j", "list", "tables",
        ).stdout
        nft_root = json.loads(nft_tables)
        actual_tables = [
            item["table"]
            for item in nft_root.get("nftables", ())
            if isinstance(item, dict) and "table" in item
        ]
        if actual_tables:
            raise RuntimeError(
                "instance lifecycle unexpectedly created nft policy: "
                f"{actual_tables!r}"
            )
        print(
            "PASS I1: absent instance -> fail-closed infrastructure -> "
            "Adapter publication without nft policy"
        )

        for assignment in (
            "net.ipv4.ip_forward=1",
            "net/ipv6/conf/all/forwarding=1",
            "net/ipv6/conf/default/forwarding=1",
        ):
            host(
                "ip", "netns", "exec", NS,
                "sysctl", "-q", "-w", assignment,
            )

        ensure_linux_instance(spec, runner)

        for key in (
            "net.ipv4.ip_forward",
            "net.ipv6.conf.all.forwarding",
            "net.ipv6.conf.default.forwarding",
        ):
            value = host(
                "ip", "netns", "exec", NS,
                "sysctl", "-n", key,
            ).stdout.strip()
            if value != "0":
                raise RuntimeError(
                    f"restart ensure left {key}={value!r}"
                )
        print("PASS I2: existing instance is protectively closed before verification")

        host(
            "ip", "netns", "exec", NS,
            "ip", "route", "del", "default",
        )
        try:
            ensure_linux_instance(spec, runner)
        except LinuxInstanceError as exc:
            if "default route" not in str(exc):
                raise
        else:
            raise RuntimeError(
                "existing structural drift was silently repaired/adopted"
            )

        forward = host(
            "ip", "netns", "exec", NS,
            "sysctl", "-n", "net.ipv4.ip_forward",
        ).stdout.strip()
        if forward != "0":
            raise RuntimeError(
                "failed structural verification did not remain fail-closed"
            )
        print("PASS I3: existing structural drift fails closed without implicit repair")

        host(
            "ip", "netns", "exec", NS,
            "ip", "route", "replace", "default",
            "via", str(spec.host_address.ip),
            "dev", "host0",
        )
        ensure_linux_instance(spec, runner)

        destroy_linux_instance(spec, runner)
        if NS in namespace_names():
            raise RuntimeError("destroy left namespace")
        if host("ip", "link", "show", "dev", HOST_IF, check=False).returncode == 0:
            raise RuntimeError("destroy left host veth")
        print("PASS I4: destroy removes owned infrastructure")

        host("ip", "link", "add", HOST_IF, "type", "dummy")
        try:
            ensure_linux_instance(spec, runner)
        except LinuxInstanceError as exc:
            if "partially present" not in str(exc):
                raise
        else:
            raise RuntimeError("partial instance state was accepted")
        print("PASS I5: partial infrastructure is rejected")

        print("NG2_LINUX_INSTANCE_INTEGRATION=PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
