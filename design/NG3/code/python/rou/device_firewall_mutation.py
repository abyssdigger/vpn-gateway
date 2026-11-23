"""One guarded structural Device-firewall convergence step.

This bounded reference slice coexists with recognized Profile forward rules but
refuses NAT/local-system rule objects. It never re-enables forwarding.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Protocol

from .device_firewall_compare import (
    DeviceFirewallComparison,
    compare_device_firewall,
)
from .device_firewall_desired import (
    DeviceFirewallChainSpec,
    DeviceFirewallDesiredState,
)
from .device_firewall_structure import (
    DEVICE_FIREWALL_CHILD_COMMENT,
    DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
    DEVICE_FIREWALL_JUMP_COMMENT,
    DEVICE_FIREWALL_RULE_COMMENT,
)
from .forwarding_gate import (
    ForwardingGateDriver,
    ForwardingGateEnforcementResult,
    ForwardingGateState,
    converge_forwarding_gate_once,
    forwarding_gate_is_lost,
)
from .interface_identity import InterfaceIdentity
from .nft_namespace_inventory import NftNamespaceObject, NftNamespaceObservation
from .nft_payload_scaffold import (
    PAYLOAD_FORWARD_CHAIN,
    PAYLOAD_NFT_SCAFFOLD,
    compare_payload_nft_scaffold,
)
from .payload_forward_observation import (
    PAYLOAD_FORWARD_NEW_COMMENT,
    PAYLOAD_FORWARD_RETURN_COMMENT,
    observe_payload_forward,
)


@dataclass(frozen=True, slots=True)
class DeviceFirewallPhysicalSnapshot:
    observation: NftNamespaceObservation
    interfaces: tuple[InterfaceIdentity, ...]


class DeviceFirewallMutationDriver(Protocol):
    def observe_device_firewall_snapshot(self) -> DeviceFirewallPhysicalSnapshot:
        """Return nft observation bracketed by stable fresh link inventories."""

    def delete_device_jump(self, handle: int) -> None:
        """Delete one exact owned payload_forward jump by handle."""

    def delete_device_child_chain(self, name: str) -> None:
        """Flush and delete one exact owned Device firewall child chain."""

    def create_device_chain(self, spec: DeviceFirewallChainSpec) -> None:
        """Create one child chain/rules and insert its jump before Profile rules."""


class DeviceFirewallMutationStatus(str, Enum):
    CONFIRMED = "confirmed"
    STEP_APPLIED = "step_applied"
    BARRIER_FAILED = "barrier_failed"
    BARRIER_LOST = "barrier_lost"
    OBSERVATION_FAILED = "observation_failed"
    CONFLICT = "conflict"
    APPLY_FAILED = "apply_failed"
    POSTCONDITION_FAILED = "postcondition_failed"


@dataclass(frozen=True, slots=True)
class DeviceFirewallMutationResult:
    status: DeviceFirewallMutationStatus
    barrier: ForwardingGateEnforcementResult
    initial: DeviceFirewallComparison | None
    final: DeviceFirewallComparison | None
    mutation_attempted: bool
    step: str | None = None
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status is DeviceFirewallMutationStatus.CONFIRMED
            and self.final is not None
            and self.final.desired_confirmed
        )


class _OwnedScopeConflict(ValueError):
    pass


def _classify(
    snapshot: DeviceFirewallPhysicalSnapshot,
    desired: DeviceFirewallDesiredState,
) -> DeviceFirewallComparison:
    if not isinstance(snapshot, DeviceFirewallPhysicalSnapshot):
        raise _OwnedScopeConflict("invalid Device firewall physical snapshot")

    scaffold = compare_payload_nft_scaffold(snapshot.observation)
    if not scaffold.scaffold_confirmed:
        raise _OwnedScopeConflict(
            "owned invariant nft scaffold is not confirmed"
        )

    profile = observe_payload_forward(
        snapshot.observation,
        snapshot.interfaces,
    )
    if profile.conflicts:
        raise _OwnedScopeConflict(
            "payload_forward Profile rules have conflicts: "
            + "; ".join(item.reason for item in profile.conflicts)
        )

    comparison = compare_device_firewall(
        snapshot.observation,
        snapshot.interfaces,
        desired,
    )
    if comparison.conflicts:
        raise _OwnedScopeConflict(
            "Device firewall structural conflicts: "
            + "; ".join(item.reason for item in comparison.conflicts)
        )

    invariant_names = {spec.name for spec in PAYLOAD_NFT_SCAFFOLD}
    owned_child_names = {chain.name for chain in comparison.stale_chains}
    owned_child_names.update(chain.child_chain_name for chain in comparison.confirmed)
    # Missing desired chains may not exist yet; collect any structurally observed
    # owned child names directly from object comments below.

    for item in snapshot.observation.objects:
        payload = _object_payload(item)
        if item.kind == "chain":
            name = payload.get("name")
            if name in invariant_names:
                continue
            if payload.get("comment") == DEVICE_FIREWALL_CHILD_COMMENT:
                if isinstance(name, str) and name:
                    owned_child_names.add(name)
                    continue
            raise _OwnedScopeConflict(
                "bounded Device firewall mutation refuses unsupported nft chain"
            )

        if item.kind != "rule":
            raise _OwnedScopeConflict(
                "bounded Device firewall mutation refuses unsupported nft object"
            )

        chain = payload.get("chain")
        comment = payload.get("comment")
        if chain == PAYLOAD_FORWARD_CHAIN and comment in {
            PAYLOAD_FORWARD_NEW_COMMENT,
            PAYLOAD_FORWARD_RETURN_COMMENT,
            DEVICE_FIREWALL_JUMP_COMMENT,
        }:
            continue
        if (
            isinstance(chain, str)
            and chain in owned_child_names
            and comment in {
                DEVICE_FIREWALL_RULE_COMMENT,
                DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
            }
        ):
            continue

        # Deliberately bounded: NAT and local/system contributions are valid
        # elsewhere in NG3, but this reference slice refuses them rather than
        # pretending to provide whole-policy mutation safety.
        raise _OwnedScopeConflict(
            "bounded Device firewall mutation refuses other policy-chain rules"
        )

    return comparison


def converge_device_firewall_step_once(
    gate_backend: ForwardingGateDriver,
    firewall_backend: DeviceFirewallMutationDriver,
    desired: DeviceFirewallDesiredState,
) -> DeviceFirewallMutationResult:
    if not isinstance(desired, DeviceFirewallDesiredState):
        raise ValueError("desired must be DeviceFirewallDesiredState")

    barrier = converge_forwarding_gate_once(
        gate_backend,
        ForwardingGateState.DISABLED,
    )

    def result(
        status: DeviceFirewallMutationStatus,
        initial: DeviceFirewallComparison | None = None,
        final: DeviceFirewallComparison | None = None,
        *,
        attempted: bool = False,
        step: str | None = None,
        diagnostic: str | None = None,
    ) -> DeviceFirewallMutationResult:
        return DeviceFirewallMutationResult(
            status=status,
            barrier=barrier,
            initial=initial,
            final=final,
            mutation_attempted=attempted,
            step=step,
            diagnostic=diagnostic,
        )

    if not barrier.confirmed:
        return result(
            DeviceFirewallMutationStatus.BARRIER_FAILED,
            diagnostic="managed IPv4 forwarding barrier is not confirmed closed",
        )

    try:
        before = firewall_backend.observe_device_firewall_snapshot()
        initial = _classify(before, desired)
    except _OwnedScopeConflict as exc:
        return result(
            DeviceFirewallMutationStatus.CONFLICT,
            diagnostic=str(exc),
        )
    except Exception as exc:
        return result(
            DeviceFirewallMutationStatus.OBSERVATION_FAILED,
            diagnostic=(
                "initial Device firewall observation failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if initial.desired_confirmed:
        if forwarding_gate_is_lost(gate_backend):
            return result(
                DeviceFirewallMutationStatus.BARRIER_LOST,
                initial,
                diagnostic="forwarding gate no longer closed",
            )
        return result(
            DeviceFirewallMutationStatus.CONFIRMED,
            initial,
            initial,
        )

    if forwarding_gate_is_lost(gate_backend):
        return result(
            DeviceFirewallMutationStatus.BARRIER_LOST,
            initial,
            diagnostic="forwarding barrier lost before Device firewall write",
        )

    step: str
    apply_error: Exception | None = None

    if initial.stale_jumps:
        target = min(initial.stale_jumps, key=lambda item: item.source_order)
        step = f"delete-jump:{target.handle}"
        try:
            firewall_backend.delete_device_jump(target.handle)
        except Exception as exc:
            apply_error = exc
    elif initial.stale_chains:
        target = min(initial.stale_chains, key=lambda item: item.source_order)
        step = f"delete-chain:{target.name}"
        try:
            firewall_backend.delete_device_child_chain(target.name)
        except Exception as exc:
            apply_error = exc
    elif initial.missing:
        target = initial.missing[0]
        step = f"create-chain:{target.child_chain_name}"
        try:
            firewall_backend.create_device_chain(target)
        except Exception as exc:
            apply_error = exc
    else:
        return result(
            DeviceFirewallMutationStatus.CONFLICT,
            initial,
            diagnostic="unclassified Device firewall difference",
        )

    final: DeviceFirewallComparison | None = None
    observation_error: Exception | None = None
    try:
        after = firewall_backend.observe_device_firewall_snapshot()
        final = _classify(after, desired)
    except Exception as exc:
        observation_error = exc

    if forwarding_gate_is_lost(gate_backend):
        return result(
            DeviceFirewallMutationStatus.BARRIER_LOST,
            initial,
            final,
            attempted=True,
            step=step,
            diagnostic="forwarding barrier lost during Device firewall write",
        )

    if observation_error is not None:
        return result(
            (
                DeviceFirewallMutationStatus.APPLY_FAILED
                if apply_error
                else DeviceFirewallMutationStatus.POSTCONDITION_FAILED
            ),
            initial,
            attempted=True,
            step=step,
            diagnostic=(
                "after-write observation/classification failed: "
                f"{type(observation_error).__name__}: {observation_error}"
            ),
        )

    assert final is not None

    if not _strict_progress(initial, final):
        return result(
            (
                DeviceFirewallMutationStatus.APPLY_FAILED
                if apply_error
                else DeviceFirewallMutationStatus.POSTCONDITION_FAILED
            ),
            initial,
            final,
            attempted=True,
            step=step,
            diagnostic=(
                "fresh Device firewall postcondition did not make strict progress"
                + (
                    f"; apply error: {type(apply_error).__name__}: {apply_error}"
                    if apply_error
                    else ""
                )
            ),
        )

    return result(
        (
            DeviceFirewallMutationStatus.CONFIRMED
            if final.desired_confirmed
            else DeviceFirewallMutationStatus.STEP_APPLIED
        ),
        initial,
        final,
        attempted=True,
        step=step,
        diagnostic=(
            f"apply raised {type(apply_error).__name__}: {apply_error}; "
            "fresh postcondition independently made strict progress"
            if apply_error
            else None
        ),
    )


def _strict_progress(
    before: DeviceFirewallComparison,
    after: DeviceFirewallComparison,
) -> bool:
    before_distance = (
        len(before.missing)
        + len(before.stale_chains)
        + len(before.stale_jumps)
    )
    after_distance = (
        len(after.missing)
        + len(after.stale_chains)
        + len(after.stale_jumps)
    )
    return (
        not after.conflicts
        and after_distance < before_distance
    )




def _object_payload(item: NftNamespaceObject) -> dict:
    try:
        row = json.loads(item.canonical_json)
    except (TypeError, ValueError):
        raise _OwnedScopeConflict("malformed reserved nft object") from None
    if (
        not isinstance(row, dict)
        or set(row) != {item.kind}
        or not isinstance(row[item.kind], dict)
    ):
        raise _OwnedScopeConflict("malformed reserved nft object")
    return row[item.kind]
