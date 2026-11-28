"""First executable NG3 alpha runtime assembly.

Architecture: structured Annex A A.001 ProductLifecycleControl,
A.004 PayloadTrafficManager, A.011 ProtectiveModeManager, A.012 ManagedDeviceManager, and Annex E
E.001 HostPublicationAdapter runtime composition.
The component specs own normative requirement traceability.

This module assembles the first executable NG3 runtime from accepted Release-1
contracts. It consumes the canonical human-facing configuration grammar and
materializes the lower capabilities already implemented by this reference slice:
- structural Device/Profile policy;
- direct-device VPN path realization;
- Device outbound NAT;
- ordinary Device firewall rules;
- Device-owned VPN client transport/control local allow;
- Release-1 ICMP availability probing, bounded confirmation and effective-order convergence;
- one local PayloadTrafficManager-style periodic reconciliation loop.

Remaining canonical capabilities whose full lower path is not yet implemented here are
rejected at configuration load rather than silently ignored.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
from enum import Enum
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
import os
from pathlib import Path
import signal
import socket
import sys
import threading
from typing import Iterable, Mapping

from .accepted_effective_state import (
    AcceptedEffectiveState, PreReclaimEvidence, observe_pre_reclaim,
)
from .composite_nft_policy import CompositeNftDesiredState
from .availability_description import resolve_availability_probe_intents
from .availability_manager import (
    LOG_TAG as AVAIL_LOG_TAG,
    AvailabilityManager,
    AvailabilityManagerPolicy,
)
from .binding import (
    LOG_TAG as BIND_LOG_TAG,
    DeviceBindingState,
    LogicalPathId,
    PathBinding,
    project_device_bindings,
)
from .controller_startup import (
    LOG_TAG as LIFE_LOG_TAG,
    ControllerStartupStatus,
    start_controller_once,
)
from .controller_stop import (
    ControllerStopStatus,
    stop_controller_once,
)
from .device_policy import (
    DeviceFirewallAction,
    DeviceFirewallDirection,
    DeviceFirewallPolicyIntent,
    DeviceFirewallRuleIntent,
    DeviceNatPolicyIntent,
    NatIntent,
)
from .direct_device_route import realize_direct_device_path_routes
from .forwarding_gate import (
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .instance_lock import InstanceLockSpec
from .interface_identity import InterfaceIdentity
from .host_publication_policy import (
    HostPublicationDesiredState,
    HostPublicationMappingIntent,
    HostPublicationSelectorKind,
    build_host_publication_desired,
)
from .icmp_probe_driver import (
    IcmpProbeExecutionPolicy,
    LinuxIcmpProbeDriver,
    SubprocessProbeCommandRunner,
)
from .linux_availability_cycle import (
    LinuxAvailabilityCycleResult,
    LinuxProbePlanePreparationResult,
    complete_linux_availability_cycle_once,
    prepare_linux_availability_probe_plane_once,
)
from .linux_forwarding_gate import LinuxForwardingGateDriver
from .linux_protective_payload_gate import LinuxProtectivePayloadGateDriver
from .linux_vpn_path_adapter import LinuxVpnPathAdapter
from .managed_device_demand import project_final
from .managed_device_manager import (
    ManagedDeviceConvergence,
    converge_managed_device_presence,
    ManagedDeviceDesiredState,
    ManagedDeviceManager,
    ManagedDeviceRealization,
)
from .managed_wireguard_adapter import (
    LinuxManagedWireGuardAdapter,
    ManagedWireGuardState,
)
from .wireguard_peer_ownership import (
    WireGuardPeerAllowedIPs,
    WireGuardPeerOwnershipDesired,
    WireGuardPeerOwnershipEnforcer,
)
from .wireguard_peer_runtime import (
    WireGuardPeerRuntimeCoordinator,
    WireGuardPeerRuntimeResult,
)
from .host_publication_adapter import HostPublicationAdapter
from .linux_host_publication import (
    HostPublicationConvergenceResult,
    HostPublicationConvergenceStatus,
    LinuxHostPublicationDriver,
)
from .linux_nft_scaffold import (
    LinuxNftScaffoldDriver,
    SubprocessNftRunner,
)
from .linux_policy_platform import (
    NG3_LINUX_POLICY_PLATFORM,
    NG3_PROBE_LOCAL_PLATFORM,
    NG3_STACK_RETURN_AFFINITY_PLATFORM,
)
from .linux_stack_return_affinity import LinuxStackReturnAffinityBackend
from .linux_structural_policy import LinuxStructuralPolicyBackend
from .local_integration_policy import (
    IntegrationLocalTransportIntent,
    IntegrationTransportProtocol,
)
from .local_publication_policy import (
    PublicationLocalEndpointIntent,
    PublicationProtocol,
)
from .managed_network_domain import (
    ManagedNetworkDomainSpec,
    ensure_managed_l3_boundary,
    ensure_managed_network_environment,
    ensure_ordinary_side_portal,
    preflight_managed_network_environment,
)
from .network_policy_layout import ProbePolicyOwner
from .network_policy_activation import (
    LOG_TAG as POLICY_LOG_TAG,
    NetworkPolicyActivationResult,
    activate_network_policy,
)
from .payload_network_policy_desired import (
    PayloadNetworkPolicyDesiredState,
    build_payload_network_policy_desired_state,
)
from .payload_forward_desired import PayloadForwardDesiredState
from .device_firewall_desired import DeviceFirewallDesiredState
from .payload_routing_desired import PayloadRoutingDesiredState, build_payload_routing_desired_state
from .probe_precondition import verify_probe_execution_precondition
from .payload_profile import (
    LOG_TAG as PROF_LOG_TAG,
    PayloadProfileRequest,
    build_payload_profile_requests,
)
from .payload_nat_desired import PayloadNatDesiredState, ProfileSnatPolicyIntent
from .probe_plane_desired import (
    ProbePlaneDesiredAssembly,
    build_probe_plane_desired_assembly,
    project_current_wireguard_probe_intents,
)
from .probe_runtime import (
    AvailabilityProbeRuntime,
    ProbeOwnershipDependency,
)
from .protective_mode_control import (
    DEFAULT_CONTROL_PATH,
    ProtectiveModeControlService,
)
from .protective_mode_manager import ProtectiveModeManager
from .route_priority_inventory import RoutePriorityPathRoute
from .release1_config import CurrentConfig, Release1Config, parse_current_config
from .operational_log import OperationalLogAdapter, OperationalLogLevel
from .release1_host_route_helper import (
    LOG_TAG as HOST_LOG_TAG,
    LinuxPeacefulHostRoutingContribution,
    build_linux_peaceful_host_routing_contribution,
    helper_routing_uses_external_ingress,
    validate_release1_helper_routing_scope,
)
from .structural_policy_mutation import compare_structural_policy
from .structural_policy_transaction import converge_structural_policy
from .stack_return_affinity import StackReturnAffinityDesired
from .stack_return_affinity_convergence import (
    StackReturnAffinityOwnerStatus,
    converge_stack_return_affinity_once,
)
from .runtime_status import (
    RuntimeReadiness,
    RuntimeStatusAgent,
    RuntimeStatusFilePublisher,
    build_configured_intent_status,
    read_release_version,
)


ALPHA_NAMESPACE = "vpn-gate-alpha"
ALPHA_HOST_INTERFACE = "vnga-host0"
ALPHA_INNER_INTERFACE = "vnga-inner0"
ALPHA_INNER_ADDRESS = IPv4Interface("198.19.255.2/32")
ALPHA_RUNTIME_DIRECTORY = Path("/run/vpn-gate-alpha")
ALPHA_STATUS_PATH = ALPHA_RUNTIME_DIRECTORY / "status.json"
ALPHA_STATUS_TEXT_PATH = ALPHA_RUNTIME_DIRECTORY / "status.txt"
ALPHA_CONTROL_PATH = DEFAULT_CONTROL_PATH
ALPHA_VERSION_PATH = Path("/usr/lib/vpn-gate-alpha/VERSION")
ALPHA_AUDIT_INTERVAL_SECONDS = 1.0
ALPHA_AVAILABILITY_DEGRADATION_THRESHOLD = 2
ALPHA_AVAILABILITY_RECOVERY_THRESHOLD = 2
ALPHA_PROBE_REPLY_TIMEOUT_SECONDS = 1


class AlphaRuntimeError(RuntimeError):
    pass


@dataclass(slots=True)
class AlphaPreparedPolicy:
    """Canonical accepted config + current Device binding state."""

    local_address: IPv4Address
    binding_state: DeviceBindingState
    current_config: CurrentConfig
    config: Release1Config
    confirmed_managed_interfaces: frozenset[InterfaceIdentity] | None = None
    last_bindings: tuple[PathBinding, ...] = ()
    last_baseline_profiles: tuple[PayloadProfileRequest, ...] = ()
    last_profiles: tuple[PayloadProfileRequest, ...] = ()
    last_path_routes: tuple[RoutePriorityPathRoute, ...] = ()
    last_probe_assembly: ProbePlaneDesiredAssembly | None = None
    accepted_effective_state: AcceptedEffectiveState | None = None
    # Trigger-local diagnostic result, never consumed by the legacy release path.
    pre_reclaim_evidence: PreReclaimEvidence | None = None

    availability_runtime: AvailabilityProbeRuntime = field(
        default_factory=AvailabilityProbeRuntime
    )
    availability_manager: AvailabilityManager = field(
        default_factory=lambda: AvailabilityManager(
            AvailabilityManagerPolicy(
                ALPHA_AVAILABILITY_DEGRADATION_THRESHOLD,
                ALPHA_AVAILABILITY_RECOVERY_THRESHOLD,
            )
        )
    )
    last_availability_dependencies: dict[
        ProbePolicyOwner,
        ProbeOwnershipDependency,
    ] = field(default_factory=dict)

    def begin_effective_transition(self) -> AcceptedEffectiveState | None:
        previous = self.accepted_effective_state
        self.accepted_effective_state = None
        self.pre_reclaim_evidence = None
        return previous

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        local_address: IPv4Address,
    ) -> "AlphaPreparedPolicy":
        current = parse_current_config(text)
        config = current.base

        prepared = cls(
            local_address=local_address,
            binding_state=DeviceBindingState.empty(),
            current_config=current,
            config=config,
        )
        try:
            prepared.build_host_publication_desired()
        except Exception as exc:
            raise AlphaRuntimeError(
                "host publication projection failed before runtime mutation: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        return prepared

    @property
    def requires_private_peer_observation(self) -> bool:
        return any(
            rule.private_peer_ipv4 is not None
            for device_id in self.config.structural.active_device_ids
            for rule in (self.config.devices[device_id].firewall or ())
        )

    def eligible_interfaces(
        self, interfaces: tuple[InterfaceIdentity, ...]
    ) -> tuple[InterfaceIdentity, ...]:
        if self.confirmed_managed_interfaces is None:
            return interfaces
        managed_names = {
            device.interface for device in self.current_config.managed_vpns.values()
        }
        return tuple(
            endpoint for endpoint in interfaces
            if endpoint.ifname not in managed_names
            or endpoint in self.confirmed_managed_interfaces
        )

    def build_current(
        self,
        host_boundary: InterfaceIdentity,
        interfaces: tuple[InterfaceIdentity, ...],
        *,
        path_private_peers: Mapping[
            InterfaceIdentity,
            IPv4Address | None,
        ] | None = None,
    ) -> PayloadNetworkPolicyDesiredState:
        projection = project_device_bindings(
            self.config.structural.device_binding_intents,
            self.binding_state,
            self.eligible_interfaces(interfaces),
        )
        self.binding_state = projection.next_state

        profiles = build_payload_profile_requests(
            self.config.structural.profiles.values(),
            projection.bindings,
        )
        path_routes = realize_direct_device_path_routes(projection.bindings)
        availability_intents = resolve_availability_probe_intents(
            self.config,
            tuple(route.path_id for route in path_routes),
        )
        peer_intents, group_intents = project_current_wireguard_probe_intents(
            self.current_config,
            profiles,
            path_routes,
        )
        probe_assembly = build_probe_plane_desired_assembly(
            profiles,
            availability_intents,
            peer_intents,
            group_intents,
            path_routes,
            NG3_LINUX_POLICY_PLATFORM,
            NG3_PROBE_LOCAL_PLATFORM,
        )
        layout = probe_assembly.layout
        pre_d002_dependencies = {
            intent.owner: (
                self.last_availability_dependencies.get(
                    intent.owner,
                    ProbeOwnershipDependency.unconfirmed(),
                )
                if (
                    intent.owner.profile_id,
                    intent.owner.path_id.device_id,
                ) in self.current_config.wireguard_groups
                else ProbeOwnershipDependency.not_applicable()
            )
            for intent in probe_assembly.availability_intents
        }
        self.availability_runtime.configure(
            probe_assembly.availability_intents,
            path_routes,
            pre_d002_dependencies,
        )
        availability_projection = self.availability_manager.synchronize(
            self.availability_runtime.current_contexts,
            profiles,
            self.config,
        )
        effective_profiles = availability_projection.effective_profiles

        nat_policies = tuple(
            DeviceNatPolicyIntent(
                device_id,
                (
                    NatIntent.MASQUERADE
                    if self.config.devices[device_id].use_outbound_nat is True
                    else NatIntent.NONE
                ),
            )
            for device_id in sorted(self.config.structural.active_device_ids)
        )
        firewall_policies = tuple(
            DeviceFirewallPolicyIntent(
                device_id,
                (
                    None
                    if self.config.devices[device_id].firewall is None
                    else tuple(
                        DeviceFirewallRuleIntent(
                            direction=DeviceFirewallDirection(rule.direction),
                            action=DeviceFirewallAction(rule.action),
                            protocol=rule.protocol,
                            source_ports=rule.source_ports,
                            destination_ports=rule.destination_ports,
                            source_ipv4_cidr=rule.source_ipv4_cidr,
                            destination_ipv4_cidr=rule.destination_ipv4_cidr,
                            path_ifname=rule.path_ifname,
                            private_peer_ipv4=rule.private_peer_ipv4,
                            comment=rule.comment,
                        )
                        for rule in self.config.devices[device_id].firewall
                    )
                ),
            )
            for device_id in sorted(self.config.structural.active_device_ids)
        )

        integration_intents = tuple(
            IntegrationLocalTransportIntent(
                integration_id=f"{device_id}-vpn-client-{index}",
                protocol=IntegrationTransportProtocol(item.protocol),
                host_boundary=host_boundary,
                local_address=self.local_address,
                remote_address=item.remote_address,
                remote_port=item.remote_port,
                local_port=item.local_port,
            )
            for device_id in sorted(self.config.structural.active_device_ids)
            for index, item in enumerate(
                self.config.devices[device_id].allow_vpn_client
            )
        )
        publication_intents = tuple(
            PublicationLocalEndpointIntent(
                device_id=device_id,
                protocol=PublicationProtocol(item.protocol),
                local_address=self.local_address,
                internal_port=internal_port,
                host_boundary=host_boundary,
            )
            for device_id in sorted(self.config.structural.active_device_ids)
            for item in self.config.devices[device_id].publish_vpn_server
            for internal_port in item.internal_ports.expanded()
        )

        profile_snat_policies = tuple(
            ProfileSnatPolicyIntent(profile_id, semantic.effective_snat_address)
            for profile_id, semantic in self.config.profiles.items()
            if self.config.structural.profiles[profile_id].enabled
            and semantic.effective_snat_address is not None
        )

        desired = build_payload_network_policy_desired_state(
            effective_profiles,
            layout,
            path_routes,
            host_boundary,
            nat_policies,
            firewall_policies,
            publication_intents,
            integration_intents,
            probe_local_rules=probe_assembly.probe.local_rules,
            stack_return_affinity_platform=NG3_STACK_RETURN_AFFINITY_PLATFORM,
            profile_snat_policies=profile_snat_policies,
            path_private_peers=path_private_peers,
        )
        self.last_bindings = projection.bindings
        self.last_baseline_profiles = profiles
        self.last_profiles = effective_profiles
        self.last_path_routes = path_routes
        self.last_probe_assembly = probe_assembly
        return desired

    def build_host_publication_desired(self) -> HostPublicationDesiredState:
        intents = []
        for device_id in sorted(self.config.structural.active_device_ids):
            for item in self.config.devices[device_id].publish_vpn_server:
                selector = HostPublicationSelectorKind(item.host_selector.kind)
                for host_port, internal_port in zip(
                    item.host_ports.expanded(),
                    item.internal_ports.expanded(),
                    strict=True,
                ):
                    intents.append(
                        HostPublicationMappingIntent(
                            device_id=device_id,
                            protocol=PublicationProtocol(item.protocol),
                            selector_kind=selector,
                            selector_value=item.host_selector.value,
                            host_port=host_port,
                            internal_address=self.local_address,
                            internal_port=internal_port,
                        )
                    )
        return build_host_publication_desired(intents)


class AlphaReconcileStatus(str, Enum):
    EXACT = "exact"
    RECONCILED = "reconciled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AlphaReconcileResult:
    status: AlphaReconcileStatus
    desired: PayloadNetworkPolicyDesiredState | None
    host_publication_desired: HostPublicationDesiredState | None = None
    activation: NetworkPolicyActivationResult | None = None
    host_publication: HostPublicationConvergenceResult | None = None
    diagnostic: str | None = None

    @property
    def ready(self) -> bool:
        return self.status in {
            AlphaReconcileStatus.EXACT,
            AlphaReconcileStatus.RECONCILED,
        }


def _managed_device_problem(
    realizations: tuple[ManagedDeviceRealization, ...],
    *,
    require_absent: bool = False,
) -> str | None:
    for item in realizations:
        if item.problem is not None:
            return f"managed Device {item.device_id!r}: {item.problem}"
        if item.waiting_for_dependencies:
            return f"managed Device {item.device_id!r} is still waiting for dependencies"
        if require_absent:
            if item.confirmed_state is not ManagedWireGuardState.ABSENT:
                return f"managed Device {item.device_id!r} absence is not confirmed"
            continue
        if (
            item.desired_state is ManagedDeviceDesiredState.PRESENT
            and item.confirmed_state is not ManagedWireGuardState.PRESENT
        ):
            return f"managed Device {item.device_id!r} presence is not confirmed"
        if (
            item.desired_state is ManagedDeviceDesiredState.ABSENT
            and item.confirmed_state is not ManagedWireGuardState.ABSENT
        ):
            return f"managed Device {item.device_id!r} absence is not confirmed"
    return None


def _observe_presence_bindings(
    prepared: AlphaPreparedPolicy,
    domain_spec: ManagedNetworkDomainSpec,
    runner: SubprocessNftRunner,
    *,
    eligible_only: bool = False,
) -> tuple[PathBinding, ...]:
    interfaces = LinuxVpnPathAdapter(
        runner, domain_spec.namespace
    ).observe_interfaces().interfaces
    if eligible_only:
        interfaces = prepared.eligible_interfaces(interfaces)
    # A tentative read-only projection does not commit C.004 slot changes.
    return project_device_bindings(
        prepared.config.structural.device_binding_intents,
        prepared.binding_state,
        interfaces,
    ).bindings


def observe_alpha_pre_reclaim(
    prepared: AlphaPreparedPolicy,
    domain_spec: ManagedNetworkDomainSpec,
    runner: SubprocessNftRunner,
    manager: ManagedDeviceManager,
    previous_accepted: AcceptedEffectiveState | None,
) -> PreReclaimEvidence:
    """Read the full inventory without committing bindings or changing eligibility."""
    return observe_pre_reclaim(
        prepared.current_config, previous_accepted, manager,
        lambda: _observe_presence_bindings(prepared, domain_spec, runner),
    )


def publish_alpha_accepted_effective(
    prepared: AlphaPreparedPolicy,
    *,
    payload_confirmed: bool,
    availability: LinuxAvailabilityCycleResult | None,
    wireguard: WireGuardPeerRuntimeResult | None,
    wireguard_error: str | None,
) -> None:
    """Publish only the final fully confirmed generation of a normal trigger."""
    prepared.accepted_effective_state = None
    if (not payload_confirmed or availability is None or not availability.confirmed
            or availability.observation is None or availability.priority is None
            or not availability.priority.confirmed or wireguard_error is not None
            or (prepared.current_config.wireguard_groups and wireguard is None)
            or (wireguard is not None and not wireguard.confirmed)):
        return
    prepared.accepted_effective_state = AcceptedEffectiveState(
        availability.observation.projection.effective_profiles,
        prepared.last_bindings,
        () if wireguard is None else wireguard.realizations,
    )


def converge_alpha_managed_device_presence(
    prepared: AlphaPreparedPolicy,
    domain_spec: ManagedNetworkDomainSpec,
    runner: SubprocessNftRunner,
    manager: ManagedDeviceManager,
) -> ManagedDeviceConvergence:
    convergence = converge_managed_device_presence(
        prepared.current_config,
        manager,
        lambda: _observe_presence_bindings(prepared, domain_spec, runner),
    )
    prepared.confirmed_managed_interfaces = convergence.confirmed_interfaces
    return convergence


@dataclass(frozen=True, slots=True)
class ManagedDeviceReleaseOutcome:
    """Dependency mutation and D.001 retirement are independent facts."""

    realizations: tuple[ManagedDeviceRealization, ...]
    dependencies_touched: bool = False
    retirement_attempted: bool = False

    @property
    def requires_reconvergence(self) -> bool:
        return self.dependencies_touched or self.retirement_attempted


@dataclass(frozen=True, slots=True)
class ReclaimReplacementEvidence:
    """Confirmed replacement inputs captured before any retirement touch."""

    config: CurrentConfig
    bindings: tuple[PathBinding, ...]
    path_routes: tuple[RoutePriorityPathRoute, ...]
    profiles: tuple[PayloadProfileRequest, ...]
    assembly: ProbePlaneDesiredAssembly
    desired: PayloadNetworkPolicyDesiredState


def capture_reclaim_replacement_evidence(
    prepared: AlphaPreparedPolicy,
    result: AlphaReconcileResult,
    availability: LinuxAvailabilityCycleResult | None,
    wireguard: WireGuardPeerRuntimeResult | None,
    wireguard_error: str | None,
) -> ReclaimReplacementEvidence | None:
    """Capture only fully confirmed C.001/A.004/D.002 replacement state."""
    if (not result.ready or result.desired is None
            or availability is None or not availability.confirmed
            or availability.observation is None
            or availability.priority is None or not availability.priority.confirmed
            or wireguard_error is not None
            or (prepared.current_config.wireguard_groups and wireguard is None)
            or (wireguard is not None and not wireguard.confirmed)
            or prepared.last_probe_assembly is None):
        return None
    return ReclaimReplacementEvidence(
        prepared.current_config, prepared.last_bindings, prepared.last_path_routes,
        availability.observation.projection.effective_profiles,
        prepared.last_probe_assembly, result.desired,
    )


def reclaim_replacement_policy_exact(
    prepared: AlphaPreparedPolicy,
    domain_spec: ManagedNetworkDomainSpec,
    runner: SubprocessNftRunner,
    replacement: ReclaimReplacementEvidence,
    retirement_ids: frozenset[str],
) -> bool:
    """Fresh read-only C.001/probe/priority/affinity verification.

    Route priorities may have legitimately changed after the initial payload
    convergence; compare against the final confirmed effective order, not
    the initial desired route metrics. The original plan is not recomputed.
    """
    if prepared.current_config is not replacement.config:
        return False
    if (any(b.path_id.device_id in retirement_ids for b in replacement.bindings)
            or any(r.path_id.device_id in retirement_ids for r in replacement.path_routes)
            or any(p.device_id in retirement_ids
                   for profile in replacement.profiles for p in profile.ordered_paths)):
        return False
    try:
        routing = build_payload_routing_desired_state(
            replacement.profiles, replacement.assembly.layout,
            replacement.path_routes, replacement.desired.routing.host_boundary,
        )
        snapshot = LinuxStructuralPolicyBackend(
            runner=runner, namespace=domain_spec.namespace,
            platform=NG3_LINUX_POLICY_PLATFORM,
        ).observe_structural_snapshot()
        if not compare_structural_policy(
            snapshot, routing, replacement.desired.nft, NG3_LINUX_POLICY_PLATFORM,
        ).desired_confirmed:
            return False
        if not verify_probe_execution_precondition(
            snapshot, replacement.assembly.probe, NG3_LINUX_POLICY_PLATFORM,
        ).confirmed:
            return False
        if replacement.desired.stack_return_affinity is not None:
            if LinuxStackReturnAffinityBackend(
                runner, domain_spec.namespace, NG3_STACK_RETURN_AFFINITY_PLATFORM,
            ).observe(replacement.desired.stack_return_affinity).status is not StackReturnAffinityOwnerStatus.EXACT:
                return False
        return LinuxForwardingGateDriver(
            runner, domain_spec.namespace,
        ).observe_forwarding_gate() is ForwardingGateState.ENABLED
    except Exception:
        return False


def release_alpha_undemanded_devices(
    prepared: AlphaPreparedPolicy,
    domain_spec: ManagedNetworkDomainSpec,
    runner: SubprocessNftRunner,
    manager: ManagedDeviceManager,
    convergence: ManagedDeviceConvergence,
    ownership: WireGuardPeerOwnershipEnforcer,
    *,
    dependencies_confirmed: bool,
) -> ManagedDeviceReleaseOutcome:
    """Stop only after exact replacement policy and peer-dependency removal."""
    pending = tuple(
        item for item in convergence.realizations if item.waiting_for_dependencies
    )
    if not dependencies_confirmed or not pending:
        return ManagedDeviceReleaseOutcome(convergence.realizations)
    desired = convergence.projection.desired_device_ids

    def replacement_still_current() -> bool:
        fresh = _observe_presence_bindings(
            prepared, domain_spec, runner, eligible_only=True
        )
        # A desired Device set alone cannot distinguish a vanished or replaced
        # concrete path from the generation whose dependencies were confirmed.
        return (
            frozenset(fresh) == frozenset(prepared.last_bindings)
            and project_final(prepared.current_config, fresh).desired_device_ids == desired
        )

    # In particular, a replacement disappearing since policy convergence
    # must not cause release of a still-needed reserve.
    try:
        if not replacement_still_current():
            return ManagedDeviceReleaseOutcome(convergence.realizations)
    except Exception:
        return ManagedDeviceReleaseOutcome(convergence.realizations)

    safe_ids: set[str] = set()
    problems: dict[str, str] = {}
    dependencies_touched = False
    for item in pending:
        try:
            config = prepared.current_config.managed_vpns[item.device_id]
            if item.confirmed_interface is None:
                raise AlphaRuntimeError("retiring interface identity is unconfirmed")
            # C.001 no longer references this path. Remove D.003 payload
            # ownership too, retaining only D.001's permanent probe identities.
            peer_desired = WireGuardPeerOwnershipDesired(
                item.device_id,
                item.confirmed_interface,
                tuple(sorted(
                    WireGuardPeerAllowedIPs(
                        peer.public_key,
                        (IPv4Network(f"{peer.probe_target}/32"),),
                    )
                    for peer in config.peers
                )),
            )
            # Even an exception or an unconfirmed result can follow mutation.
            dependencies_touched = True
            result = ownership.converge(peer_desired)
            if not result.confirmed:
                raise AlphaRuntimeError(result.diagnostic or "peer release unconfirmed")
            safe_ids.add(item.device_id)
        except Exception as exc:
            problems[item.device_id] = f"dependency release: {type(exc).__name__}: {exc}"
    if safe_ids:
        # Recheck after D.003 mutations, immediately before authorizing D.001.
        try:
            if not replacement_still_current():
                safe_ids.clear()
        except Exception:
            safe_ids.clear()
    if safe_ids:
        absent = manager.reconcile_undemanded(
            prepared.current_config,
            desired_device_ids=desired,
            dependency_free_device_ids=frozenset(safe_ids),
        )
        realizations = tuple(sorted(
            tuple(item for item in convergence.realizations if item.device_id in desired)
            + absent,
            key=lambda item: item.device_id,
        ))
    else:
        realizations = convergence.realizations
    return ManagedDeviceReleaseOutcome(
        tuple(
            replace(item, waiting_for_dependencies=False, problem=problems[item.device_id])
            if item.device_id in problems else item
            for item in realizations
        ),
        dependencies_touched=dependencies_touched,
        retirement_attempted=bool(safe_ids),
    )


def refresh_alpha_managed_demand_status(
    prepared: AlphaPreparedPolicy,
    agent: RuntimeStatusAgent,
) -> None:
    """Project diagnostics from the last confirmed normal binding observation.

    The caller must have confirmed the current binding-dependent policy.
    This read-only A.013 calculation does not actuate a new desired set;
    A.012's accepted desired and confirmed states remain separate.
    """
    agent.confirm_managed_demand(
        project_final(prepared.current_config, prepared.last_bindings)
    )


def _release_alpha_managed_device_dependencies(
    desired: PayloadNetworkPolicyDesiredState,
    domain_spec: ManagedNetworkDomainSpec,
    runner: SubprocessNftRunner,
) -> None:
    """Remove owned policy dependencies before A.012 may stop managed Devices."""
    gate = LinuxForwardingGateDriver(runner, domain_spec.namespace)
    containment = converge_forwarding_gate_once(gate, ForwardingGateState.DISABLED)
    if not containment.confirmed:
        raise AlphaRuntimeError(
            "managed Device dependency release requires confirmed disabled forwarding"
        )

    host_boundary = desired.routing.host_boundary
    affinity = converge_stack_return_affinity_once(
        gate,
        LinuxStackReturnAffinityBackend(
            runner,
            domain_spec.namespace,
            NG3_STACK_RETURN_AFFINITY_PLATFORM,
        ),
        StackReturnAffinityDesired(host_boundary, (), (), ()),
    )
    if not affinity.confirmed:
        raise AlphaRuntimeError(
            "stack return-affinity dependency cleanup is not confirmed"
            + (f": {affinity.diagnostic}" if affinity.diagnostic else "")
        )

    structural = converge_structural_policy(
        gate,
        LinuxStructuralPolicyBackend(
            runner=runner,
            namespace=domain_spec.namespace,
            platform=NG3_LINUX_POLICY_PLATFORM,
        ),
        PayloadRoutingDesiredState(host_boundary, (), ()),
        CompositeNftDesiredState(
            PayloadForwardDesiredState(()),
            PayloadNatDesiredState(()),
            DeviceFirewallDesiredState(()),
        ),
        NG3_LINUX_POLICY_PLATFORM,
    )
    if not structural.confirmed:
        raise AlphaRuntimeError(
            "payload policy dependency cleanup is not confirmed"
            + (f": {structural.diagnostic}" if structural.diagnostic else "")
        )


def reconcile_alpha_payload_once(
    prepared: AlphaPreparedPolicy,
    domain_spec: ManagedNetworkDomainSpec,
    runner: SubprocessNftRunner,
) -> AlphaReconcileResult:
    """Freshly audit one Manager-owned payload domain and converge only on drift."""
    lifecycle_errors: list[str] = []
    host_boundary: InterfaceIdentity | None = None
    try:
        if not preflight_managed_network_environment(domain_spec, runner):
            lifecycle_errors.append("managed network environment is absent")
        else:
            environment = ensure_managed_network_environment(domain_spec, runner)
            boundary = ensure_managed_l3_boundary(domain_spec, runner)
            portal = ensure_ordinary_side_portal(domain_spec, runner)
            lifecycle_errors.extend(environment.verification.errors)
            lifecycle_errors.extend(boundary.verification.errors)
            lifecycle_errors.extend(portal.errors)
            host_boundary = boundary.verification.private_boundary
            if host_boundary is None:
                lifecycle_errors.append(
                    "ordinary-side transition has no confirmed private boundary identity"
                )
    except Exception as exc:
        lifecycle_errors.append(
            "managed lifecycle repair/verification failed: "
            f"{type(exc).__name__}: {exc}"
        )

    if lifecycle_errors or host_boundary is None:
        containment_detail = "not attempted"
        try:
            containment = converge_forwarding_gate_once(
                LinuxForwardingGateDriver(runner, domain_spec.namespace),
                ForwardingGateState.DISABLED,
            )
            containment_detail = (
                "confirmed"
                if containment.confirmed
                else (
                    "not confirmed"
                    + (
                        f": {containment.diagnostic}"
                        if containment.diagnostic
                        else ""
                    )
                )
            )
        except Exception as exc:
            containment_detail = f"failed: {type(exc).__name__}: {exc}"
        return AlphaReconcileResult(
            AlphaReconcileStatus.FAILED,
            None,
            diagnostic=(
                "managed lifecycle is not recoverably exact: "
                + "; ".join(lifecycle_errors)
                + f"; fail-closed containment={containment_detail}"
            ),
        )

    try:
        path_observation = LinuxVpnPathAdapter(
            runner,
            domain_spec.namespace,
        ).observe_interfaces(
            required_host_boundary=host_boundary,
            require_private_peer=prepared.requires_private_peer_observation,
        )
        desired = prepared.build_current(
            host_boundary,
            path_observation.interfaces,
            path_private_peers=(
                path_observation.private_peers
                if prepared.requires_private_peer_observation
                else None
            ),
        )
        host_publication_desired = prepared.build_host_publication_desired()
    except Exception as exc:
        containment_detail = "not attempted"
        try:
            containment = converge_forwarding_gate_once(
                LinuxForwardingGateDriver(runner, domain_spec.namespace),
                ForwardingGateState.DISABLED,
            )
            containment_detail = (
                "confirmed"
                if containment.confirmed
                else (
                    "not confirmed"
                    + (
                        f": {containment.diagnostic}"
                        if containment.diagnostic
                        else ""
                    )
                )
            )
        except Exception as containment_exc:
            containment_detail = (
                f"failed: {type(containment_exc).__name__}: {containment_exc}"
            )
        return AlphaReconcileResult(
            AlphaReconcileStatus.FAILED,
            None,
            diagnostic=(
                f"desired-state rebuild failed: {type(exc).__name__}: {exc}; "
                f"fail-closed containment={containment_detail}"
            ),
        )

    gate_backend = LinuxForwardingGateDriver(runner, domain_spec.namespace)
    structural_backend = LinuxStructuralPolicyBackend(
        runner=runner,
        namespace=domain_spec.namespace,
        platform=NG3_LINUX_POLICY_PLATFORM,
    )

    # Fast no-op audit path: do not close forwarding merely because the local
    # Manager's periodic audit fired.
    try:
        snapshot = structural_backend.observe_structural_snapshot()
        comparison = compare_structural_policy(
            snapshot,
            desired.routing,
            desired.nft,
            NG3_LINUX_POLICY_PLATFORM,
        )
        affinity_exact = True
        if desired.stack_return_affinity is not None:
            affinity_exact = (
                LinuxStackReturnAffinityBackend(
                    runner,
                    domain_spec.namespace,
                    NG3_STACK_RETURN_AFFINITY_PLATFORM,
                ).observe(desired.stack_return_affinity).status
                is StackReturnAffinityOwnerStatus.EXACT
            )
        gate = gate_backend.observe_forwarding_gate()
        if (
            comparison.desired_confirmed
            and affinity_exact
            and gate is ForwardingGateState.ENABLED
        ):
            host_result = HostPublicationAdapter(
                LinuxHostPublicationDriver(runner)
            ).apply(host_publication_desired)
            if host_result.confirmed:
                return AlphaReconcileResult(
                    status=(
                        AlphaReconcileStatus.RECONCILED
                        if host_result.status
                        is HostPublicationConvergenceStatus.APPLIED
                        else AlphaReconcileStatus.EXACT
                    ),
                    desired=desired,
                    host_publication_desired=host_publication_desired,
                    host_publication=host_result,
                )
            return AlphaReconcileResult(
                status=AlphaReconcileStatus.FAILED,
                desired=desired,
                host_publication_desired=host_publication_desired,
                host_publication=host_result,
                diagnostic=(
                    host_result.diagnostic
                    or "host publication convergence is not confirmed"
                ),
            )
    except Exception:
        # The guarded activation boundary below re-observes from authoritative
        # state, closes forwarding first and classifies the concrete failure.
        pass

    activation = activate_network_policy(
        gate_backend,
        LinuxNftScaffoldDriver(runner, domain_spec.namespace),
        structural_backend,
        desired.routing,
        desired.nft,
        NG3_LINUX_POLICY_PLATFORM,
        LinuxStackReturnAffinityBackend(
            runner,
            domain_spec.namespace,
            NG3_STACK_RETURN_AFFINITY_PLATFORM,
        ),
        desired.stack_return_affinity,
    )
    if activation.ready:
        host_result = HostPublicationAdapter(
            LinuxHostPublicationDriver(runner)
        ).apply(host_publication_desired)
        if host_result.confirmed:
            return AlphaReconcileResult(
                status=AlphaReconcileStatus.RECONCILED,
                desired=desired,
                host_publication_desired=host_publication_desired,
                activation=activation,
                host_publication=host_result,
            )
        return AlphaReconcileResult(
            status=AlphaReconcileStatus.FAILED,
            desired=desired,
            host_publication_desired=host_publication_desired,
            activation=activation,
            host_publication=host_result,
            diagnostic=(
                host_result.diagnostic
                or "host publication convergence is not confirmed"
            ),
        )

    return AlphaReconcileResult(
        AlphaReconcileStatus.FAILED,
        desired,
        activation=activation,
        diagnostic=(
            activation.diagnostic
            or f"network-policy activation failed: {activation.status.value}"
        ),
    )


def prepare_alpha_availability_probe_plane_once(
    prepared: AlphaPreparedPolicy,
    runner: SubprocessNftRunner,
) -> LinuxProbePlanePreparationResult:
    if prepared.last_probe_assembly is None:
        raise AlphaRuntimeError(
            "availability cycle requires a current probe desired assembly"
        )
    return prepare_linux_availability_probe_plane_once(
        prepared.last_probe_assembly,
        runner=runner,
        namespace=ALPHA_NAMESPACE,
        platform=NG3_LINUX_POLICY_PLATFORM,
    )


def reconcile_alpha_availability_after_probe_plane_once(
    prepared: AlphaPreparedPolicy,
    preparation: LinuxProbePlanePreparationResult,
    ownership_dependencies: Mapping[
        ProbePolicyOwner,
        ProbeOwnershipDependency,
    ],
    runner: SubprocessNftRunner,
    probe_driver: LinuxIcmpProbeDriver,
) -> LinuxAvailabilityCycleResult:
    if prepared.last_probe_assembly is None:
        raise AlphaRuntimeError(
            "availability cycle requires a current probe desired assembly"
        )
    prepared.last_availability_dependencies = dict(ownership_dependencies)
    result = complete_linux_availability_cycle_once(
        prepared.config,
        prepared.last_baseline_profiles,
        prepared.last_path_routes,
        prepared.last_probe_assembly,
        preparation,
        prepared.availability_runtime,
        prepared.availability_manager,
        probe_driver,
        ownership_dependencies=ownership_dependencies,
        runner=runner,
        namespace=ALPHA_NAMESPACE,
        platform=NG3_LINUX_POLICY_PLATFORM,
    )
    if (
        result.observation is not None
        and result.priority is not None
        and result.priority.confirmed
    ):
        prepared.last_profiles = (
            result.observation.projection.effective_profiles
        )
    return result


def reconcile_alpha_wireguard_peers_once(
    prepared: AlphaPreparedPolicy,
    managed_realizations: tuple[ManagedDeviceRealization, ...],
    coordinator: WireGuardPeerRuntimeCoordinator,
    runner: SubprocessNftRunner,
    probe_driver: LinuxIcmpProbeDriver,
    ownership: WireGuardPeerOwnershipEnforcer,
) -> WireGuardPeerRuntimeResult:
    """Run one D.002 trigger from the current accepted alpha probe plane."""
    if prepared.last_probe_assembly is None:
        raise AlphaRuntimeError(
            "WireGuard peer reconciliation requires a current probe desired assembly"
        )
    return coordinator.reconcile(
        prepared.current_config,
        managed_realizations,
        prepared.last_path_routes,
        prepared.last_probe_assembly,
        snapshot_observer=LinuxStructuralPolicyBackend(
            runner=runner,
            namespace=ALPHA_NAMESPACE,
            platform=NG3_LINUX_POLICY_PLATFORM,
        ),
        probe_driver=probe_driver,
        ownership=ownership,
        platform=NG3_LINUX_POLICY_PLATFORM,
    )


def build_alpha_availability_ownership_dependencies(
    prepared: AlphaPreparedPolicy,
    wireguard_result: WireGuardPeerRuntimeResult | None,
) -> dict[ProbePolicyOwner, ProbeOwnershipDependency]:
    if prepared.last_probe_assembly is None:
        raise AlphaRuntimeError(
            "availability dependencies require a current probe desired assembly"
        )
    realizations = (
        {}
        if wireguard_result is None
        else {
            realization.device_id: realization
            for realization in wireguard_result.realizations
        }
    )
    dependencies: dict[
        ProbePolicyOwner,
        ProbeOwnershipDependency,
    ] = {}
    for intent in prepared.last_probe_assembly.availability_intents:
        owner = intent.owner
        group_key = (owner.profile_id, owner.path_id.device_id)
        if group_key not in prepared.current_config.wireguard_groups:
            dependencies[owner] = ProbeOwnershipDependency.not_applicable()
            continue
        realization = realizations.get(owner.path_id.device_id)
        if (
            realization is None
            or realization.problem is not None
            or realization.generation is None
        ):
            dependencies[owner] = ProbeOwnershipDependency.unconfirmed()
            continue
        dependencies[owner] = ProbeOwnershipDependency.confirmed(
            realization.generation
        )
    return dependencies


def reconcile_alpha_availability_wireguard_once(
    prepared: AlphaPreparedPolicy,
    managed_realizations: tuple[ManagedDeviceRealization, ...],
    coordinator: WireGuardPeerRuntimeCoordinator,
    runner: SubprocessNftRunner,
    probe_driver: LinuxIcmpProbeDriver,
    ownership: WireGuardPeerOwnershipEnforcer,
) -> tuple[
    LinuxAvailabilityCycleResult,
    WireGuardPeerRuntimeResult | None,
    str | None,
]:
    """Apply C.001 -> D.002 -> A.007 -> A.004 ordering in one normal trigger."""
    preparation = prepare_alpha_availability_probe_plane_once(
        prepared,
        runner,
    )
    wireguard_result: WireGuardPeerRuntimeResult | None = None
    wireguard_error: str | None = None
    if preparation.confirmed:
        try:
            wireguard_result = reconcile_alpha_wireguard_peers_once(
                prepared,
                managed_realizations,
                coordinator,
                runner,
                probe_driver,
                ownership,
            )
            wireguard_error = _wireguard_peer_problem(wireguard_result)
        except Exception as exc:
            wireguard_error = (
                "WireGuard peer reconciliation failed: "
                f"{type(exc).__name__}: {exc}"
            )
    dependencies = build_alpha_availability_ownership_dependencies(
        prepared,
        wireguard_result,
    )
    availability_result = reconcile_alpha_availability_after_probe_plane_once(
        prepared,
        preparation,
        dependencies,
        runner,
        probe_driver,
    )
    return availability_result, wireguard_result, wireguard_error


@dataclass(frozen=True, slots=True)
class AlphaPostReleaseResult:
    realizations: tuple[ManagedDeviceRealization, ...]
    payload: AlphaReconcileResult
    availability: LinuxAvailabilityCycleResult | None
    wireguard: WireGuardPeerRuntimeResult | None
    wireguard_error: str | None


def reconcile_alpha_after_managed_release(
    prepared: AlphaPreparedPolicy,
    domain_spec: ManagedNetworkDomainSpec,
    runner: SubprocessNftRunner,
    manager: ManagedDeviceManager,
    coordinator: WireGuardPeerRuntimeCoordinator,
    probe_driver: LinuxIcmpProbeDriver,
    ownership: WireGuardPeerOwnershipEnforcer,
) -> AlphaPostReleaseResult:
    """Fresh recovery after possible dependency mutation, without another release.

    Recompute presence first: merely reapplying payload policy with the old
    confirmed managed-interface set can exclude the retained reserve again.
    One bounded recovery pass is not a recursive retirement attempt.
    """
    try:
        fresh = converge_alpha_managed_device_presence(
            prepared, domain_spec, runner, manager
        )
        payload = reconcile_alpha_payload_once(prepared, domain_spec, runner)
        if not payload.ready:
            return AlphaPostReleaseResult(
                fresh.realizations, payload, None, None, None
            )
        availability, wireguard, error = reconcile_alpha_availability_wireguard_once(
            prepared, fresh.realizations, coordinator, runner, probe_driver, ownership
        )
        return AlphaPostReleaseResult(
            fresh.realizations, payload, availability, wireguard, error
        )
    except Exception as exc:
        prepared.confirmed_managed_interfaces = frozenset()
        diagnostic = f"post-release recovery failed: {type(exc).__name__}: {exc}"
        try:
            containment = converge_forwarding_gate_once(
                LinuxForwardingGateDriver(runner, domain_spec.namespace),
                ForwardingGateState.DISABLED,
            )
            diagnostic += f"; containment confirmed={containment.confirmed}"
        except Exception as containment_exc:
            diagnostic += f"; containment failed: {containment_exc}"
        return AlphaPostReleaseResult(
            (),
            AlphaReconcileResult(AlphaReconcileStatus.FAILED, None, diagnostic=diagnostic),
            None,
            None,
            None,
        )


def complete_alpha_normal_reconciliation(
    prepared: AlphaPreparedPolicy,
    domain_spec: ManagedNetworkDomainSpec,
    runner: SubprocessNftRunner,
    manager: ManagedDeviceManager,
    convergence: ManagedDeviceConvergence,
    coordinator: WireGuardPeerRuntimeCoordinator,
    probe_driver: LinuxIcmpProbeDriver,
    ownership: WireGuardPeerOwnershipEnforcer,
    result: AlphaReconcileResult,
    availability_result: LinuxAvailabilityCycleResult | None,
    wireguard_result: WireGuardPeerRuntimeResult | None,
    wireguard_error: str | None,
) -> AlphaPostReleaseResult:
    """Finish the unchanged legacy release path before admitting its final state.

    Pre-reclaim evidence is diagnostic only: this helper never reads it.
    In particular, a post-release recovery is the only possible source of
    accepted state after dependency/lifecycle mutation in the same trigger.
    """
    final = AlphaPostReleaseResult(
        convergence.realizations, result, availability_result,
        wireguard_result, wireguard_error,
    )
    if (result.ready and availability_result is not None
            and availability_result.confirmed and wireguard_error is None):
        release = release_alpha_undemanded_devices(
            prepared, domain_spec, runner, manager, convergence, ownership,
            dependencies_confirmed=True,
        )
        if release.requires_reconvergence:
            final = reconcile_alpha_after_managed_release(
                prepared, domain_spec, runner, manager, coordinator, probe_driver, ownership,
            )
        else:
            final = replace(final, realizations=release.realizations)
    publish_alpha_accepted_effective(
        prepared, payload_confirmed=final.payload.ready,
        availability=final.availability, wireguard=final.wireguard,
        wireguard_error=final.wireguard_error,
    )
    return final


def _wireguard_peer_problem(
    result: WireGuardPeerRuntimeResult,
) -> str | None:
    for realization in result.realizations:
        if realization.problem is not None:
            return (
                f"managed WireGuard Device {realization.device_id!r}: "
                f"{realization.problem}"
            )
    return None


def _domain_spec() -> ManagedNetworkDomainSpec:
    return ManagedNetworkDomainSpec(
        namespace=ALPHA_NAMESPACE,
        host_interface=ALPHA_HOST_INTERFACE,
        inner_interface=ALPHA_INNER_INTERFACE,
        inner_address=ALPHA_INNER_ADDRESS,
    )


def _notify_systemd(message: str) -> bool:
    notify_socket = os.environ.get("NOTIFY_SOCKET")
    if not notify_socket:
        return False

    address = (
        "\0" + notify_socket[1:]
        if notify_socket.startswith("@")
        else notify_socket
    )
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.connect(address)
        sock.sendall(message.encode("utf-8"))
    return True


def _path_label(path_id: LogicalPathId) -> str:
    return (
        f"{path_id.device_id}:{path_id.selector_index}:{path_id.slot_index}"
    )


def _binding_map(
    bindings: tuple[PathBinding, ...],
) -> dict[LogicalPathId, str]:
    return {
        binding.path_id: (
            f"{binding.endpoint.ifname}@{binding.endpoint.ifindex}"
        )
        for binding in bindings
    }


def _emit_binding_transitions(
    logger: OperationalLogAdapter,
    previous: tuple[PathBinding, ...],
    current: tuple[PathBinding, ...],
) -> None:
    before = _binding_map(previous)
    after = _binding_map(current)
    for path_id in sorted(set(before) | set(after)):
        old = before.get(path_id)
        new = after.get(path_id)
        if old == new:
            continue
        logger.emit(
            OperationalLogLevel.INFO,
            BIND_LOG_TAG,
            "path_binding_changed",
            device=path_id.device_id,
            path=_path_label(path_id),
            previous=old,
            current=new,
        )


def _profile_orders(
    profiles: tuple[PayloadProfileRequest, ...],
) -> dict[str, tuple[str, ...]]:
    return {
        profile.profile_id: tuple(
            _path_label(path)
            for path in profile.ordered_paths
        )
        for profile in profiles
    }


def _emit_profile_reactions(
    logger: OperationalLogAdapter,
    previous: tuple[PayloadProfileRequest, ...],
    current: tuple[PayloadProfileRequest, ...],
) -> None:
    before = _profile_orders(previous)
    after = _profile_orders(current)
    for profile_id in sorted(set(before) | set(after)):
        old = before.get(profile_id, ())
        new = after.get(profile_id, ())
        if old == new:
            continue
        logger.emit(
            OperationalLogLevel.DEBUG,
            PROF_LOG_TAG,
            "effective_order_changed",
            profile=profile_id,
            previous=",".join(old) or "-",
            current=",".join(new) or "-",
        )


def _emit_availability_transitions(
    logger: OperationalLogAdapter,
    previous_problem_owners,
    current_problem_owners,
) -> None:
    before = frozenset(previous_problem_owners)
    after = frozenset(current_problem_owners)
    for owner in sorted(after - before):
        logger.emit(
            OperationalLogLevel.INFO,
            AVAIL_LOG_TAG,
            "path_unavailable",
            profile=owner.profile_id,
            path=_path_label(owner.path_id),
        )
    for owner in sorted(before - after):
        logger.emit(
            OperationalLogLevel.INFO,
            AVAIL_LOG_TAG,
            "path_available",
            profile=owner.profile_id,
            path=_path_label(owner.path_id),
        )


def run_alpha_runtime(
    config_path: Path,
    *,
    audit_interval_seconds: float = ALPHA_AUDIT_INTERVAL_SECONDS,
) -> int:
    if os.geteuid() != 0:
        raise AlphaRuntimeError("alpha runtime must run as root")
    if audit_interval_seconds <= 0:
        raise ValueError("audit_interval_seconds must be positive")
    try:
        release_version = read_release_version(ALPHA_VERSION_PATH)
    except (OSError, ValueError) as exc:
        raise AlphaRuntimeError(
            f"release VERSION is unavailable or invalid at {ALPHA_VERSION_PATH}: {exc}"
        ) from exc

    runner = SubprocessNftRunner()
    managed_wireguard_adapter = LinuxManagedWireGuardAdapter(
        runner,
        ALPHA_NAMESPACE,
    )
    managed_device_manager = ManagedDeviceManager(
        managed_wireguard_adapter
    )
    wireguard_peer_runtime = WireGuardPeerRuntimeCoordinator()
    wireguard_peer_ownership = WireGuardPeerOwnershipEnforcer(
        runner,
        ALPHA_NAMESPACE,
        managed_wireguard_adapter,
    )
    managed_realizations_holder: dict[str, tuple[ManagedDeviceRealization, ...]] = {
        "current": ()
    }
    managed_convergence_holder: dict[str, ManagedDeviceConvergence] = {}
    probe_driver = LinuxIcmpProbeDriver(
        runner=SubprocessProbeCommandRunner(),
        namespace=ALPHA_NAMESPACE,
        process_uid=NG3_PROBE_LOCAL_PLATFORM.process_uid,
        execution_policy=IcmpProbeExecutionPolicy(
            ALPHA_PROBE_REPLY_TIMEOUT_SECONDS,
        ),
    )
    domain_spec = _domain_spec()
    stop_event = threading.Event()
    normal_operation_lock = threading.RLock()
    protective_service: ProtectiveModeControlService | None = None
    holder: dict[str, AlphaPreparedPolicy] = {}
    logger_holder = {
        "logger": OperationalLogAdapter(OperationalLogLevel.INFO)
    }

    def log(level, tag, event, **context):
        return logger_holder["logger"].emit(
            level,
            tag,
            event,
            **context,
        )

    def request_stop(signum, _frame):
        log(
            OperationalLogLevel.INFO,
            LIFE_LOG_TAG,
            "stop_requested",
            signal=signum,
        )
        stop_event.set()

    previous_sigterm = signal.signal(signal.SIGTERM, request_stop)
    previous_sigint = signal.signal(signal.SIGINT, request_stop)

    def load_policy() -> AlphaPreparedPolicy:
        text = config_path.read_text(encoding="utf-8")
        prepared = AlphaPreparedPolicy.from_text(
            text,
            local_address=domain_spec.inner_address.ip,
        )
        logger_holder["logger"] = OperationalLogAdapter(
            prepared.config.log_level
        )
        log(
            OperationalLogLevel.INFO,
            LIFE_LOG_TAG,
            "config_accepted",
            devices=len(prepared.config.structural.active_device_ids),
            profiles=sum(
                1
                for profile in prepared.config.structural.profiles.values()
                if profile.enabled
            ),
            log_level=prepared.config.log_level.value,
        )
        validate_release1_helper_routing_scope(
            prepared.config,
            domain_spec,
        )
        if helper_routing_uses_external_ingress(prepared.config):
            try:
                host_forwarding = Path(
                    "/proc/sys/net/ipv4/ip_forward"
                ).read_text(encoding="ascii").strip()
            except OSError as exc:
                log(
                    OperationalLogLevel.WARNING,
                    HOST_LOG_TAG,
                    "host_forwarding_observation_failed",
                    diagnostic=f"{type(exc).__name__}: {exc}",
                )
            else:
                if host_forwarding == "0":
                    log(
                        OperationalLogLevel.WARNING,
                        HOST_LOG_TAG,
                        "host_forwarding_disabled",
                        selector="external",
                    )
        holder["policy"] = prepared
        return prepared

    def build_host_routing_contribution(prepared, current_domain_spec):
        if not isinstance(prepared, AlphaPreparedPolicy):
            raise AlphaRuntimeError(
                "alpha host-routing contribution requires AlphaPreparedPolicy"
            )
        return build_linux_peaceful_host_routing_contribution(
            prepared.config,
            current_domain_spec,
            runner,
        )

    def prepare_managed_devices(prepared, current_domain_spec):
        if not isinstance(prepared, AlphaPreparedPolicy):
            raise AlphaRuntimeError(
                "managed Device preparation requires AlphaPreparedPolicy"
            )
        if current_domain_spec.namespace != domain_spec.namespace:
            raise AlphaRuntimeError("managed Device preparation namespace mismatch")
        previous_accepted = prepared.begin_effective_transition()
        convergence = converge_alpha_managed_device_presence(
            prepared, current_domain_spec, runner, managed_device_manager
        )
        prepared.pre_reclaim_evidence = observe_alpha_pre_reclaim(
            prepared, current_domain_spec, runner, managed_device_manager, previous_accepted,
        )
        managed_realizations_holder["current"] = convergence.realizations
        managed_convergence_holder["current"] = convergence
        for problem in convergence.attempt_problems:
            log(OperationalLogLevel.WARNING, LIFE_LOG_TAG, "managed_presence_failed",
                device_id=problem.device_id, diagnostic=problem.problem)

    try:
        startup = start_controller_once(
            InstanceLockSpec(
                runtime_directory=ALPHA_RUNTIME_DIRECTORY,
                expected_owner_uid=os.getuid(),
            ),
            domain_spec,
            runner,
            NG3_LINUX_POLICY_PLATFORM,
            load_policy,
            stop_requested=stop_event.is_set,
            build_host_routing_contribution=build_host_routing_contribution,
            stack_return_affinity_platform=NG3_STACK_RETURN_AFFINITY_PLATFORM,
            prepare_private_network=prepare_managed_devices,
        )
        if startup.status is not ControllerStartupStatus.READY:
            log(
                OperationalLogLevel.ERROR,
                LIFE_LOG_TAG,
                "start_failed",
                status=startup.status.value,
                diagnostic=startup.diagnostic,
            )
            return 1

        assert startup.session is not None
        prepared = holder["policy"]
        host_routing_contribution = startup.session.host_routing_contribution
        if (
            host_routing_contribution is not None
            and not isinstance(
                host_routing_contribution,
                LinuxPeacefulHostRoutingContribution,
            )
        ):
            raise AlphaRuntimeError(
                "alpha startup returned an unexpected host-routing helper"
            )
        status_agent = RuntimeStatusAgent(
            build_configured_intent_status(prepared.current_config),
            version=release_version,
        )
        status_publisher = RuntimeStatusFilePublisher(
            ALPHA_STATUS_PATH,
            ALPHA_STATUS_TEXT_PATH,
        )
        status_agent.confirm_managed_devices(
            managed_realizations_holder["current"]
        )
        refresh_alpha_managed_demand_status(prepared, status_agent)
        status_publisher.publish(status_agent.snapshot())

        def stop_owned_runtime():
            prepared.begin_effective_transition()
            host_cleanup = HostPublicationAdapter(
                LinuxHostPublicationDriver(runner)
            ).cleanup()
            managed_cleanup_error = None
            try:
                _release_alpha_managed_device_dependencies(
                    startup.session.desired,
                    domain_spec,
                    runner,
                )
                status_agent.confirm_managed_demand(None)
                shutdown_config = CurrentConfig(prepared.config, {})
                shutdown_realizations = managed_device_manager.reconcile(
                    shutdown_config,
                    desired_device_ids=frozenset(),
                    dependency_free_device_ids=frozenset(
                        prepared.current_config.managed_vpns
                    ),
                )
                managed_realizations_holder["current"] = shutdown_realizations
                status_agent.confirm_managed_devices(shutdown_realizations)
                status_agent.confirm_wireguard_peers(())
                problem = _managed_device_problem(
                    shutdown_realizations,
                    require_absent=True,
                )
                if problem is not None:
                    raise AlphaRuntimeError(problem)
            except Exception as exc:
                managed_cleanup_error = f"{type(exc).__name__}: {exc}"
            if managed_cleanup_error is not None:
                return host_cleanup, managed_cleanup_error, None
            stopped = stop_controller_once(
                startup.session,
                domain_spec,
                runner,
            )
            return host_cleanup, None, stopped

        (
            availability_start,
            wireguard_start,
            wireguard_start_error,
        ) = reconcile_alpha_availability_wireguard_once(
            prepared,
            managed_realizations_holder["current"],
            wireguard_peer_runtime,
            runner,
            probe_driver,
            wireguard_peer_ownership,
        )
        if availability_start.confirmed and wireguard_start_error is None:
            release = release_alpha_undemanded_devices(
                prepared, domain_spec, runner, managed_device_manager,
                managed_convergence_holder["current"], wireguard_peer_ownership,
                dependencies_confirmed=True,
            )
            realizations = release.realizations
            if release.requires_reconvergence:
                recovered = reconcile_alpha_after_managed_release(
                    prepared, domain_spec, runner, managed_device_manager,
                    wireguard_peer_runtime, probe_driver, wireguard_peer_ownership,
                )
                realizations = recovered.realizations
                availability_start = recovered.availability
                wireguard_start = recovered.wireguard
                wireguard_start_error = recovered.wireguard_error
                if not recovered.payload.ready:
                    wireguard_start_error = (
                        recovered.payload.diagnostic or "post-release payload unconfirmed"
                    )
            managed_realizations_holder["current"] = realizations
            status_agent.confirm_managed_devices(realizations)
        status_agent.confirm_wireguard_peers(
            ()
            if wireguard_start is None
            else wireguard_start.realizations
        )
        if (
            availability_start is None
            or not availability_start.confirmed
            or wireguard_start_error is not None
        ):
            host_cleanup, managed_cleanup_error, stopped = stop_owned_runtime()
            status_agent.mark_unconfirmed(
                readiness=RuntimeReadiness.FAILED,
                problem=(
                    wireguard_start_error
                    or (
                        availability_start.diagnostic
                        if availability_start is not None else None
                    )
                    or (
                        "availability startup cycle is not confirmed: "
                        + (availability_start.status.value
                           if availability_start is not None else "not_attempted")
                    )
                ),
                unknown_fields=(
                    (
                        "confirmed_effective_state",
                        "wireguard_peer_realizations",
                    )
                    if (
                        prepared.current_config.wireguard_groups
                        and wireguard_start is None
                    )
                    else ("confirmed_effective_state",)
                ),
            )
            status_publisher.publish(status_agent.snapshot())
            log(
                OperationalLogLevel.ERROR,
                LIFE_LOG_TAG,
                "start_failed",
                status="availability_unready",
                availability=(
                    availability_start.status.value
                    if availability_start is not None else "not_attempted"
                ),
                diagnostic=(
                    wireguard_start_error
                    or (availability_start.diagnostic
                        if availability_start is not None else None)
                ),
                host_cleanup=host_cleanup.status.value,
                managed_device_cleanup_error=managed_cleanup_error,
                managed_cleanup=(
                    stopped.status.value
                    if stopped is not None
                    else "not_attempted"
                ),
            )
            return (
                1
                if host_cleanup.confirmed
                and managed_cleanup_error is None
                and stopped is not None
                and stopped.status is ControllerStopStatus.STOPPED
                else 2
            )

        def reconcile_normal_once_unlocked():
            previous_accepted = prepared.begin_effective_transition()
            try:
                convergence = converge_alpha_managed_device_presence(
                    prepared, domain_spec, runner, managed_device_manager
                )
            except Exception as exc:
                diagnostic = f"managed presence observation failed: {type(exc).__name__}: {exc}"
                try:
                    containment = converge_forwarding_gate_once(
                        LinuxForwardingGateDriver(runner, domain_spec.namespace),
                        ForwardingGateState.DISABLED,
                    )
                    diagnostic += f"; containment confirmed={containment.confirmed}"
                except Exception as containment_exc:
                    diagnostic += f"; containment failed: {containment_exc}"
                status_agent.confirm_managed_devices(())
                status_agent.confirm_managed_demand(None)
                status_agent.confirm_wireguard_peers(())
                managed_realizations_holder["current"] = ()
                return (
                    AlphaReconcileResult(AlphaReconcileStatus.FAILED, None, diagnostic=diagnostic),
                    None, None, None,
                )
            managed_realizations = convergence.realizations
            managed_realizations_holder["current"] = managed_realizations
            status_agent.confirm_managed_devices(managed_realizations)
            for problem in convergence.attempt_problems:
                log(OperationalLogLevel.WARNING, LIFE_LOG_TAG, "managed_presence_failed",
                    device_id=problem.device_id, diagnostic=problem.problem)
            prepared.pre_reclaim_evidence = observe_alpha_pre_reclaim(
                prepared, domain_spec, runner, managed_device_manager, previous_accepted,
            )
            result = reconcile_alpha_payload_once(
                prepared,
                domain_spec,
                runner,
            )
            if result.ready:
                (
                    availability_result,
                    wireguard_result,
                    wireguard_error,
                ) = reconcile_alpha_availability_wireguard_once(
                    prepared,
                    managed_realizations,
                    wireguard_peer_runtime,
                    runner,
                    probe_driver,
                    wireguard_peer_ownership,
                )
            else:
                availability_result = None
                wireguard_result = None
                wireguard_error = None
            final = complete_alpha_normal_reconciliation(
                prepared, domain_spec, runner, managed_device_manager,
                convergence, wireguard_peer_runtime, probe_driver,
                wireguard_peer_ownership, result, availability_result,
                wireguard_result, wireguard_error,
            )
            managed_realizations = final.realizations
            result = final.payload
            availability_result = final.availability
            wireguard_result = final.wireguard
            wireguard_error = final.wireguard_error
            managed_realizations_holder["current"] = managed_realizations
            status_agent.confirm_managed_devices(managed_realizations)
            if result.ready:
                refresh_alpha_managed_demand_status(prepared, status_agent)
            else:
                status_agent.confirm_managed_demand(None)
            status_agent.confirm_wireguard_peers(
                ()
                if wireguard_result is None
                else wireguard_result.realizations
            )
            return (
                result,
                availability_result,
                wireguard_result,
                wireguard_error,
            )

        def normal_release_confirmed_unlocked() -> bool:
            (
                result,
                availability_result,
                _wireguard_result,
                wireguard_error,
            ) = reconcile_normal_once_unlocked()
            confirmed = (
                result.ready
                and availability_result is not None
                and availability_result.confirmed
                and wireguard_error is None
            )
            if not confirmed:
                log(
                    OperationalLogLevel.WARNING,
                    POLICY_LOG_TAG,
                    "protective_release_precondition_unconfirmed",
                    payload_status=result.status.value,
                    payload_diagnostic=result.diagnostic,
                    availability_status=(
                        availability_result.status.value
                        if availability_result is not None
                        else "not_attempted"
                    ),
                    availability_diagnostic=(
                        availability_result.diagnostic
                        if availability_result is not None
                        else None
                    ),
                    wireguard_diagnostic=wireguard_error,
                )
            return confirmed

        host_publication_desired = prepared.build_host_publication_desired()
        host_publication_adapter = HostPublicationAdapter(
            LinuxHostPublicationDriver(runner)
        )
        host_start = host_publication_adapter.apply(host_publication_desired)
        if not host_start.confirmed:
            host_cleanup, managed_cleanup_error, stopped = stop_owned_runtime()
            status_agent.mark_unconfirmed(
                readiness=RuntimeReadiness.FAILED,
                problem=(
                    host_start.diagnostic
                    or "host publication convergence is not confirmed"
                ),
            )
            status_publisher.publish(status_agent.snapshot())
            log(
                OperationalLogLevel.ERROR,
                LIFE_LOG_TAG,
                "start_failed",
                status="host_publication_unready",
                diagnostic=host_start.diagnostic,
                host_cleanup=host_cleanup.status.value,
                managed_device_cleanup_error=managed_cleanup_error,
                managed_cleanup=(
                    stopped.status.value
                    if stopped is not None
                    else "not_attempted"
                ),
            )
            return (
                1
                if host_cleanup.confirmed
                and managed_cleanup_error is None
                and stopped is not None
                and stopped.status is ControllerStopStatus.STOPPED
                else 2
            )

        publish_alpha_accepted_effective(
            prepared, payload_confirmed=True, availability=availability_start,
            wireguard=wireguard_start, wireguard_error=wireguard_start_error,
        )
        status_agent.confirm_effective(
            prepared.last_profiles,
            prepared.last_bindings,
        )
        refresh_alpha_managed_demand_status(prepared, status_agent)
        managed_problem = _managed_device_problem(managed_realizations_holder["current"])
        if managed_problem is not None:
            status_agent.mark_degraded(problem=managed_problem)
        if availability_start.observation is not None:
            status_agent.confirm_availability(
                availability_start.observation.projection.problem_owners
            )
        status_publisher.publish(status_agent.snapshot())

        protective_manager = ProtectiveModeManager()
        protective_driver = LinuxProtectivePayloadGateDriver(
            runner,
            domain_spec.namespace,
        )
        protective_service = ProtectiveModeControlService(
            protective_manager,
            protective_driver,
            ALPHA_INNER_INTERFACE,
            normal_release_confirmed_unlocked,
            normal_operation_lock,
            socket_path=ALPHA_CONTROL_PATH,
            audit_interval_seconds=audit_interval_seconds,
            logger=logger_holder["logger"],
        )
        try:
            protective_service.start()
        except Exception as exc:
            host_cleanup, managed_cleanup_error, stopped = stop_owned_runtime()
            status_agent.mark_unconfirmed(
                readiness=RuntimeReadiness.FAILED,
                problem=(
                    "protective-mode control startup failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )
            status_publisher.publish(status_agent.snapshot())
            log(
                OperationalLogLevel.ERROR,
                LIFE_LOG_TAG,
                "start_failed",
                status="protective_mode_unready",
                diagnostic=f"{type(exc).__name__}: {exc}",
                host_cleanup=host_cleanup.status.value,
                managed_device_cleanup_error=managed_cleanup_error,
                managed_cleanup=(
                    stopped.status.value
                    if stopped is not None
                    else "not_attempted"
                ),
            )
            return (
                1
                if host_cleanup.confirmed
                and managed_cleanup_error is None
                and stopped is not None
                and stopped.status is ControllerStopStatus.STOPPED
                else 2
            )

        _emit_binding_transitions(
            logger_holder["logger"],
            (),
            prepared.last_bindings,
        )
        initial_problem_owners = (
            availability_start.observation.projection.problem_owners
            if availability_start.observation is not None
            else frozenset()
        )
        _emit_availability_transitions(
            logger_holder["logger"],
            frozenset(),
            initial_problem_owners,
        )

        log(
            OperationalLogLevel.INFO,
            LIFE_LOG_TAG,
            "ready",
            namespace=domain_spec.namespace,
            netns_path=f"/run/netns/{domain_spec.namespace}",
        )
        _notify_systemd(
            "READY=1\n"
            f"STATUS=VPN-GATE alpha ready in /run/netns/{domain_spec.namespace}"
        )

        last_status: AlphaReconcileStatus | None = None
        last_diagnostic: str | None = None
        last_problem_owners = initial_problem_owners
        while not stop_event.wait(audit_interval_seconds):
            previous_bindings = prepared.last_bindings
            previous_profiles = prepared.last_profiles
            # Peaceful host-routing assistance is lifecycle-scoped. Ordinary-host
            # route changes after successful start are administrator-owned and do
            # not gate core managed-domain reconciliation.
            with normal_operation_lock:
                (
                    result,
                    availability_result,
                    wireguard_result,
                    wireguard_error,
                ) = reconcile_normal_once_unlocked()
            if (
                result.ready
                and availability_result is not None
                and availability_result.confirmed
                and wireguard_error is None
            ):
                status_agent.confirm_effective(
                    prepared.last_profiles,
                    prepared.last_bindings,
                    readiness=RuntimeReadiness.READY,
                )
                if availability_result.observation is not None:
                    status_agent.confirm_availability(
                        availability_result.observation.projection.problem_owners
                    )
                managed_problem = _managed_device_problem(managed_realizations_holder["current"])
                if managed_problem is not None:
                    status_agent.mark_degraded(problem=managed_problem)
            elif (
                result.ready
                and availability_result is not None
                and availability_result.confirmed
                and wireguard_error is not None
            ):
                status_agent.confirm_effective(
                    prepared.last_profiles,
                    prepared.last_bindings,
                    readiness=RuntimeReadiness.DEGRADED,
                )
                if availability_result.observation is not None:
                    status_agent.confirm_availability(
                        availability_result.observation.projection.problem_owners
                    )
                status_agent.mark_degraded(
                    problem=wireguard_error,
                    unknown_fields=(
                        ("wireguard_peer_realizations",)
                        if wireguard_result is None
                        else ()
                    ),
                )
            else:
                status_agent.mark_unconfirmed(
                    readiness=RuntimeReadiness.DEGRADED,
                    problem=(
                        (
                            availability_result.diagnostic
                            if availability_result is not None
                            else None
                        )
                        or result.diagnostic
                        or (
                            "availability reconcile is not confirmed: "
                            f"{availability_result.status.value}"
                            if availability_result is not None
                            else f"alpha reconcile failed: {result.status.value}"
                        )
                    ),
                    unknown_fields=(
                        ("confirmed_effective_state",)
                        + (
                            ("wireguard_peer_realizations",)
                            if prepared.current_config.wireguard_groups else ()
                        )
                        + (
                            ("managed_profile_demands",)
                            if status_agent.snapshot().managed_profile_demands is None
                            else ()
                        )
                        + (
                            ("managed_device_realizations",)
                            if prepared.current_config.managed_vpns
                            and not managed_realizations_holder["current"]
                            else ()
                        )
                    ),
                )
            current_problem_owners = (
                availability_result.observation.projection.problem_owners
                if availability_result is not None
                and availability_result.observation is not None
                else last_problem_owners
            )
            _emit_binding_transitions(
                logger_holder["logger"],
                previous_bindings,
                prepared.last_bindings,
            )
            _emit_availability_transitions(
                logger_holder["logger"],
                last_problem_owners,
                current_problem_owners,
            )
            _emit_profile_reactions(
                logger_holder["logger"],
                previous_profiles,
                prepared.last_profiles,
            )
            last_problem_owners = current_problem_owners

            status_publisher.publish(status_agent.snapshot())
            changed_result = (
                result.status is not last_status
                or result.diagnostic != last_diagnostic
            )
            if changed_result:
                if result.status is AlphaReconcileStatus.FAILED:
                    log(
                        OperationalLogLevel.ERROR,
                        POLICY_LOG_TAG,
                        "reconcile_failed",
                        status=result.status.value,
                        diagnostic=result.diagnostic,
                    )
                elif result.status is AlphaReconcileStatus.RECONCILED:
                    log(
                        OperationalLogLevel.DEBUG,
                        POLICY_LOG_TAG,
                        "policy_applied",
                        status=result.status.value,
                    )
                else:
                    log(
                        OperationalLogLevel.DEBUG,
                        POLICY_LOG_TAG,
                        "reconcile_confirmed",
                        status=result.status.value,
                    )
            if changed_result:
                _notify_systemd(
                    f"STATUS=VPN-GATE alpha reconcile {result.status.value}"
                )
            last_status = result.status
            last_diagnostic = result.diagnostic

        if protective_service is not None:
            protective_service.stop()
            protective_service = None

        status_agent.mark_stopping()
        status_publisher.publish(status_agent.snapshot())
        _notify_systemd("STOPPING=1\nSTATUS=VPN-GATE alpha stopping")
        host_cleanup, managed_cleanup_error, stopped = stop_owned_runtime()
        if (
            host_cleanup.confirmed
            and managed_cleanup_error is None
            and stopped is not None
            and stopped.status is ControllerStopStatus.STOPPED
        ):
            status_agent.mark_stopped()
        else:
            status_agent.mark_unconfirmed(
                readiness=RuntimeReadiness.FAILED,
                problem=(
                    "shutdown cleanup is not confirmed: "
                    f"host={host_cleanup.status.value}, "
                    f"managed_devices={managed_cleanup_error or 'confirmed'}, "
                    f"managed={stopped.status.value if stopped is not None else 'not_attempted'}"
                ),
            )
        status_publisher.publish(status_agent.snapshot())
        log(
            (
                OperationalLogLevel.INFO
                if host_cleanup.confirmed
                and managed_cleanup_error is None
                and stopped is not None
                and stopped.status is ControllerStopStatus.STOPPED
                else OperationalLogLevel.ERROR
            ),
            LIFE_LOG_TAG,
            "stop_complete",
            status=(
                stopped.status.value
                if stopped is not None
                else "managed_device_cleanup_failed"
            ),
            host_publication_cleanup=host_cleanup.status.value,
            host_publication_error=host_cleanup.diagnostic,
            managed_device_cleanup_error=managed_cleanup_error,
            cleanup_error=(
                stopped.cleanup_error if stopped is not None else None
            ),
            lock_error=(
                stopped.lock_error if stopped is not None else None
            ),
        )
        return (
            0
            if host_cleanup.confirmed
            and managed_cleanup_error is None
            and stopped is not None
            and stopped.status is ControllerStopStatus.STOPPED
            else 2
        )
    finally:
        if protective_service is not None:
            protective_service.stop()
        signal.signal(signal.SIGTERM, previous_sigterm)
        signal.signal(signal.SIGINT, previous_sigint)


def _parse_args(argv: Iterable[str] | None = None):
    parser = argparse.ArgumentParser(
        prog="vpn-gate-alpha",
        description="First executable NG3 alpha runtime assembly",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="canonical NG3 Release-1 Device/Profile TOML",
    )
    parser.add_argument(
        "--audit-interval",
        type=float,
        default=ALPHA_AUDIT_INTERVAL_SECONDS,
        help="local Manager audit interval in seconds (alpha implementation parameter)",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return run_alpha_runtime(
            args.config,
            audit_interval_seconds=args.audit_interval,
        )
    except Exception as exc:
        OperationalLogAdapter(OperationalLogLevel.INFO).emit(
            OperationalLogLevel.ERROR,
            LIFE_LOG_TAG,
            "fatal",
            diagnostic=f"{type(exc).__name__}: {exc}",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
