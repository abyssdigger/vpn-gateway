"""One bounded Linux availability cycle after shared structural policy reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

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
from .network_policy_layout import NetworkPolicyPlatformSpace, ProbePolicyOwner
from .payload_profile import PayloadProfileRequest
from .probe_attempt import ProbeAttemptDriver
from .probe_desired import ProbeDesiredAssembly
from .probe_plane_desired import ProbePlaneDesiredAssembly
from .probe_precondition import (
    ProbeExecutionPrecondition,
    verify_probe_execution_precondition,
    verify_probe_execution_precondition_scoped,
)
from .probe_routing_convergence import (
    ProbeRoutingTransactionResult,
    converge_probe_routing,
)
from .probe_runtime import (
    AvailabilityProbeRuntime,
    ProbeOwnershipDependency,
)
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


class LinuxProbePlanePreparationStatus(str, Enum):
    CONFIRMED = "confirmed"
    PROBE_ROUTING_UNCONFIRMED = "probe_routing_unconfirmed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LinuxProbePlanePreparationResult:
    status: LinuxProbePlanePreparationStatus
    probe_routing: ProbeRoutingTransactionResult | None = None
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return self.status is LinuxProbePlanePreparationStatus.CONFIRMED


def prepare_linux_availability_probe_plane_once(
    assembly: ProbeDesiredAssembly | ProbePlaneDesiredAssembly,
    *,
    runner: CommandRunner,
    namespace: str,
    platform: NetworkPolicyPlatformSpace,
) -> LinuxProbePlanePreparationResult:
    """Converge and fresh-confirm the complete shared C.001 probe-routing plane."""
    try:
        probe_routing = converge_probe_routing(
            LinuxProbeRoutingBackend(runner, namespace, platform),
            assembly.probe,
            platform,
        )
    except Exception as exc:
        return LinuxProbePlanePreparationResult(
            LinuxProbePlanePreparationStatus.FAILED,
            diagnostic=(
                "probe routing convergence failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if not probe_routing.confirmed:
        return LinuxProbePlanePreparationResult(
            LinuxProbePlanePreparationStatus.PROBE_ROUTING_UNCONFIRMED,
            probe_routing=probe_routing,
            diagnostic=probe_routing.diagnostic,
        )

    return LinuxProbePlanePreparationResult(
        LinuxProbePlanePreparationStatus.CONFIRMED,
        probe_routing=probe_routing,
    )


def complete_linux_availability_cycle_once(
    config: Release1Config,
    baseline_profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
    assembly: ProbeDesiredAssembly | ProbePlaneDesiredAssembly,
    preparation: LinuxProbePlanePreparationResult,
    runtime: AvailabilityProbeRuntime,
    manager: AvailabilityManager,
    driver: ProbeAttemptDriver,
    *,
    ownership_dependencies: Mapping[
        ProbePolicyOwner,
        ProbeOwnershipDependency,
    ] | None = None,
    runner: CommandRunner,
    namespace: str,
    platform: NetworkPolicyPlatformSpace,
) -> LinuxAvailabilityCycleResult:
    """Fresh-observe A.007 after C.001 preparation and converge A.004 priority."""
    if not isinstance(preparation, LinuxProbePlanePreparationResult):
        raise TypeError(
            "preparation must be LinuxProbePlanePreparationResult"
        )

    probe_routing = preparation.probe_routing
    if not preparation.confirmed:
        if (
            preparation.status
            is LinuxProbePlanePreparationStatus.PROBE_ROUTING_UNCONFIRMED
        ):
            return LinuxAvailabilityCycleResult(
                LinuxAvailabilityCycleStatus.PROBE_ROUTING_UNCONFIRMED,
                probe_routing=probe_routing,
                diagnostic=preparation.diagnostic,
            )
        return LinuxAvailabilityCycleResult(
            LinuxAvailabilityCycleStatus.FAILED,
            probe_routing=probe_routing,
            diagnostic=preparation.diagnostic,
        )

    profiles = tuple(baseline_profiles)
    routes = tuple(path_routes)

    try:
        snapshot = LinuxStructuralPolicyBackend(
            runner=runner,
            namespace=namespace,
            platform=platform,
        ).observe_structural_snapshot()
        if isinstance(assembly, ProbePlaneDesiredAssembly):
            precondition = verify_probe_execution_precondition_scoped(
                snapshot,
                assembly.probe,
                frozenset(
                    intent.owner
                    for intent in assembly.availability_intents
                ),
                platform,
            )
        else:
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
            ownership_dependencies=ownership_dependencies,
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


def run_linux_availability_cycle_once(
    config: Release1Config,
    baseline_profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
    assembly: ProbeDesiredAssembly | ProbePlaneDesiredAssembly,
    runtime: AvailabilityProbeRuntime,
    manager: AvailabilityManager,
    driver: ProbeAttemptDriver,
    *,
    runner: CommandRunner,
    namespace: str,
    platform: NetworkPolicyPlatformSpace,
) -> LinuxAvailabilityCycleResult:
    """Legacy bounded wrapper for callers without a D.002 dependency."""
    preparation = prepare_linux_availability_probe_plane_once(
        assembly,
        runner=runner,
        namespace=namespace,
        platform=platform,
    )
    return complete_linux_availability_cycle_once(
        config,
        baseline_profiles,
        path_routes,
        assembly,
        preparation,
        runtime,
        manager,
        driver,
        runner=runner,
        namespace=namespace,
        platform=platform,
    )
