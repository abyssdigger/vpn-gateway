#!/usr/bin/env python3
"""Kernel integration evidence for A.012 alpha runtime composition."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv4Interface
import os
from pathlib import Path
import subprocess
import tempfile

from rou.alpha_runtime import (
    AlphaPreparedPolicy,
    _managed_device_problem,
    _release_alpha_managed_device_dependencies,
)
from rou.controller_startup import ControllerStartupStatus, start_controller_once
from rou.controller_stop import ControllerStopStatus, stop_controller_once
from rou.instance_lock import InstanceLockSpec
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_policy_platform import (
    NG3_LINUX_POLICY_PLATFORM,
    NG3_STACK_RETURN_AFFINITY_PLATFORM,
)
from rou.managed_device_manager import ManagedDeviceManager
from rou.managed_network_domain import ManagedNetworkDomainSpec
from rou.managed_wireguard_adapter import (
    LinuxManagedWireGuardAdapter,
    ManagedWireGuardState,
)
from rou.release1_config import CurrentConfig
from rou.runtime_status import RuntimeStatusAgent, build_configured_intent_status


NS = "ng3-a012-runtime"
HOST_IF = "ng3-a012-h0"
INNER_IF = "ng3-a012-i0"


def run(*argv: str, input_text: str | None = None, check: bool = True) -> str:
    completed = subprocess.run(
        argv,
        input=input_text,
        check=check,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def main() -> None:
    subprocess.run(("ip", "netns", "del", NS), check=False)
    subprocess.run(("ip", "link", "del", HOST_IF), check=False)

    private = run("wg", "genkey").strip()
    peer_private = run("wg", "genkey").strip()
    peer_public = run("wg", "pubkey", input_text=peer_private + "\n").strip()

    with tempfile.TemporaryDirectory(prefix="ng3-a012-runtime-") as root_text:
        root = Path(root_text)
        key_path = root / "private.key"
        key_path.write_text(private + "\n", encoding="ascii")
        key_path.chmod(0o600)
        runtime_dir = root / "run"
        runtime_dir.mkdir(mode=0o700)
        runtime_dir.chmod(0o700)

        config = f"""
[device.wg-main]
enabled = true
use_outbound_nat = true

[device.wg-main.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "{key_path}"

[[device.wg-main.managed_vpn.peers]]
id = "edge-a"
public_key = "{peer_public}"
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.77.0.0/24"]
device_order = ["wg-main"]
"""
        prepared = AlphaPreparedPolicy.from_text(
            config,
            local_address=IPv4Address("198.19.255.2"),
        )
        domain = ManagedNetworkDomainSpec(
            namespace=NS,
            host_interface=HOST_IF,
            inner_interface=INNER_IF,
            inner_address=IPv4Interface("198.19.255.2/32"),
        )
        runner = SubprocessNftRunner()
        manager = ManagedDeviceManager(
            LinuxManagedWireGuardAdapter(runner, NS)
        )
        current_realizations = ()

        def prepare_private_network(candidate, current_domain):
            nonlocal current_realizations
            if candidate is not prepared or current_domain != domain:
                raise AssertionError("startup preparation context changed")
            current_realizations = manager.reconcile(
                prepared.current_config, desired_device_ids=frozenset({"wg-main"})
            )
            problem = _managed_device_problem(current_realizations)
            if problem is not None:
                raise AssertionError(problem)

        startup = None
        try:
            startup = start_controller_once(
                InstanceLockSpec(
                    runtime_directory=runtime_dir,
                    expected_owner_uid=os.getuid(),
                ),
                domain,
                runner,
                NG3_LINUX_POLICY_PLATFORM,
                lambda: prepared,
                prepare_private_network=prepare_private_network,
                stack_return_affinity_platform=NG3_STACK_RETURN_AFFINITY_PLATFORM,
            )
            if startup.status is not ControllerStartupStatus.READY:
                raise AssertionError(
                    f"runtime startup failed: {startup.status.value}: {startup.diagnostic}"
                )
            assert startup.session is not None

            if not current_realizations:
                raise AssertionError("A.012 did not publish managed Device realization")
            realized = current_realizations[0]
            if realized.confirmed_state is not ManagedWireGuardState.PRESENT:
                raise AssertionError("managed WireGuard presence is not confirmed")
            if realized.confirmed_generation != realized.desired_generation:
                raise AssertionError("managed WireGuard generation is not exact")

            if not any(item.ifname == "wg0" for item in startup.session.interfaces):
                raise AssertionError(
                    "fresh VPN-path observation did not see A.012-created wg0"
                )
            if "wg0" not in run("ip", "-n", NS, "-o", "link", "show"):
                raise AssertionError("managed WireGuard interface is absent after READY")
            print("A012_RUNTIME_START_BEFORE_PATH_OBSERVATION=PASS")

            status = RuntimeStatusAgent(
                build_configured_intent_status(prepared.config)
            )
            status.confirm_managed_devices(current_realizations)
            status_item = status.snapshot().managed_device_realizations[0]
            if status_item.confirmed_generation != realized.desired_generation:
                raise AssertionError("A.008 lost managed Device generation")
            print("A012_RUNTIME_STATUS_PROJECTION=PASS")

            _release_alpha_managed_device_dependencies(
                startup.session.desired,
                domain,
                runner,
            )
            shutdown = manager.reconcile(
                CurrentConfig(prepared.config, {}),
                desired_device_ids=frozenset(),
                dependency_free_device_ids=frozenset({"wg-main"}),
            )
            problem = _managed_device_problem(shutdown, require_absent=True)
            if problem is not None:
                raise AssertionError(problem)
            if shutdown[0].confirmed_state is not ManagedWireGuardState.ABSENT:
                raise AssertionError("managed WireGuard absence is not confirmed")
            print("A012_RUNTIME_DEPENDENCY_RELEASE_AND_STOP=PASS")

            stopped = stop_controller_once(
                startup.session,
                domain,
                runner,
            )
            if stopped.status is not ControllerStopStatus.STOPPED:
                raise AssertionError(
                    f"controller cleanup failed: {stopped.status.value}"
                )
            if Path(f"/run/netns/{NS}").exists():
                raise AssertionError("managed namespace remains after controller stop")
            print("A012_RUNTIME_PRIVATE_NETWORK_TEARDOWN=PASS")
            print("A012_RUNTIME_RESULT=PASS")
        finally:
            if (
                startup is not None
                and startup.session is not None
                and startup.session.lock.acquired
            ):
                startup.session.lock.release()
            subprocess.run(("ip", "netns", "del", NS), check=False)
            subprocess.run(("ip", "link", "del", HOST_IF), check=False)


if __name__ == "__main__":
    main()
