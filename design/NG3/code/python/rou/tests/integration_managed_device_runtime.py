#!/usr/bin/env python3
"""Kernel integration evidence for A.012 alpha runtime composition."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv4Interface, IPv4Network
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from rou.alpha_runtime import (
    AlphaPreparedPolicy, AlphaReconcileResult, AlphaReconcileStatus,
    prepare_alpha_normal_reconciliation, finish_alpha_normal_replacement,
    reconcile_alpha_normal_once, publish_alpha_normal_status,
    _managed_device_problem,
    _release_alpha_managed_device_dependencies,
    converge_alpha_managed_device_presence,
    reconcile_alpha_payload_once,
    reconcile_alpha_after_managed_release,
    reconcile_alpha_availability_wireguard_once,
    refresh_alpha_managed_demand_status,
    release_alpha_undemanded_devices,
)
from rou.binding import PathBinding
from rou.interface_identity import InterfaceIdentity
from rou.controller_startup import ControllerStartupStatus, start_controller_once
from rou.controller_stop import ControllerStopStatus, stop_controller_once
from rou.icmp_probe_driver import (
    IcmpProbeExecutionPolicy,
    LinuxIcmpProbeDriver,
    SubprocessProbeCommandRunner,
)
from rou.instance_lock import InstanceLockSpec
from rou.linux_nft_scaffold import SubprocessNftRunner
from rou.linux_policy_platform import (
    NG3_LINUX_POLICY_PLATFORM,
    NG3_PROBE_LOCAL_PLATFORM,
    NG3_STACK_RETURN_AFFINITY_PLATFORM,
)
from rou.managed_device_manager import ManagedDeviceManager, ManagedDeviceIntentBasis
from rou.managed_network_domain import ManagedNetworkDomainSpec
from rou.managed_wireguard_adapter import (
    LinuxManagedWireGuardAdapter,
    ManagedWireGuardState,
)
from rou.wireguard_peer_ownership import (
    WireGuardPeerAllowedIPs,
    WireGuardPeerOwnershipDesired,
    WireGuardPeerOwnershipEnforcer,
    WireGuardPeerOwnershipResult,
)
from rou.wireguard_peer_runtime import WireGuardPeerRuntimeCoordinator
from rou.release1_config import CurrentConfig
from rou.probe_runtime import ProbeTechnicalObservation, ProbeTechnicalOutcome
from rou.runtime_status import RuntimeReadiness, RuntimeStatusAgent, build_configured_intent_status


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



def verify_cold_start_reserve_reclaim(config: str, runtime_dir: Path, key_path: Path) -> None:
    """F4 direct cold start through the normal A.012 composition and kernel adapters."""
    runtime_dir.mkdir(mode=0o700)
    prepared = AlphaPreparedPolicy.from_text(config, local_address=IPv4Address("198.19.255.2"))
    domain = ManagedNetworkDomainSpec(
        namespace=NS, host_interface=HOST_IF, inner_interface=INNER_IF,
        inner_address=IPv4Interface("198.19.255.2/32"),
    )
    runner = SubprocessNftRunner()
    adapter = LinuxManagedWireGuardAdapter(runner, NS)
    manager = ManagedDeviceManager(adapter)
    ownership = WireGuardPeerOwnershipEnforcer(runner, NS, adapter)
    coordinator = WireGuardPeerRuntimeCoordinator()
    probe = LinuxIcmpProbeDriver(
        runner=SubprocessProbeCommandRunner(), namespace=NS,
        process_uid=NG3_PROBE_LOCAL_PLATFORM.process_uid,
        execution_policy=IcmpProbeExecutionPolicy(1),
    )
    plan = None
    realizations = ()

    def prepare_private_network(candidate, current_domain):
        nonlocal plan, realizations
        assert candidate is prepared and current_domain == domain
        convergence, plan, realizations = prepare_alpha_normal_reconciliation(
            prepared, domain, runner, manager,
        )
        assert plan is not None and plan.previous_accepted is None
        assert convergence.projection.desired_device_ids == {"wg-main", "wg-reserve"}
        assert convergence.projection.profiles[0].regular_deficit == 1
        assert {r.device_id for r in convergence.attempt_problems} == {"wg-main"}
        assert not plan.projection.retirement_candidates
        assert plan.mandatory_device_ids == {"wg-reserve"}
        assert _managed_device_problem(realizations) is not None

    startup = None
    # Fail the ordinary key before the first controller startup, not after READY.
    key_path.chmod(0o644)
    try:
        startup = start_controller_once(
            InstanceLockSpec(runtime_directory=runtime_dir, expected_owner_uid=os.getuid()),
            domain, runner, NG3_LINUX_POLICY_PLATFORM, lambda: prepared,
            prepare_private_network=prepare_private_network,
            stack_return_affinity_platform=NG3_STACK_RETURN_AFFINITY_PLATFORM,
        )
        assert startup.status is ControllerStartupStatus.READY, startup.diagnostic
        assert startup.session is not None and plan is not None
        assert adapter.observe("wg-main").state is ManagedWireGuardState.ABSENT
        assert adapter.observe("wg-reserve").state is ManagedWireGuardState.PRESENT
        assert not any(i.ifname == "wg0" for i in startup.session.interfaces)
        assert any(i.ifname == "wg1" for i in startup.session.interfaces)
        assert {b.path_id.device_id for b in prepared.last_bindings} == {"wg-reserve"}
        with patch("rou.alpha_runtime.ALPHA_NAMESPACE", NS):
            completion = finish_alpha_normal_replacement(
                prepared, domain, runner, manager, plan, realizations,
                AlphaReconcileResult(AlphaReconcileStatus.EXACT, startup.session.desired),
                coordinator, probe, ownership,
            )
        assert completion.batch is None and completion.problem is None
        final = completion.final
        assert final.payload.ready and final.availability.confirmed
        assert final.wireguard_error is None, final.wireguard_error
        status = RuntimeStatusAgent(build_configured_intent_status(prepared.current_config))
        publish_alpha_normal_status(prepared, domain, runner, manager, status, completion)
        assert prepared.accepted_effective_state is not None
        problem = _managed_device_problem(final.realizations)
        assert problem is not None and "wg-main" in problem
        snapshot = status.snapshot()
        assert snapshot.readiness is RuntimeReadiness.DEGRADED
        assert snapshot.confirmed_effective_state is not None
        assert snapshot.managed_profile_demands is not None
        assert snapshot.managed_profile_demands[0].regular_deficit == 1
        assert snapshot.managed_reclaim_projection is not None
        assert not snapshot.managed_reclaim_projection.retirement_candidates
        assert {row.device_id for row in snapshot.managed_reclaim_projection.survivors} == {"wg-reserve"}
        print("A012_NORMAL_COLD_START_RESERVE_RECLAIM=PASS")

        _release_alpha_managed_device_dependencies(startup.session.desired, domain, runner)
        shutdown = manager.reconcile(
            CurrentConfig(prepared.config, {}), desired_device_ids=frozenset(),
            dependency_free_device_ids=frozenset({"wg-main", "wg-reserve"}),
        )
        assert _managed_device_problem(shutdown, require_absent=True) is None
        stopped = stop_controller_once(startup.session, domain, runner)
        assert stopped.status is ControllerStopStatus.STOPPED, stopped.cleanup_error
        assert not Path(f"/run/netns/{NS}").exists()
    finally:
        key_path.chmod(0o600)
        if (startup is not None and startup.session is not None
                and startup.session.lock.acquired):
            startup.session.lock.release()
        subprocess.run(("ip", "netns", "del", NS), check=False)
        subprocess.run(("ip", "link", "del", HOST_IF), check=False)



def verify_normal_ordinary_reclaim(root: Path, policy: str) -> None:
    """Real kernel policy/base/AllowedIPs, injected positive technical probes.

    Start with three demanded managed ordinary paths and no external path.
    A shared external path then appears and covers all three fixed floors.
    Positive peer probe outcomes are injected only to exercise exact D.002
    ownership/accepted current-use, not to claim end-to-end remote reachability.
    """
    root.mkdir(mode=0o700)
    runtime_dir = root / "run"
    runtime_dir.mkdir(mode=0o700)
    peer_public = run("wg", "pubkey", input_text=run("wg", "genkey").strip() + "\n").strip()
    config = f"""
