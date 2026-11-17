from __future__ import annotations

from ipaddress import IPv4Interface, IPv4Network
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from rou.controller_startup import (
    ControllerStartupStatus,
    start_controller_once,
)
from rou.domain import Direction
from rou.instance_lock import InstanceLockSpec
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.managed_network_domain import (
    ManagedNetworkDomainSpec,
    destroy_managed_network_domain,
)
from rou.network_policy_layout import allocate_network_policy_layout
from rou.payload_network_policy_desired import (
    build_payload_network_policy_desired_state,
)
from rou.payload_profile import PayloadProfileRequest


class ZeroPathPreparedPolicy:
    def __init__(self):
        self.profile = PayloadProfileRequest(
            profile_id="future",
            direction=Direction.OUTBOUND,
            destinations=(IPv4Network("203.0.113.66/32"),),
            ordered_paths=(),
        )
        self.layout = allocate_network_policy_layout(
            (self.profile,),
            (),
            NG3_LINUX_POLICY_PLATFORM,
        )

    def build_current(self, host_boundary, interfaces):
        assert host_boundary in interfaces
        return build_payload_network_policy_desired_state(
            (self.profile,),
            self.layout,
            (),
            host_boundary,
            (),
            (),
            (),
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
            "integration_controller_startup must run as root"
        )

    suffix = str(os.getpid())[-6:]
    namespace = f"vg-start-{suffix}"
    host_interface = f"vgs{suffix}"
    runtime_root = Path(tempfile.mkdtemp(prefix="vg-ng3-start-"))
    runtime_dir = runtime_root / "runtime"

    lock_spec = InstanceLockSpec(
        runtime_directory=runtime_dir,
        expected_owner_uid=os.getuid(),
    )
    domain_spec = ManagedNetworkDomainSpec(
        namespace=namespace,
        host_interface=host_interface,
        inner_interface="host0",
        host_address=IPv4Interface("198.19.255.1/30"),
        inner_address=IPv4Interface("198.19.255.2/30"),
    )
    runner = SubprocessNftRunner()

    def cleanup() -> None:
        try:
            destroy_managed_network_domain(domain_spec, runner)
        except Exception:
            raw_run("ip", "netns", "del", namespace, check=False)
            raw_run("ip", "link", "del", host_interface, check=False)
        shutil.rmtree(runtime_root, ignore_errors=True)

    raw_run("ip", "netns", "del", namespace, check=False)
    raw_run("ip", "link", "del", host_interface, check=False)

    try:
        def invalid_loader():
            raise ValueError("synthetic invalid candidate")

        invalid = start_controller_once(
            lock_spec,
            domain_spec,
            runner,
            NG3_LINUX_POLICY_PLATFORM,
            invalid_loader,
        )
        assert invalid.status is ControllerStartupStatus.POLICY_LOAD_FAILED, (
            invalid.status,
            invalid.diagnostic,
        )
        assert namespace not in runner.run(("ip", "netns", "list"))
        assert raw_run(
            "ip", "link", "show", "dev", host_interface,
            check=False,
        ).returncode != 0
        print("CONTROLLER_STARTUP_INVALID_CONFIG_NO_DOMAIN_CREATE=PASS")

        ready = start_controller_once(
            lock_spec,
            domain_spec,
            runner,
            NG3_LINUX_POLICY_PLATFORM,
            ZeroPathPreparedPolicy,
        )
        assert ready.status is ControllerStartupStatus.READY, (
            ready.status,
            ready.diagnostic,
        )
        assert ready.ready
        assert ready.session is not None
        assert ready.session.lock.acquired
        assert ready.session.domain.created
        assert ready.session.activation.ready
        assert ready.session.desired.routing.host_boundary == (
            ready.session.domain.verification.host_boundary
        )

        tables = runner.run(
            (
                "ip", "netns", "exec", namespace,
                "nft", "list", "table", "ip", "vpn_gate",
            )
        )
        assert "payload_forward" in tables
        routes = runner.run(
            (
                "ip", "-n", namespace,
                "-4", "route", "show",
                "table", str(0x80000000),
            )
        )
        assert "blackhole default" in routes
        print("CONTROLLER_STARTUP_ZERO_PATH_READY=PASS")

        busy = start_controller_once(
            lock_spec,
            domain_spec,
            runner,
            NG3_LINUX_POLICY_PLATFORM,
            ZeroPathPreparedPolicy,
        )
        assert busy.status is ControllerStartupStatus.LOCK_BUSY, (
            busy.status,
            busy.diagnostic,
        )
        assert ready.session.lock.acquired
        print("CONTROLLER_STARTUP_SECOND_INSTANCE_REFUSED=PASS")

        ready.session.lock.release()
        destroy_managed_network_domain(domain_spec, runner)
        assert namespace not in runner.run(("ip", "netns", "list"))
        print("CONTROLLER_STARTUP_CLEANUP_AFTER_LOCK_RELEASE=PASS")

        print("NG3 bounded controller startup integration: PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
