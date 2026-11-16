from __future__ import annotations

from typing import Iterable

from .binding import LogicalPathId, PathBinding
from .interface_identity import InterfaceIdentity
from .route_priority_inventory import RoutePriorityPathRoute


class DirectDeviceRouteRealizationError(ValueError):
    pass


def realize_direct_device_path_routes(
    bindings: Iterable[PathBinding],
) -> tuple[RoutePriorityPathRoute, ...]:
    """Realize an explicitly direct-device VPN integration.

    This helper is not a generic inference from interface presence. Callers may
    use it only when their accepted integration/onboarding contract guarantees
    that protected destinations are routed directly through the bound endpoint
    without a Linux next-hop gateway or onlink flag.
    """
    current = tuple(bindings)
    by_path: dict[LogicalPathId, InterfaceIdentity] = {}
    endpoint_owner: dict[InterfaceIdentity, LogicalPathId] = {}

    for binding in current:
        if not isinstance(binding, PathBinding):
            raise DirectDeviceRouteRealizationError(
                "bindings must contain PathBinding"
            )
        if not isinstance(binding.path_id, LogicalPathId):
            raise DirectDeviceRouteRealizationError(
                "PathBinding.path_id must be LogicalPathId"
            )
        if not isinstance(binding.endpoint, InterfaceIdentity):
            raise DirectDeviceRouteRealizationError(
                "PathBinding.endpoint must be InterfaceIdentity"
            )

        if binding.path_id in by_path:
            raise DirectDeviceRouteRealizationError(
                f"duplicate current binding for {binding.path_id!r}"
            )
        previous = endpoint_owner.get(binding.endpoint)
        if previous is not None:
            raise DirectDeviceRouteRealizationError(
                f"endpoint {binding.endpoint!r} is bound to multiple logical paths"
            )

        by_path[binding.path_id] = binding.endpoint
        endpoint_owner[binding.endpoint] = binding.path_id

    return tuple(
        RoutePriorityPathRoute(
            path_id=path_id,
            endpoint=by_path[path_id],
            gateway=None,
            onlink=False,
        )
        for path_id in sorted(by_path)
    )
