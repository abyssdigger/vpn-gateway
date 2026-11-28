"""A.012 runtime reclaim plan (not a lifecycle mutation authority by itself).

Architecture: A.012 ManagedDeviceManager.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from ipaddress import IPv4Network

from .accepted_effective_state import AcceptedEffectiveState, PreReclaimEvidence
from .binding import PathBinding
from .confirmed_current_use import CurrentUseState
from .interface_identity import InterfaceIdentity
from .managed_device_demand import project_final
from .managed_device_manager import (
    ManagedDeviceDesiredState, ManagedDeviceIntentBasis, ManagedDeviceRealization,
)
from .managed_reclaim_projection import ReclaimDecision, ReclaimProfile, ReclaimProjection, project_reclaim
from .managed_wireguard_adapter import ManagedWireGuardState
from .release1_config import CurrentConfig, ManagedReclaimPolicy
from .wireguard_peer_manager import WireGuardPeerRealization
from .wireguard_peer_ownership import (
    WireGuardPeerAllowedIPs, WireGuardPeerOwnershipDesired, WireGuardPeerOwnershipObservation,
)


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
    if (len(set(paths)) != len(paths)
            or len({b.endpoint.ifname for b in evidence.bindings}) != len(paths)
            or len({b.endpoint.ifindex for b in evidence.bindings}) != len(paths)
            or any(b.path_id.device_id not in config.structural.active_device_ids
                   for b in evidence.bindings)):
        raise ValueError("ambiguous pre-reclaim path identity")
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
        if sum(other.device_id == o.device_id for other in evidence.managed_base_observations) == 1
        and o.device_id not in evidence.unconfirmed_devices
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


@dataclass(frozen=True, slots=True)
class ExactEligibility:
    binding: PathBinding
    generation: str


def _exact_bindings(evidence: PreReclaimEvidence) -> frozenset[ExactEligibility]:
    """Require unique positive D.001 evidence cross-linked to the fresh C.004 path."""
    expected = dict(evidence.expected_base_generations)
    result = set()
    for binding in evidence.bindings:
        device_id = binding.path_id.device_id
        rows = [o for o in evidence.managed_base_observations if o.device_id == device_id]
        if device_id in evidence.unconfirmed_devices or len(rows) != 1:
            continue
        row = rows[0]
        if (row.state is ManagedWireGuardState.PRESENT
                and row.interface == binding.endpoint
                and row.confirmed_generation
                and row.confirmed_generation == expected.get(device_id)):
            # A conflicting physical realization is not exact eligibility.
            if any(o.device_id != device_id and o.interface is not None
                   and (o.interface.ifname == binding.endpoint.ifname
                        or o.interface.ifindex == binding.endpoint.ifindex)
                   for o in evidence.managed_base_observations):
                continue
            result.add(ExactEligibility(binding, row.confirmed_generation))
    return frozenset(result)


def recovery_eligibility_seed(plan: RuntimeReclaimPlan) -> frozenset[ExactEligibility]:
    allowed = exact_survivor_bindings(plan) | previously_admitted_deferred_bindings(plan)
    return frozenset(row for row in _exact_bindings(plan.evidence) if row.binding in allowed)


def replacement_managed_interfaces(plan: RuntimeReclaimPlan) -> frozenset[InterfaceIdentity]:
    """v1.3: independent structural eligibility plus retained exact identities."""
    assert plan.evidence.demand is not None
    structural = plan.evidence.demand.desired_device_ids
    retiring = {r.device_id for r in plan.projection.retirement_candidates}
    exact = _exact_bindings(plan.evidence)
    allowed = recovery_eligibility_seed(plan) | frozenset(
        row for row in exact if row.binding.path_id.device_id in structural
    )
    return frozenset(row.binding.endpoint for row in allowed
                     if row.binding.path_id.device_id not in retiring)


def recovery_managed_interfaces(
    config: CurrentConfig,
    evidence: PreReclaimEvidence,
    seed: frozenset[ExactEligibility],
) -> frozenset[InterfaceIdentity]:
    """Fresh eligibility only; does not compute or replay a retirement plan."""
    _validate_inventory(config, evidence)
    assert evidence.demand is not None
    demanded = evidence.demand.desired_device_ids
    return frozenset(
        row.binding.endpoint for row in _exact_bindings(evidence)
        if row.binding.path_id.device_id in demanded or row in seed
    )


def affected_profiles(plan: RuntimeReclaimPlan, candidate_id: str) -> frozenset[str]:
    return frozenset(
        p.profile_id for p in plan.profiles
        if any(c.device_id == candidate_id and c.fresh_path_count > 0
               for c in p.contributions)
    )


def affected_support_ids(plan: RuntimeReclaimPlan, candidate_id: str) -> frozenset[str]:
    affected = affected_profiles(plan, candidate_id)
    demand = plan.evidence.demand
    assert demand is not None
    result = {candidate_id}
    for p in plan.profiles:
        if p.profile_id in affected:
            result.update(p.managed_ordinary_ids | p.external_ordinary_ids)
    for p in demand.profiles:
        if p.profile_id in affected:
            result.update(p.reserve_device_ids)
    return frozenset(result)


def structural_retirement_precondition(
    plan: RuntimeReclaimPlan,
    config: CurrentConfig,
    fresh: PreReclaimEvidence,
    *,
    candidate_id: str,
    already_retired: frozenset[str],
    replacement_bindings: frozenset[PathBinding],
) -> bool:
    """Candidate-scoped C.004/D.001 half of the v1.4 guard.

    The caller independently verifies replacement policy and peer dependencies.
    Fixed floors come from the original plan, never from a pruned observation.
    """
    try:
        _validate_inventory(config, fresh)
    except ValueError:
        return False
    if config is not plan.config:
        return False
    retired = {row.device_id for row in plan.projection.retirement_candidates}
    if (candidate_id not in retired or candidate_id in already_retired
            or not already_retired <= retired or candidate_id in plan.mandatory_device_ids):
        return False
    assert fresh.demand is not None
    if candidate_id in fresh.demand.reserve_device_ids:
        return False
    if any(b.path_id.device_id in retired for b in replacement_bindings):
        return False
    affected = affected_profiles(plan, candidate_id)
    scope = affected_support_ids(plan, candidate_id)
    expected = frozenset(b for b in plan.evidence.bindings
                         if b.path_id.device_id in scope - already_retired)
    if frozenset(b for b in fresh.bindings if b.path_id.device_id in scope) != expected:
        return False
    if set(fresh.unconfirmed_devices) & scope != set(plan.evidence.unconfirmed_devices) & scope:
        return False
    old = plan.evidence.managed_base_observations
    new = fresh.managed_base_observations
    remaining = scope - already_retired
    if frozenset(o for o in old if o.device_id in remaining) != frozenset(
        o for o in new if o.device_id in remaining
    ):
        return False
    for device_id in already_retired & scope:
        observations = [o for o in new if o.device_id == device_id]
        if (len(observations) != 1 or observations[0].state is not ManagedWireGuardState.ABSENT
                or observations[0].interface is not None
                or observations[0].confirmed_generation is not None):
            return False
    if {d: g for d, g in fresh.expected_base_generations if d in scope} != {
        d: g for d, g in plan.evidence.expected_base_generations if d in remaining
    }:
        return False
    candidate = next(r for r in plan.projection.retirement_candidates if r.device_id == candidate_id)
    matches = [o for o in new if o.device_id == candidate_id]
    if (len(matches) != 1 or matches[0].state is not ManagedWireGuardState.PRESENT
            or matches[0].interface != candidate.interface
            or matches[0].confirmed_generation != candidate.generation
            or candidate_id in fresh.unconfirmed_devices):
        return False
    # Check relevant independent reserve support and fixed ordinary floors.
    old_demand = {p.profile_id: p for p in plan.evidence.demand.profiles}
    fresh_demand = {p.profile_id: p for p in fresh.demand.profiles}
    exact = {row.binding for row in _exact_bindings(fresh)}
    eligible = {b for b in replacement_bindings & expected
                if b.path_id.device_id not in config.managed_vpns or b in exact}
    floors = dict(plan.projection.floors)
    for profile in plan.profiles:
        if profile.profile_id not in affected:
            continue
        old_reserve = old_demand[profile.profile_id].reserve_device_ids
        if fresh_demand[profile.profile_id].reserve_device_ids != old_reserve:
            return False
        members = profile.managed_ordinary_ids | profile.external_ordinary_ids
        paths = {b.path_id for b in eligible if b.path_id.device_id in members}
        if len(paths) < floors[profile.profile_id]:
            return False
    return True


@dataclass(frozen=True, slots=True)
class ReclaimBatchOutcome:
    retired: frozenset[str]
    dependencies_touched: bool
    retirement_attempted: bool
    problem: str | None

    @property
    def requires_recovery(self) -> bool:
        return self.dependencies_touched or self.retirement_attempted


def execute_reclaim_batch(
    plan: RuntimeReclaimPlan,
    *,
    verify: Callable[[ReclaimDecision, frozenset[str], bool], bool],
    cleanup: Callable[[ReclaimDecision], bool],
    retire: Callable[[ReclaimDecision], None],
) -> ReclaimBatchOutcome:
    """Bounded ordering only; caller provides complete exact guards and operations.

    verify must include fresh replacement-policy/dependency, structural and
    protected peer realization checks. retire must raise unless exact absence
    has been confirmed. Caller must run one F2 recovery after any touch.
    """
    retired: set[str] = set()
    touched = attempted = False
    problem = None
    for candidate in plan.projection.retirement_candidates:
        try:
            if candidate.interface is None or not candidate.generation:
                raise RuntimeError("retirement decision lacks exact identity")
            if not verify(candidate, frozenset(retired), False):
                raise RuntimeError("pre-cleanup retirement guard failed")
            touched = True
            if not cleanup(candidate):
                raise RuntimeError("dependency cleanup unconfirmed")
            if not verify(candidate, frozenset(retired), True):
                raise RuntimeError("post-cleanup retirement guard failed")
            attempted = True
            retire(candidate)
            retired.add(candidate.device_id)
        except Exception as exc:
            problem = f"{candidate.device_id}: {type(exc).__name__}: {exc}"
            break
    return ReclaimBatchOutcome(frozenset(retired), touched, attempted, problem)


def _ownership_for(
    config: CurrentConfig,
    device_id: str,
    identity: InterfaceIdentity,
    group_owners: dict[str, str | None],
) -> WireGuardPeerOwnershipDesired:
    """Reconstruct the accepted D.002 realization's D.003 expected state."""
    base = config.managed_vpns[device_id]
    groups = {pid: group for (pid, did), group in config.wireguard_groups.items()
              if did == device_id}
    if groups.keys() != group_owners.keys():
        raise ValueError("peer realization does not cover exactly the configured groups")
    allowed = {p.peer_id: {IPv4Network(f"{p.probe_target}/32")} for p in base.peers}
    for pid, group in groups.items():
        owner = group_owners[pid]
        if owner is not None:
            if owner not in {m.peer_id for m in group.peer_memberships}:
                raise ValueError("peer owner is outside its configured group")
            allowed[owner].update(group.prefixes)
    return WireGuardPeerOwnershipDesired(
        device_id, identity, tuple(sorted(
            WireGuardPeerAllowedIPs(p.public_key, tuple(sorted(allowed[p.peer_id])))
            for p in base.peers
        )),
    )


