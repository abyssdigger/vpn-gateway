"""Bounded NG3 controller startup orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .forwarding_gate import (
    ForwardingGateExecutionResult,
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
from .interface_inventory import parse_ip_link_inventory
from .linux_forwarding_gate import LinuxForwardingGateBackend
from .linux_nft_scaffold import (
    LinuxNftScaffoldBackend,
    NftScriptRunner,
)
from .linux_structural_policy import LinuxStructuralPolicyBackend
from .managed_network_domain import (
    ManagedNetworkDomainEnsureResult,
    ManagedNetworkDomainPreflightResult,
    ManagedNetworkDomainSpec,
    ensure_managed_network_domain,
    preflight_managed_network_domain,
)
from .network_policy_activation import (
    NetworkPolicyActivationResult,
    NetworkPolicyActivationStatus,
    activate_network_policy,
)
from .network_policy_layout import NetworkPolicyPlatformSpace
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
    ACTIVATION_FAILED = "activation_failed"
    FAILURE_CONTAINMENT_FAILED = "failure_containment_failed"


@dataclass(slots=True)
class ControllerStartupSession:
    lock: ControllerInstanceLock
    preflight: ManagedNetworkDomainPreflightResult
    domain: ManagedNetworkDomainEnsureResult
    interfaces: tuple[InterfaceIdentity, ...]
    desired: PayloadNetworkPolicyDesiredState
    activation: NetworkPolicyActivationResult

    def __post_init__(self) -> None:
        if not self.lock.acquired:
            raise ValueError("startup session requires an acquired lifetime lock")
        if not self.preflight.confirmed:
            raise ValueError("startup session requires confirmed domain preflight")
        if not self.domain.confirmed:
            raise ValueError("startup session requires confirmed managed domain")
        if not self.activation.ready:
            raise ValueError("startup session requires READY network-policy activation")


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
    preflight: ManagedNetworkDomainPreflightResult | None = None
    domain: ManagedNetworkDomainEnsureResult | None = None
    activation: NetworkPolicyActivationResult | None = None
    failure_containment: ForwardingGateExecutionResult | None = None
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

    preflight: ManagedNetworkDomainPreflightResult | None = None
    domain: ManagedNetworkDomainEnsureResult | None = None

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
        )
        if stopped.stopped:
            return ControllerStartupResult(
                status=ControllerStartupStatus.STOPPED,
                session=None,
                preflight=preflight,
                domain=domain,
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
            preflight=preflight,
            domain=domain,
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
        containment: ForwardingGateExecutionResult | None = None,
        failure_status: ControllerStartupStatus | None = None,
    ) -> ControllerStartupResult:
        lock.release()
        return ControllerStartupResult(
            status=status,
            session=None,
            preflight=preflight,
            domain=domain,
            activation=activation,
            failure_containment=containment,
            failure_status=failure_status,
            diagnostic=diagnostic,
        )

    try:
        preflight = preflight_managed_network_domain(
            domain_spec,
            runner,
        )
    except Exception as exc:
        return fail(
            ControllerStartupStatus.DOMAIN_PREFLIGHT_FAILED,
            "managed-domain startup preflight failed: "
            f"{type(exc).__name__}: {exc}",
        )

    interrupted = interrupted_stop("managed-domain preflight")
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
        domain = ensure_managed_network_domain(
            domain_spec,
            runner,
        )
    except Exception as exc:
        return fail(
            ControllerStartupStatus.DOMAIN_ENSURE_FAILED,
            "managed-domain ensure failed: "
            f"{type(exc).__name__}: {exc}",
        )

    interrupted = interrupted_stop("managed-domain ensure")
    if interrupted is not None:
        return interrupted

    host_boundary = domain.verification.host_boundary
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
        interfaces = parse_ip_link_inventory(
            runner.run(
                (
                    "ip", "-n", domain_spec.namespace,
                    "-j", "link", "show",
                )
            )
        )
        if host_boundary not in interfaces:
            raise ValueError(
                "fresh managed-domain interface inventory does not contain "
                "the verified host-boundary generation"
            )
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

    gate = LinuxForwardingGateBackend(
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
    )

    if not activation.ready:
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
            preflight=interrupted.preflight,
            domain=interrupted.domain,
            activation=activation,
            stop=interrupted.stop,
            stopping=interrupted.stopping,
            diagnostic=interrupted.diagnostic,
        )

    session = ControllerStartupSession(
        lock=lock,
        preflight=preflight,
        domain=domain,
        interfaces=interfaces,
        desired=desired,
        activation=activation,
    )
    return ControllerStartupResult(
        status=ControllerStartupStatus.READY,
        session=session,
        preflight=preflight,
        domain=domain,
        activation=activation,
        diagnostic=activation.diagnostic,
    )


def _contain(
    domain_spec: ManagedNetworkDomainSpec,
    runner: NftScriptRunner,
) -> ForwardingGateExecutionResult:
    return converge_forwarding_gate_once(
        LinuxForwardingGateBackend(
            runner,
            domain_spec.namespace,
        ),
        ForwardingGateState.DISABLED,
    )
