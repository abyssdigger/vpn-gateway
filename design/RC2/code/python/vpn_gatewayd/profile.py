from __future__ import annotations

from .constants import (
    BLACKHOLE_METRIC,
    BLACKHOLE_ROUTE_PROTO,
    PEER_METRIC_STEP,
    VPN_ROUTE_PROTO,
)
from .models import ProfileResourceSet, RouteSpec, RouteType, VpnProfileConfig

class VpnProfile:
    """
    Pure profile/domain object.

    No kernel reads.
    No kernel writes.
    No readiness query.
    No Netlink socket.
    """

    def __init__(self, config: VpnProfileConfig) -> None:
        self.config = config
        self._owned_routes: set[RouteSpec] = set()

    def _list_routes(self, source: ProfileResourceSet) -> frozenset[RouteSpec]:
        if source is ProfileResourceSet.CONFIGURED:
            return self._configured_routes()
        if source is ProfileResourceSet.OWNED:
            return frozenset(self._owned_routes)
        raise AssertionError(f"unhandled ProfileResourceSet: {source!r}")

    def _configured_routes(self) -> frozenset[RouteSpec]:
        """
        CONFIGURED is derived only from immutable config.

        For every protected prefix:
        - one BLACKHOLE guard;
        - one UNICAST route per peer.
        """
        routes: set[RouteSpec] = set()

        for destination in self.config.routes:
            routes.add(
                RouteSpec(
                    destination=destination,
                    route_type=RouteType.BLACKHOLE,
                    via=None,
                    interface=None,
                    metric=BLACKHOLE_METRIC,
                    proto=BLACKHOLE_ROUTE_PROTO,
                    onlink=False,
                )
            )

            for index, peer in enumerate(self.config.peers):
                routes.add(
                    RouteSpec(
                        destination=destination,
                        route_type=RouteType.UNICAST,
                        via=peer,
                        interface=self.config.interface,
                        metric=(index + 1) * PEER_METRIC_STEP,
                        proto=VPN_ROUTE_PROTO,
                        onlink=True,
                    )
                )

        return frozenset(routes)

    def update_owned_state(
        self,
        *,
        routes: set[RouteSpec] | frozenset[RouteSpec],
    ) -> None:
        """Atomic defensive replacement after daemon verify."""
        self._owned_routes = set(routes)


# ---------------------------------------------------------------------------
# Kernel/userspace boundary
# ---------------------------------------------------------------------------


