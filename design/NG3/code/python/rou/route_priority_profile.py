from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Network
from typing import Iterable, Mapping

from .binding import LogicalPathId
from .route_priority_enforcer import (
    RoutePriorityBackend,
    RoutePriorityEnforcementResult,
    RoutePrioritySnapshot,
    converge_route_priority_once,
)


@dataclass(frozen=True, order=True, slots=True)
class RoutePriorityDomainId:
    profile_id: str
    destination: IPv4Network

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise ValueError("profile_id must be a non-empty string")
        if not isinstance(self.destination, IPv4Network):
            raise ValueError("destination must be an IPv4Network")


@dataclass(frozen=True, slots=True)
class RoutePriorityDomainRequest:
    domain_id: RoutePriorityDomainId
    backend: RoutePriorityBackend
    desired: Mapping[LogicalPathId, int]
    working_metrics: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.domain_id, RoutePriorityDomainId):
            raise ValueError("domain_id must be a RoutePriorityDomainId")
        if not isinstance(self.working_metrics, tuple):
            raise ValueError("working_metrics must be a tuple")


@dataclass(frozen=True, slots=True)
class RoutePriorityDomainOutcome:
    domain_id: RoutePriorityDomainId
    attempt: RoutePriorityEnforcementResult | None
    attempt_error: str | None
    final: RoutePrioritySnapshot | None
    final_error: str | None
    confirmed: bool


class RoutePriorityProfileStatus(str, Enum):
    SUCCESS = "success"
    UNCONFIRMED = "unconfirmed"


@dataclass(frozen=True, slots=True)
class RoutePriorityProfileResult:
    status: RoutePriorityProfileStatus
    domains: tuple[RoutePriorityDomainOutcome, ...]

    @property
    def confirmed(self) -> bool:
        return self.status is RoutePriorityProfileStatus.SUCCESS


def converge_route_priority_profile_once(
    requests: Iterable[RoutePriorityDomainRequest],
) -> RoutePriorityProfileResult:
    """Converge each route-key domain once, then re-verify every domain.

    Domain attempts are independent and deterministic. A failure in one domain
    does not cause stale-plan replay and does not prevent another domain from
    performing its own fresh observe/plan/apply attempt.

    Profile success is based only on a final fresh verification pass across all
    supplied domains, not on whether command attempts happened to return success.
    """
    ordered = tuple(
        sorted(
            requests,
            key=lambda request: (
                request.domain_id.profile_id,
                int(request.domain_id.destination.network_address),
                request.domain_id.destination.prefixlen,
            ),
        )
    )
    _validate_requests(ordered)

    attempts: dict[RoutePriorityDomainId, RoutePriorityEnforcementResult | None] = {}
    attempt_errors: dict[RoutePriorityDomainId, str | None] = {}

    for request in ordered:
        try:
            attempts[request.domain_id] = converge_route_priority_once(
                request.backend,
                request.desired,
                request.working_metrics,
            )
            attempt_errors[request.domain_id] = None
        except Exception as exc:
            attempts[request.domain_id] = None
            attempt_errors[request.domain_id] = (
                f"{type(exc).__name__}: {exc}"
            )

    outcomes: list[RoutePriorityDomainOutcome] = []

    for request in ordered:
        final: RoutePrioritySnapshot | None
        final_error: str | None

        try:
            final = request.backend.observe_route_priority()
            final_error = None
            confirmed = _matches_desired(final, request.desired)
        except Exception as exc:
            final = None
            final_error = f"{type(exc).__name__}: {exc}"
            confirmed = False

        outcomes.append(
            RoutePriorityDomainOutcome(
                domain_id=request.domain_id,
                attempt=attempts[request.domain_id],
                attempt_error=attempt_errors[request.domain_id],
                final=final,
                final_error=final_error,
                confirmed=confirmed,
            )
        )

    status = (
        RoutePriorityProfileStatus.SUCCESS
        if all(outcome.confirmed for outcome in outcomes)
        else RoutePriorityProfileStatus.UNCONFIRMED
    )
    return RoutePriorityProfileResult(status=status, domains=tuple(outcomes))


def _validate_requests(
    requests: tuple[RoutePriorityDomainRequest, ...],
) -> None:
    if not requests:
        raise ValueError("at least one route-priority domain is required")

    seen: set[RoutePriorityDomainId] = set()
    profile_ids = {request.domain_id.profile_id for request in requests}
    if len(profile_ids) != 1:
        raise ValueError("one profile convergence call cannot mix profile IDs")

    for request in requests:
        if request.domain_id in seen:
            raise ValueError(
                f"duplicate route-priority domain {request.domain_id!r}"
            )
        seen.add(request.domain_id)


def _matches_desired(
    snapshot: RoutePrioritySnapshot,
    desired: Mapping[LogicalPathId, int],
) -> bool:
    if set(snapshot.routes) != set(desired):
        return False
    return all(
        snapshot.routes[path_id] == frozenset((metric,))
        for path_id, metric in desired.items()
    )
