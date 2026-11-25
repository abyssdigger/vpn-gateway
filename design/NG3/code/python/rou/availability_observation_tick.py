"""One bounded availability observation tick over already-materialized probe policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .availability_manager import (
    AvailabilityManager,
    AvailabilityManagerProjection,
)
from .network_policy_layout import ProbePolicyOwner
from .payload_profile import PayloadProfileRequest
from .probe_attempt import ProbeAttemptDriver, execute_probe_attempt_once
from .probe_desired import ProbeDesiredAssembly
from .probe_plane_desired import ProbePlaneDesiredAssembly
from .probe_precondition import ProbeExecutionPrecondition
from .probe_runtime import (
    AvailabilityProbeRuntime,
    ProbeEvidence,
    ProbeOwnershipDependency,
)
from .release1_config import Release1Config
from .route_priority_inventory import RoutePriorityPathRoute


class AvailabilityObservationTickError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AvailabilityObservationTickResult:
    projection: AvailabilityManagerProjection
    evidence: tuple[ProbeEvidence, ...]
    attempts_enabled: bool


def run_availability_observation_tick(
    config: Release1Config,
    baseline_profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
    assembly: ProbeDesiredAssembly | ProbePlaneDesiredAssembly,
    precondition: ProbeExecutionPrecondition,
    runtime: AvailabilityProbeRuntime,
    manager: AvailabilityManager,
    driver: ProbeAttemptDriver,
    *,
    ownership_dependencies: Mapping[
        ProbePolicyOwner,
        ProbeOwnershipDependency,
    ] | None = None,
) -> AvailabilityObservationTickResult:
    """Run at most one probe attempt per current subject from one external wakeup.

    This function does not schedule itself, repair probe policy or converge route
    priority. It only consumes an exact readiness decision for the current desired
    probe plane and returns the resulting effective Profile order.
    """
    profiles = tuple(baseline_profiles)
    routes = tuple(path_routes)

    if not isinstance(
        assembly,
        (ProbeDesiredAssembly, ProbePlaneDesiredAssembly),
    ):
        raise AvailabilityObservationTickError(
            "assembly must be a supported probe desired assembly"
        )
    if not isinstance(precondition, ProbeExecutionPrecondition):
        raise AvailabilityObservationTickError(
            "precondition must be ProbeExecutionPrecondition"
        )
    if not isinstance(runtime, AvailabilityProbeRuntime):
        raise AvailabilityObservationTickError(
            "runtime must be AvailabilityProbeRuntime"
        )
    if not isinstance(manager, AvailabilityManager):
        raise AvailabilityObservationTickError(
            "manager must be AvailabilityManager"
        )

    availability_intents = (
        assembly.availability_intents
        if isinstance(assembly, ProbePlaneDesiredAssembly)
        else assembly.intents
    )
    runtime.configure(
        availability_intents,
        routes,
        ownership_dependencies,
    )
    projection = manager.synchronize(
        runtime.current_contexts,
        profiles,
        config,
    )

    if not precondition.confirmed:
        return AvailabilityObservationTickResult(
            projection=projection,
            evidence=(),
            attempts_enabled=False,
        )

    evidence: list[ProbeEvidence] = []
    for context in runtime.current_contexts:
        if not context.ownership_dependency.permits_remote_evidence:
            continue
        item = execute_probe_attempt_once(
            runtime,
            context.intent.owner,
            precondition,
            driver,
        )
        if item is None:
            continue
        evidence.append(item)
        projection = manager.apply_evidence(
            item,
            profiles,
            config,
        )

    return AvailabilityObservationTickResult(
        projection=projection,
        evidence=tuple(evidence),
        attempts_enabled=True,
    )
