"""A.012 runtime reclaim plan (not a lifecycle mutation authority by itself).

Architecture: A.012 ManagedDeviceManager.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .accepted_effective_state import AcceptedEffectiveState, PreReclaimEvidence
from .binding import PathBinding
from .interface_identity import InterfaceIdentity
from .managed_device_demand import project_final
from .managed_reclaim_projection import ReclaimDecision, ReclaimProfile, ReclaimProjection, project_reclaim
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


def structural_retirement_precondition(
    plan: RuntimeReclaimPlan,
    config: CurrentConfig,
    fresh: PreReclaimEvidence,
    *,
    already_retired: frozenset[str],
    replacement_bindings: frozenset[PathBinding],
) -> bool:
    """Check the preserved original inventory and eligible retained capacity.

    This is only the C.004/D.001/structural half of the guard. The caller must
    independently verify current replacement policy, dependencies and protected
    peer-owner evidence before and after D.003 cleanup.
    """
    try:
        _validate_inventory(config, fresh)
    except ValueError:
        return False
    if config is not plan.config:
        return False
    retired = {row.device_id for row in plan.projection.retirement_candidates}
    if not already_retired <= retired:
        return False
    if any(b.path_id.device_id in retired for b in replacement_bindings):
        return False
    # Only the deletion of already-confirmed retired identities is expected.
    original = frozenset(plan.evidence.bindings)
    expected = frozenset(b for b in original if b.path_id.device_id not in already_retired)
    if frozenset(fresh.bindings) != expected:
        return False
    if fresh.unconfirmed_devices != plan.evidence.unconfirmed_devices:
        return False
    old = plan.evidence.managed_base_observations
    new = fresh.managed_base_observations
    if frozenset(o for o in old if o.device_id not in already_retired) != frozenset(
        o for o in new if o.device_id not in already_retired
    ):
        return False
    for device_id in already_retired:
        observations = [o for o in new if o.device_id == device_id]
        if (len(observations) != 1 or observations[0].state is not ManagedWireGuardState.ABSENT
                or observations[0].interface is not None
                or observations[0].confirmed_generation is not None):
            return False
    if dict(fresh.expected_base_generations) != {
        d: generation for d, generation in plan.evidence.expected_base_generations
        if d not in already_retired
    }:
        return False
    assert fresh.demand is not None
    if fresh.demand.reserve_device_ids != plan.mandatory_device_ids:
        return False
    # Every retained managed contribution counted toward the floor must have
    # an exact confirmed identity and be present in the replacement policy.
    # A physical hold by itself supplies no policy capacity.
    exact = {row.binding for row in _exact_bindings(fresh)}
    eligible = {b for b in replacement_bindings & expected
                if b.path_id.device_id not in config.managed_vpns or b in exact}
    floors = dict(plan.projection.floors)
    for profile in plan.profiles:
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
    verify: Callable[[ReclaimDecision, frozenset[str]], bool],
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
            if not verify(candidate, frozenset(retired)):
                raise RuntimeError("pre-cleanup retirement guard failed")
            touched = True
            if not cleanup(candidate):
                raise RuntimeError("dependency cleanup unconfirmed")
            if not verify(candidate, frozenset(retired)):
                raise RuntimeError("post-cleanup retirement guard failed")
            attempted = True
            retire(candidate)
            retired.add(candidate.device_id)
        except Exception as exc:
            problem = f"{candidate.device_id}: {type(exc).__name__}: {exc}"
            break
    return ReclaimBatchOutcome(frozenset(retired), touched, attempted, problem)
