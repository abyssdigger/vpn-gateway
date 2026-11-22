"""First executable NG3 alpha runtime assembly.

Architecture: structured Annex A A.001 ProductLifecycleControl and
Annex E E.001 HostPublicationAdapter runtime composition.
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
from dataclasses import dataclass, field
from enum import Enum
from ipaddress import IPv4Address, IPv4Interface
import os
from pathlib import Path
import signal
import socket
import sys
import threading
from typing import Iterable

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
    run_linux_availability_cycle_once,
)
from .linux_forwarding_gate import LinuxForwardingGateDriver
from .linux_vpn_path_adapter import LinuxVpnPathAdapter
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
from .network_policy_activation import (
    LOG_TAG as POLICY_LOG_TAG,
    NetworkPolicyActivationResult,
    activate_network_policy,
)
from .payload_network_policy_desired import (
    PayloadNetworkPolicyDesiredState,
    build_payload_network_policy_desired_state,
)
from .payload_profile import (
    LOG_TAG as PROF_LOG_TAG,
    PayloadProfileRequest,
    build_payload_profile_requests,
)
from .payload_nat_desired import ProfileSnatPolicyIntent
from .probe_desired import ProbeDesiredAssembly, build_probe_desired_assembly
from .probe_runtime import AvailabilityProbeRuntime
from .route_priority_inventory import RoutePriorityPathRoute
from .release1_config import Release1Config, parse_release1_config
from .operational_log import OperationalLogAdapter, OperationalLogLevel
from .release1_host_route_helper import (
    LOG_TAG as HOST_LOG_TAG,
    LinuxPeacefulHostRoutingContribution,
    build_linux_peaceful_host_routing_contribution,
    helper_routing_uses_external_ingress,
    validate_release1_helper_routing_scope,
)
from .structural_policy_mutation import compare_structural_policy
from .stack_return_affinity_convergence import StackReturnAffinityOwnerStatus
from .runtime_status import (
    RuntimeReadiness,
    RuntimeStatusAgent,
    RuntimeStatusFilePublisher,
    build_configured_intent_status,
)


ALPHA_NAMESPACE = "vpn-gate-alpha"
ALPHA_HOST_INTERFACE = "vnga-host0"
ALPHA_INNER_INTERFACE = "vnga-inner0"
ALPHA_INNER_ADDRESS = IPv4Interface("198.19.255.2/32")
ALPHA_RUNTIME_DIRECTORY = Path("/run/vpn-gate-alpha")
ALPHA_STATUS_PATH = ALPHA_RUNTIME_DIRECTORY / "status.json"
ALPHA_STATUS_TEXT_PATH = ALPHA_RUNTIME_DIRECTORY / "status.txt"
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
    config: Release1Config
    last_bindings: tuple[PathBinding, ...] = ()
    last_baseline_profiles: tuple[PayloadProfileRequest, ...] = ()
    last_profiles: tuple[PayloadProfileRequest, ...] = ()
    last_path_routes: tuple[RoutePriorityPathRoute, ...] = ()
    last_probe_assembly: ProbeDesiredAssembly | None = None
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

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        local_address: IPv4Address,
    ) -> "AlphaPreparedPolicy":
        config = parse_release1_config(text)

        prepared = cls(
            local_address=local_address,
            binding_state=DeviceBindingState.empty(),
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

    def build_current(
        self,
        host_boundary: InterfaceIdentity,
        interfaces: tuple[InterfaceIdentity, ...],
    ) -> PayloadNetworkPolicyDesiredState:
        projection = project_device_bindings(
            self.config.structural.device_binding_intents,
            self.binding_state,
            interfaces,
        )
        self.binding_state = projection.next_state

        profiles = build_payload_profile_requests(
            self.config.structural.profiles.values(),
            projection.bindings,
        )
        path_routes = realize_direct_device_path_routes(projection.bindings)
        probe_assembly = build_probe_desired_assembly(
            self.config,
            profiles,
            path_routes,
            NG3_LINUX_POLICY_PLATFORM,
            NG3_PROBE_LOCAL_PLATFORM,
        )
        layout = probe_assembly.layout
        self.availability_runtime.configure(
            probe_assembly.intents,
            path_routes,
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
        interfaces = LinuxVpnPathAdapter(
            runner,
            domain_spec.namespace,
        ).observe_interfaces(
            required_host_boundary=host_boundary,
        ).interfaces
        desired = prepared.build_current(
            host_boundary,
            interfaces,
        )
        host_publication_desired = prepared.build_host_publication_desired()
    except Exception as exc:
        return AlphaReconcileResult(
            AlphaReconcileStatus.FAILED,
            None,
            diagnostic=f"desired-state rebuild failed: {type(exc).__name__}: {exc}",
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


def reconcile_alpha_availability_once(
    prepared: AlphaPreparedPolicy,
    runner: SubprocessNftRunner,
    probe_driver: LinuxIcmpProbeDriver,
) -> LinuxAvailabilityCycleResult:
    if prepared.last_probe_assembly is None:
        raise AlphaRuntimeError(
            "availability cycle requires a current probe desired assembly"
        )
    result = run_linux_availability_cycle_once(
        prepared.config,
        prepared.last_baseline_profiles,
        prepared.last_path_routes,
        prepared.last_probe_assembly,
        prepared.availability_runtime,
        prepared.availability_manager,
        probe_driver,
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

    runner = SubprocessNftRunner()
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
            build_configured_intent_status(prepared.config)
        )
        status_publisher = RuntimeStatusFilePublisher(
            ALPHA_STATUS_PATH,
            ALPHA_STATUS_TEXT_PATH,
        )
        status_publisher.publish(status_agent.snapshot())

        availability_start = reconcile_alpha_availability_once(
            prepared,
            runner,
            probe_driver,
        )
        if not availability_start.confirmed:
            stopped = stop_controller_once(
                startup.session,
                domain_spec,
                runner,
            )
            status_agent.mark_unconfirmed(
                readiness=RuntimeReadiness.FAILED,
                problem=(
                    availability_start.diagnostic
                    or (
                        "availability startup cycle is not confirmed: "
                        f"{availability_start.status.value}"
                    )
                ),
            )
            status_publisher.publish(status_agent.snapshot())
            log(
                OperationalLogLevel.ERROR,
                LIFE_LOG_TAG,
                "start_failed",
                status="availability_unready",
                availability=availability_start.status.value,
                diagnostic=availability_start.diagnostic,
                managed_cleanup=stopped.status.value,
            )
            return (
                1
                if stopped.status is ControllerStopStatus.STOPPED
                else 2
            )

        host_publication_desired = prepared.build_host_publication_desired()
        host_publication_adapter = HostPublicationAdapter(
            LinuxHostPublicationDriver(runner)
        )
        host_start = host_publication_adapter.apply(host_publication_desired)
        if not host_start.confirmed:
            host_cleanup = host_publication_adapter.cleanup()
            stopped = stop_controller_once(
                startup.session,
                domain_spec,
                runner,
            )
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
                managed_cleanup=stopped.status.value,
            )
            return (
                1
                if host_cleanup.confirmed
                and stopped.status is ControllerStopStatus.STOPPED
                else 2
            )

        status_agent.confirm_effective(
            prepared.last_profiles,
            prepared.last_bindings,
        )
        if availability_start.observation is not None:
            status_agent.confirm_availability(
                availability_start.observation.projection.problem_owners
            )
        status_publisher.publish(status_agent.snapshot())
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
            result = reconcile_alpha_payload_once(
                prepared,
                domain_spec,
                runner,
            )
            availability_result = (
                reconcile_alpha_availability_once(
                    prepared,
                    runner,
                    probe_driver,
                )
                if result.ready
                else None
            )
            if (
                result.ready
                and availability_result is not None
                and availability_result.confirmed
            ):
                status_agent.confirm_effective(
                    prepared.last_profiles,
                    prepared.last_bindings,
                )
                if availability_result.observation is not None:
                    status_agent.confirm_availability(
                        availability_result.observation.projection.problem_owners
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
            if (
                result.status is not last_status
                or result.diagnostic != last_diagnostic
            ):
                log(
                    (
                        OperationalLogLevel.ERROR
                        if result.status is AlphaReconcileStatus.FAILED
                        else OperationalLogLevel.DEBUG
                    ),
                    POLICY_LOG_TAG,
                    (
                        "reconcile_failed"
                        if result.status is AlphaReconcileStatus.FAILED
                        else "reconcile_result_changed"
                    ),
                    status=result.status.value,
                    diagnostic=result.diagnostic,
                )
                _notify_systemd(
                    f"STATUS=VPN-GATE alpha reconcile {result.status.value}"
                )
                last_status = result.status
                last_diagnostic = result.diagnostic

        status_agent.mark_stopping()
        status_publisher.publish(status_agent.snapshot())
        _notify_systemd("STOPPING=1\nSTATUS=VPN-GATE alpha stopping")
        host_cleanup = HostPublicationAdapter(
            LinuxHostPublicationDriver(runner)
        ).cleanup()
        stopped = stop_controller_once(
            startup.session,
            domain_spec,
            runner,
        )
        if (
            host_cleanup.confirmed
            and stopped.status is ControllerStopStatus.STOPPED
        ):
            status_agent.mark_stopped()
        else:
            status_agent.mark_unconfirmed(
                readiness=RuntimeReadiness.FAILED,
                problem=(
                    "shutdown cleanup is not confirmed: "
                    f"host={host_cleanup.status.value}, "
                    f"managed={stopped.status.value}"
                ),
            )
        status_publisher.publish(status_agent.snapshot())
        log(
            (
                OperationalLogLevel.INFO
                if host_cleanup.confirmed
                and stopped.status is ControllerStopStatus.STOPPED
                else OperationalLogLevel.ERROR
            ),
            LIFE_LOG_TAG,
            "stop_complete",
            status=stopped.status.value,
            host_publication_cleanup=host_cleanup.status.value,
            host_publication_error=host_cleanup.diagnostic,
            cleanup_error=stopped.cleanup_error,
            lock_error=stopped.lock_error,
        )
        return (
            0
            if host_cleanup.confirmed
            and stopped.status is ControllerStopStatus.STOPPED
            else 2
        )
    finally:
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
