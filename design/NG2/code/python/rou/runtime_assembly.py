from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Address
from math import isfinite
from typing import Protocol

from .availability_collector import (
    AvailabilityGoodNews,
    AvailabilityHysteresisPolicy,
    AvailabilityPriorityChannel,
    AvailabilityPriorityConfig,
    AvailabilityTick,
    ProfileAvailabilityAssignment,
)
from .availability_probe_manager import AvailabilityProbeManager
from .interface_identity import InterfaceIdentity
from .payload_traffic_manager import PayloadTrafficManager
from .probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
    ProbeMechanism,
)
from .probe_transport import ProbeExecutionPlan


@dataclass(frozen=True)
class RuntimeAvailabilityChannel:
    """Normalized upstream availability channel before domain projection."""

    channel_id: str
    path: InterfaceIdentity
    target: IPv4Address
    mechanism: ProbeMechanism = ProbeMechanism.ICMP
    enabled: bool = True
    interval_seconds: float = field(kw_only=True)
    hysteresis: AvailabilityHysteresisPolicy = field(kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.channel_id, str) or not self.channel_id:
            raise ValueError("runtime availability channel_id must be non-empty")
        if not isinstance(self.path, InterfaceIdentity):
            raise ValueError(
                "runtime availability path must be InterfaceIdentity"
            )
        if not isinstance(self.target, IPv4Address):
            raise ValueError(
                "runtime availability target must be IPv4Address"
            )
        if not isinstance(self.mechanism, ProbeMechanism):
            raise ValueError(
                "runtime availability mechanism must be ProbeMechanism"
            )
        if type(self.enabled) is not bool:
            raise ValueError("runtime availability enabled must be boolean")
        if (
            isinstance(self.interval_seconds, bool)
            or not isinstance(self.interval_seconds, (int, float))
            or not isfinite(float(self.interval_seconds))
            or float(self.interval_seconds) <= 0
        ):
            raise ValueError(
                "runtime availability interval_seconds must be positive finite"
            )
        if not isinstance(self.hysteresis, AvailabilityHysteresisPolicy):
            raise ValueError(
                "runtime availability hysteresis must be "
                "AvailabilityHysteresisPolicy"
            )


@dataclass(frozen=True)
class RuntimeAvailabilityConfig:
    """Normalized current availability slice shared by independent projections."""

    channels: tuple[RuntimeAvailabilityChannel, ...]
    assignments: tuple[ProfileAvailabilityAssignment, ...]

    def __post_init__(self) -> None:
        ids = [item.channel_id for item in self.channels]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate runtime availability channel_id")

        profile_names = [item.profile_name for item in self.assignments]
        if len(set(profile_names)) != len(profile_names):
            raise ValueError(
                "duplicate runtime Profile availability assignment"
            )

        known = set(ids)
        for assignment in self.assignments:
            missing = set(assignment.channel_ids) - known
            if missing:
                raise ValueError(
                    f"Profile {assignment.profile_name!r} references "
                    "unknown runtime availability channel_id: "
                    + ", ".join(sorted(missing))
                )


class AvailabilityProbeSetCalculator:
    """Project normalized runtime availability into physical/logical probe demand."""

    def calculate(
        self,
        config: RuntimeAvailabilityConfig,
    ) -> AvailabilityProbeSetRequest:
        if not isinstance(config, RuntimeAvailabilityConfig):
            raise ValueError(
                "probe projection requires RuntimeAvailabilityConfig"
            )

        return AvailabilityProbeSetRequest(
            tuple(
                AvailabilityProbeRequest(
                    item.channel_id,
                    item.path,
                    item.target,
                    mechanism=item.mechanism,
                    enabled=item.enabled,
                    interval_seconds=item.interval_seconds,
                    hysteresis=item.hysteresis,
                )
                for item in config.channels
            )
        )


class AvailabilityPriorityConfigCalculator:
    """Project the same normalized slice onto payload-priority semantics."""

    def calculate(
        self,
        config: RuntimeAvailabilityConfig,
    ) -> AvailabilityPriorityConfig:
        if not isinstance(config, RuntimeAvailabilityConfig):
            raise ValueError(
                "availability priority projection requires "
                "RuntimeAvailabilityConfig"
            )

        return AvailabilityPriorityConfig(
            tuple(
                AvailabilityPriorityChannel(
                    item.channel_id,
                    item.path,
                    item.enabled,
                    item.hysteresis,
                )
                for item in config.channels
            ),
            config.assignments,
        )


class ProbePlanConsumer(Protocol):
    def update_plan(self, plan: ProbeExecutionPlan | None) -> None:
        ...


class ProbeExecutionPlanPort:
    """Synchronous publisher port from ProbeManager to ProbeExecutionAgent."""

    def __init__(self, consumer: ProbePlanConsumer) -> None:
        if not callable(getattr(consumer, "update_plan", None)):
            raise ValueError("probe plan consumer must expose update_plan")
        self._consumer = consumer

    def publish(self, plan: ProbeExecutionPlan | None) -> None:
        if plan is not None and not isinstance(plan, ProbeExecutionPlan):
            raise ValueError("probe plan port requires ProbeExecutionPlan or None")
        self._consumer.update_plan(plan)


class AvailabilityGoodNewsPort:
    """Publisher port from ProbeExecutionAgent to PayloadTrafficManager."""

    def __init__(self, manager: PayloadTrafficManager) -> None:
        if not isinstance(manager, PayloadTrafficManager):
            raise ValueError(
                "good-news port requires PayloadTrafficManager"
            )
        self._manager = manager

    def publish(self, info: AvailabilityGoodNews) -> None:
        self._manager.handle_availability_good_news(info)


class AvailabilityTickPort:
    """Publisher port from ProbeExecutionAgent to PayloadTrafficManager."""

    def __init__(self, manager: PayloadTrafficManager) -> None:
        if not isinstance(manager, PayloadTrafficManager):
            raise ValueError("tick port requires PayloadTrafficManager")
        self._manager = manager

    def publish(self, info: AvailabilityTick) -> None:
        self._manager.handle_availability_tick(info)


class AvailabilityConfigFanout:
    """Project one normalized slice independently into both owning Managers.

    Payload-priority configuration is installed first. The probe Manager is then allowed
    to publish a new execution plan whose outputs can immediately match the current
    payload-priority channel descriptors.

    This is ordered fanout, not a cross-Manager transaction. Before the probe Manager
    accepts the new request, its preceding probe demand remains the current demand.
    """

    def __init__(
        self,
        probe_manager: AvailabilityProbeManager,
        payload_manager: PayloadTrafficManager,
        *,
        probe_calculator: AvailabilityProbeSetCalculator | None = None,
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
        self._probe_calculator = (
            probe_calculator or AvailabilityProbeSetCalculator()
        )
        self._priority_calculator = (
            priority_calculator or AvailabilityPriorityConfigCalculator()
        )

    def apply(self, config: RuntimeAvailabilityConfig) -> None:
        priority = self._priority_calculator.calculate(config)
        probes = self._probe_calculator.calculate(config)

        self._payload_manager.configure_availability(priority)
        self._probe_manager.handle_request(probes)
