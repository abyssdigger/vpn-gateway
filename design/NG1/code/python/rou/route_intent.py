from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from .domain import ActiveConfig, Availability
from .metrics import BLACKHOLE_METRIC, UNAVAILABLE_METRIC
from .traffic_state import TrafficProjection


@dataclass(frozen=True)
class DirectRouteIntent:
    destination: IPv4Network
    identity: InterfaceIdentity
    metric: int


@dataclass(frozen=True)
class FallbackRouteIntent:
    destination: IPv4Network
    members: tuple[InterfaceIdentity, ...]
    metric: int = UNAVAILABLE_METRIC


@dataclass(frozen=True)
class ProfileRouteIntent:
    profile_name: str
    normal_routes: tuple[DirectRouteIntent, ...]
    fallback_routes: tuple[FallbackRouteIntent, ...]
    terminal_blackhole_metric: int = BLACKHOLE_METRIC


def _binding_index(bindings: DeviceBindingSnapshot) -> dict[InterfaceIdentity, BoundInterface]:
    out: dict[InterfaceIdentity, BoundInterface] = {}
    for binding in bindings.bound:
        if binding.identity in out:
            raise ValueError(f"duplicate bound interface identity {binding.identity!r}")
        out[binding.identity] = binding
    return out


def _profile_bound_members(
    config: ActiveConfig,
    profile_name: str,
    bindings: DeviceBindingSnapshot,
) -> tuple[InterfaceIdentity, ...]:
    profile = config.profiles[profile_name]
    members: list[InterfaceIdentity] = []

    for device_name in profile.device_order:
        device = config.devices[device_name]
        if not device.enabled:
            continue

        for expected_index in range(len(device.expected_interfaces)):
            for binding in bindings.bound:
                if (
                    binding.device_name == device_name
                    and binding.expected_index == expected_index
                ):
                    members.append(binding.identity)

    return tuple(members)


def compile_profile_route_intents(
    config: ActiveConfig,
    bindings: DeviceBindingSnapshot,
    metrics: TrafficProjection,
) -> tuple[ProfileRouteIntent, ...]:
    """Compile kernel-independent Profile route intent.

    EXP-013 established the persistent-shadow model:

    - every bound interface of a Profile is always a member of its fallback route at
      UNAVAILABLE_METRIC;
    - UNKNOWN and AVAILABLE paths additionally receive their stable normal route;
    - UNAVAILABLE removes only the normal route, leaving fallback membership unchanged;
    - one fallback member materializes as a direct-device route, while two or more
      members materialize as one equal-cost direct-device multipath route;
    - equal-cost fallback is ECMP/hash selection, not sequential retry.
    """

    binding_by_identity = _binding_index(bindings)

    assignments_by_profile: dict[str, list] = {}
    for assignment in metrics.assignments:
        profile = config.profiles.get(assignment.profile_name)
        if profile is None or not profile.enabled:
            raise ValueError(
                f"metric assignment references unknown/disabled Profile "
                f"{assignment.profile_name!r}"
            )
        if assignment.device_name not in profile.device_order:
            raise ValueError(
                f"metric assignment Device {assignment.device_name!r} is not referenced "
                f"by Profile {assignment.profile_name!r}"
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

        assignments_by_profile.setdefault(
            assignment.profile_name,
            [],
        ).append(assignment)

    out: list[ProfileRouteIntent] = []
    for profile in config.profiles.values():
        if not profile.enabled:
            continue

        normal_routes: list[DirectRouteIntent] = []
        fallback_routes: list[FallbackRouteIntent] = []
        fallback_members = _profile_bound_members(config, profile.name, bindings)

        for destination in profile.destinations:
            for assignment in assignments_by_profile.get(profile.name, []):
                binding = binding_by_identity[assignment.identity]
                if binding.availability is Availability.UNAVAILABLE:
                    continue
                normal_routes.append(
                    DirectRouteIntent(
                        destination=destination,
                        identity=assignment.identity,
                        metric=assignment.metric,
                    )
                )

            if fallback_members:
                fallback_routes.append(
                    FallbackRouteIntent(
                        destination=destination,
                        members=fallback_members,
                    )
                )

        out.append(
            ProfileRouteIntent(
                profile_name=profile.name,
                normal_routes=tuple(normal_routes),
                fallback_routes=tuple(fallback_routes),
            )
        )

    return tuple(out)
