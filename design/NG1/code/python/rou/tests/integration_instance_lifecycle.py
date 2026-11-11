from __future__ import annotations

from ipaddress import IPv4Interface
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import SubprocessBackend
from rou.instance_lifecycle import (
    InstanceConfig,
    create_instance,
    destroy_instance,
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
