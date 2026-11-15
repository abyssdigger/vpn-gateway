from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from math import isfinite

from .availability_collector import AvailabilityChannelPolicy
from .availability_probe_state import ProbeObservationGeneration
from .interface_identity import InterfaceIdentity
from .probe_rules import (
    AvailabilityProbeSetRequest,
    ProbeMechanism,
)


@dataclass(frozen=True)
class PhysicalProbePlane:
    mechanism: ProbeMechanism
    path: InterfaceIdentity
    target: IPv4Address
    interval_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.mechanism, ProbeMechanism):
            raise ValueError("physical probe plane requires ProbeMechanism")
        if not isinstance(self.path, InterfaceIdentity):
            raise ValueError("physical probe plane requires InterfaceIdentity")
        if not isinstance(self.target, IPv4Address):
            raise ValueError("physical probe plane requires IPv4Address target")
        if (
            isinstance(self.interval_seconds, bool)
            or not isinstance(self.interval_seconds, (int, float))
            or not isfinite(float(self.interval_seconds))
            or self.interval_seconds <= 0
        ):
            raise ValueError("physical probe plane interval must be positive")


@dataclass(frozen=True)
class LogicalProbeChannel:
    probe_id: str
    mechanism: ProbeMechanism
    path: InterfaceIdentity
    target: IPv4Address
    policy: AvailabilityChannelPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.probe_id, str) or not self.probe_id:
            raise ValueError("logical probe channel requires non-empty probe_id")
        if not isinstance(self.mechanism, ProbeMechanism):
            raise ValueError("logical probe channel requires ProbeMechanism")
        if not isinstance(self.path, InterfaceIdentity):
            raise ValueError("logical probe channel requires InterfaceIdentity")
        if not isinstance(self.target, IPv4Address):
            raise ValueError("logical probe channel requires IPv4Address target")
        if not isinstance(self.policy, AvailabilityChannelPolicy):
            raise ValueError("logical probe channel requires AvailabilityChannelPolicy")


@dataclass(frozen=True)
class ProbeExecutionPlan:
    """Generation-bound physical-send and logical-tick demand."""

    generation: ProbeObservationGeneration
    planes: tuple[PhysicalProbePlane, ...]
    channels: tuple[LogicalProbeChannel, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.generation, ProbeObservationGeneration):
            raise ValueError("execution plan requires ProbeObservationGeneration")

        plane_keys = []
        for item in self.planes:
            if not isinstance(item, PhysicalProbePlane):
                raise ValueError(
                    "execution plan planes must contain PhysicalProbePlane"
                )
            plane_keys.append((item.mechanism, item.path, item.target))
        if len(set(plane_keys)) != len(plane_keys):
            raise ValueError("execution plan contains duplicate physical planes")

        probe_ids = []
        for item in self.channels:
            if not isinstance(item, LogicalProbeChannel):
                raise ValueError(
                    "execution plan channels must contain LogicalProbeChannel"
                )
            probe_ids.append(item.probe_id)
        if len(set(probe_ids)) != len(probe_ids):
            raise ValueError("execution plan contains duplicate logical channels")


@dataclass(frozen=True)
class ProbeGoodNewsInfo:
    probe_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.probe_id, str) or not self.probe_id:
            raise ValueError("good-news info requires non-empty probe_id")


@dataclass(frozen=True)
class ProbeTickInfo:
    probe_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.probe_id, str) or not self.probe_id:
            raise ValueError("tick info requires non-empty probe_id")


class ProbeExecutionPlanCalculator:
    """Pure projection from enabled logical probes to physical sends and ticks."""

    def calculate(
        self,
        request: AvailabilityProbeSetRequest,
        generation: ProbeObservationGeneration,
    ) -> ProbeExecutionPlan:
        if not isinstance(request, AvailabilityProbeSetRequest):
            raise ValueError("execution plan requires AvailabilityProbeSetRequest")
        if not isinstance(generation, ProbeObservationGeneration):
            raise ValueError("execution plan requires ProbeObservationGeneration")

        interval_by_plane: dict[
            tuple[ProbeMechanism, InterfaceIdentity, IPv4Address],
            float,
        ] = {}
        channels: list[LogicalProbeChannel] = []

        for probe in request.probes:
            if not probe.enabled:
                continue

            key = (probe.mechanism, probe.path, probe.target)
            interval = float(probe.policy.interval_seconds)
            previous = interval_by_plane.get(key)
            if previous is None or interval < previous:
                interval_by_plane[key] = interval

            channels.append(
                LogicalProbeChannel(
                    probe.probe_id,
                    probe.mechanism,
                    probe.path,
                    probe.target,
                    probe.policy,
                )
            )

        planes = tuple(
            PhysicalProbePlane(mechanism, path, target, interval)
            for (mechanism, path, target), interval in sorted(
                interval_by_plane.items(),
                key=lambda item: (
                    item[0][0].value,
                    item[0][1].ifname,
                    item[0][1].ifindex,
                    int(item[0][2]),
                ),
            )
        )
        return ProbeExecutionPlan(
            generation,
            planes,
            tuple(sorted(channels, key=lambda item: item.probe_id)),
        )
