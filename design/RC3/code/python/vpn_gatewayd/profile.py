from __future__ import annotations

from .interfaces import InterfaceBinding
from .models import RouteSpec, VpnProfileConfig


class VpnProfile:
    """
    Pure profile/domain object.

    Immutable configuration is separate from process-local committed state.
    No kernel reads, writes, readiness queries or Netlink operations live here.
    """

    def __init__(self, config: VpnProfileConfig) -> None:
        self.config = config
        self._owned_routes: set[RouteSpec] = set()
        self._committed_binding: InterfaceBinding | None = None
        self._committed_ready = False

    @property
    def owned_routes(self) -> frozenset[RouteSpec]:
        return frozenset(self._owned_routes)

    @property
    def committed_binding(self) -> InterfaceBinding | None:
        return self._committed_binding

    @property
    def committed_ready(self) -> bool:
        return self._committed_ready

    def commit_verified_state(
        self,
        *,
        routes: set[RouteSpec] | frozenset[RouteSpec],
        binding: InterfaceBinding | None,
        ready: bool,
    ) -> None:
        """Replace process-local state only after daemon verification."""
        if ready and binding is None:
            raise ValueError("ready committed state requires a binding")

        new_routes = set(routes)
        self._owned_routes = new_routes
        self._committed_binding = binding
        self._committed_ready = ready
