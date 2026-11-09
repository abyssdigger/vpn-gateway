from __future__ import annotations

from .interfaces import InterfaceBinding, InterfaceResolutionState
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
        self._committed_resolution_state: InterfaceResolutionState | None = None
        self._committed_match_count: int | None = None

    @property
    def owned_routes(self) -> frozenset[RouteSpec]:
        return frozenset(self._owned_routes)

    @property
    def committed_binding(self) -> InterfaceBinding | None:
        return self._committed_binding

    @property
    def committed_ready(self) -> bool:
        return self._committed_ready

    @property
    def committed_resolution_state(self) -> InterfaceResolutionState | None:
        return self._committed_resolution_state

    @property
    def committed_match_count(self) -> int | None:
        return self._committed_match_count

    def commit_verified_state(
        self,
        *,
        routes: set[RouteSpec] | frozenset[RouteSpec],
        binding: InterfaceBinding | None,
        ready: bool,
        resolution_state: InterfaceResolutionState | None = None,
        match_count: int | None = None,
    ) -> None:
        """Replace process-local state only after daemon verification."""
        if ready and binding is None:
            raise ValueError("ready committed state requires a binding")

        if resolution_state is None:
            resolution_state = (
                InterfaceResolutionState.BOUND
                if binding is not None
                else InterfaceResolutionState.ABSENT
            )
        if match_count is None:
            match_count = 1 if binding is not None else 0

        if match_count < 0:
            raise ValueError("committed match_count must be non-negative")
        if (
            resolution_state is InterfaceResolutionState.ABSENT
            and match_count != 0
        ):
            raise ValueError("ABSENT committed state requires match_count=0")
        if (
            resolution_state is InterfaceResolutionState.BOUND
            and (match_count != 1 or binding is None)
        ):
            raise ValueError(
                "BOUND committed state requires one match and a binding"
            )
        if (
            resolution_state is InterfaceResolutionState.AMBIGUOUS
            and (match_count < 2 or binding is not None or ready)
        ):
            raise ValueError(
                "AMBIGUOUS committed state requires >=2 matches, no binding, "
                "and ready=False"
            )

        new_routes = set(routes)
        self._owned_routes = new_routes
        self._committed_binding = binding
        self._committed_ready = ready
        self._committed_resolution_state = resolution_state
        self._committed_match_count = match_count
