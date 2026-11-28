"""A.012 pure reclaim selection over a caller-admitted current snapshot.

No observation, actuation, dependency release or structural-demand mutation.
The caller owns freshness/completeness of the admitted Profile and realization
inventory, including A.004's effective-policy/peer-generation evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .binding import LogicalPathId
from .confirmed_current_use import ConfirmedCurrentUse, CurrentUseState
from .interface_identity import InterfaceIdentity
from .managed_device_demand import ManagedOrdinaryContribution
from .managed_wireguard_adapter import (
    ManagedWireGuardObservation, ManagedWireGuardState,
)
from .release1_config import ManagedReclaimPolicy


@dataclass(frozen=True, slots=True)
class ReclaimProfile:
    """Normalized enabled Profile facts; contribution rows include zeros.

    Membership sets come from normalized configuration, the counts from A.013.
    The redundant observed total detects incomplete/contradictory count rows.
    A missing current_use is unresolved, not NONE.
    """

    profile_id: str
    ordinary_target: int
    ordinary_present: int
    external_ordinary_present: int
    managed_ordinary_ids: frozenset[str]
    external_ordinary_ids: frozenset[str]
    contributions: tuple[ManagedOrdinaryContribution, ...]
    current_use: ConfirmedCurrentUse | None


class ReclaimReason(str, Enum):
    MANDATORY = "mandatory"
    CURRENT_USE = "current_use"
    CAPACITY = "capacity_floor"
    SURPLUS = "surplus"
    IDENTITY = "unconfirmed_identity"
    USE = "unconfirmed_use"
    STRUCTURE = "inconsistent_structure"
    COVERAGE = "unconfirmed_coverage"


@dataclass(frozen=True, slots=True)
class ReclaimDecision:
    device_id: str
    interface: InterfaceIdentity | None
    generation: str | None
    reason: ReclaimReason


@dataclass(frozen=True, slots=True)
class ReclaimProjection:
    survivors: tuple[ReclaimDecision, ...]
    retirement_candidates: tuple[ReclaimDecision, ...]
    deferred: tuple[ReclaimDecision, ...]
    floors: tuple[tuple[str, int], ...]


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _ids(value: object) -> bool:
    return isinstance(value, frozenset) and all(_text(x) for x in value)


def _count(value: object) -> bool:
    return type(value) is int and value >= 0


def _current_use(
    row: ReclaimProfile,
    present: dict[str, ManagedWireGuardObservation],
    counts: dict[str, int],
) -> tuple[bool, str | None]:
    use = row.current_use
    if not isinstance(use, ConfirmedCurrentUse) or use.profile_id != row.profile_id:
        return False, None
    proof = (use.managed_base_generation, use.wireguard_generation,
             use.wireguard_owner_peer_id)
    if use.state is CurrentUseState.NONE:
        return (use.path_id is None and use.endpoint is None
                and all(x is None for x in proof)), None
    if use.state is not CurrentUseState.CONFIRMED:
        return False, None
    path = use.path_id
    if (not isinstance(path, LogicalPathId)
            or not _text(path.device_id)
            or not _count(path.selector_index) or not _count(path.slot_index)
            or not isinstance(use.endpoint, InterfaceIdentity)):
        return False, None
    d = path.device_id
    if d in row.external_ordinary_ids:
        # A.004 external ordinary use has no managed generation proof.
        return (row.external_ordinary_present > 0
                and all(x is None for x in proof)
                and all(o.interface is not None
                        and o.interface.ifname != use.endpoint.ifname
                        and o.interface.ifindex != use.endpoint.ifindex
                        for o in present.values())), None
    observation = present.get(d)
    if (d not in counts or counts[d] <= 0 or observation is None
            or observation.interface != use.endpoint
            or observation.confirmed_generation != use.managed_base_generation
            or not all(_text(x) for x in proof)):
        return False, None
    return True, d


def _isolated(
    devices: set[str], counts: dict[str, int], need: int, used: set[str],
) -> set[str]:
    """Exact minimum count, then maximum use; stable ID resolves remaining ties."""
    if need <= 0:
        return set()
    ranked = sorted((counts[d] for d in devices), reverse=True)
    total = 0
    for k, capacity in enumerate(ranked, 1):
        total += capacity
        if total >= need:
            break
    else:
        raise ValueError("isolated floor is not attainable")

    def feasible(pool: set[str], slots: int, sticky: int, residual: int) -> bool:
        if not 0 <= sticky <= slots:
            return False
        yes = sorted((counts[d] for d in pool if d in used), reverse=True)
        no = sorted((counts[d] for d in pool if d not in used), reverse=True)
        other = slots - sticky
        return (len(yes) >= sticky and len(no) >= other
                and sum(yes[:sticky]) + sum(no[:other]) >= residual)

    preferred = next(u for u in range(min(k, len(devices & used)), -1, -1)
                     if feasible(devices, k, u, need))
    result: set[str] = set()
    pool = set(devices)
    for d in sorted(devices):
        pool.remove(d)
        sticky = int(d in used)
        if feasible(pool, k - 1, preferred - sticky, need - counts[d]):
            result.add(d)
            k -= 1
            preferred -= sticky
            need -= counts[d]
    assert k == 0 and need <= 0
    return result


def _shared(
    devices: set[str], vectors: dict[str, dict[str, int]],
    residuals: dict[str, int], used: set[str],
) -> set[str]:
    """Deterministic residual-cover heuristic, then irreducible pruning.

    No global set-cover optimum is claimed. Prefer use on equal coverage,
    prune unused first, and try improving equal-count one-for-one exchanges.
    """
    selected: set[str] = set()
    remaining = dict(residuals)
    while any(remaining.values()):
        def gain(d: str) -> int:
            return sum(min(vectors[p].get(d, 0), n) for p, n in remaining.items())
        d = min(devices - selected, key=lambda x: (-gain(x), x not in used, x))
        if gain(d) <= 0:
            raise ValueError("shared floor is not attainable")
        selected.add(d)
        remaining = {p: max(0, n - vectors[p].get(d, 0))
                     for p, n in remaining.items()}

    def covers(items: set[str]) -> bool:
        return all(sum(vectors[p].get(d, 0) for d in items) >= n
                   for p, n in residuals.items())

    def prune() -> None:
        for d in sorted(selected, key=lambda x: (x in used, x), reverse=False):
            if covers(selected - {d}):
                selected.remove(d)

    prune()
    # Every accepted swap either increases retained use at the same count or,
    # after pruning, decreases count. The finite lexicographic objective improves.
    while True:
        exchange = next(((old, new)
                         for old in sorted(selected - used)
                         for new in sorted((devices & used) - selected)
                         if covers((selected - {old}) | {new})), None)
        if exchange is None:
            return selected
        old, new = exchange
        selected.remove(old)
        selected.add(new)
        prune()


def project_reclaim(
    policy: ManagedReclaimPolicy,
    *,
    profiles: tuple[ReclaimProfile, ...],
    managed_device_ids: frozenset[str],
    observations: tuple[ManagedWireGuardObservation, ...],
    mandatory_device_ids: frozenset[str] = frozenset(),
) -> ReclaimProjection:
    """Project exact present survivors / candidates and scoped unresolved facts.

    All enabled Profiles and all eligible managed Device IDs must be supplied.
    An explicit ABSENT observation is not a reclaim subject. Missing/unconfirmed
    observations are deferred. Unidentifiable envelope errors reject the whole
    call; identifiable bad Profile facts never authorize retirement of its members.
    No returned decision implies dependency release or authority to actuate.
    """
    if not isinstance(policy, ManagedReclaimPolicy):
        raise ValueError("normalized reclaim policy required")
    if (not _ids(managed_device_ids) or not _ids(mandatory_device_ids)
            or not mandatory_device_ids <= managed_device_ids):
        raise ValueError("invalid managed/mandatory inventory")
    if (not isinstance(profiles, tuple) or not isinstance(observations, tuple)
            or any(not isinstance(p, ReclaimProfile) or not _text(p.profile_id)
                   for p in profiles)
            or len({p.profile_id for p in profiles}) != len(profiles)):
        raise ValueError("unidentifiable or duplicate Profile inventory")
    grouped: dict[str, list[ManagedWireGuardObservation]] = {}
    for o in observations:
        if (not isinstance(o, ManagedWireGuardObservation)
                or o.device_id not in managed_device_ids):
            raise ValueError("observation outside managed inventory")
        grouped.setdefault(o.device_id, []).append(o)

    present: dict[str, ManagedWireGuardObservation] = {}
    absent: set[str] = set()
    deferred: dict[str, ReclaimReason] = {}
    for d in sorted(managed_device_ids):
        rows = grouped.get(d, [])
        if len(rows) == 1:
            o = rows[0]
            if (o.state is ManagedWireGuardState.ABSENT
                    and o.interface is None and o.confirmed_generation is None):
                absent.add(d)
                continue
            if (o.state is ManagedWireGuardState.PRESENT
                    and isinstance(o.interface, InterfaceIdentity)
                    and _text(o.confirmed_generation)):
                present[d] = o
                continue
        deferred[d] = ReclaimReason.IDENTITY

    # Neither ifname nor ifindex may identify two different live Devices.
    names: dict[str, set[str]] = {}
    indices: dict[int, set[str]] = {}
    for d, rows in grouped.items():
        # Even an ambiguous/unconfirmed observation can contradict an otherwise
        # valid identity; ignoring its endpoint would authorize the latter.
        for o in rows:
            if isinstance(o.interface, InterfaceIdentity):
                names.setdefault(o.interface.ifname, set()).add(d)
                indices.setdefault(o.interface.ifindex, set()).add(d)
    for group in (*names.values(), *indices.values()):
        if len(group) > 1:
            for d in group:
                deferred[d] = ReclaimReason.IDENTITY
                present.pop(d, None)

    reason_priority = {
        ReclaimReason.USE: 0,
        ReclaimReason.COVERAGE: 1,
        ReclaimReason.STRUCTURE: 2,
        ReclaimReason.IDENTITY: 3,
    }

    def defer(ids: frozenset[str] | set[str], reason: ReclaimReason) -> None:
        for d in ids:
            if d not in absent and (
                d not in deferred
                or reason_priority[reason] > reason_priority[deferred[d]]
            ):
                deferred[d] = reason

    # Cross-check positive A.004 claims across the admitted snapshot. One
    # physical endpoint cannot belong to another logical Device, and D.002
    # generation is Device-wide (the Profile-local peer owner may differ).
    # This detects contradictions, not freshness of an isolated claim.
    bad_use_profiles: set[str] = set()
    use_by_device: dict[str, list[ConfirmedCurrentUse]] = {}
    for row in profiles:
        members = row.managed_ordinary_ids
        if (not _ids(members) or not members <= managed_device_ids
                or not _ids(row.external_ordinary_ids)
                or row.external_ordinary_ids & managed_device_ids):
            raise ValueError("unidentifiable Profile membership")
        u = row.current_use
        if (not isinstance(u, ConfirmedCurrentUse)
                or u.profile_id != row.profile_id
                or u.state is not CurrentUseState.CONFIRMED
                or not isinstance(u.path_id, LogicalPathId)
                or not _text(u.path_id.device_id)
                or not isinstance(u.endpoint, InterfaceIdentity)):
            continue
        d = u.path_id.device_id
        aliases = (names.get(u.endpoint.ifname, set())
                   | indices.get(u.endpoint.ifindex, set())) - {d}
        if aliases:
            bad_use_profiles.add(row.profile_id)
            defer(aliases, ReclaimReason.USE)
        if d in managed_device_ids:
            if d in absent:
                absent.remove(d)
                deferred[d] = ReclaimReason.IDENTITY
            if d not in members:
                bad_use_profiles.add(row.profile_id)
                defer({d}, ReclaimReason.USE)
            o = present.get(d)
            if (o is not None and o.interface == u.endpoint
                    and o.confirmed_generation == u.managed_base_generation
                    and _text(u.wireguard_generation)
                    and _count(u.path_id.selector_index)
                    and _count(u.path_id.slot_index)):
                use_by_device.setdefault(d, []).append(u)
    for d, claims in use_by_device.items():
        if len({(u.path_id, u.wireguard_generation) for u in claims}) > 1:
            bad_use_profiles.update(u.profile_id for u in claims)
            defer({d}, ReclaimReason.USE)

    vectors: dict[str, dict[str, int]] = {}
    floors: dict[str, int] = {}
    external: dict[str, int] = {}
    used: set[str] = set()
    for row in sorted(profiles, key=lambda p: p.profile_id):
        members = row.managed_ordinary_ids
        counts: dict[str, int] = {}
        valid = (isinstance(row.contributions, tuple)
                 and all(_count(x) for x in (
                     row.ordinary_target, row.ordinary_present,
                     row.external_ordinary_present)))
        if valid:
            for item in row.contributions:
                if (not isinstance(item, ManagedOrdinaryContribution)
                        or not _text(item.device_id)
                        or item.device_id not in members
                        or item.device_id in counts
                        or not _count(item.fresh_path_count)):
                    valid = False
                    break
                counts[item.device_id] = item.fresh_path_count
        if (not valid or set(counts) != members
                or row.external_ordinary_present + sum(counts.values())
                   != row.ordinary_present
                or (row.external_ordinary_present and not row.external_ordinary_ids)):
            defer(members, ReclaimReason.STRUCTURE)
            continue
        # A claimed positive count contradicts an explicit ABSENT observation.
        for d in members & absent:
            if counts[d]:
                absent.remove(d)
                deferred[d] = ReclaimReason.IDENTITY
        p = row.profile_id
        floors[p] = min(row.ordinary_target, row.ordinary_present)
        external[p] = row.external_ordinary_present
        vectors[p] = {d: n for d, n in counts.items() if d in present and n}
        ok, selected = _current_use(row, present, counts)
        if not ok or p in bad_use_profiles:
            # A.004 UNKNOWN is per Profile, not per global inventory.
            defer(members, ReclaimReason.USE)
        elif selected is not None:
            used.add(selected)

    # A valid known identity with an uncertain use decision stays physically
    # present; it can supply its independently confirmed structural contribution.
    # Never count an unconfirmed realization as guaranteed capacity.
    for p, counts in vectors.items():
        if external[p] + sum(counts.values()) < floors[p]:
            defer(set(counts), ReclaimReason.COVERAGE)

    mandatory = set(mandatory_device_ids) & present.keys()
    protected = used if policy is ManagedReclaimPolicy.CAREFUL else set()
    # Independently proven hard retention resolves a use-only ambiguity, but
    # never an invalid identity or structural observation.
    for d in mandatory | protected:
        if deferred.get(d) is ReclaimReason.USE:
            del deferred[d]

    hard = mandatory | protected | (set(deferred) & present.keys())
    optional = set(present) - hard
    residuals = {
        p: max(0, floor - external[p]
               - sum(vectors[p].get(d, 0) for d in hard))
        for p, floor in floors.items()
    }
    # Unprovable floors stay in the public result. They can leave the
    # optimization problem only after every exact positive contributor has
    # been made non-retirable above. Never silently drop an impossible floor
    # while an optional contributor remains.
    for p, n in tuple(residuals.items()):
        if not n:
            del residuals[p]
            continue
        available = sum(vectors[p].get(d, 0) for d in optional)
        if n > available:
            if available:
                raise ValueError("unresolved floor has optional contributors")
            del residuals[p]
    # Split the residual bipartite graph into independent components.
    pending = set(residuals)
    selected: set[str] = set()
    while pending:
        component = {min(pending)}
        devices: set[str] = set()
        while True:
            expanded_devices = {d for p in component for d in vectors[p]
                                if d in optional}
            expanded_profiles = {p for p in pending
                                 if expanded_devices & vectors[p].keys()}
            if expanded_devices == devices and expanded_profiles <= component:
                break
            devices = expanded_devices
            component |= expanded_profiles
        pending -= component
        if len(component) == 1:
            p = next(iter(component))
            selected |= _isolated(devices, vectors[p], residuals[p], used)
        else:
            selected |= _shared(devices, vectors,
                                {p: residuals[p] for p in component}, used)

    def decision(d: str, reason: ReclaimReason) -> ReclaimDecision:
        o = present.get(d)
        return ReclaimDecision(d, o.interface if o else None,
                               o.confirmed_generation if o else None, reason)

    survivors = tuple(decision(
        d, ReclaimReason.MANDATORY if d in mandatory else
        ReclaimReason.CURRENT_USE if d in protected else ReclaimReason.CAPACITY)
        for d in sorted((hard | selected) - deferred.keys()))
    retirement = tuple(decision(d, ReclaimReason.SURPLUS)
                       for d in sorted(optional - selected))
    return ReclaimProjection(survivors, retirement,
                             tuple(decision(d, deferred[d]) for d in sorted(deferred)),
                             tuple(sorted(floors.items())))
