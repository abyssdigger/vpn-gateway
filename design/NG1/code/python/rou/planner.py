from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import Callable, Mapping

from .command_backend import CommandBackend, NamespaceBackend
from .device_engine import (
    DeviceBindingSnapshot,
    DeviceBindingState,
    InterfaceIdentity,
    reconcile_devices,
)
from .domain import ActiveConfig, Availability
from .environment import EnvironmentSnapshot, collect_environment_snapshot
from .firewall_kernel import apply_filter_state, verify_filter_state
from .firewall_state import FirewallDesiredState, compile_filter_state
from .kernel_allocation import KernelAllocation, compile_kernel_allocation
from .kernel_mutation import compile_kernel_mutation_plan
from .kernel_state import (
    KernelDesiredState,
    compile_kernel_desired_state,
    verify_kernel_desired_state,
)
from .command_backend import execute_kernel_mutation_plan
from .namespace_prereq import (
    apply_namespace_prerequisites,
    verify_namespace_prerequisites,
)
from .nat_kernel import apply_nat_state, verify_nat_state
from .nat_state import NatDesiredState, NatProvider
from .traffic_state import (
    TrafficProjection,
    TrafficRuntimeState,
    committed_state_from_verified,
    project_normal_metrics,
)


class PlannerError(RuntimeError):
    pass


class PlannerRetryRequired(PlannerError):
    pass


class PlannerVerificationError(PlannerError):
    pass


@dataclass(frozen=True)
class PlannerRuntimeState:
    devices: DeviceBindingState
    traffic: TrafficRuntimeState

    @classmethod
    def empty(cls) -> "PlannerRuntimeState":
        return cls(DeviceBindingState.empty(), TrafficRuntimeState.empty())


@dataclass(frozen=True)
class PlannerProjection:
    device_state: DeviceBindingState
    bindings: DeviceBindingSnapshot
    metrics: TrafficProjection
    allocation: KernelAllocation
    kernel: KernelDesiredState
    firewall: FirewallDesiredState
    nat: NatDesiredState


@dataclass(frozen=True)
class PlannerResult:
    state: PlannerRuntimeState
    projection: PlannerProjection
    changed_kernel: bool
    needs_immediate_reconcile: bool


SnapshotCollector = Callable[[str, CommandBackend], EnvironmentSnapshot]
AvailabilityProvider = Callable[
    [EnvironmentSnapshot],
    Mapping[InterfaceIdentity, Availability],
]
VerifiedStatePersister = Callable[[PlannerRuntimeState], None]


def default_snapshot_collector(
    namespace: str,
    host_backend: CommandBackend,
) -> EnvironmentSnapshot:
    return collect_environment_snapshot(
        namespace,
        lambda argv: host_backend.run(argv).stdout,
    )


def _project(
    config: ActiveConfig,
    committed: PlannerRuntimeState,
    snapshot: EnvironmentSnapshot,
    nat_provider: NatProvider,
    availability_provider: AvailabilityProvider | None,
    local_publication_address: IPv4Address | None,
) -> PlannerProjection:
    availability = (
        availability_provider(snapshot)
        if availability_provider is not None
        else {}
    )
    devices = reconcile_devices(
        config,
        committed.devices,
        snapshot.interfaces,
        availability,
    )
    metrics = project_normal_metrics(
        config,
        devices.snapshot,
        committed.traffic,
    )
    allocation = compile_kernel_allocation(config)
    kernel = compile_kernel_desired_state(
        config,
        devices.snapshot,
        metrics,
        allocation,
    )
    firewall = compile_filter_state(
        config,
        devices.snapshot,
        local_publication_address=local_publication_address,
    )
    nat = nat_provider.compile(config, devices.snapshot)
    return PlannerProjection(
        device_state=devices.next_state,
        bindings=devices.snapshot,
        metrics=metrics,
        allocation=allocation,
        kernel=kernel,
        firewall=firewall,
        nat=nat,
    )


def _best_effort_close(backend: NamespaceBackend) -> None:
    try:
        backend.run(
            ("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"),
            check=False,
        )
    except Exception:
        pass


def _verify_all(
    projection: PlannerProjection,
    snapshot: EnvironmentSnapshot,
    backend: NamespaceBackend,
    *,
    forwarding: bool,
) -> tuple[str, ...]:
    errors: list[str] = []

    kernel = verify_kernel_desired_state(projection.kernel, snapshot)
    errors.extend(kernel.errors)

    prereq = verify_namespace_prerequisites(
        snapshot,
        projection.bindings,
        forwarding=forwarding,
    )
    errors.extend(prereq.errors)

    firewall = verify_filter_state(projection.firewall, backend)
    if not firewall.ok:
        errors.append("filter table mismatch")

    nat = verify_nat_state(projection.nat, backend)
    if not nat.ok:
        errors.append("nat table mismatch")

    return tuple(errors)


def _commit(projection: PlannerProjection) -> PlannerRuntimeState:
    return PlannerRuntimeState(
        devices=projection.device_state,
        traffic=committed_state_from_verified(projection.metrics),
    )


