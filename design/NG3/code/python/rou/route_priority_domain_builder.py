from __future__ import annotations

from typing import Iterable

from .payload_profile import PayloadProfileRequest
from .network_policy_layout import PayloadPolicyAllocation
from .route_priority_inventory import RoutePriorityPathRoute
from .route_priority_profile import RoutePriorityDomainId
from .route_priority_realization import (
    RoutePriorityDomainRealization,
    RoutePriorityRealizationError,
)


class RoutePriorityDomainBuildError(ValueError):
    pass


def build_route_priority_domain_realizations(
    profile: PayloadProfileRequest,
    allocation: PayloadPolicyAllocation,
    path_routes: Iterable[RoutePriorityPathRoute],
) -> tuple[RoutePriorityDomainRealization, ...]:
    """Build pure-priority route domains from semantic + lower realization inputs.

    This function intentionally does not infer gateway/onlink or endpoint identity.
    Those are already-proved lower integration facts carried by RoutePriorityPathRoute.
    """
    if not isinstance(profile, PayloadProfileRequest):
        raise RoutePriorityDomainBuildError(
            "profile must be PayloadProfileRequest"
        )
    if not isinstance(allocation, PayloadPolicyAllocation):
        raise RoutePriorityDomainBuildError(
            "allocation must be PayloadPolicyAllocation"
        )
    if profile.profile_id != allocation.profile_id:
        raise RoutePriorityDomainBuildError(
            "Profile identity does not match payload allocation"
        )

    supplied = tuple(path_routes)
    if any(
        not isinstance(spec, RoutePriorityPathRoute)
        for spec in supplied
    ):
        raise RoutePriorityDomainBuildError(
            "path_routes must contain RoutePriorityPathRoute"
        )

    by_path = {}
    for spec in supplied:
        if spec.path_id in by_path:
            raise RoutePriorityDomainBuildError(
                f"duplicate physical route realization for {spec.path_id!r}"
            )
        by_path[spec.path_id] = spec

    semantic_paths = tuple(profile.ordered_paths)
    if len(set(semantic_paths)) != len(semantic_paths):
        raise RoutePriorityDomainBuildError(
            "semantic Profile path order contains duplicate logical paths"
        )

    if set(by_path) != set(semantic_paths):
        raise RoutePriorityDomainBuildError(
            "physical route realization membership does not match semantic Profile paths"
        )

    if not semantic_paths:
        if allocation.metric_space is not None:
            raise RoutePriorityDomainBuildError(
                "zero-path Profile must not have a priority metric space"
            )
        return ()

    if allocation.metric_space is None:
        raise RoutePriorityDomainBuildError(
            "non-empty Profile has no priority metric space"
        )

    ordered_path_routes = tuple(
        by_path[path_id]
        for path_id in semantic_paths
    )

    destinations = tuple(
        sorted(
            profile.destinations,
            key=lambda network: (
                int(network.network_address),
                network.prefixlen,
            ),
        )
    )

    out: list[RoutePriorityDomainRealization] = []
    for destination in destinations:
        try:
            realization = RoutePriorityDomainRealization(
                domain_id=RoutePriorityDomainId(
                    profile_id=profile.profile_id,
                    destination=destination,
                ),
                table=allocation.table,
                owner_protocol=allocation.path_route_protocol,
                path_routes=ordered_path_routes,
                metric_space=allocation.metric_space,
            )
            # Force membership/order validation now rather than leaving it to
            # a later caller.
            realization.desired_metrics(semantic_paths)
        except (ValueError, RoutePriorityRealizationError) as exc:
            raise RoutePriorityDomainBuildError(str(exc)) from exc
        out.append(realization)

    return tuple(out)
