"""Pure config-driven managed Device presence projection.

Architecture: A.013 ManagedDeviceDemandCalculator.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .binding import PathBinding
from .release1_config import CurrentConfig


@dataclass(frozen=True, slots=True)
class ManagedOrdinaryContribution:
    device_id: str
    fresh_path_count: int


@dataclass(frozen=True, slots=True)
class ProfileManagedDeviceDemand:
    profile_id: str
    regular_target: int
    regular_present: int
    regular_deficit: int
    reserve_present: int
    ordinary_device_ids: tuple[str, ...]
    reserve_device_ids: tuple[str, ...]
    # Absent candidates remain in baseline order for a bounded convergence
    # attempt to consider alternatives after a failed actuation.
    ordinary_candidates: tuple[str, ...]
    reserve_candidates: tuple[str, ...]
    # Fresh structural observation only; not survivor selection or retirement.
    external_ordinary_present: int
    managed_ordinary_contributions: tuple[ManagedOrdinaryContribution, ...]


@dataclass(frozen=True, slots=True)
class ManagedDeviceDemandProjection:
    profiles: tuple[ProfileManagedDeviceDemand, ...]
    ordinary_device_ids: frozenset[str]
    reserve_device_ids: frozenset[str]

    @property
    def desired_device_ids(self) -> frozenset[str]:
        return self.ordinary_device_ids | self.reserve_device_ids


def _select(
    config: CurrentConfig,
    members: tuple[str, ...],
    counts: Counter[str],
    target: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    # External paths already exist independently of demand. Count them before
    # retaining any managed capacity; among present managed Devices use baseline.
    remaining = max(
        0, target - sum(counts[d] for d in members if d not in config.managed_vpns)
    )
    chosen: list[str] = []
    for device_id in members:
        if remaining <= 0:
            break
        if device_id in config.managed_vpns and counts[device_id]:
            chosen.append(device_id)
            remaining -= counts[device_id]

    candidates = tuple(
        d for d in members if d in config.managed_vpns and not counts[d]
    )
    for device_id in candidates:
        if remaining <= 0:
            break
        chosen.append(device_id)
        remaining -= config.structural.devices[device_id].path_capacity
    return tuple(chosen), candidates


def _project(
    config: CurrentConfig,
    fresh_presence: Iterable[PathBinding],
    *,
    include_reserve: bool,
) -> ManagedDeviceDemandProjection:
    # The caller supplies an authoritative, quota-bounded fresh structural
    # projection, not a cached binding or a payload/availability verdict.
    path_ids = {binding.path_id for binding in fresh_presence}
    counts = Counter(path_id.device_id for path_id in path_ids)
    profiles: list[ProfileManagedDeviceDemand] = []
    ordinary_demand: set[str] = set()
    reserve_demand: set[str] = set()
    for profile_id, profile in sorted(config.structural.profiles.items()):
        if not profile.enabled:
            continue
        reserves = config.profiles[profile_id].reserve_device_ids
        members = tuple(
            d for d in profile.device_order if config.structural.devices[d].enabled
        )
        ordinary = tuple(d for d in members if d not in reserves)
        reserve = tuple(d for d in members if d in reserves)
        target = config.warm_target(profile_id)
        present = sum(counts[d] for d in ordinary)
        deficit = max(0, target - present)
        selected, candidates = _select(config, ordinary, counts, target)
        reserve_present = sum(counts[d] for d in reserve)
        if include_reserve and deficit:
            selected_reserve, reserve_candidates = _select(
                config, reserve, counts, deficit
            )
        else:
            selected_reserve, reserve_candidates = (), ()
        profiles.append(
            ProfileManagedDeviceDemand(
                profile_id, target, present, deficit, reserve_present,
                selected, selected_reserve, candidates, reserve_candidates,
                external_ordinary_present=sum(
                    counts[d] for d in ordinary if d not in config.managed_vpns
                ),
                managed_ordinary_contributions=tuple(
                    ManagedOrdinaryContribution(d, counts[d])
                    for d in ordinary if d in config.managed_vpns
                ),
            )
        )
        ordinary_demand.update(selected)
        reserve_demand.update(selected_reserve)
    return ManagedDeviceDemandProjection(
        tuple(profiles), frozenset(ordinary_demand), frozenset(reserve_demand)
    )


def project_regular(
    config: CurrentConfig, fresh_presence: Iterable[PathBinding]
) -> ManagedDeviceDemandProjection:
    """Project ordinary demand without reserve actuation."""
    return _project(config, fresh_presence, include_reserve=False)


def project_final(
    config: CurrentConfig, fresh_presence: Iterable[PathBinding]
) -> ManagedDeviceDemandProjection:
    """Project ordinary demand and the residual reserve exception."""
    return _project(config, fresh_presence, include_reserve=True)
