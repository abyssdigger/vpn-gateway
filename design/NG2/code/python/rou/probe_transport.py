from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from math import isfinite

from .availability_collector import AvailabilityGoodNews, AvailabilityTick
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
    channel_id: str
    mechanism: ProbeMechanism
    path: InterfaceIdentity
    target: IPv4Address
    interval_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.channel_id, str) or not self.channel_id:
            raise ValueError("logical probe channel requires non-empty channel_id")
        if not isinstance(self.mechanism, ProbeMechanism):
            raise ValueError("logical probe channel requires ProbeMechanism")
        if not isinstance(self.path, InterfaceIdentity):
            raise ValueError("logical probe channel requires InterfaceIdentity")
        if not isinstance(self.target, IPv4Address):
            raise ValueError("logical probe channel requires IPv4Address target")
        if (
            isinstance(self.interval_seconds, bool)
            or not isinstance(self.interval_seconds, (int, float))
            or not isfinite(float(self.interval_seconds))
            or self.interval_seconds <= 0
        ):
            raise ValueError(
                "logical probe channel interval must be positive"
            )


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

        channel_ids = []
        for item in self.channels:
            if not isinstance(item, LogicalProbeChannel):
                raise ValueError(
                    "execution plan channels must contain LogicalProbeChannel"
                )
            channel_ids.append(item.channel_id)
        if len(set(channel_ids)) != len(channel_ids):
            raise ValueError("execution plan contains duplicate logical channels")


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
            interval = float(probe.interval_seconds)
            previous = interval_by_plane.get(key)
            if previous is None or interval < previous:
                interval_by_plane[key] = interval

            channels.append(
                LogicalProbeChannel(
                    probe.channel_id,
                    probe.mechanism,
                    probe.path,
                    probe.target,
                    probe.interval_seconds,
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
            tuple(sorted(channels, key=lambda item: item.channel_id)),
        )