managed_reclaim = "{policy}"
[device.ext]
enabled = true
expected_interfaces = ["ext0"]
use_outbound_nat = true
"""
    ids = ("a", "b", "c")
    for index, did in enumerate(ids, 1):
        key = root / f"{did}.key"
        key.write_text(run("wg", "genkey").strip() + "\n", encoding="ascii")
        key.chmod(0o600)
        config += f"""
[device.{did}]
enabled = true
use_outbound_nat = true
[device.{did}.managed_vpn]
kind = "wireguard"
interface = "wg{index}"
address = "10.200.0.{index}/32"
private_key_file = "{key}"
[[device.{did}.managed_vpn.peers]]
id = "edge"
public_key = "{peer_public}"
endpoint = "192.0.2.{index}:51820"
probe_target = "10.201.0.{index}"
[profile.p-{did}]
enabled = true
direction = "outbound"
destinations = ["10.77.{index}.0/24"]
device_order = ["ext", "{did}"]
warm_paths = 1
"""
    prepared = AlphaPreparedPolicy.from_text(config, local_address=IPv4Address("198.19.255.2"))
    domain = ManagedNetworkDomainSpec(
        namespace=NS, host_interface=HOST_IF, inner_interface=INNER_IF,
        inner_address=IPv4Interface("198.19.255.2/32"),
    )
    runner = SubprocessNftRunner()
    adapter = LinuxManagedWireGuardAdapter(runner, NS)
    manager = ManagedDeviceManager(adapter)
    ownership = WireGuardPeerOwnershipEnforcer(runner, NS, adapter)
    coordinator = WireGuardPeerRuntimeCoordinator()
    probe = LinuxIcmpProbeDriver(
        runner=SubprocessProbeCommandRunner(), namespace=NS,
        process_uid=NG3_PROBE_LOCAL_PLATFORM.process_uid,
        execution_policy=IcmpProbeExecutionPolicy(1),
    )
    status = RuntimeStatusAgent(build_configured_intent_status(prepared.current_config))
    plan = None
    realizations = ()

    def prepare_private_network(candidate, current_domain):
        nonlocal plan, realizations
        assert candidate is prepared and current_domain == domain
        convergence, plan, realizations = prepare_alpha_normal_reconciliation(
            prepared, domain, runner, manager,
        )
        assert plan is not None and not plan.projection.retirement_candidates
        assert convergence.projection.desired_device_ids == set(ids)

    def reply(_driver, context):
        assert context.target in {IPv4Address(f"10.201.0.{i}") for i in range(1, 4)}
        return ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)

    def audit():
        result, problems = reconcile_alpha_normal_once(
            prepared, domain, runner, manager, coordinator, probe, ownership,
        )
        assert not problems, problems
        assert result.final.payload.ready, result.final.payload.diagnostic
        assert result.final.availability is not None and result.final.availability.confirmed
        assert result.final.wireguard_error is None, result.final.wireguard_error
        publish_alpha_normal_status(prepared, domain, runner, manager, status, result)
        assert prepared.accepted_effective_state is not None
        return result

    def allowed(did):
        return run("ip", "netns", "exec", NS, "wg", "show",
                   prepared.current_config.managed_vpns[did].interface, "allowed-ips")

    startup = None
    try:
        startup = start_controller_once(
            InstanceLockSpec(runtime_directory=runtime_dir, expected_owner_uid=os.getuid()),
            domain, runner, NG3_LINUX_POLICY_PLATFORM, lambda: prepared,
            prepare_private_network=prepare_private_network,
            stack_return_affinity_platform=NG3_STACK_RETURN_AFFINITY_PLATFORM,
        )
        assert startup.status is ControllerStartupStatus.READY, startup.diagnostic
        assert startup.session is not None and plan is not None
        with patch("rou.alpha_runtime.ALPHA_NAMESPACE", NS), \
             patch.object(LinuxIcmpProbeDriver, "execute", reply):
            first = finish_alpha_normal_replacement(
                prepared, domain, runner, manager, plan, realizations,
                AlphaReconcileResult(AlphaReconcileStatus.EXACT, startup.session.desired),
                coordinator, probe, ownership,
            )
            assert first.problem is None and first.batch is None
            assert first.final.wireguard is not None and first.final.wireguard.ready
            publish_alpha_normal_status(prepared, domain, runner, manager, status, first)
            assert prepared.accepted_effective_state is not None
            assert {p.ordered_paths[0].device_id for p in prepared.accepted_effective_state.profiles} == set(ids)
            assert {r.device_id for r in first.final.wireguard.realizations} == set(ids)
            for i, did in enumerate(ids, 1):
                assert f"10.77.{i}.0/24" in allowed(did)

            run("ip", "-n", NS, "link", "add", "ext0", "type", "dummy")
            run("ip", "-n", NS, "link", "set", "ext0", "up")
            original_retire = LinuxManagedWireGuardAdapter.retire_exact
            original_cleanup = WireGuardPeerOwnershipEnforcer.converge
            retired = []
            cleanups = []

            def checked_retire(instance, did, identity, generation, desired):
                i = ids.index(did) + 1
                observed = allowed(did)
                assert f"10.77.{i}.0/24" not in observed, observed
                assert f"10.201.0.{i}/32" in observed, observed
                retired.append(did)
                return original_retire(instance, did, identity, generation, desired)

            def cleanup_with_drift(instance, desired):
                result = original_cleanup(instance, desired)
                assert result.confirmed, result.diagnostic
                cleanups.append(desired.device_id)
                if desired.device_id == "b":
                    # Actual D.003 cleanup succeeds, then an out-of-band
                    # payload prefix reappears before the fresh postcondition.
                    restore = WireGuardPeerOwnershipDesired(
                        "b", desired.interface,
                        (WireGuardPeerAllowedIPs(peer_public, tuple(sorted((
                            IPv4Network("10.201.0.2/32"), IPv4Network("10.77.2.0/24"),
                        )))),),
                    )
                    assert original_cleanup(instance, restore).confirmed
                return result

            # Structural demand is now covered by external presence. Neither
            # retention nor F2 should actuate a new managed presence.
            with patch.object(LinuxManagedWireGuardAdapter, "converge_present",
                              side_effect=AssertionError("unexpected managed start/restart")), \
                 patch.object(LinuxManagedWireGuardAdapter, "converge_absent",
                              side_effect=AssertionError("generic absence is not GC authority")), \
                 patch.object(LinuxManagedWireGuardAdapter, "retire_exact", checked_retire), \
                 patch("rou.alpha_runtime.reconcile_alpha_after_managed_release",
                       wraps=reconcile_alpha_after_managed_release) as recover:
                if policy == "careful":
                    result = audit()
                    assert result.problem is None and result.batch is None
                    assert not retired
                    recover.assert_not_called()
                    assert {r.device_id for r in result.final.wireguard.realizations} == set(ids)
                    assert all(r.intent_basis is ManagedDeviceIntentBasis.RECLAIM_RETENTION
                               and r.payload_eligible for r in result.final.realizations)
                    assert {p.ordered_paths[0].device_id for p in prepared.accepted_effective_state.profiles} == set(ids)
                    projection = status.snapshot().managed_reclaim_projection
                    assert projection is not None and not projection.retirement_candidates
                    assert {r.device_id for r in projection.survivors} == set(ids)
                    assert status.snapshot().readiness is RuntimeReadiness.READY
                    print("A012_NORMAL_CAREFUL_RETAINED_D002_KERNEL=PASS (injected peer replies)")
                else:
                    with patch.object(WireGuardPeerOwnershipEnforcer, "converge", cleanup_with_drift):
                        partial = audit()
                    assert partial.batch is not None and partial.batch.retired == {"a"}
                    assert partial.problem is not None and "post-cleanup" in partial.problem
                    assert retired == ["a"] and cleanups == ["a", "b"], (retired, cleanups)
                    recover.assert_called_once()
                    assert adapter.observe("a").state is ManagedWireGuardState.ABSENT
                    assert all(adapter.observe(d).state is ManagedWireGuardState.PRESENT for d in ("b", "c"))
                    assert "10.77.2.0/24" in allowed("b")
                    assert "10.77.3.0/24" in allowed("c")
                    assert {b.path_id.device_id for b in prepared.last_bindings} == {"ext"}
                    snapshot = status.snapshot()
                    assert snapshot.readiness is RuntimeReadiness.DEGRADED
                    assert snapshot.confirmed_effective_state is not None
                    assert any("post-cleanup" in p for p in snapshot.blocking_problems)
                    assert snapshot.managed_reclaim_projection is not None
                    assert {d.device_id for d in snapshot.managed_reclaim_projection.retirement_candidates} == {"b", "c"}
                    print("A012_NORMAL_STRICT_PARTIAL_BATCH_F2_KERNEL=PASS (injected peer replies)")
                    recover.reset_mock()
                    resumed = audit()
                    assert resumed.problem is None and resumed.batch is not None
                    assert resumed.batch.retired == {"b", "c"}
                    assert retired == list(ids)
                    recover.assert_called_once()
                    assert all(adapter.observe(d).state is ManagedWireGuardState.ABSENT for d in ids)
                    assert status.snapshot().readiness is RuntimeReadiness.READY
                    projection = status.snapshot().managed_reclaim_projection
                    assert projection is not None and not projection.retirement_candidates
                    print("A012_NORMAL_STRICT_REMAINING_BATCH_F2_KERNEL=PASS (injected peer replies)")

        final_payload = reconcile_alpha_payload_once(prepared, domain, runner)
        assert final_payload.ready and final_payload.desired is not None
        _release_alpha_managed_device_dependencies(final_payload.desired, domain, runner)
        shutdown = manager.reconcile(
            CurrentConfig(prepared.config, {}), desired_device_ids=frozenset(),
            dependency_free_device_ids=frozenset(ids),
        )
        assert _managed_device_problem(shutdown, require_absent=True) is None
        stopped = stop_controller_once(startup.session, domain, runner)
        assert stopped.status is ControllerStopStatus.STOPPED, stopped.cleanup_error
        assert not Path(f"/run/netns/{NS}").exists()
    finally:
        if startup is not None and startup.session is not None and startup.session.lock.acquired:
            startup.session.lock.release()
        subprocess.run(("ip", "netns", "del", NS), check=False)
        subprocess.run(("ip", "link", "del", HOST_IF), check=False)


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
        reserve_key = root / "reserve.key"
        reserve_key.write_text(run("wg", "genkey").strip() + "\n", encoding="ascii")
        reserve_key.chmod(0o600)
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

[device.wg-reserve]
enabled = true
use_outbound_nat = true

[device.wg-reserve.managed_vpn]
kind = "wireguard"
interface = "wg1"
address = "10.200.0.2/32"
private_key_file = "{reserve_key}"

[[device.wg-reserve.managed_vpn.peers]]
id = "edge-b"
public_key = "{peer_public}"
endpoint = "198.51.100.11:51820"
probe_target = "10.201.0.2"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.77.0.0/24"]
device_order = ["wg-main", "wg-reserve:reserve"]
warm_paths = 1
"""
        verify_cold_start_reserve_reclaim(config, root / "cold-run", key_path)
        verify_normal_ordinary_reclaim(root / "careful", "careful")
        verify_normal_ordinary_reclaim(root / "strict", "strict")
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
        adapter = LinuxManagedWireGuardAdapter(runner, NS)
        manager = ManagedDeviceManager(adapter)
        ownership = WireGuardPeerOwnershipEnforcer(runner, NS, adapter)
        coordinator = WireGuardPeerRuntimeCoordinator()
        probe = LinuxIcmpProbeDriver(
            runner=SubprocessProbeCommandRunner(),
            namespace=NS,
            process_uid=NG3_PROBE_LOCAL_PLATFORM.process_uid,
            execution_policy=IcmpProbeExecutionPolicy(1),
        )
        current_realizations = ()

        def prepare_private_network(candidate, current_domain):
            nonlocal current_realizations
            if candidate is not prepared or current_domain != domain:
                raise AssertionError("startup preparation context changed")
            convergence = converge_alpha_managed_device_presence(
                prepared, domain, runner, manager
            )
            assert convergence.projection.desired_device_ids == {"wg-main"}
            current_realizations = convergence.realizations
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

            def reconcile_dependencies(convergence):
                payload = reconcile_alpha_payload_once(prepared, domain, runner)
                assert payload.ready, payload.diagnostic
                with patch("rou.alpha_runtime.ALPHA_NAMESPACE", NS):
                    availability, _, problem = reconcile_alpha_availability_wireguard_once(
                        prepared, convergence.realizations, coordinator, runner,
                        probe, ownership,
                    )
                assert availability.confirmed, availability.diagnostic
                assert problem is None, problem
                return payload

            assert adapter.observe("wg-reserve").state is ManagedWireGuardState.ABSENT

            # Remove the primary and independently prevent its D.001 recovery.
            run("ip", "-n", NS, "link", "del", "wg0")
            key_path.chmod(0o644)
            fallback = converge_alpha_managed_device_presence(prepared, domain, runner, manager)
            assert fallback.projection.desired_device_ids == {"wg-main", "wg-reserve"}
            assert fallback.projection.profiles[0].regular_deficit == 1
            assert any(item.device_id == "wg-main" and item.problem for item in fallback.realizations)
            assert adapter.observe("wg-reserve").state is ManagedWireGuardState.PRESENT
            reconcile_dependencies(fallback)
            assert {b.path_id.device_id for b in prepared.last_bindings} == {"wg-reserve"}
            print("A012_RUNTIME_RESERVE_AFTER_FAILED_ORDINARY=PASS")

            # Independently seed a valid old dynamic D.003 payload ownership
            # state, even though the isolated test has no responsive remote peer.
            reserve = adapter.observe("wg-reserve")
            old_owner = WireGuardPeerOwnershipDesired(
                "wg-reserve", reserve.interface,
                (WireGuardPeerAllowedIPs(
                    peer_public, tuple(sorted((
                        IPv4Network("10.201.0.2/32"),
                        IPv4Network("10.77.0.0/24"),
                    )))
                ),),
            )
            assert ownership.converge(old_owner).confirmed

            # Recover ordinary presence with reserve still physically present.
            key_path.chmod(0o600)
            recovery = converge_alpha_managed_device_presence(prepared, domain, runner, manager)
            assert recovery.projection.desired_device_ids == {"wg-main"}
            assert recovery.projection.profiles[0].regular_deficit == 0
            assert adapter.observe("wg-main").state is ManagedWireGuardState.PRESENT
            assert adapter.observe("wg-reserve").state is ManagedWireGuardState.PRESENT
            assert any(item.device_id == "wg-reserve" and item.waiting_for_dependencies
                       for item in recovery.realizations)
            release = release_alpha_undemanded_devices(
                prepared, domain, runner, manager, recovery, ownership,
                dependencies_confirmed=False,
            )
            assert not release.retirement_attempted
            assert adapter.observe("wg-reserve").state is ManagedWireGuardState.PRESENT

            # Reconcile all path-dependent objects before releasing the old device.
            reconcile_dependencies(recovery)
            assert {b.path_id.device_id for b in prepared.last_bindings} == {"wg-main"}
            # A different observed generation is not evidence that the
            # already-applied replacement policy remains valid.
            original_binding = prepared.last_bindings[0]
            changed = PathBinding(
                original_binding.path_id,
                InterfaceIdentity(
                    original_binding.endpoint.ifname,
                    original_binding.endpoint.ifindex + 10000,
                ),
            )
            with patch("rou.alpha_runtime._observe_presence_bindings", return_value=(changed,)):
                release = release_alpha_undemanded_devices(
                    prepared, domain, runner, manager, recovery, ownership,
                    dependencies_confirmed=True,
                )
            assert not release.retirement_attempted
            assert adapter.observe("wg-reserve").state is ManagedWireGuardState.PRESENT
            print("A012_RUNTIME_STALE_REPLACEMENT_BLOCKS_RELEASE=PASS")
            with patch.object(
                WireGuardPeerOwnershipEnforcer, "converge",
                return_value=WireGuardPeerOwnershipResult(False, False, None, "test failure"),
            ):
                release = release_alpha_undemanded_devices(
                    prepared, domain, runner, manager, recovery, ownership,
                    dependencies_confirmed=True,
                )
            assert not release.retirement_attempted
            assert release.dependencies_touched
            assert _managed_device_problem(release.realizations) is not None
            assert adapter.observe("wg-reserve").state is ManagedWireGuardState.PRESENT
            print("A012_RUNTIME_PEER_RELEASE_FAILURE_BLOCKS_STOP=PASS")

            # Real D.003 mutation followed by replacement disappearance.
            # Repeat with an unconfirmed result AFTER mutation, not merely
            # a fake failure that leaves kernel state untouched.
            original_converge = WireGuardPeerOwnershipEnforcer.converge
            for confirmed_cleanup in (True, False):
                assert ownership.converge(old_owner).confirmed
                cleanup_calls = []

                def lose_replacement(instance, desired):
                    result = original_converge(instance, desired)
                    assert result.confirmed, result.diagnostic
                    cleanup_calls.append(desired)
                    run("ip", "-n", NS, "link", "del", "wg0")
                    key_path.chmod(0o644)
                    if confirmed_cleanup:
                        return result
                    return WireGuardPeerOwnershipResult(
                        False, False, None, "test failure after real mutation"
                    )

                with patch.object(WireGuardPeerOwnershipEnforcer, "converge", lose_replacement):
                    release = release_alpha_undemanded_devices(
                        prepared, domain, runner, manager, recovery, ownership,
                        dependencies_confirmed=True,
                    )
                assert len(cleanup_calls) == 1
                assert release.dependencies_touched
                assert not release.retirement_attempted
                assert release.requires_reconvergence
                assert adapter.observe("wg-reserve").state is ManagedWireGuardState.PRESENT
                assert "10.77.0.0/24" not in run(
                    "ip", "netns", "exec", NS, "wg", "show", "wg1", "allowed-ips"
                )
                with patch("rou.alpha_runtime.ALPHA_NAMESPACE", NS):
                    recovered = reconcile_alpha_after_managed_release(
                        prepared, domain, runner, manager, coordinator, probe, ownership,
                    )
                assert recovered.payload.ready, recovered.payload.diagnostic
                assert recovered.availability is not None
                assert recovered.availability.confirmed, recovered.availability.diagnostic
                assert recovered.wireguard_error is None, recovered.wireguard_error
                assert {b.path_id.device_id for b in prepared.last_bindings} == {"wg-reserve"}
                assert any(item.device_id == "wg-reserve" and
                           item.confirmed_state is ManagedWireGuardState.PRESENT
                           for item in recovered.realizations)
                assert adapter.observe("wg-reserve").state is ManagedWireGuardState.PRESENT
                # Return to the normal recovery setup for the next scenario.
                key_path.chmod(0o600)
                recovery = converge_alpha_managed_device_presence(prepared, domain, runner, manager)
                reconcile_dependencies(recovery)
                assert {b.path_id.device_id for b in prepared.last_bindings} == {"wg-main"}
            print("A012_RUNTIME_POST_CLEANUP_ABORT_RECONVERGES=PASS")

            # Observe exact kernel AllowedIPs immediately before the real D.001
            # delete. Do not substitute an assertion on the desired projection.
            original_stop = LinuxManagedWireGuardAdapter.converge_absent

            def checked_stop(instance, device_id):
                if device_id == "wg-reserve":
                    allowed = run("ip", "netns", "exec", NS, "wg", "show", "wg1", "allowed-ips")
                    assert "10.77.0.0/24" not in allowed, allowed
                    assert "10.201.0.2/32" in allowed, allowed
                return original_stop(instance, device_id)

            with patch.object(LinuxManagedWireGuardAdapter, "converge_absent", checked_stop):
                release = release_alpha_undemanded_devices(
                    prepared, domain, runner, manager, recovery, ownership,
                    dependencies_confirmed=True,
                )
            assert release.retirement_attempted and release.dependencies_touched
            released_realizations = release.realizations
            print("A012_RUNTIME_DYNAMIC_PEER_DEPENDENCY_REMOVED_BEFORE_STOP=PASS")
            assert _managed_device_problem(released_realizations) is None
            assert adapter.observe("wg-reserve").state is ManagedWireGuardState.ABSENT
            final_payload = reconcile_alpha_payload_once(prepared, domain, runner)
            assert final_payload.ready, final_payload.diagnostic
            assert {b.path_id.device_id for b in prepared.last_bindings} == {"wg-main"}
            status.confirm_managed_devices(released_realizations)
            refresh_alpha_managed_demand_status(prepared, status)
            demand = status.snapshot().managed_profile_demands[0]
            assert demand.regular_present == 1
            assert demand.regular_deficit == 0
            assert demand.reserve_present == 0
            print("A012_RUNTIME_POST_RELEASE_DEMAND_STATUS=PASS")
            print("A012_RUNTIME_MAKE_BEFORE_BREAK=PASS")

            _release_alpha_managed_device_dependencies(
                final_payload.desired,
                domain,
                runner,
            )
            shutdown = manager.reconcile(
                CurrentConfig(prepared.config, {}),
                desired_device_ids=frozenset(),
                dependency_free_device_ids=frozenset({"wg-main", "wg-reserve"}),
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