def reconcile_once(
    config: ActiveConfig,
    namespace: str,
    committed: PlannerRuntimeState,
    host_backend: CommandBackend,
    nat_provider: NatProvider,
    *,
    availability_provider: AvailabilityProvider | None = None,
    collect_snapshot: SnapshotCollector = default_snapshot_collector,
    persist_verified_state: VerifiedStatePersister | None = None,
    local_publication_address: IPv4Address | None = None,
) -> PlannerResult:
    """Run one complete observe->plan->apply->observe->verify->commit cycle.

    Interface churn during a barriered transition is not hidden by retries inside this
    function. It returns PlannerRetryRequired with forwarding left closed; the outer event
    loop can immediately reconcile again from a fresh snapshot.

    When a persistence callback is supplied, verified runtime history is durably recorded
    before forwarding is opened. Persistence failure is therefore fail-closed and prevents
    exposure of kernel state whose stable metric/binding history was not committed.
    """

    ns = NamespaceBackend(namespace, host_backend)

    try:
        initial = collect_snapshot(namespace, host_backend)
        projection = _project(
            config,
            committed,
            initial,
            nat_provider,
            availability_provider,
            local_publication_address,
        )

        current_errors_open = _verify_all(
            projection,
            initial,
            ns,
            forwarding=True,
        )
        if not current_errors_open:
            next_state = _commit(projection)
            if persist_verified_state is not None:
                persist_verified_state(next_state)
            return PlannerResult(
                state=next_state,
                projection=projection,
                changed_kernel=False,
                needs_immediate_reconcile=bool(projection.metrics.waiting_for_slot),
            )

        # Crash/restart recovery: complete state may already be correct with forwarding
        # intentionally closed. Reopen only after proving that exact condition.
        current_errors_closed = _verify_all(
            projection,
            initial,
            ns,
            forwarding=False,
        )
        if not current_errors_closed:
            next_state = _commit(projection)
            if persist_verified_state is not None:
                persist_verified_state(next_state)
            ns.run(("sysctl", "-q", "-w", "net.ipv4.ip_forward=1"))
            final = collect_snapshot(namespace, host_backend)
            if final.interfaces != initial.interfaces:
                _best_effort_close(ns)
                raise PlannerRetryRequired(
                    "interface set changed while reopening verified state"
                )
            final_errors = _verify_all(
                projection,
                final,
                ns,
                forwarding=True,
            )
            if final_errors:
                _best_effort_close(ns)
                raise PlannerVerificationError(
                    "post-reopen verification failed: " + "; ".join(final_errors)
                )
            return PlannerResult(
                state=next_state,
                projection=projection,
                changed_kernel=True,
                needs_immediate_reconcile=bool(projection.metrics.waiting_for_slot),
            )

        # From this point on, all structural repair runs behind a closed barrier.
        ns.run(("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"))

        barrier_snapshot = collect_snapshot(namespace, host_backend)
        barrier_projection = _project(
            config,
            committed,
            barrier_snapshot,
            nat_provider,
            availability_provider,
            local_publication_address,
        )

        apply_namespace_prerequisites(
            barrier_projection.bindings,
            ns,
        )
        prepared = collect_snapshot(namespace, host_backend)
        if prepared.interfaces != barrier_snapshot.interfaces:
            raise PlannerRetryRequired(
                "interface set changed while preparing namespace prerequisites"
            )

        prereq = verify_namespace_prerequisites(
            prepared,
            barrier_projection.bindings,
            forwarding=False,
        )
        if not prereq.ok:
            raise PlannerVerificationError(
                "closed-barrier prerequisites failed: " + "; ".join(prereq.errors)
            )

        mutation_plan = compile_kernel_mutation_plan(
            barrier_projection.kernel,
            prepared,
        )
        execute_kernel_mutation_plan(mutation_plan, ns)
        apply_filter_state(barrier_projection.firewall, ns)
        apply_nat_state(barrier_projection.nat, ns)

        applied = collect_snapshot(namespace, host_backend)
        if applied.interfaces != barrier_snapshot.interfaces:
            raise PlannerRetryRequired(
                "interface set changed during kernel apply"
            )

        applied_errors = _verify_all(
            barrier_projection,
            applied,
            ns,
            forwarding=False,
        )
        if applied_errors:
            raise PlannerVerificationError(
                "closed-barrier verification failed: "
                + "; ".join(applied_errors)
            )

        next_state = _commit(barrier_projection)
        if persist_verified_state is not None:
            persist_verified_state(next_state)

        ns.run(("sysctl", "-q", "-w", "net.ipv4.ip_forward=1"))
        final = collect_snapshot(namespace, host_backend)
        if final.interfaces != barrier_snapshot.interfaces:
            _best_effort_close(ns)
            raise PlannerRetryRequired(
                "interface set changed while opening forwarding"
            )

        final_errors = _verify_all(
            barrier_projection,
            final,
            ns,
            forwarding=True,
        )
        if final_errors:
            _best_effort_close(ns)
            raise PlannerVerificationError(
                "final verification failed: " + "; ".join(final_errors)
            )

        return PlannerResult(
            state=next_state,
            projection=barrier_projection,
            changed_kernel=True,
            needs_immediate_reconcile=bool(
                barrier_projection.metrics.waiting_for_slot
            ),
        )

    except PlannerError:
        _best_effort_close(ns)
        raise
    except Exception as exc:
        _best_effort_close(ns)
        raise PlannerError(f"reconciliation failed: {exc}") from exc
