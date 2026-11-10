from __future__ import annotations

from .interfaces import InterfaceBinding
from .models import RouteSpec, VpnProfileConfig


class VpnProfile:
    """Immutable config plus process-local verified daemon state."""

    def __init__(self, config: VpnProfileConfig) -> None:
        self.config = config
        self._owned_routes: set[RouteSpec] = set()
        self._committed_candidates: tuple[InterfaceBinding, ...] | None = None
        self._committed_active_bindings: tuple[InterfaceBinding, ...] | None = None

    @property
    def owned_routes(self) -> frozenset[RouteSpec]:
        return frozenset(self._owned_routes)

    @property
    def committed_candidates(self) -> tuple[InterfaceBinding, ...] | None:
        return self._committed_candidates

    @property
    def committed_active_bindings(self) -> tuple[InterfaceBinding, ...] | None:
        return self._committed_active_bindings

    def commit_verified_state(
        self,
        *,
        routes: set[RouteSpec] | frozenset[RouteSpec],
        candidates: tuple[InterfaceBinding, ...],
        active_bindings: tuple[InterfaceBinding, ...],
    ) -> None:
        self._owned_routes = set(routes)
        self._committed_candidates = tuple(candidates)
        self._committed_active_bindings = tuple(active_bindings)