def cleanup_ownership_desired(
    config: CurrentConfig, candidate: ReclaimDecision,
) -> WireGuardPeerOwnershipDesired:
    """Only permanent probe addresses remain on a retiring base."""
    if candidate.interface is None or not candidate.generation:
        raise ValueError("exact retirement identity required")
    return _ownership_for(config, candidate.device_id, candidate.interface, {
        pid: None for pid, did in config.wireguard_groups if did == candidate.device_id
    })


def _ownership_exact(
    desired: WireGuardPeerOwnershipDesired,
    observe: Callable[[WireGuardPeerOwnershipDesired], WireGuardPeerOwnershipObservation],
) -> bool:
    return observe(desired) == WireGuardPeerOwnershipObservation(
        desired.device_id, desired.interface, desired.peers)


def replacement_peer_ownership_exact(
    plan: RuntimeReclaimPlan,
    fresh: PreReclaimEvidence,
    replacement_bindings: frozenset[PathBinding],
    candidate_id: str,
    realizations: tuple[WireGuardPeerRealization, ...],
    observe: Callable[[WireGuardPeerOwnershipDesired], WireGuardPeerOwnershipObservation],
) -> bool:
    """Fresh read-only D.003 confirmation of accepted replacement peer owners.

    Preserve original careful use independently of the pruned current-use
    projection. The caller still must check C.001 policy and D.001 facts.
    """
    config = plan.config
    groups = {did for _, did in config.wireguard_groups}
    scope = affected_support_ids(plan, candidate_id) - {candidate_id}
    expected = {b.path_id.device_id: b for b in replacement_bindings
                if b.path_id.device_id in groups & scope}
    relevant = tuple(row for row in realizations if row.device_id in scope)
    peers = {row.device_id: row for row in relevant}
    if len(peers) != len(relevant) or peers.keys() != expected.keys():
        return False
    exact = _exact_bindings(fresh)
    try:
        for did, binding in expected.items():
            row = peers[did]
            if (row.problem is not None or not row.generation
                    or row.interface_ifname != binding.endpoint.ifname
                    or row.interface_ifindex != binding.endpoint.ifindex
                    or ExactEligibility(binding, row.base_generation) not in exact):
                return False
            desired = _ownership_for(config, did, binding.endpoint, {
                item.profile_id: item.owner_peer_id for item in row.group_owners
            })
            if not _ownership_exact(desired, observe):
                return False
        if config.managed_reclaim is ManagedReclaimPolicy.CAREFUL:
            # Any admitted managed current-use proof in the original snapshot
            # must retain its exact identity, peer owner and generation.
            for profile in plan.profiles:
                use = profile.current_use
                if (use is None or use.state is not CurrentUseState.CONFIRMED
                        or use.path_id is None
                        or use.path_id.device_id not in config.managed_vpns
                        or use.path_id.device_id not in scope):
                    continue
                did = use.path_id.device_id
                row = peers.get(did)
                if (row is None or PathBinding(use.path_id, use.endpoint)
                        not in replacement_bindings
                        or row.base_generation != use.managed_base_generation
                        or row.generation != use.wireguard_generation
                        or row.owner_for(profile.profile_id) != use.wireguard_owner_peer_id):
                    return False
        return True
    except Exception:
        return False


