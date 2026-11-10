from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .constants import BLACKHOLE_METRIC, ROUTE_METRIC_STEP
from .interfaces import InterfaceBinding
from .models import RouteSpec, VpnProfileConfig


@dataclass(slots=True, frozen=True)
class PreparedProfileState:
    routes: frozenset[RouteSpec]
    active_bindings: tuple[InterfaceBinding, ...]
    prefix_metrics: Mapping[InterfaceBinding, int]
    prefix_metric_cursor: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "routes", frozenset(self.routes))
        object.__setattr__(self, "active_bindings", tuple(self.active_bindings))
        object.__setattr__(
            self,
            "prefix_metrics",
            MappingProxyType(dict(self.prefix_metrics)),
        )


class VpnProfile:
    """Immutable config plus process-local verified daemon state."""

    def __init__(self, config: VpnProfileConfig) -> None:
        self.config = config
        self._owned_routes: frozenset[RouteSpec] = frozenset()
        self._committed_active_bindings: tuple[InterfaceBinding, ...] | None = None
        self._committed_prefix_metrics: Mapping[InterfaceBinding, int] = (
            MappingProxyType({})
        )
        self._committed_prefix_metric_cursor = config.dynamic_metric_min

    @property
    def owned_routes(self) -> frozenset[RouteSpec]:
        return self._owned_routes

    @property
    def committed_active_bindings(self) -> tuple[InterfaceBinding, ...] | None:
        return self._committed_active_bindings

    @property
    def committed_prefix_metrics(self) -> Mapping[InterfaceBinding, int]:
        return self._committed_prefix_metrics

    @property
    def committed_prefix_metric_cursor(self) -> int:
        return self._committed_prefix_metric_cursor

    def _valid_prefix_metric(self, metric: int) -> bool:
        start = self.config.dynamic_metric_min
        return (
            start <= metric < BLACKHOLE_METRIC
            and (metric - start) % ROUTE_METRIC_STEP == 0
        )

    def prepare_verified_state(
        self,
        *,
        routes: set[RouteSpec] | frozenset[RouteSpec],
        active_bindings: tuple[InterfaceBinding, ...],
        prefix_bindings: tuple[InterfaceBinding, ...],
        prefix_metrics: Mapping[InterfaceBinding, int] | None = None,
        prefix_metric_cursor: int | None = None,
    ) -> PreparedProfileState:
        active = tuple(active_bindings)
        prefix = tuple(prefix_bindings)
        if len(set(active)) != len(active):
            raise ValueError("active bindings contain duplicates")
        if len(set(prefix)) != len(prefix):
            raise ValueError("prefix bindings contain duplicates")
        if not set(prefix) <= set(active):
            raise ValueError("prefix bindings must be active bindings")

        metrics = dict(prefix_metrics or {})
        if self.config.has_prefix_bindings:
            if prefix_metric_cursor is None:
                raise ValueError("prefix profile requires allocator cursor")
            if set(metrics) != set(prefix):
                raise ValueError(
                    "prefix metric mapping must match prefix bindings exactly"
                )
            if len(set(metrics.values())) != len(metrics):
                raise ValueError("prefix metric mapping contains duplicate metrics")
            if not all(self._valid_prefix_metric(metric) for metric in metrics.values()):
                raise ValueError("prefix metric mapping contains invalid metric")
            if not self._valid_prefix_metric(prefix_metric_cursor):
                raise ValueError("prefix metric cursor is invalid")
            cursor = prefix_metric_cursor
        else:
            if prefix:
                raise ValueError("profile without prefix specs has prefix bindings")
            if metrics:
                raise ValueError("profile without prefix specs has prefix metrics")
            if prefix_metric_cursor not in (None, self.config.dynamic_metric_min):
                raise ValueError("profile without prefix specs has prefix cursor")
            cursor = self.config.dynamic_metric_min

        return PreparedProfileState(
            routes=frozenset(routes),
            active_bindings=active,
            prefix_metrics=metrics,
            prefix_metric_cursor=cursor,
        )

    def commit_prepared_state(self, prepared: PreparedProfileState) -> None:
        """Non-validating commit stage used only after all profiles prepare."""
        self._owned_routes = prepared.routes
        self._committed_active_bindings = prepared.active_bindings
        self._committed_prefix_metrics = prepared.prefix_metrics
        self._committed_prefix_metric_cursor = prepared.prefix_metric_cursor

    def commit_verified_state(
        self,
        *,
        routes: set[RouteSpec] | frozenset[RouteSpec],
        active_bindings: tuple[InterfaceBinding, ...],
        prefix_bindings: tuple[InterfaceBinding, ...] = (),
        prefix_metrics: Mapping[InterfaceBinding, int] | None = None,
        prefix_metric_cursor: int | None = None,
    ) -> None:
        """Convenience API for tests/single-profile callers."""
        prepared = self.prepare_verified_state(
            routes=routes,
            active_bindings=active_bindings,
            prefix_bindings=prefix_bindings,
            prefix_metrics=prefix_metrics,
            prefix_metric_cursor=prefix_metric_cursor,
        )
        self.commit_prepared_state(prepared)
