from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .device_engine import DeviceBindingSnapshot, InterfaceIdentity
from .domain import ActiveConfig
from .metrics import compile_profile_metric_layout


@dataclass(frozen=True)
class TrafficRuntimeState:
    """Committed normal-slot history.

    This state changes only after applied traffic state has been freshly observed and
    verified. In particular, a removed interface's metric stays reserved until that
    removal has crossed the verify/commit boundary.
    """

    normal_metrics: Mapping[tuple[str, InterfaceIdentity], int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "normal_metrics", MappingProxyType(dict(self.normal_metrics)))

    @classmethod
    def empty(cls) -> "TrafficRuntimeState":
        return cls({})


@dataclass(frozen=True)
class MetricAssignment:
    profile_name: str
    device_name: str
    expected_index: int
    identity: InterfaceIdentity
    metric: int


@dataclass(frozen=True)
class TrafficProjection:
    assignments: tuple[MetricAssignment, ...]
    waiting_for_slot: tuple[tuple[str, InterfaceIdentity], ...]


def committed_state_from_verified(projection: TrafficProjection) -> TrafficRuntimeState:
    """Build the next committed history after complete desired state was verified."""

    return TrafficRuntimeState(
        {
            (assignment.profile_name, assignment.identity): assignment.metric
            for assignment in projection.assignments
        }
    )


def project_normal_metrics(
    config: ActiveConfig,
    bindings: DeviceBindingSnapshot,
    committed: TrafficRuntimeState,
) -> TrafficProjection:
    """Project stable normal-tier metrics without reusing uncommitted removals.

    Metrics belonging to committed-but-now-absent interfaces stay reserved during this
    projection. This forces route removal to be verified and committed before a later
    reconcile may reuse the slot.

    UNAVAILABLE fallback materialization is deliberately excluded pending EXP-013.
    """

    grouped: dict[tuple[str, int], list] = {}
    for binding in bindings.bound:
        grouped.setdefault((binding.device_name, binding.expected_index), []).append(binding)

    assignments: list[MetricAssignment] = []
    waiting: list[tuple[str, InterfaceIdentity]] = []
    assigned_keys: set[tuple[str, InterfaceIdentity]] = set()

    for profile in config.profiles.values():
        if not profile.enabled:
            continue

        for metric_range in compile_profile_metric_layout(config, profile):
            members = grouped.get((metric_range.device_name, metric_range.expected_index), [])
            reserved = {
                metric
                for (profile_name, _identity), metric in committed.normal_metrics.items()
                if profile_name == profile.name
                and metric_range.start <= metric <= metric_range.end
            }

            for binding in members:
                key = (profile.name, binding.identity)
                old_metric = committed.normal_metrics.get(key)
                if (
                    old_metric is not None
                    and metric_range.start <= old_metric <= metric_range.end
                ):
                    assignments.append(
                        MetricAssignment(
                            profile.name,
                            metric_range.device_name,
                            metric_range.expected_index,
                            binding.identity,
                            old_metric,
                        )
                    )
                    assigned_keys.add(key)

            free = [
                metric
                for metric in range(metric_range.start, metric_range.end + 1)
                if metric not in reserved
            ]

            for binding in members:
                key = (profile.name, binding.identity)
                if key in assigned_keys:
                    continue
                if not free:
                    waiting.append(key)
                    continue

                metric = free.pop(0)
                assignments.append(
                    MetricAssignment(
                        profile.name,
                        metric_range.device_name,
                        metric_range.expected_index,
                        binding.identity,
                        metric,
                    )
                )
                assigned_keys.add(key)

    return TrafficProjection(tuple(assignments), tuple(waiting))