def project_managed_reclaim_realizations(
    config: CurrentConfig,
    evidence: PreReclaimEvidence,
    previous_realizations: tuple[ManagedDeviceRealization, ...],
    eligible_interfaces: frozenset[InterfaceIdentity],
    retirement_ids: frozenset[str] = frozenset(),
) -> tuple[ManagedDeviceRealization, ...]:
    """Non-mutating A.012 lifecycle intent for D.002 and status (v1.4).

    Structural demand remains in A.013; a PRESENT retention intent never
    causes a D.001 converge_present call. Explicit inactive/removed Device
    lifecycle rows are left with their original semantics.
    """
    _validate_inventory(config, evidence)
    assert evidence.demand is not None
    active = frozenset(config.managed_vpns) & config.structural.active_device_ids
    demanded = evidence.demand.desired_device_ids
    if not retirement_ids <= active or retirement_ids & evidence.demand.reserve_device_ids:
        raise ValueError("retirement outside ordinary reclaim scope")
    result = {row.device_id: row for row in previous_realizations}
    if len(result) != len(previous_realizations):
        raise ValueError("duplicate lifecycle realization")
    exact = {item.binding.path_id.device_id: item for item in _exact_bindings(evidence)}
    expected = dict(evidence.expected_base_generations)
    for device_id in sorted(active):
        old = result.get(device_id)
        rows = [o for o in evidence.managed_base_observations if o.device_id == device_id]
        observed = rows[0] if len(rows) == 1 and device_id not in evidence.unconfirmed_devices else None
        if (observed is not None and observed.state is ManagedWireGuardState.PRESENT
                and (not observed.confirmed_generation
                     or observed.confirmed_generation != expected.get(device_id))):
            observed = None
        path = exact.get(device_id)
        eligible = (
            device_id not in retirement_ids and path is not None
            and path.binding.endpoint in eligible_interfaces
        )
        if eligible:
            assert path is not None
            result[device_id] = ManagedDeviceRealization(
                device_id, ManagedDeviceDesiredState.PRESENT, path.generation,
                ManagedWireGuardState.PRESENT, path.generation,
                confirmed_interface=path.binding.endpoint,
                intent_basis=(ManagedDeviceIntentBasis.STRUCTURAL if device_id in demanded
                              else ManagedDeviceIntentBasis.RECLAIM_RETENTION),
                payload_eligible=True,
            )
            continue
        # Independent structural demand without exact eligible presence is
        # still structural, not a healthy reclaim hold or a new permission.
        if device_id in demanded and device_id not in retirement_ids:
            generation = expected.get(device_id)
            result[device_id] = ManagedDeviceRealization(
                device_id, ManagedDeviceDesiredState.PRESENT, generation,
                None if observed is None else observed.state,
                None if observed is None else observed.confirmed_generation,
                problem=(old.problem if old is not None and old.problem
                         else "structural presence not independently eligible"),
                confirmed_interface=None if observed is None else observed.interface,
                intent_basis=ManagedDeviceIntentBasis.STRUCTURAL,
                payload_eligible=False,
            )
            continue
        basis = (ManagedDeviceIntentBasis.RECLAIM_RETIREMENT if device_id in retirement_ids
                 else ManagedDeviceIntentBasis.RECLAIM_DEFERRED_HOLD)
        result[device_id] = ManagedDeviceRealization(
            device_id, ManagedDeviceDesiredState.ABSENT, None,
            None if observed is None else observed.state,
            None if observed is None else observed.confirmed_generation,
            waiting_for_dependencies=(device_id in retirement_ids and observed is not None
                                      and observed.state is ManagedWireGuardState.PRESENT),
            problem="exact managed realization unconfirmed" if observed is None else None,
            confirmed_interface=None if observed is None else observed.interface,
            intent_basis=basis, payload_eligible=False,
        )
    return tuple(result[d] for d in sorted(result))
