"""Runtime admission of effective current-use and pre-reclaim structural facts.

Architecture: A.004 PayloadTrafficManager, A.012 ManagedDeviceManager.

No reclaim decision or policy/lifecycle mutation is performed here. The caller
serializes the normal trigger and owns the actual policy-confirmation boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .binding import PathBinding
from .confirmed_current_use import (
    ConfirmedCurrentUse, ConfirmedEffectiveUseContext, project_confirmed_current_use,
)
from .managed_device_demand import ManagedDeviceDemandProjection, project_final
from .managed_device_manager import ManagedDeviceManager
from .managed_wireguard_adapter import ManagedWireGuardObservation
from .payload_profile import PayloadProfileRequest
from .release1_config import CurrentConfig
from .wireguard_peer_manager import WireGuardPeerRealization


@dataclass(frozen=True, slots=True)
class AcceptedEffectiveState:
    profiles: tuple[PayloadProfileRequest, ...]
    bindings: tuple[PathBinding, ...]
    wireguard_peer_realizations: tuple[WireGuardPeerRealization, ...]

    def __post_init__(self) -> None:
        for name in ("profiles", "bindings", "wireguard_peer_realizations"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class PreReclaimEvidence:
    """Diagnostic facts for this trigger, not a current retirement authorization.

    A.013's full fresh structural inventory remains separate from exact
    D.001 confirmation. Missing confirmations are not absence.
    """
    bindings: tuple[PathBinding, ...]
    demand: ManagedDeviceDemandProjection | None
    expected_base_generations: tuple[tuple[str, str], ...]
    managed_base_observations: tuple[ManagedWireGuardObservation, ...]
    current_use: tuple[ConfirmedCurrentUse, ...]
    unconfirmed_devices: tuple[str, ...] = ()
    observation_problem: str | None = None


def observe_pre_reclaim(
    config: CurrentConfig,
    previous_accepted: AcceptedEffectiveState | None,
    manager: ManagedDeviceManager,
    observe_bindings: Callable[[], tuple[PathBinding, ...]],
) -> PreReclaimEvidence:
    """Read all-interface C.004 and exact D.001; never converge a Device."""
    try:
        bindings = tuple(observe_bindings())
        demand = project_final(config, bindings)
    except Exception as exc:
        return PreReclaimEvidence(
            (), None, (), (), project_confirmed_current_use(config, None),
            observation_problem=type(exc).__name__,
        )

    expected: dict[str, str] = {}
    observations: list[ManagedWireGuardObservation] = []
    problems: list[str] = []
    for device_id in sorted(set(config.managed_vpns) & config.structural.active_device_ids):
        try:
            generation, observation = manager.observe_exact_base(config, device_id)
        except Exception:
            problems.append(device_id)
            continue
        if generation is not None:
            expected[device_id] = generation
        observations.append(observation)

    context = None
    if previous_accepted is not None:
        # The full fresh binding inventory is for structural demand. A.004
        # may only use an exact binding previously confirmed AND still present.
        # Do not deduplicate the accepted rows; the existing A.004 validator
        # must still see duplicate admitted identities as ambiguous.
        fresh = set(bindings)
        admitted = tuple(row for row in previous_accepted.bindings if row in fresh)
        context = ConfirmedEffectiveUseContext(
            previous_accepted.profiles, admitted, expected, tuple(observations),
            previous_accepted.wireguard_peer_realizations,
        )
    use = project_confirmed_current_use(config, context)
    return PreReclaimEvidence(
        bindings, demand, tuple(sorted(expected.items())), tuple(observations),
        use, tuple(problems),
    )
