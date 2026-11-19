"""One bounded Linux availability cycle after shared structural policy reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .availability_manager import AvailabilityManager
from .availability_observation_tick import (
    AvailabilityObservationTickResult,
    run_availability_observation_tick,
)
from .availability_route_priority import (
    AvailabilityRoutePriorityResult,
    converge_availability_route_priority_once,
)
from .iproute_priority_backend import CommandRunner
from .linux_probe_routing import LinuxProbeRoutingBackend
from .linux_structural_policy import LinuxStructuralPolicyBackend
from .network_policy_layout import NetworkPolicyPlatformSpace
from .payload_profile import PayloadProfileRequest
from .probe_attempt import ProbeAttemptDriver
from .probe_desired import ProbeDesiredAssembly
from .probe_precondition import (
    ProbeExecutionPrecondition,
    verify_probe_execution_precondition,
)
from .probe_routing_convergence import (
    ProbeRoutingTransactionResult,
    converge_probe_routing,
)
from .probe_runtime import AvailabilityProbeRuntime
from .release1_config import Release1Config
from .route_priority_inventory import RoutePriorityPathRoute


class LinuxAvailabilityCycleStatus(str, Enum):
    CONFIRMED = "confirmed"
    PROBE_ROUTING_UNCONFIRMED = "probe_routing_unconfirmed"
    PRECONDITION_UNCONFIRMED = "precondition_unconfirmed"
    PRIORITY_UNCONFIRMED = "priority_unconfirmed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LinuxAvailabilityCycleResult:
    status: LinuxAvailabilityCycleStatus
    probe_routing: ProbeRoutingTransactionResult | None = None
    precondition: ProbeExecutionPrecondition | None = None
    observation: AvailabilityObservationTickResult | None = None
    priority: AvailabilityRoutePriorityResult | None = None
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return self.status is LinuxAvailabilityCycleStatus.CONFIRMED


def run_linux_availability_cycle_once(
    config: Release1Config,
    baseline_profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
    assembly: ProbeDesiredAssembly,
    runtime: AvailabilityProbeRuntime,
    manager: AvailabilityManager,
    driver: ProbeAttemptDriver,
    *,
    runner: CommandRunner,
    namespace: str,
    platform: NetworkPolicyPlatformSpace,
) -> LinuxAvailabilityCycleResult:
    """Converge probe routing, observe readiness, probe once, then converge priority."""
    profiles = tuple(baseline_profiles)
    routes = tuple(path_routes)

    try:
        probe_routing = converge_probe_routing(
            LinuxProbeRoutingBackend(runner, namespace, platform),
            assembly.probe,
            platform,
        )
    except Exception as exc:
        return LinuxAvailabilityCycleResult(
            LinuxAvailabilityCycleStatus.FAILED,
            diagnostic=(
                "probe routing convergence failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if not probe_routing.confirmed:
        return LinuxAvailabilityCycleResult(
            LinuxAvailabilityCycleStatus.PROBE_ROUTING_UNCONFIRMED,
            probe_routing=probe_routing,
            diagnostic=probe_routing.diagnostic,
        )

    try:
        snapshot = LinuxStructuralPolicyBackend(
            runner=runner,
            namespace=namespace,
            platform=platform,
        ).observe_structural_snapshot()
        precondition = verify_probe_execution_precondition(
            snapshot,
            assembly.probe,
            platform,
        )
    except Exception as exc:
        return LinuxAvailabilityCycleResult(
            LinuxAvailabilityCycleStatus.FAILED,
            probe_routing=probe_routing,
            diagnostic=(
                "probe readiness observation failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    try:
        observation = run_availability_observation_tick(
            config,
            profiles,
            routes,
            assembly,
            precondition,
            runtime,
            manager,
            driver,
        )
    except Exception as exc:
        return LinuxAvailabilityCycleResult(
            LinuxAvailabilityCycleStatus.FAILED,
            probe_routing=probe_routing,
            precondition=precondition,
            diagnostic=(
                "availability observation tick failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if not precondition.confirmed:
        return LinuxAvailabilityCycleResult(
            LinuxAvailabilityCycleStatus.PRECONDITION_UNCONFIRMED,
            probe_routing=probe_routing,
            precondition=precondition,
            observation=observation,
            diagnostic=(
                "probe execution precondition is not exact; "
                "no remote availability failure was inferred"
            ),
        )

    try:
        priority = converge_availability_route_priority_once(
            observation.projection.effective_profiles,
            assembly.layout,
            routes,
            runner=runner,
            namespace=namespace,
        )
    except Exception as exc:
        return LinuxAvailabilityCycleResult(
            LinuxAvailabilityCycleStatus.FAILED,
            probe_routing=probe_routing,
            precondition=precondition,
            observation=observation,
            diagnostic=(
                "availability route-priority convergence failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if not priority.confirmed:
        return LinuxAvailabilityCycleResult(
            LinuxAvailabilityCycleStatus.PRIORITY_UNCONFIRMED,
            probe_routing=probe_routing,
            precondition=precondition,
            observation=observation,
            priority=priority,
            diagnostic="availability route-priority state is not confirmed",
        )

    return LinuxAvailabilityCycleResult(
        LinuxAvailabilityCycleStatus.CONFIRMED,
        probe_routing=probe_routing,
        precondition=precondition,
        observation=observation,
        priority=priority,
    )
