from __future__ import annotations

from ipaddress import IPv4Interface
import os
import subprocess
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import SubprocessBackend
from rou.instance_lifecycle import (
    InstanceConfig,
    create_instance,
    destroy_instance,
    ensure_instance,
    verify_instance,
)


CONFIG = InstanceConfig(
    namespace="vpn-gate-ng1-ci",
    host_if="rouci0",
    inner_if="host0",
    host_address=IPv4Interface("192.0.2.1/30"),
    inner_address=IPv4Interface("192.0.2.2/30"),
)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration test must run as root")

    host = SubprocessBackend()
    try:
        destroy_instance(CONFIG, host)
        create_instance(CONFIG, host)
        verified = verify_instance(CONFIG, host)
        if not verified.ok:
            print("VERIFY FAIL:", "; ".join(verified.errors))
            return 1
        print("NG1_INSTANCE_CREATE_VERIFY=PASS")

        # Simulate safe-repairable bootstrap drift while forwarding remains a containment
        # concern: wrong rp_filter plus fail-open local filter policies.
        subprocess.run(
            (
                "ip", "netns", "exec", CONFIG.namespace,
                "sysctl", "-q", "-w", "net.ipv4.conf.all.rp_filter=1",
            ),
            text=True,
            check=True,
        )
        bad_filter = (
            "*filter\n"
            ":INPUT ACCEPT [0:0]\n"
            ":FORWARD ACCEPT [0:0]\n"
            ":OUTPUT ACCEPT [0:0]\n"
            "COMMIT\n"
        )
        subprocess.run(
            (
                "ip", "netns", "exec", CONFIG.namespace,
                "iptables-legacy-restore",
            ),
            input=bad_filter,
            text=True,
            check=True,
        )

        ensure_instance(CONFIG, host)
        repaired = verify_instance(CONFIG, host, forwarding=False)
        if not repaired.ok:
            print("ENSURE REPAIR FAIL:", "; ".join(repaired.errors))
            return 1
        print("NG1_INSTANCE_ENSURE_REPAIR=PASS")
    finally:
        destroy_instance(CONFIG, host)

    verified_absent_ns = host.run(
        ("ip", "netns", "list"),
    ).stdout
    if CONFIG.namespace in verified_absent_ns:
        print("namespace remains after cleanup")
        return 1

    link = host.run(
        ("ip", "link", "show", "dev", CONFIG.host_if),
        check=False,
    )
    if link.returncode == 0:
        print("host link remains after cleanup")
        return 1

    print("NG1_INSTANCE_LIFECYCLE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
