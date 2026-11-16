from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Iterable

from .binding import LogicalPathId
from .route_priority_inventory import RoutePriorityPathRoute
from .route_priority_profile import RoutePriorityDomainId


class RoutePriorityRealizationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RoutePriorityMetricSpace:
    """Internal metric allocation for one route-priority domain."""

    preference_slots: tuple[int, ...]
    scratch_metrics: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.preference_slots:
            raise RoutePriorityRealizationError(
                "preference_slots must be non-empty"
            )
        all_metrics = self.preference_slots + self.scratch_metrics
        if any(
            type(metric) is not int or not 0 <= metric <= 0xFFFFFFFF
            for metric in all_metrics
        ):
            raise RoutePriorityRealizationError(
                "all route-priority metrics must be integers in [0, 2^32-1]"
            )
        if len(set(all_metrics)) != len(all_metrics):
            raise RoutePriorityRealizationError(
                "route-priority metric space contains duplicate metrics"
            )
        if tuple(sorted(self.preference_slots)) != self.preference_slots:
            raise RoutePriorityRealizationError(
                "preference_slots must be strictly increasing Linux metrics"
            )

    @property
    def working_metrics(self) -> tuple[int, ...]:
        return self.preference_slots + self.scratch_metrics

    def assign(
        self,
        ordered_paths: Iterable[LogicalPathId],
    ) -> Mapping[LogicalPathId, int]:
        paths = tuple(ordered_paths)
        if len(set(paths)) != len(paths):
            raise RoutePriorityRealizationError(
                "ordered_paths contains duplicate logical paths"
            )
        if len(paths) > len(self.preference_slots):
            raise RoutePriorityRealizationError(
                "metric preference slots are insufficient for path membership"
            )
        if len(paths) > 1 and not self.scratch_metrics:
            raise RoutePriorityRealizationError(
                "multi-path priority space requires at least one scratch metric"
            )
        return MappingProxyType(
            {
                path_id: self.preference_slots[index]
                for index, path_id in enumerate(paths)
            }
        )


@dataclass(frozen=True, slots=True)
class RoutePriorityDomainRealization:
    """Lower Adapter realization required by one physical route-key domain."""

    domain_id: RoutePriorityDomainId
    table: int
    owner_protocol: int
    path_routes: tuple[RoutePriorityPathRoute, ...]
    metric_space: RoutePriorityMetricSpace

    def __post_init__(self) -> None:
        if not isinstance(self.domain_id, RoutePriorityDomainId):
            raise RoutePriorityRealizationError(
                "domain_id must be a RoutePriorityDomainId"
            )
        if type(self.table) is not int or not 1 <= self.table <= 0xFFFFFFFF:
            raise RoutePriorityRealizationError(
                "table must be an integer in [1, 2^32-1]"
            )
        if (
            type(self.owner_protocol) is not int
            or not 0 <= self.owner_protocol <= 255
        ):
            raise RoutePriorityRealizationError(
                "owner_protocol must be an integer in [0, 255]"
            )
        if not isinstance(self.metric_space, RoutePriorityMetricSpace):
            raise RoutePriorityRealizationError(
                "metric_space must be RoutePriorityMetricSpace"
            )
        if not isinstance(self.path_routes, tuple) or not self.path_routes:
            raise RoutePriorityRealizationError(
                "path_routes must be a non-empty tuple"
            )
        if any(
            not isinstance(spec, RoutePriorityPathRoute)
            for spec in self.path_routes
        ):
            raise RoutePriorityRealizationError(
                "path_routes must contain RoutePriorityPathRoute"
            )

        path_ids = tuple(spec.path_id for spec in self.path_routes)
        if len(set(path_ids)) != len(path_ids):
            raise RoutePriorityRealizationError(
                "path_routes contains duplicate logical paths"
            )
        endpoints = tuple(spec.endpoint for spec in self.path_routes)
        if len(set(endpoints)) != len(endpoints):
            raise RoutePriorityRealizationError(
                "path_routes assigns one endpoint to multiple logical paths"
            )
        if len(path_ids) > len(self.metric_space.preference_slots):
            raise RoutePriorityRealizationError(
                "metric preference slots are insufficient for realized paths"
            )
        if len(path_ids) > 1 and not self.metric_space.scratch_metrics:
            raise RoutePriorityRealizationError(
                "multi-path realization requires scratch metric space"
            )

    @property
    def logical_paths(self) -> frozenset[LogicalPathId]:
        return frozenset(spec.path_id for spec in self.path_routes)

    def desired_metrics(
        self,
        ordered_paths: Iterable[LogicalPathId],
    ) -> Mapping[LogicalPathId, int]:
        paths = tuple(ordered_paths)
        if frozenset(paths) != self.logical_paths:
            raise RoutePriorityRealizationError(
                "semantic ordered path membership does not match physical realization"
            )
        return self.metric_space.assign(paths)
