from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from math import isfinite

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
class LogicalProbeWindow:
    probe_id: str
    interval_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.probe_id, str) or not self.probe_id:
            raise ValueError("logical probe window requires non-empty probe_id")
        if (
            isinstance(self.interval_seconds, bool)
            or not isinstance(self.interval_seconds, (int, float))
            or not isfinite(float(self.interval_seconds))
            or self.interval_seconds <= 0
        ):
            raise ValueError("logical probe window interval must be positive")


@dataclass(frozen=True)
class ProbeExecutionPlan:
    """Generation-bound transport/timer demand.

    Physical send cadence is deduplicated by probe plane. Logical observation-window
    cadence remains per probe_id because consumers sharing one plane may use different
    failure-window policy. This type does not prescribe whether the eventual lower
    execution subsystem is in-process or hidden behind an Adapter.
    """

    generation: ProbeObservationGeneration
    planes: tuple[PhysicalProbePlane, ...]
    windows: tuple[LogicalProbeWindow, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.generation, ProbeObservationGeneration):
            raise ValueError("execution plan requires ProbeObservationGeneration")
        for item in self.planes:
            if not isinstance(item, PhysicalProbePlane):
                raise ValueError(
                    "execution plan planes must contain PhysicalProbePlane"
                )
        plane_keys = [
            (item.mechanism, item.path, item.target)
            for item in self.planes
        ]
        if len(set(plane_keys)) != len(plane_keys):
            raise ValueError("execution plan contains duplicate physical planes")
        for item in self.windows:
            if not isinstance(item, LogicalProbeWindow):
                raise ValueError(
                    "execution plan windows must contain LogicalProbeWindow"
                )
        probe_ids = [item.probe_id for item in self.windows]
        if len(set(probe_ids)) != len(probe_ids):
            raise ValueError("execution plan contains duplicate logical windows")


@dataclass(frozen=True)
class ProbeGoodNewsInfo:
    mechanism: ProbeMechanism
    path: InterfaceIdentity
    target: IPv4Address
    generation: ProbeObservationGeneration

    def __post_init__(self) -> None:
        if not isinstance(self.mechanism, ProbeMechanism):
            raise ValueError("good-news info requires ProbeMechanism")
        if not isinstance(self.path, InterfaceIdentity):
            raise ValueError("good-news info requires InterfaceIdentity")
        if not isinstance(self.target, IPv4Address):
            raise ValueError("good-news info requires IPv4Address target")
        if not isinstance(self.generation, ProbeObservationGeneration):
            raise ValueError("good-news info requires ProbeObservationGeneration")


@dataclass(frozen=True)
class ProbeWindowBoundaryInfo:
    probe_id: str
    generation: ProbeObservationGeneration
    elapsed_intervals: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.probe_id, str) or not self.probe_id:
            raise ValueError("window-boundary info requires non-empty probe_id")
        if not isinstance(self.generation, ProbeObservationGeneration):
            raise ValueError("window-boundary info requires ProbeObservationGeneration")
        if type(self.elapsed_intervals) is not int or self.elapsed_intervals <= 0:
            raise ValueError("window-boundary elapsed_intervals must be positive")


class ProbeExecutionPlanCalculator:
    """Pure projection from logical probes + READY generation to execution demand."""

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
        windows: list[LogicalProbeWindow] = []

        for probe in request.probes:
            if not probe.enabled:
                continue
            key = (probe.mechanism, probe.path, probe.target)
            interval = float(probe.policy.interval_seconds)
            previous = interval_by_plane.get(key)
            if previous is None or interval < previous:
                interval_by_plane[key] = interval
            windows.append(LogicalProbeWindow(probe.probe_id, interval))

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
            tuple(sorted(windows, key=lambda item: item.probe_id)),
        )
