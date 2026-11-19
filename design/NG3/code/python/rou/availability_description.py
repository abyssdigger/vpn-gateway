"""Resolve Profile availability selection into concrete subject-specific probe intents."""

from __future__ import annotations

from typing import Iterable

from .binding import LogicalPathId
from .network_policy_layout import ProbePolicyOwner
from .probe_policy import AvailabilityProbeIntent, AvailabilityProbeMechanism
from .release1_config import AvailabilityCheckConfig, Release1Config


class AvailabilityDescriptionResolutionError(ValueError):
    pass


def resolve_availability_probe_intents(
    config: Release1Config,
    current_paths: Iterable[LogicalPathId],
) -> tuple[AvailabilityProbeIntent, ...]:
    """Purely resolve current Profile/path availability descriptions.

    Device defaults are copied into each Profile/path subject. They never create
    Device-global availability state.
    """
    if not isinstance(config, Release1Config):
        raise AvailabilityDescriptionResolutionError(
            "config must be Release1Config"
        )

    paths = tuple(current_paths)
    if any(not isinstance(path, LogicalPathId) for path in paths):
        raise AvailabilityDescriptionResolutionError(
            "current_paths must contain LogicalPathId"
        )
    if len(set(paths)) != len(paths):
        raise AvailabilityDescriptionResolutionError(
            "current_paths contains duplicates"
        )

    intents: list[AvailabilityProbeIntent] = []
    for profile_id in sorted(config.structural.profiles):
        structural = config.structural.profiles[profile_id]
        semantic = config.profiles[profile_id]
        if not structural.enabled:
            continue
        if (
            semantic.availability_check is None
            and not semantic.availability_uses_device_default
        ):
            continue

        allowed_devices = set(structural.device_order)
        for path in paths:
            if path.device_id not in allowed_devices:
                continue
            if path.device_id not in config.devices:
                raise AvailabilityDescriptionResolutionError(
                    f"current path references unknown Device {path.device_id!r}"
                )
            device_structural = config.structural.devices[path.device_id]
            if not device_structural.enabled:
                continue

            description = _description_for_subject(
                config,
                profile_id,
                path,
            )
            intents.append(
                AvailabilityProbeIntent(
                    owner=ProbePolicyOwner(profile_id, path),
                    target=description.target,
                    mechanism=AvailabilityProbeMechanism(
                        description.mechanism
                    ),
                )
            )

    return tuple(sorted(
        intents,
        key=lambda value: (
            value.owner.profile_id,
            value.owner.path_id,
            int(value.target),
        ),
    ))


def _description_for_subject(
    config: Release1Config,
    profile_id: str,
    path: LogicalPathId,
) -> AvailabilityCheckConfig:
    profile = config.profiles[profile_id]
    if profile.availability_uses_device_default:
        value = config.devices[path.device_id].availability_check
        if value is None:
            raise AvailabilityDescriptionResolutionError(
                f"Device {path.device_id!r} has no default availability description "
                f"required by Profile {profile_id!r}"
            )
        return value

    value = profile.availability_check
    if value is None:
        raise AvailabilityDescriptionResolutionError(
            f"Profile {profile_id!r} has no concrete availability description"
        )
    return value
