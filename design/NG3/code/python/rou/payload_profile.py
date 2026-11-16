from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network
from typing import Iterable

from .binding import LogicalPathId, PathBinding
from .domain import Direction, ProfileStructuralIntent


class PayloadProfileProjectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PayloadProfileRequest:
    profile_id: str
    direction: Direction
    destinations: tuple[IPv4Network, ...]
    ordered_paths: tuple[LogicalPathId, ...]


def build_payload_profile_requests(
    profiles: Iterable[ProfileStructuralIntent],
    bindings: Iterable[PathBinding],
) -> tuple[PayloadProfileRequest, ...]:
    """Build structural Profile requests from current accepted logical path bindings."""
    ordered_profiles = tuple(sorted(profiles, key=lambda profile: profile.profile_id))
    current_bindings = tuple(bindings)
    _validate_inputs(ordered_profiles, current_bindings)

    paths_by_device: dict[str, list[LogicalPathId]] = {}
    for binding in current_bindings:
        paths_by_device.setdefault(binding.path_id.device_id, []).append(binding.path_id)
    for paths in paths_by_device.values():
        paths.sort(key=lambda path: (path.selector_index, path.slot_index))

    requests: list[PayloadProfileRequest] = []
    for profile in ordered_profiles:
        if not profile.enabled:
            continue
        if profile.direction is None:
            raise PayloadProfileProjectionError(
                f"enabled Profile {profile.profile_id!r} has no direction"
            )

        ordered_paths = tuple(
            path
            for device_id in profile.device_order
            for path in paths_by_device.get(device_id, ())
        )
        requests.append(
            PayloadProfileRequest(
                profile_id=profile.profile_id,
                direction=profile.direction,
                destinations=profile.destinations,
                ordered_paths=ordered_paths,
            )
        )

    return tuple(requests)


def _validate_inputs(
    profiles: tuple[ProfileStructuralIntent, ...],
    bindings: tuple[PathBinding, ...],
) -> None:
    profile_ids: set[str] = set()
    for profile in profiles:
        if profile.profile_id in profile_ids:
            raise PayloadProfileProjectionError(
                f"duplicate ProfileStructuralIntent for {profile.profile_id!r}"
            )
        profile_ids.add(profile.profile_id)

    path_ids: set[LogicalPathId] = set()
    for binding in bindings:
        if binding.path_id in path_ids:
            raise PayloadProfileProjectionError(
                f"duplicate current logical path binding {binding.path_id!r}"
            )
        path_ids.add(binding.path_id)
