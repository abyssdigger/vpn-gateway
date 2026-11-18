"""Pure derivation of external VPN transport endpoints requiring host underlay pins."""

from __future__ import annotations

from ipaddress import IPv4Address
from typing import Iterable

from .host_boundary_policy import HostBoundaryPolicyPlan


class UnderlayEndpointPayloadConflict(ValueError):
    pass


def required_underlay_endpoints(
    plan: HostBoundaryPolicyPlan,
    transport_endpoints: Iterable[IPv4Address],
) -> tuple[IPv4Address, ...]:
    """Return exact external endpoints captured by at least one bootstrap prefix.

    The test is intentionally global rather than Profile-local: host bootstrap routes affect
    the whole ordinary host routing domain, so a broad Profile route may capture another
    Device's transport endpoint too.
    """
    if not isinstance(plan, HostBoundaryPolicyPlan):
        raise ValueError("plan must be HostBoundaryPolicyPlan")

    endpoints = tuple(transport_endpoints)
    if any(not isinstance(item, IPv4Address) for item in endpoints):
        raise ValueError("transport_endpoints must contain IPv4Address values")

    for endpoint in endpoints:
        if any(
            route.destination.prefixlen == 32
            and endpoint in route.destination
            for route in plan.bootstrap_routes
        ):
            raise UnderlayEndpointPayloadConflict(
                f"external VPN endpoint {endpoint} is also an exact /32 host bootstrap destination"
            )

    captured = {
        endpoint
        for endpoint in endpoints
        if any(endpoint in route.destination for route in plan.bootstrap_routes)
    }
    return tuple(sorted(captured, key=int))
