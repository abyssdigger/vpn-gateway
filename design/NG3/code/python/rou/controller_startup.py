"""Bounded NG3 controller startup orchestration.

Architecture: structured Annex A A.001 ProductLifecycleControl composing
B.001 ManagedL3BoundaryLifecycle and C.007/C.009 Private-network lifecycle APIs.
Requirement traceability: VPNG0005-R5.R1/R4/R5/R6, VPNG0004-R4.R6,
VPNG0007-R7.R3/R7.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .host_routing_contribution import HostRoutingContribution
from .forwarding_gate import (
    ForwardingGateEnforcementResult,
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .instance_lock import (
    ControllerInstanceBusyError,
    ControllerInstanceLock,
    ControllerInstanceLockError,
    InstanceLockSpec,
    acquire_controller_instance_lock,
)
from .interface_identity import InterfaceIdentity
from .linux_forwarding_gate import LinuxForwardingGateDriver
from .linux_vpn_path_adapter import LinuxVpnPathAdapter
from .linux_nft_scaffold import (
    LinuxNftScaffoldBackend,
    NftScriptRunner,
)
from .linux_structural_policy import LinuxStructuralPolicyBackend
from .linux_stack_return_affinity import LinuxStackReturnAffinityBackend
from .managed_network_domain import (
    ManagedL3BoundaryEnsureResult,
    ManagedNetworkDomainSpec,
    ManagedNetworkEnvironmentEnsureResult,
    OrdinarySidePortalVerification,
    ensure_managed_l3_boundary,
    ensure_managed_network_environment,
    ensure_ordinary_side_portal,
    preflight_managed_l3_boundary,
    preflight_managed_network_environment,
)
from .network_policy_activation import (
    NetworkPolicyActivationResult,
    NetworkPolicyActivationStatus,
    activate_network_policy,
)
from .network_policy_layout import NetworkPolicyPlatformSpace
from .stack_return_affinity import StackReturnAffinityPlatformSpace
from .payload_network_policy_desired import (
    PayloadNetworkPolicyDesiredState,
)
from .controller_stop import (
    ControllerStopResult,
    cleanup_controller_owned_domain_once,
)


class PreparedPayloadPolicy(Protocol):
    def build_current(
        self,
        host_boundary: InterfaceIdentity,
        interfaces: tuple[InterfaceIdentity, ...],
    ) -> PayloadNetworkPolicyDesiredState:
        """Build complete current lower desired state from fresh interface facts."""


class ValidatedPolicyLoader(Protocol):
    def __call__(self) -> PreparedPayloadPolicy:
        """Load/validate candidate config and return a pure current-state builder."""


class HostRoutingContributionBuilder(Protocol):
    def __call__(
        self,
        prepared: PreparedPayloadPolicy,
        domain_spec: ManagedNetworkDomainSpec,
    ) -> HostRoutingContribution | None:
        """Build one bounded optional host-routing contribution."""


class ControllerStopRequested(Protocol):
    def __call__(self) -> bool:
        """Return whether graceful stop has been requested; must not mutate network state."""


class ControllerStartupStatus(str, Enum):
    READY = "ready"
    STOPPED = "stopped"
    STOP_CLEANUP_FAILED = "stop_cleanup_failed"
    LOCK_BUSY = "lock_busy"
    LOCK_FAILED = "lock_failed"
    DOMAIN_PREFLIGHT_FAILED = "domain_preflight_failed"
    POLICY_LOAD_FAILED = "policy_load_failed"
    DOMAIN_ENSURE_FAILED = "domain_ensure_failed"
    INTERFACE_OBSERVATION_FAILED = "interface_observation_failed"
    DESIRED_BUILD_FAILED = "desired_build_failed"
    HOST_ROUTING_BUILD_FAILED = "boundary_build_failed"
    HOST_ROUTING_CONVERGENCE_FAILED = "boundary_convergence_failed"
    ACTIVATION_FAILED = "activation_failed"
    FAILURE_CONTAINMENT_FAILED = "failure_containment_failed"


@dataclass(slots=True)
class ControllerStartupSession:
    lock: ControllerInstanceLock
    environment: ManagedNetworkEnvironmentEnsureResult
    boundary: ManagedL3BoundaryEnsureResult
    portal: OrdinarySidePortalVerification
    interfaces: tuple[InterfaceIdentity, ...]
    desired: PayloadNetworkPolicyDesiredState
    activation: NetworkPolicyActivationResult
    host_routing_contribution: HostRoutingContribution | None = None

    def __post_init__(self) -> None:
        if not self.lock.acquired:
            raise ValueError("startup session requires an acquired lifetime lock")
        if not self.environment.confirmed:
            raise ValueError("startup session requires confirmed Private-network environment")
        if not self.boundary.confirmed:
            raise ValueError("startup session requires confirmed ordinary-side transition")
        if not self.portal.confirmed:
            raise ValueError("startup session requires confirmed ordinary-side portal")
        if not self.activation.ready:
            raise ValueError("startup session requires confirmed network-policy activation")

@dataclass(slots=True)
class ControllerStartupStoppingContext:
    lock: ControllerInstanceLock
    stop: ControllerStopResult

    def __post_init__(self) -> None:
        if self.stop.stopped:
            raise ValueError("stopping context requires incomplete stop cleanup")
        if not self.lock.acquired:
            raise ValueError("stopping context requires retained lifetime lock")


@dataclass(frozen=True, slots=True)
class ControllerStartupResult:
    status: ControllerStartupStatus
    session: ControllerStartupSession | None
    environment: ManagedNetworkEnvironmentEnsureResult | None = None
    boundary: ManagedL3BoundaryEnsureResult | None = None
    portal: OrdinarySidePortalVerification | None = None
    host_routing_contribution: HostRoutingContribution | None = None
    activation: NetworkPolicyActivationResult | None = None
    failure_containment: ForwardingGateEnforcementResult | None = None
    failure_status: ControllerStartupStatus | None = None
    stop: ControllerStopResult | None = None
    stopping: ControllerStartupStoppingContext | None = None
    diagnostic: str | None = None

    @property
    def ready(self) -> bool:
        return (
            self.status is ControllerStartupStatus.READY
            and self.session is not None
            and self.session.lock.acquired
            and self.session.activation.ready
        )

    @property
    def stopped(self) -> bool:
        return (
            self.status is ControllerStartupStatus.STOPPED
            and self.session is None
            and self.stopping is None
        )


def _never_stop_requested() -> bool:
    return False


def start_controller_once(
    lock_spec: InstanceLockSpec,
    domain_spec: ManagedNetworkDomainSpec,
    runner: NftScriptRunner,
    platform: NetworkPolicyPlatformSpace,
    load_validated_policy: ValidatedPolicyLoader,
    stop_requested: ControllerStopRequested | None = None,
    build_host_routing_contribution: HostRoutingContributionBuilder | None = None,
    stack_return_affinity_platform: StackReturnAffinityPlatformSpace | None = None,
) -> ControllerStartupResult:
    """Run one bounded startup attempt with phase-boundary graceful-stop checkpoints."""
    requested = stop_requested or _never_stop_requested

    if requested():
        return ControllerStartupResult(
            status=ControllerStartupStatus.STOPPED,
            session=None,
            diagnostic="stop requested before controller ownership",
        )

    try:
        lock = acquire_controller_instance_lock(lock_spec)
    except ControllerInstanceBusyError as exc:
        return ControllerStartupResult(
            status=ControllerStartupStatus.LOCK_BUSY,
            session=None,
            diagnostic=str(exc),
        )
    except ControllerInstanceLockError as exc:
        return ControllerStartupResult(
            status=ControllerStartupStatus.LOCK_FAILED,
            session=None,
            diagnostic=str(exc),
        )

    environment: ManagedNetworkEnvironmentEnsureResult | None = None
    boundary: ManagedL3BoundaryEnsureResult | None = None
    portal: OrdinarySidePortalVerification | None = None
    host_routing_contribution: HostRoutingContribution | None = None

    if requested():
        lock.release()
        return ControllerStartupResult(
            status=ControllerStartupStatus.STOPPED,
            session=None,
            diagnostic="stop requested after controller ownership and before managed-domain work",
        )

    def interrupted_stop(phase: str) -> ControllerStartupResult | None:
        if not requested():
            return None

        stopped = cleanup_controller_owned_domain_once(
            lock,
            domain_spec,
            runner,
            host_routing_contribution,
        )
        if stopped.stopped:
            return ControllerStartupResult(
                status=ControllerStartupStatus.STOPPED,
                session=None,
                environment=environment,
                boundary=boundary,
                portal=portal,
                stop=stopped,
                diagnostic=f"stop requested after {phase}; owned cleanup confirmed",
            )

        stopping = (
            ControllerStartupStoppingContext(
                lock=lock,
                stop=stopped,
            )
            if lock.acquired
            else None
        )
        return ControllerStartupResult(
            status=ControllerStartupStatus.STOP_CLEANUP_FAILED,
            session=None,
            environment=environment,
            boundary=boundary,
            portal=portal,
            stop=stopped,
            stopping=stopping,
            diagnostic=(
                f"stop requested after {phase}; "
                + (
                    "owned cleanup incomplete with lifetime lock retained"
                    if stopping is not None
                    else "owned cleanup completed but lifetime lock release failed"
                )
            ),
        )

    def fail(
        status: ControllerStartupStatus,
        diagnostic: str,
        *,
        activation: NetworkPolicyActivationResult | None = None,
        containment: ForwardingGateEnforcementResult | None = None,
        failure_status: ControllerStartupStatus | None = None,
        retain_lock: bool = False,
    ) -> ControllerStartupResult:
        if not retain_lock:
            lock.release()
        return ControllerStartupResult(
            status=status,
            session=None,
            environment=environment,
            boundary=boundary,
            portal=portal,
            host_routing_contribution=host_routing_contribution,
            activation=activation,
            failure_containment=containment,
            failure_status=failure_status,
            diagnostic=diagnostic,
        )

    try:
        preflight_managed_network_environment(domain_spec, runner)
        preflight_managed_l3_boundary(domain_spec, runner)
    except Exception as exc:
        return fail(
            ControllerStartupStatus.DOMAIN_PREFLIGHT_FAILED,
            "managed lifecycle startup preflight failed: "
            f"{type(exc).__name__}: {exc}",
        )

    interrupted = interrupted_stop("managed lifecycle preflight")
    if interrupted is not None:
        return interrupted

    try:
        prepared = load_validated_policy()
    except Exception as exc:
        return fail(
            ControllerStartupStatus.POLICY_LOAD_FAILED,
            "candidate policy load/validation failed: "
            f"{type(exc).__name__}: {exc}",
        )

    interrupted = interrupted_stop("candidate policy load/validation")
    if interrupted is not None:
        return interrupted

    try:
        environment = ensure_managed_network_environment(
            domain_spec,
            runner,
        )
    except Exception as exc:
        return fail(
            ControllerStartupStatus.DOMAIN_ENSURE_FAILED,
            "managed-network environment ensure failed: "
            f"{type(exc).__name__}: {exc}",
        )

    interrupted = interrupted_stop("managed-network environment ensure")
    if interrupted is not None:
        return interrupted

    try:
        boundary = ensure_managed_l3_boundary(
            domain_spec,
            runner,
        )
    except Exception as exc:
        return fail(
            ControllerStartupStatus.DOMAIN_ENSURE_FAILED,
            "ordinary-side transition ensure failed: "
            f"{type(exc).__name__}: {exc}",
        )

    interrupted = interrupted_stop("ordinary-side transition ensure")
    if interrupted is not None:
        return interrupted

    try:
        portal = ensure_ordinary_side_portal(
            domain_spec,
            runner,
        )
    except Exception as exc:
        return fail(
            ControllerStartupStatus.DOMAIN_ENSURE_FAILED,
            "ordinary-side portal ensure failed: "
            f"{type(exc).__name__}: {exc}",
        )

    host_boundary = boundary.verification.private_boundary

    interrupted = interrupted_stop("ordinary-side portal ensure")
    if interrupted is not None:
        return interrupted

    if host_boundary is None:
        containment = _contain(domain_spec, runner)
        status = (
            ControllerStartupStatus.INTERFACE_OBSERVATION_FAILED
            if containment.confirmed
            else ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED
        )
        return fail(
            status,
            "confirmed managed domain has no current host-boundary identity"
            + (
                ""
                if containment.confirmed
                else "; failure containment is not confirmed"
            ),
            containment=containment,
            failure_status=ControllerStartupStatus.INTERFACE_OBSERVATION_FAILED,
        )

    try:
        interfaces = LinuxVpnPathAdapter(
            runner,
            domain_spec.namespace,
        ).observe_interfaces(
            required_host_boundary=host_boundary,
        ).interfaces
    except Exception as exc:
        containment = _contain(domain_spec, runner)
        status = (
            ControllerStartupStatus.INTERFACE_OBSERVATION_FAILED
            if containment.confirmed
            else ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED
        )
        return fail(
            status,
            "fresh managed-domain interface observation failed: "
            f"{type(exc).__name__}: {exc}"
            + (
                ""
                if containment.confirmed
                else "; failure containment is not confirmed"
            ),
            containment=containment,
            failure_status=ControllerStartupStatus.INTERFACE_OBSERVATION_FAILED,
        )

    interrupted = interrupted_stop("fresh interface observation")
    if interrupted is not None:
        return interrupted

    try:
        desired = prepared.build_current(
            host_boundary,
            interfaces,
        )
        if not isinstance(desired, PayloadNetworkPolicyDesiredState):
            raise TypeError(
                "prepared policy must return PayloadNetworkPolicyDesiredState"
            )
    except Exception as exc:
        containment = _contain(domain_spec, runner)
        status = (
            ControllerStartupStatus.DESIRED_BUILD_FAILED
            if containment.confirmed
            else ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED
        )
        return fail(
            status,
            "current payload desired-state build failed: "
            f"{type(exc).__name__}: {exc}"
            + (
                ""
                if containment.confirmed
                else "; failure containment is not confirmed"
            ),
            containment=containment,
            failure_status=ControllerStartupStatus.DESIRED_BUILD_FAILED,
        )

    interrupted = interrupted_stop("desired-state build")
    if interrupted is not None:
        return interrupted

    if build_host_routing_contribution is not None:
        try:
            host_routing_contribution = build_host_routing_contribution(
                prepared,
                domain_spec,
            )
            if (
                host_routing_contribution is not None
                and not hasattr(host_routing_contribution, "converge")
            ):
                raise TypeError(
                    "host-routing contribution must implement converge()/cleanup()"
                )
        except Exception as exc:
            containment = _contain(domain_spec, runner)
            return fail(
                (
                    ControllerStartupStatus.HOST_ROUTING_BUILD_FAILED
                    if containment.confirmed
                    else ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED
                ),
                "host-routing contribution build failed: "
                f"{type(exc).__name__}: {exc}"
                + (
                    ""
                    if containment.confirmed
                    else "; failure containment is not confirmed"
                ),
                containment=containment,
                failure_status=ControllerStartupStatus.HOST_ROUTING_BUILD_FAILED,
            )

        if host_routing_contribution is not None:
            try:
                host_routing_contribution.converge()
            except Exception as exc:
                cleanup_error = None
                try:
                    host_routing_contribution.cleanup()
                except Exception as cleanup_exc:
                    cleanup_error = (
                        f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                    )
                containment = _contain(domain_spec, runner)
                failed_safe = containment.confirmed and cleanup_error is None
                return fail(
                    (
                        ControllerStartupStatus.HOST_ROUTING_CONVERGENCE_FAILED
                        if failed_safe
                        else ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED
                    ),
                    "host-routing contribution convergence failed: "
                    f"{type(exc).__name__}: {exc}"
                    + (
                        ""
                        if cleanup_error is None
                        else f"; boundary cleanup failed: {cleanup_error}"
                    )
                    + (
                        ""
                        if containment.confirmed
                        else "; failure containment is not confirmed"
                    ),
                    containment=containment,
                    failure_status=ControllerStartupStatus.HOST_ROUTING_CONVERGENCE_FAILED,
                    retain_lock=cleanup_error is not None,
                )

        interrupted = interrupted_stop("host-routing contribution convergence")
        if interrupted is not None:
            return interrupted

    gate = LinuxForwardingGateDriver(
        runner,
        domain_spec.namespace,
    )
    activation = activate_network_policy(
        gate,
        LinuxNftScaffoldBackend(
            runner,
            domain_spec.namespace,
        ),
        LinuxStructuralPolicyBackend(
            runner=runner,
            namespace=domain_spec.namespace,
            platform=platform,
        ),
        desired.routing,
        desired.nft,
        platform,
        (
            LinuxStackReturnAffinityBackend(
                runner,
                domain_spec.namespace,
                stack_return_affinity_platform,
            )
            if desired.stack_return_affinity is not None
            else None
        ),
        desired.stack_return_affinity,
    )

    if not activation.ready:
        boundary_cleanup_error = None
        if host_routing_contribution is not None:
            try:
                host_routing_contribution.cleanup()
            except Exception as exc:
                boundary_cleanup_error = f"{type(exc).__name__}: {exc}"
        if boundary_cleanup_error is not None:
            return fail(
                ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED,
                "network-policy activation failed and boundary cleanup failed: "
                f"{boundary_cleanup_error}"
                + (
                    f"; activation: {activation.diagnostic}"
                    if activation.diagnostic
                    else ""
                ),
                activation=activation,
                failure_status=ControllerStartupStatus.ACTIVATION_FAILED,
                retain_lock=True,
            )
        if (
            activation.status
            is NetworkPolicyActivationStatus.FAILURE_CONTAINMENT_FAILED
        ):
            return fail(
                ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED,
                "network-policy activation failed and containment is not confirmed"
                + (
                    f": {activation.diagnostic}"
                    if activation.diagnostic
                    else ""
                ),
                activation=activation,
                failure_status=ControllerStartupStatus.ACTIVATION_FAILED,
            )
        return fail(
            ControllerStartupStatus.ACTIVATION_FAILED,
            "network-policy activation failed"
            + (
                f": {activation.diagnostic}"
                if activation.diagnostic
                else ""
            ),
            activation=activation,
        )

    interrupted = interrupted_stop("network-policy activation")
    if interrupted is not None:
        return ControllerStartupResult(
            status=interrupted.status,
            session=None,
            environment=interrupted.environment,
            boundary=interrupted.boundary,
            portal=interrupted.portal,
            activation=activation,
            stop=interrupted.stop,
            stopping=interrupted.stopping,
            diagnostic=interrupted.diagnostic,
        )

    session = ControllerStartupSession(
        lock=lock,
        environment=environment,
        boundary=boundary,
        portal=portal,
        interfaces=interfaces,
        desired=desired,
        activation=activation,
        host_routing_contribution=host_routing_contribution,
    )
    return ControllerStartupResult(
        status=ControllerStartupStatus.READY,
        session=session,
        environment=environment,
        boundary=boundary,
        portal=portal,
        activation=activation,
        diagnostic=activation.diagnostic,
    )


def _contain(
    domain_spec: ManagedNetworkDomainSpec,
    runner: NftScriptRunner,
) -> ForwardingGateEnforcementResult:
    return converge_forwarding_gate_once(
        LinuxForwardingGateDriver(
            runner,
            domain_spec.namespace,
        ),
        ForwardingGateState.DISABLED,
    )
