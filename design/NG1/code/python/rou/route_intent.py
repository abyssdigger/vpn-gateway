from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from .domain import ActiveConfig
from .metrics import BLACKHOLE_METRIC
from .traffic_state import TrafficProjection


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


def _binding_index(
    bindings: DeviceBindingSnapshot,
) -> dict[InterfaceIdentity, BoundInterface]:
    out: dict[InterfaceIdentity, BoundInterface] = {}
    for binding in bindings.bound:
        if binding.identity in out:
            raise ValueError(f"duplicate bound interface identity {binding.identity!r}")
        out[binding.identity] = binding
    return out


def compile_profile_route_intents(
    config: ActiveConfig,
    bindings: DeviceBindingSnapshot,
    metrics: TrafficProjection,
) -> tuple[ProfileRouteIntent, ...]:
    """Compile the baseline Profile payload-route intent.

    The baseline is deliberately independent of future availability mechanics: every
    metric-assigned bound interface contributes its deterministic normal route, and every
    Profile retains one terminal blackhole.

    A future Profile-binding control layer may suppress Profile-specific materialization
    for a concrete (Profile, binding) pair, but it must do so outside DeviceEngine and
    without introducing a shadow payload fallback tier.
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
        for destination in profile.destinations:
            for assignment in assignments_by_profile.get(profile.name, []):
                normal_routes.append(
                    DirectRouteIntent(
                        destination=destination,
                        identity=assignment.identity,
                        metric=assignment.metric,
                    )
                )

        out.append(
            ProfileRouteIntent(
                profile_name=profile.name,
                normal_routes=tuple(normal_routes),
            )
        )

    return tuple(out)
