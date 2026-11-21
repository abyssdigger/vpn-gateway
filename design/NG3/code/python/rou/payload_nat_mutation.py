"""One guarded read/one write/read NAT-only convergence step.

This is a bounded reference slice. It refuses all other nft table objects and
never re-enables the managed forwarding gate. It is not full structural policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Protocol

from .forwarding_gate import (
    ForwardingGateDriver, ForwardingGateEnforcementResult,
    ForwardingGateState, converge_forwarding_gate_once,
)
from .interface_identity import InterfaceIdentity
from .nft_namespace_inventory import NftNamespaceObject, NftNamespaceObservation
from .nft_payload_scaffold import PAYLOAD_POSTROUTING_CHAIN, compare_payload_nft_scaffold
from .payload_nat_desired import PayloadMasqueradeSpec, PayloadNatDesiredState
from .payload_nat_observation import (
    PayloadNatComparison, PayloadNatObservationError, compare_payload_nat,
)


@dataclass(frozen=True, slots=True)
class PayloadNatPhysicalSnapshot:
    observation: NftNamespaceObservation
    interfaces: tuple[InterfaceIdentity, ...]


class PayloadNatMutationBackend(Protocol):
    def observe_nat_snapshot(self) -> PayloadNatPhysicalSnapshot:
        """Return nft observation bracketed by stable fresh link inventories."""

    def add_nat_rule(self, spec: PayloadMasqueradeSpec) -> None:
        """Issue one exact-ifindex NAT add; successful return is not confirmation."""

    def delete_nat_rule(self, handle: int) -> None:
        """Issue one exact-handle delete; successful return is not confirmation."""


class PayloadNatMutationStatus(str, Enum):
    CONFIRMED = "confirmed"
    STEP_APPLIED = "step_applied"
    BARRIER_FAILED = "barrier_failed"
    BARRIER_LOST = "barrier_lost"
    OBSERVATION_FAILED = "observation_failed"
    CONFLICT = "conflict"
    APPLY_FAILED = "apply_failed"
    POSTCONDITION_FAILED = "postcondition_failed"


@dataclass(frozen=True, slots=True)
class PayloadNatMutationResult:
    status: PayloadNatMutationStatus
    barrier: ForwardingGateEnforcementResult
    initial: PayloadNatComparison | None
    final: PayloadNatComparison | None
    mutation_attempted: bool
    step: str | None = None
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status is PayloadNatMutationStatus.CONFIRMED
            and self.final is not None
            and not self.final.missing
            and not self.final.stale
            and self.final.conflict_free
        )


class _OwnedScopeConflict(ValueError):
    pass


def _classify(
    snapshot: PayloadNatPhysicalSnapshot,
    desired: PayloadNatDesiredState,
) -> PayloadNatComparison:
    if not isinstance(snapshot, PayloadNatPhysicalSnapshot):
        raise _OwnedScopeConflict("invalid NAT physical snapshot")
    scaffold = compare_payload_nft_scaffold(snapshot.observation)
    if not scaffold.scaffold_confirmed:
        raise _OwnedScopeConflict("owned invariant nft scaffold is not confirmed")
    try:
        comparison = compare_payload_nat(
            snapshot.observation, snapshot.interfaces, desired,
        )
    except (PayloadNatObservationError, ValueError) as exc:
        raise _OwnedScopeConflict(str(exc)) from None
    if comparison.conflicts:
        raise _OwnedScopeConflict(
            "owned payload NAT chain has conflicts: "
            + "; ".join(item.reason for item in comparison.conflicts)
        )
    for item in scaffold.unclassified_objects:
        if item.kind != "rule":
            raise _OwnedScopeConflict("unsupported nft object in reserved table")
        try:
            payload = json.loads(item.canonical_json)["rule"]
        except (TypeError, ValueError, KeyError):
            raise _OwnedScopeConflict("malformed reserved nft rule") from None
        if not isinstance(payload, dict) or payload.get("chain") != PAYLOAD_POSTROUTING_CHAIN:
            raise _OwnedScopeConflict(
                "NAT-only reference refuses other policy-chain rules"
            )
    return comparison


def _nat_rule_by_handle(
    objects: tuple[NftNamespaceObject, ...],
    handle: int,
) -> NftNamespaceObject:
    matches = []
    for item in objects:
        if item.kind != "rule":
            continue
        payload = json.loads(item.canonical_json)["rule"]
        if payload.get("handle") == handle:
            matches.append(item)
    if len(matches) != 1:
        raise _OwnedScopeConflict("stale rule handle not uniquely present")
    return matches[0]


def _exact_step_postcondition(
    before: PayloadNatPhysicalSnapshot,
    after: PayloadNatPhysicalSnapshot,
    comparison: PayloadNatComparison,
    *,
    deleted_handle: int | None,
    added: PayloadMasqueradeSpec | None,
) -> bool:
    if before.interfaces != after.interfaces:
        return False
    old = set(before.observation.objects)
    new = set(after.observation.objects)
    if deleted_handle is not None:
        target = _nat_rule_by_handle(before.observation.objects, deleted_handle)
        return new == old - {target}
    if added is not None:
        introduced = new - old
        return (
            old <= new
            and len(introduced) == 1
            and next(iter(introduced)).kind == "rule"
            and added in comparison.confirmed
        )
    return False


def converge_payload_nat_step_once(
    gate_backend: ForwardingGateDriver,
    nat_backend: PayloadNatMutationBackend,
    desired: PayloadNatDesiredState,
) -> PayloadNatMutationResult:
    """One fail-closed NAT mutation attempt; never re-enable forwarding.

    A caller may request another step only from a fresh authoritative snapshot.
    The result cannot be promoted to whole-policy or forwarding activation.
    """
    if not isinstance(desired, PayloadNatDesiredState):
        raise ValueError("desired must be PayloadNatDesiredState")
    barrier = converge_forwarding_gate_once(gate_backend, ForwardingGateState.DISABLED)

    def result(
        status: PayloadNatMutationStatus,
        initial: PayloadNatComparison | None = None,
        final: PayloadNatComparison | None = None,
        *,
        attempted: bool = False,
        step: str | None = None,
        diagnostic: str | None = None,
    ) -> PayloadNatMutationResult:
        return PayloadNatMutationResult(
            status, barrier, initial, final, attempted, step, diagnostic,
        )

    if not barrier.confirmed:
        return result(PayloadNatMutationStatus.BARRIER_FAILED,
                      diagnostic="managed IPv4 forwarding barrier is not confirmed closed")
    try:
        before = nat_backend.observe_nat_snapshot()
        initial = _classify(before, desired)
    except _OwnedScopeConflict as exc:
        return result(PayloadNatMutationStatus.CONFLICT, diagnostic=str(exc))
    except Exception as exc:
        return result(PayloadNatMutationStatus.OBSERVATION_FAILED,
                      diagnostic=f"initial NAT observation failed: {type(exc).__name__}: {exc}")

    if not initial.stale and not initial.missing:
        try:
            gate = gate_backend.observe_forwarding_gate()
        except Exception as exc:
            return result(PayloadNatMutationStatus.BARRIER_LOST, initial,
                          diagnostic=f"final gate observation failed: {exc}")
        if gate is not ForwardingGateState.DISABLED:
            return result(PayloadNatMutationStatus.BARRIER_LOST, initial,
                          diagnostic="forwarding gate no longer closed")
        return result(PayloadNatMutationStatus.CONFIRMED, initial, initial)

    try:
        gate = gate_backend.observe_forwarding_gate()
    except Exception as exc:
        return result(PayloadNatMutationStatus.BARRIER_LOST, initial,
                      diagnostic=f"pre-write gate observation failed: {exc}")
    if gate is not ForwardingGateState.DISABLED:
        return result(PayloadNatMutationStatus.BARRIER_LOST, initial,
                      diagnostic="forwarding barrier lost before NAT write")

    deleted_handle: int | None = None
    added: PayloadMasqueradeSpec | None = None
    apply_error: Exception | None = None
    if initial.stale:
        deleted_handle = min(item.handle for item in initial.stale)
        step = f"delete:{deleted_handle}"
        try:
            nat_backend.delete_nat_rule(deleted_handle)
        except Exception as exc:
            apply_error = exc
    else:
        added = min(
            initial.missing,
            key=lambda spec: (
                spec.ingress.ifindex, spec.egress.ifindex, repr(spec.path_id),
            ),
        )
        step = f"add:{added.ingress.ifindex}:{added.egress.ifindex}"
        try:
            nat_backend.add_nat_rule(added)
        except Exception as exc:
            apply_error = exc

    after = None
    final = None
    observation_error: Exception | None = None
    try:
        after = nat_backend.observe_nat_snapshot()
        final = _classify(after, desired)
    except Exception as exc:
        observation_error = exc
    # Gate re-observation is mandatory even when nft re-observation failed.
    # No successful or failed command is authorization to open forwarding.
    try:
        final_gate = gate_backend.observe_forwarding_gate()
    except Exception as exc:
        return result(PayloadNatMutationStatus.BARRIER_LOST, initial, final,
                      attempted=True, step=step,
                      diagnostic=f"final forwarding-gate observation failed: {exc}")
    if final_gate is not ForwardingGateState.DISABLED:
        return result(PayloadNatMutationStatus.BARRIER_LOST, initial, final,
                      attempted=True, step=step,
                      diagnostic="forwarding barrier lost during NAT write")
    if observation_error is not None:
        return result(
            PayloadNatMutationStatus.APPLY_FAILED if apply_error else
            PayloadNatMutationStatus.POSTCONDITION_FAILED,
            initial, attempted=True, step=step,
            diagnostic=(
                "after-write observation/classification failed: "
                f"{type(observation_error).__name__}: {observation_error}"
            ),
        )
    assert after is not None and final is not None

    if not _exact_step_postcondition(
        before, after, final,
        deleted_handle=deleted_handle, added=added,
    ):
        return result(
            PayloadNatMutationStatus.APPLY_FAILED if apply_error else
            PayloadNatMutationStatus.POSTCONDITION_FAILED,
            initial, final, attempted=True, step=step,
            diagnostic="fresh whole-owned-scope postcondition mismatch"
            + (f"; apply error: {type(apply_error).__name__}: {apply_error}" if apply_error else ""),
        )

    complete = not final.missing and not final.stale
    return result(
        PayloadNatMutationStatus.CONFIRMED if complete else
        PayloadNatMutationStatus.STEP_APPLIED,
        initial, final, attempted=True, step=step,
        diagnostic=(
            f"apply raised {type(apply_error).__name__}: {apply_error}; "
            "exact postcondition independently confirmed"
        ) if apply_error else None,
    )
