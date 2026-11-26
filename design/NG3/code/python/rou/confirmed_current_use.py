"""A.004 pure, current-generation evidence projection.

The caller admits one already-confirmed effective-policy reconciliation generation.
This module validates its cross-links; it cannot establish freshness or actuate policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .binding import LogicalPathId, PathBinding
from .domain import Direction
from .interface_identity import InterfaceIdentity
from .managed_wireguard_adapter import ManagedWireGuardObservation, ManagedWireGuardState
from .payload_profile import PayloadProfileRequest
from .release1_config import CurrentConfig, ManagedVpnKind
from .wireguard_peer_manager import WireGuardPeerRealization


class CurrentUseState(str, Enum):
    CONFIRMED = "confirmed"
    NONE = "none"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ConfirmedEffectiveUseContext:
    profiles: tuple[PayloadProfileRequest, ...]
    bindings: tuple[PathBinding, ...]
    expected_base_generations: Mapping[str, str]
    managed_base_observations: tuple[ManagedWireGuardObservation, ...]
    wireguard_peer_realizations: tuple[WireGuardPeerRealization, ...]

    def __post_init__(self) -> None:
        for name in (
            "profiles", "bindings", "managed_base_observations",
            "wireguard_peer_realizations",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(
            self, "expected_base_generations",
            MappingProxyType(dict(self.expected_base_generations)),
        )


@dataclass(frozen=True, slots=True)
class ConfirmedCurrentUse:
    profile_id: str
    state: CurrentUseState
    path_id: LogicalPathId | None = None
    endpoint: InterfaceIdentity | None = None
    managed_base_generation: str | None = None
    wireguard_generation: str | None = None
    wireguard_owner_peer_id: str | None = None


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _valid_path_key(path: object) -> bool:
    return (
        isinstance(path, LogicalPathId)
        and _text(path.device_id)
        and type(path.selector_index) is int
        and type(path.slot_index) is int
    )


def _binding_index(
    config: CurrentConfig, rows: tuple[PathBinding, ...],
) -> dict[LogicalPathId, list[PathBinding]] | None:
    """Index without last-wins. None denotes shared identity contradiction."""
    index: dict[LogicalPathId, list[PathBinding]] = {}
    by_name: dict[str, PathBinding] = {}
    by_ifindex: dict[int, PathBinding] = {}
    for row in rows:
        if (
            not isinstance(row, PathBinding)
            or not _valid_path_key(row.path_id)
            or not isinstance(row.endpoint, InterfaceIdentity)
            or row.path_id.device_id not in config.structural.devices
        ):
            return None
        prior = index.get(row.path_id, ())
        if prior and prior[0].endpoint != row.endpoint:
            return None
        # One live ifname/index cannot denote two distinct current paths or
        # two different endpoint identities in the same admitted generation.
        for previous in (
            by_name.get(row.endpoint.ifname), by_ifindex.get(row.endpoint.ifindex),
        ):
            if previous is not None and previous != row:
                return None
        by_name[row.endpoint.ifname] = row
        by_ifindex[row.endpoint.ifindex] = row
        index.setdefault(row.path_id, []).append(row)
    return index


def _exact_binding(
    config: CurrentConfig,
    path: LogicalPathId,
    members: tuple[str, ...],
    index: dict[LogicalPathId, list[PathBinding]],
) -> PathBinding | None:
    if not _valid_path_key(path) or path.device_id not in members:
        return None
    device = config.structural.devices.get(path.device_id)
    if device is None or not device.enabled:
        return None
    if not 0 <= path.selector_index < len(device.expected_interfaces):
        return None
    selector = device.expected_interfaces[path.selector_index]
    if not 0 <= path.slot_index < selector.quota:
        return None
    matches = index.get(path, ())
    if len(matches) != 1 or not selector.matches_name(matches[0].endpoint.ifname):
        return None
    return matches[0]


def _managed_proof(
    config: CurrentConfig,
    context: ConfirmedEffectiveUseContext,
    profile_id: str,
    binding: PathBinding,
) -> tuple[str, str, str] | None:
    device_id = binding.path_id.device_id
    base = config.managed_vpns[device_id]
    expected = context.expected_base_generations.get(device_id)
    observations = [
        row for row in context.managed_base_observations
        if row.device_id == device_id
    ]
    if not _text(expected) or len(observations) != 1:
        return None
    observation = observations[0]
    if (
        observation.state is not ManagedWireGuardState.PRESENT
        or observation.interface != binding.endpoint
        or not _text(observation.confirmed_generation)
        or observation.confirmed_generation != expected
    ):
        return None
    # Applicability comes from normalized configuration, not missing evidence.
    if base.kind is not ManagedVpnKind.WIREGUARD:
        return None
    group = config.wireguard_groups.get((profile_id, device_id))
    if group is None or (group.profile_id, group.device_id) != (profile_id, device_id):
        return None
    realizations = [
        row for row in context.wireguard_peer_realizations
        if row.device_id == device_id
    ]
    if len(realizations) != 1:
        return None
    realization = realizations[0]
    if (
        realization.problem is not None
        or not _text(realization.generation)
        or realization.base_generation != expected
        or realization.interface_ifname != binding.endpoint.ifname
        or realization.interface_ifindex != binding.endpoint.ifindex
    ):
        return None
    try:
        owner = realization.owner_for(profile_id)
    except KeyError:
        return None
    if not _text(owner) or owner not in {row.peer_id for row in group.peer_memberships}:
        return None
    return expected, realization.generation, owner


def project_confirmed_current_use(
    config: CurrentConfig,
    context: ConfirmedEffectiveUseContext | None,
) -> tuple[ConfirmedCurrentUse, ...]:
    """Produce current ordinary use, never structural demand or reclaim permission."""
    enabled = tuple(
        key for key, profile in sorted(config.structural.profiles.items())
        if profile.enabled
    )

    def unknown(key: str) -> ConfirmedCurrentUse:
        return ConfirmedCurrentUse(key, CurrentUseState.UNKNOWN)

    def all_unknown() -> tuple[ConfirmedCurrentUse, ...]:
        return tuple(unknown(key) for key in enabled)

    if context is None:
        return all_unknown()
    index = _binding_index(config, context.bindings)
    if index is None:
        return all_unknown()
    # Unidentifiable evidence is not part of a coherent shared envelope.
    if any(
        not isinstance(row, ManagedWireGuardObservation) or not _text(row.device_id)
        for row in context.managed_base_observations
    ) or any(
        not isinstance(row, WireGuardPeerRealization) or not _text(row.device_id)
        for row in context.wireguard_peer_realizations
    ):
        return all_unknown()

    requests: dict[str, list[PayloadProfileRequest]] = {}
    for row in context.profiles:
        if (
            not isinstance(row, PayloadProfileRequest)
            or not _text(row.profile_id)
            or row.profile_id not in enabled
        ):
            return all_unknown()
        requests.setdefault(row.profile_id, []).append(row)

    result: list[ConfirmedCurrentUse] = []
    for key in enabled:
        candidates = requests.get(key, ())
        if len(candidates) != 1:
            result.append(unknown(key))
            continue
        request = candidates[0]
        profile = config.structural.profiles[key]
        if (
            request.direction is not profile.direction
            or request.direction not in (
                Direction.OUTBOUND, Direction.INBOUND, Direction.BIDIRECTIONAL,
            )
            or request.destinations != profile.destinations
            or not isinstance(request.ordered_paths, tuple)
            or any(not _valid_path_key(path) for path in request.ordered_paths)
            or len(set(request.ordered_paths)) != len(request.ordered_paths)
            or (
                request.direction is not Direction.OUTBOUND
                and len(request.ordered_paths) > 1
            )
        ):
            result.append(unknown(key))
            continue
        # Validate effective request membership and binding structure, not
        # unselected managed base/group realization evidence.
        bindings = tuple(
            _exact_binding(config, path, profile.device_order, index)
            for path in request.ordered_paths
        )
        if any(row is None for row in bindings):
            result.append(unknown(key))
            continue
        if not bindings:
            result.append(ConfirmedCurrentUse(key, CurrentUseState.NONE))
            continue
        selected = bindings[0]
        assert selected is not None
        device_id = selected.path_id.device_id
        reserve = device_id in config.base.profiles[key].reserve_device_ids
        proof = (None, None, None)
        if device_id in config.managed_vpns:
            managed = _managed_proof(config, context, key, selected)
            if managed is None:
                result.append(unknown(key))
                continue
            proof = managed
        if reserve:
            result.append(ConfirmedCurrentUse(key, CurrentUseState.NONE))
        else:
            result.append(ConfirmedCurrentUse(
                key, CurrentUseState.CONFIRMED, selected.path_id, selected.endpoint,
                *proof,
            ))
    return tuple(result)
