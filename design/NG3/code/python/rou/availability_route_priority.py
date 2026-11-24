"""Availability effective-order to existing route-priority convergence bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .iproute_priority_backend import CommandRunner, IproutePriorityDriver
from .network_policy_layout import NetworkPolicyLayout, PayloadPolicyAllocation
from .payload_profile import PayloadProfileRequest
from .route_priority_domain_builder import (
    RoutePriorityDomainBuildError,
    build_route_priority_domain_realizations,
)
from .route_priority_inventory import RoutePriorityPathRoute
from .route_priority_profile import (
    RoutePriorityDomainRequest,
    RoutePriorityProfileResult,
    converge_route_priority_profile_once,
)


class AvailabilityRoutePriorityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AvailabilityRoutePriorityPlan:
    profile_id: str
    requests: tuple[RoutePriorityDomainRequest, ...]


@dataclass(frozen=True, slots=True)
class AvailabilityRoutePriorityProfileResult:
    profile_id: str
    result: RoutePriorityProfileResult | None

    @property
    def confirmed(self) -> bool:
        return self.result is None or self.result.confirmed


@dataclass(frozen=True, slots=True)
class AvailabilityRoutePriorityResult:
    profiles: tuple[AvailabilityRoutePriorityProfileResult, ...]

    @property
    def confirmed(self) -> bool:
        return all(profile.confirmed for profile in self.profiles)


def build_availability_route_priority_plans(
    effective_profiles: Iterable[PayloadProfileRequest],
    layout: NetworkPolicyLayout,
    path_routes: Iterable[RoutePriorityPathRoute],
    *,
    runner: CommandRunner,
    namespace: str,
) -> tuple[AvailabilityRoutePriorityPlan, ...]:
    profiles = tuple(sorted(effective_profiles, key=lambda item: item.profile_id))
    routes = tuple(path_routes)

    _validate_inputs(profiles, layout, routes, namespace)

    allocation_by_id = {
        allocation.profile_id: allocation
        for allocation in layout.payload
    }
    route_by_path = {
        route.path_id: route
        for route in routes
    }

    plans: list[AvailabilityRoutePriorityPlan] = []
    for profile in profiles:
        allocation = allocation_by_id[profile.profile_id]
        required_routes = tuple(
            route_by_path[path_id]
            for path_id in profile.ordered_paths
        )
        try:
            realizations = build_route_priority_domain_realizations(
                profile,
                allocation,
                required_routes,
            )
        except RoutePriorityDomainBuildError as exc:
            raise AvailabilityRoutePriorityError(str(exc)) from exc

        requests = tuple(
            _request_for_realization(
                realization,
                runner=runner,
                namespace=namespace,
            )
            for realization in realizations
        )
        plans.append(
            AvailabilityRoutePriorityPlan(
                profile.profile_id,
                requests,
            )
        )

    return tuple(plans)


def converge_availability_route_priority_once(
    effective_profiles: Iterable[PayloadProfileRequest],
    layout: NetworkPolicyLayout,
    path_routes: Iterable[RoutePriorityPathRoute],
    *,
    runner: CommandRunner,
    namespace: str,
) -> AvailabilityRoutePriorityResult:
    plans = build_availability_route_priority_plans(
        effective_profiles,
        layout,
        path_routes,
        runner=runner,
        namespace=namespace,
    )

    outcomes: list[AvailabilityRoutePriorityProfileResult] = []
    for plan in plans:
        if not plan.requests:
            outcomes.append(
                AvailabilityRoutePriorityProfileResult(
                    plan.profile_id,
                    None,
                )
            )
            continue
        outcomes.append(
            AvailabilityRoutePriorityProfileResult(
                plan.profile_id,
                converge_route_priority_profile_once(plan.requests),
            )
        )

    return AvailabilityRoutePriorityResult(tuple(outcomes))


def _request_for_realization(
    realization,
    *,
    runner: CommandRunner,
    namespace: str,
) -> RoutePriorityDomainRequest:
    ordered_paths = tuple(
        spec.path_id
        for spec in realization.path_routes
    )
    return RoutePriorityDomainRequest(
        domain_id=realization.domain_id,
        backend=IproutePriorityDriver(
            runner=runner,
            namespace=namespace,
            table=realization.table,
            owner_protocol=realization.owner_protocol,
            destination=realization.domain_id.destination,
            path_routes=realization.path_routes,
        ),
        desired=realization.desired_metrics(ordered_paths),
        working_metrics=realization.metric_space.working_metrics,
    )


def _validate_inputs(
    profiles: tuple[PayloadProfileRequest, ...],
    layout: NetworkPolicyLayout,
    routes: tuple[RoutePriorityPathRoute, ...],
    namespace: str,
) -> None:
    if not isinstance(layout, NetworkPolicyLayout):
        raise AvailabilityRoutePriorityError(
            "layout must be NetworkPolicyLayout"
        )
    if not isinstance(namespace, str) or not namespace:
        raise AvailabilityRoutePriorityError(
            "namespace must be non-empty"
        )
    if any(
        not isinstance(profile, PayloadProfileRequest)
        for profile in profiles
    ):
        raise AvailabilityRoutePriorityError(
            "effective_profiles must contain PayloadProfileRequest"
        )
    profile_ids = tuple(profile.profile_id for profile in profiles)
    if len(set(profile_ids)) != len(profile_ids):
        raise AvailabilityRoutePriorityError(
            "effective_profiles contains duplicate Profile"
        )

    allocations = tuple(layout.payload)
    if any(
        not isinstance(allocation, PayloadPolicyAllocation)
        for allocation in allocations
    ):
        raise AvailabilityRoutePriorityError(
            "layout payload contains invalid allocation"
        )
    allocation_ids = tuple(
        allocation.profile_id
        for allocation in allocations
    )
    if set(profile_ids) != set(allocation_ids):
        raise AvailabilityRoutePriorityError(
            "effective Profile set does not match payload layout"
        )

    if any(
        not isinstance(route, RoutePriorityPathRoute)
        for route in routes
    ):
        raise AvailabilityRoutePriorityError(
            "path_routes must contain RoutePriorityPathRoute"
        )
    route_ids = tuple(route.path_id for route in routes)
    if len(set(route_ids)) != len(route_ids):
        raise AvailabilityRoutePriorityError(
            "path_routes contains duplicate logical path"
        )
    required_ids = {
        path_id
        for profile in profiles
        for path_id in profile.ordered_paths
    }
    if set(route_ids) != required_ids:
        raise AvailabilityRoutePriorityError(
            "path_routes does not match effective Profile membership"
        )
