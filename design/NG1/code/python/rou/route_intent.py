from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .device_engine import DeviceBindingSnapshot, InterfaceIdentity
from .domain import ActiveConfig, Availability
from .metrics import BLACKHOLE_METRIC
from .traffic_state import TrafficProjection


class UnavailablePathProjectionBlocked(RuntimeError):
    """EXP-013 has not yet authorized production unavailable-path materialization."""


@dataclass(frozen=True)
class DirectRouteIntent:
    destination: IPv4Network
    identity: InterfaceIdentity
    metric: int


@dataclass(frozen=True)
class ProfileRouteIntent:
    profile_name: str
    normal_routes: tuple[DirectRouteIntent, ...]
    terminal_blackhole_metric: int = BLACKHOLE_METRIC


def compile_profile_route_intents(
    config: ActiveConfig,
    bindings: DeviceBindingSnapshot,
    metrics: TrafficProjection,
) -> tuple[ProfileRouteIntent, ...]:
    """Compile kernel-independent Profile route intent for the proven subset.

    UNKNOWN and AVAILABLE bindings remain normal-tier. Any bound UNAVAILABLE path blocks
    route projection until EXP-013 closes the common-metric direct-device multipath gate.
    """

    binding_by_identity = {
        binding.identity: binding
        for binding in bindings.bound
    }

    assignments_by_profile: dict[str, list] = {}
    for assignment in metrics.assignments:
        profile = config.profiles.get(assignment.profile_name)
        if profile is None or not profile.enabled:
            raise ValueError(
                f"metric assignment references unknown/disabled Profile "
                f"{assignment.profile_name!r}"
            )

        binding = binding_by_identity.get(assignment.identity)
        if binding is None:
            raise ValueError(
                f"metric assignment references unbound interface {assignment.identity!r}"
            )
        if binding.device_name != assignment.device_name:
            raise ValueError(
                f"metric assignment Device mismatch for {assignment.identity!r}"
            )
        if binding.expected_index != assignment.expected_index:
            raise ValueError(
                f"metric assignment ExpectedInterface mismatch for {assignment.identity!r}"
            )

        if binding.availability is Availability.UNAVAILABLE:
            raise UnavailablePathProjectionBlocked(
                f"profile {assignment.profile_name!r} contains UNAVAILABLE path "
                f"{assignment.identity.ifname}/{assignment.identity.ifindex}; "
                "production fallback is blocked on EXP-013"
            )

        assignments_by_profile.setdefault(
            assignment.profile_name,
            [],
        ).append(assignment)

    out: list[ProfileRouteIntent] = []
    for profile in config.profiles.values():
        if not profile.enabled:
            continue

        routes: list[DirectRouteIntent] = []
        for destination in profile.destinations:
            for assignment in assignments_by_profile.get(profile.name, []):
                routes.append(
                    DirectRouteIntent(
                        destination=destination,
                        identity=assignment.identity,
                        metric=assignment.metric,
                    )
                )

        out.append(
            ProfileRouteIntent(
                profile_name=profile.name,
                normal_routes=tuple(routes),
            )
        )

    return tuple(out)
