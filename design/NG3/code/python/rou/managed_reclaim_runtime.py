"""A.012 runtime reclaim plan (not a lifecycle mutation authority by itself).

Architecture: A.012 ManagedDeviceManager.
"""
from __future__ import annotations

from dataclasses import dataclass

from .accepted_effective_state import AcceptedEffectiveState, PreReclaimEvidence
from .binding import PathBinding
from .interface_identity import InterfaceIdentity
from .managed_device_demand import project_final
from .managed_reclaim_projection import ReclaimProfile, ReclaimProjection, project_reclaim
from .managed_wireguard_adapter import ManagedWireGuardState
from .release1_config import CurrentConfig


@dataclass(frozen=True, slots=True)
class RuntimeReclaimPlan:
    """One trigger's original inputs and exact decisions; never re-plan after pruning."""

    config: CurrentConfig
    evidence: PreReclaimEvidence
    profiles: tuple[ReclaimProfile, ...]
    mandatory_device_ids: frozenset[str]
    projection: ReclaimProjection
    previous_accepted: AcceptedEffectiveState | None


def _validate_inventory(config: CurrentConfig, evidence: PreReclaimEvidence) -> None:
    if evidence.observation_problem is not None or evidence.demand is None:
        raise ValueError("unconfirmed pre-reclaim inventory")
    paths = tuple(b.path_id for b in evidence.bindings)
    if len(set(paths)) != len(paths):
        raise ValueError("duplicate pre-reclaim path identity")
    if evidence.demand != project_final(config, evidence.bindings):
        raise ValueError("pre-reclaim demand does not match its bindings")
    if len(dict(evidence.expected_base_generations)) != len(evidence.expected_base_generations):
        raise ValueError("ambiguous desired generation inventory")


def build_runtime_reclaim_plan(
    config: CurrentConfig,
    evidence: PreReclaimEvidence,
    previous_accepted: AcceptedEffectiveState | None,
) -> RuntimeReclaimPlan:
    """Compose A.013, A.004 and D.001 without treating baseline demand as GC authority."""
    _validate_inventory(config, evidence)
    demand = evidence.demand
    assert demand is not None
    managed = frozenset(config.managed_vpns) & config.structural.active_device_ids
    use = {row.profile_id: row for row in evidence.current_use}
    enabled = {p for p, row in config.structural.profiles.items() if row.enabled}
    if len(use) != len(evidence.current_use) or not use.keys() <= enabled:
        raise ValueError("ambiguous current-use Profile inventory")

    profiles = []
    for row in demand.profiles:
        pid = row.profile_id
        members = frozenset(
            d for d in config.structural.profiles[pid].device_order
            if config.structural.devices[d].enabled
            and d not in config.profiles[pid].reserve_device_ids
        )
        profiles.append(ReclaimProfile(
            pid, row.regular_target, row.regular_present,
            row.external_ordinary_present, members & managed, members - managed,
            row.managed_ordinary_contributions, use.get(pid),
        ))

    # Reserve demand is the explicit non-GC presence obligation in this alpha.
    mandatory = demand.reserve_device_ids
    # Only exact admitted observations may back positive decisions. Preserve
    # omission as uncertainty; never manufacture an ABSENT observation.
    expected = dict(evidence.expected_base_generations)
    observations = tuple(
        o for o in evidence.managed_base_observations
        if o.device_id not in evidence.unconfirmed_devices
        and (o.state is ManagedWireGuardState.ABSENT or (
            o.confirmed_generation is not None
            and expected.get(o.device_id) == o.confirmed_generation
            and all(b.endpoint == o.interface for b in evidence.bindings
                    if b.path_id.device_id == o.device_id)
        ))
    )
    projection = project_reclaim(
        config.managed_reclaim, profiles=tuple(profiles), managed_device_ids=managed,
        observations=observations, mandatory_device_ids=mandatory,
    )
    return RuntimeReclaimPlan(config, evidence, tuple(profiles), mandatory,
                              projection, previous_accepted)


def exact_survivor_bindings(plan: RuntimeReclaimPlan) -> frozenset[PathBinding]:
    """Positive survivor exposure only; deferred/structural exceptions are separate."""
    survivors = {row.device_id: row.interface for row in plan.projection.survivors}
    return frozenset(
        b for b in plan.evidence.bindings
        if survivors.get(b.path_id.device_id) == b.endpoint
    )


def previously_admitted_deferred_bindings(
    plan: RuntimeReclaimPlan,
) -> frozenset[PathBinding]:
    """Deferral is not an authorization to widen prior exposure."""
    previous = plan.previous_accepted
    if previous is None:
        return frozenset()
    used_paths = {p for row in previous.profiles for p in row.ordered_paths}
    old_bindings = frozenset(previous.bindings)
    peer_rows = previous.wireguard_peer_realizations
    deferred = {row.device_id: row for row in plan.projection.deferred}
    result = set()
    for binding in plan.evidence.bindings:
        decision = deferred.get(binding.path_id.device_id)
        if (decision is None or decision.interface != binding.endpoint
                or not decision.generation or binding not in old_bindings
                or binding.path_id not in used_paths):
            continue
        peers = [p for p in peer_rows if p.device_id == decision.device_id]
        if len(peers) != 1:
            continue
        peer = peers[0]
        if (peer.problem is None and peer.generation
                and peer.base_generation == decision.generation
                and peer.interface_ifname == binding.endpoint.ifname
                and peer.interface_ifindex == binding.endpoint.ifindex):
            result.add(binding)
    return frozenset(result)
