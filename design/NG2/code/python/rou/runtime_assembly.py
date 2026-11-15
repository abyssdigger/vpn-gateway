from __future__ import annotations

from typing import Protocol

from .availability_collector import (
    AvailabilityGoodNews,
    AvailabilityPriorityChannel,
    AvailabilityPriorityConfig,
    AvailabilityTick,
    ProfileAvailabilityAssignment,
)
from .availability_probe_manager import AvailabilityProbeManager
from .payload_traffic_manager import PayloadTrafficManager
from .probe_rules import AvailabilityProbeSetRequest
from .probe_transport import ProbeExecutionPlan


class ProbePlanConsumer(Protocol):
    def update_plan(self, plan: ProbeExecutionPlan | None) -> None:
        ...


class AvailabilityPriorityConfigCalculator:
    """Project normalized logical probes onto the payload-priority boundary."""

    def calculate(
        self,
        probes: AvailabilityProbeSetRequest,
        assignments: tuple[ProfileAvailabilityAssignment, ...],
    ) -> AvailabilityPriorityConfig:
        if not isinstance(probes, AvailabilityProbeSetRequest):
            raise ValueError(
                "availability priority projection requires AvailabilityProbeSetRequest"
            )
        if any(
            not isinstance(item, ProfileAvailabilityAssignment)
            for item in assignments
        ):
            raise ValueError(
                "availability assignments must contain ProfileAvailabilityAssignment"
            )

        channels = tuple(
            AvailabilityPriorityChannel(
                probe.probe_id,
                probe.path,
                probe.enabled,
                probe.hysteresis,
            )
            for probe in probes.probes
        )
        return AvailabilityPriorityConfig(channels, assignments)


class ProbeExecutionPlanPort:
    """Typed synchronous publisher port from ProbeManager to ProbeExecutionAgent."""

    def __init__(self, consumer: ProbePlanConsumer) -> None:
        if not callable(getattr(consumer, "update_plan", None)):
            raise ValueError("probe plan consumer must expose update_plan")
        self._consumer = consumer

    def publish(self, plan: ProbeExecutionPlan | None) -> None:
        if plan is not None and not isinstance(plan, ProbeExecutionPlan):
            raise ValueError("probe plan port requires ProbeExecutionPlan or None")
        self._consumer.update_plan(plan)


class AvailabilityGoodNewsPort:
    """Typed publisher port from ProbeExecutionAgent to PayloadTrafficManager."""

    def __init__(self, manager: PayloadTrafficManager) -> None:
        if not isinstance(manager, PayloadTrafficManager):
            raise ValueError(
                "good-news port requires PayloadTrafficManager"
            )
        self._manager = manager

    def publish(self, info: AvailabilityGoodNews) -> None:
        self._manager.handle_availability_good_news(info)


class AvailabilityTickPort:
    """Typed publisher port from ProbeExecutionAgent to PayloadTrafficManager."""

    def __init__(self, manager: PayloadTrafficManager) -> None:
        if not isinstance(manager, PayloadTrafficManager):
            raise ValueError("tick port requires PayloadTrafficManager")
        self._manager = manager

    def publish(self, info: AvailabilityTick) -> None:
        self._manager.handle_availability_tick(info)


class AvailabilityConfigFanout:
    """Apply one normalized logical-probe snapshot to both owning Managers.

    Payload-priority configuration is installed first. The probe Manager is then allowed
    to publish a new execution plan whose outputs can immediately match the current
    payload-priority channel descriptors.

    This is ordered fanout, not a cross-Manager transaction. Before the probe Manager
    accepts the new request, its preceding probe demand is still the current demand.
    """

    def __init__(
        self,
        probe_manager: AvailabilityProbeManager,
        payload_manager: PayloadTrafficManager,
        *,
        priority_calculator: AvailabilityPriorityConfigCalculator | None = None,
    ) -> None:
        if not isinstance(probe_manager, AvailabilityProbeManager):
            raise ValueError(
                "availability fanout requires AvailabilityProbeManager"
            )
        if not isinstance(payload_manager, PayloadTrafficManager):
            raise ValueError(
                "availability fanout requires PayloadTrafficManager"
            )
        self._probe_manager = probe_manager
        self._payload_manager = payload_manager
        self._priority_calculator = (
            priority_calculator or AvailabilityPriorityConfigCalculator()
        )

    def apply(
        self,
        probes: AvailabilityProbeSetRequest,
        assignments: tuple[ProfileAvailabilityAssignment, ...],
    ) -> None:
        priority = self._priority_calculator.calculate(
            probes,
            assignments,
        )
        self._payload_manager.configure_availability(priority)
        self._probe_manager.handle_request(probes)
