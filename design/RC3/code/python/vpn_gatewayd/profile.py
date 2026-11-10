from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .constants import (
    BLACKHOLE_METRIC,
    FIRST_UNICAST_METRIC,
    ROUTE_METRIC_STEP,
)
from .interfaces import (
    InterfaceBinding,
    InterfaceSelectorKind,
)
from .models import RouteSpec, VpnProfileConfig


class VpnProfile:
    """Immutable config plus process-local verified daemon state."""

    def __init__(self, config: VpnProfileConfig) -> None:
        self.config = config
        self._owned_routes: set[RouteSpec] = set()
        self._committed_active_bindings: tuple[InterfaceBinding, ...] | None = None
        self._committed_prefix_metrics: Mapping[InterfaceBinding, int] = (
            MappingProxyType({})
        )
        self._committed_prefix_metric_cursor = FIRST_UNICAST_METRIC

    @property
    def owned_routes(self) -> frozenset[RouteSpec]:
        return frozenset(self._owned_routes)

    @property
    def committed_active_bindings(self) -> tuple[InterfaceBinding, ...] | None:
        return self._committed_active_bindings

    @property
    def committed_prefix_metrics(self) -> Mapping[InterfaceBinding, int]:
        return self._committed_prefix_metrics

    @property
    def committed_prefix_metric_cursor(self) -> int:
        return self._committed_prefix_metric_cursor

    @staticmethod
    def _valid_prefix_metric(metric: int) -> bool:
        return (
            FIRST_UNICAST_METRIC <= metric < BLACKHOLE_METRIC
            and (metric - FIRST_UNICAST_METRIC) % ROUTE_METRIC_STEP == 0
        )

    def commit_verified_state(
        self,
        *,
        routes: set[RouteSpec] | frozenset[RouteSpec],
        active_bindings: tuple[InterfaceBinding, ...],
        prefix_metrics: Mapping[InterfaceBinding, int] | None = None,
        prefix_metric_cursor: int | None = None,
    ) -> None:
        active = tuple(active_bindings)
        if len(set(active)) != len(active):
            raise ValueError("active bindings contain duplicates")

        if self.config.interface.kind is InterfaceSelectorKind.PREFIX:
            if prefix_metrics is None or prefix_metric_cursor is None:
                raise ValueError(
                    "prefix profile commit requires allocator mapping and cursor"
                )
            metrics = dict(prefix_metrics)
            if set(metrics) != set(active):
                raise ValueError(
                    "prefix metric mapping must match active bindings exactly"
                )
            if len(set(metrics.values())) != len(metrics):
                raise ValueError("prefix metric mapping contains duplicate metrics")
            if not all(self._valid_prefix_metric(metric) for metric in metrics.values()):
                raise ValueError("prefix metric mapping contains invalid metric")
            if not self._valid_prefix_metric(prefix_metric_cursor):
                raise ValueError("prefix metric cursor is invalid")
            self._committed_prefix_metrics = MappingProxyType(metrics)
            self._committed_prefix_metric_cursor = prefix_metric_cursor
        else:
            if prefix_metrics not in (None, {}):
                raise ValueError("non-prefix profile cannot commit prefix metrics")
            if prefix_metric_cursor is not None:
                raise ValueError("non-prefix profile cannot commit prefix metric cursor")
            self._committed_prefix_metrics = MappingProxyType({})
            self._committed_prefix_metric_cursor = FIRST_UNICAST_METRIC

        self._owned_routes = set(routes)
        self._committed_active_bindings = active
