"""One guarded combined NG3 nft convergence step for materialized owner classes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .composite_nft_plan import (
    CompositeNftMutationStep,
    CompositeNftPlanError,
    CompositeNftStepKind,
    select_composite_nft_step,
)
from .composite_nft_policy import (
    CompositeNftDesiredState,
    CompositeNftPolicyComparison,
    compare_composite_nft_policy,
)
from .device_firewall_desired import DeviceFirewallChainSpec
from .forwarding_gate import (
    ForwardingGateBackend,
    ForwardingGateExecutionResult,
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .interface_identity import InterfaceIdentity
from .local_publication_mutation import LocalPublicationMutationStep
from .nft_namespace_inventory import NftNamespaceObservation
from .payload_forward_desired import PayloadForwardRuleSpec
from .payload_nat_desired import PayloadMasqueradeSpec


@dataclass(frozen=True, slots=True)
class CompositeNftPhysicalSnapshot:
    observation: NftNamespaceObservation
    interfaces: tuple[InterfaceIdentity, ...]


class CompositeNftMutationBackend(Protocol):
    def observe_composite_snapshot(self) -> CompositeNftPhysicalSnapshot:
        """Return nft observation bracketed by stable fresh link inventories."""

    def delete_profile_rule(self, handle: int) -> None: ...
    def add_profile_rule(self, spec: PayloadForwardRuleSpec) -> None: ...
    def delete_device_jump(self, handle: int) -> None: ...
    def delete_device_child_chain(self, name: str) -> None: ...
    def create_device_chain(self, spec: DeviceFirewallChainSpec) -> None: ...
    def delete_nat_rule(self, handle: int) -> None: ...
    def add_nat_rule(self, spec: PayloadMasqueradeSpec) -> None: ...
    def apply_local_publication_step(
        self,
        step: LocalPublicationMutationStep,
    ) -> None: ...


class CompositeNftMutationStatus(str, Enum):
    CONFIRMED = "confirmed"
    STEP_APPLIED = "step_applied"
    BARRIER_FAILED = "barrier_failed"
    BARRIER_LOST = "barrier_lost"
    OBSERVATION_FAILED = "observation_failed"
    CONFLICT = "conflict"
    APPLY_FAILED = "apply_failed"
    POSTCONDITION_FAILED = "postcondition_failed"


@dataclass(frozen=True, slots=True)
class CompositeNftMutationResult:
    status: CompositeNftMutationStatus
    barrier: ForwardingGateExecutionResult
    initial: CompositeNftPolicyComparison | None
    final: CompositeNftPolicyComparison | None
    mutation_attempted: bool
    step: CompositeNftMutationStep | None = None
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status is CompositeNftMutationStatus.CONFIRMED
            and self.final is not None
            and self.final.desired_confirmed
        )


def converge_composite_nft_step_once(
    gate_backend: ForwardingGateBackend,
    nft_backend: CompositeNftMutationBackend,
    desired: CompositeNftDesiredState,
) -> CompositeNftMutationResult:
    if not isinstance(desired, CompositeNftDesiredState):
        raise ValueError("desired must be CompositeNftDesiredState")

    barrier = converge_forwarding_gate_once(
        gate_backend,
        ForwardingGateState.DISABLED,
    )

    def result(
        status: CompositeNftMutationStatus,
        initial: CompositeNftPolicyComparison | None = None,
        final: CompositeNftPolicyComparison | None = None,
        *,
        attempted: bool = False,
        step: CompositeNftMutationStep | None = None,
        diagnostic: str | None = None,
    ) -> CompositeNftMutationResult:
        return CompositeNftMutationResult(
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
            CompositeNftMutationStatus.BARRIER_FAILED,
            diagnostic="managed IPv4 forwarding barrier is not confirmed closed",
        )

    try:
        before = nft_backend.observe_composite_snapshot()
        initial = compare_composite_nft_policy(
            before.observation,
            before.interfaces,
            desired,
        )
    except ValueError as exc:
        return result(
            CompositeNftMutationStatus.CONFLICT,
            diagnostic=str(exc),
        )
    except Exception as exc:
        return result(
            CompositeNftMutationStatus.OBSERVATION_FAILED,
            diagnostic=(
                "initial composite nft observation failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if initial.desired_confirmed:
        if _gate_lost(gate_backend):
            return result(
                CompositeNftMutationStatus.BARRIER_LOST,
                initial,
                diagnostic="forwarding gate no longer closed",
            )
        return result(
            CompositeNftMutationStatus.CONFIRMED,
            initial,
            initial,
        )

    try:
        step = select_composite_nft_step(
            initial,
            desired.local_publication,
        )
    except CompositeNftPlanError as exc:
        return result(
            CompositeNftMutationStatus.CONFLICT,
            initial,
            diagnostic=str(exc),
        )
    if step is None:
        return result(
            CompositeNftMutationStatus.CONFLICT,
            initial,
            diagnostic="composite desired state is not confirmed but no safe step exists",
        )

    if _gate_lost(gate_backend):
        return result(
            CompositeNftMutationStatus.BARRIER_LOST,
            initial,
            step=step,
            diagnostic="forwarding barrier lost before composite nft write",
        )

    apply_error: Exception | None = None
    try:
        _apply_step(nft_backend, step)
    except Exception as exc:
        apply_error = exc

    final: CompositeNftPolicyComparison | None = None
    after: CompositeNftPhysicalSnapshot | None = None
    observation_error: Exception | None = None
    try:
        after = nft_backend.observe_composite_snapshot()
        final = compare_composite_nft_policy(
            after.observation,
            after.interfaces,
            desired,
        )
    except Exception as exc:
        observation_error = exc

    if _gate_lost(gate_backend):
        return result(
            CompositeNftMutationStatus.BARRIER_LOST,
            initial,
            final,
            attempted=True,
            step=step,
            diagnostic="forwarding barrier lost during composite nft write",
        )

    if observation_error is not None:
        return result(
            (
                CompositeNftMutationStatus.APPLY_FAILED
                if apply_error
                else CompositeNftMutationStatus.POSTCONDITION_FAILED
            ),
            initial,
            attempted=True,
            step=step,
            diagnostic=(
                "after-write composite observation failed: "
                f"{type(observation_error).__name__}: {observation_error}"
            ),
        )

    assert after is not None and final is not None
    if before.interfaces != after.interfaces or not _strict_progress(initial, final):
        return result(
            (
                CompositeNftMutationStatus.APPLY_FAILED
                if apply_error
                else CompositeNftMutationStatus.POSTCONDITION_FAILED
            ),
            initial,
            final,
            attempted=True,
            step=step,
            diagnostic=(
                "fresh composite postcondition did not make strict progress"
                + (
                    f"; apply error: {type(apply_error).__name__}: {apply_error}"
                    if apply_error
                    else ""
                )
            ),
        )

    return result(
        (
            CompositeNftMutationStatus.CONFIRMED
            if final.desired_confirmed
            else CompositeNftMutationStatus.STEP_APPLIED
        ),
        initial,
        final,
        attempted=True,
        step=step,
        diagnostic=(
            f"apply raised {type(apply_error).__name__}: {apply_error}; "
            "fresh composite postcondition independently made strict progress"
            if apply_error
            else None
        ),
    )


def _apply_step(
    backend: CompositeNftMutationBackend,
    step: CompositeNftMutationStep,
) -> None:
    if step.kind is CompositeNftStepKind.DELETE_PROFILE_RULE:
        assert step.handle is not None
        backend.delete_profile_rule(step.handle)
    elif step.kind is CompositeNftStepKind.ADD_PROFILE_RULE:
        assert step.profile_rule is not None
        backend.add_profile_rule(step.profile_rule)
    elif step.kind is CompositeNftStepKind.DELETE_DEVICE_JUMP:
        assert step.handle is not None
        backend.delete_device_jump(step.handle)
    elif step.kind is CompositeNftStepKind.DELETE_DEVICE_CHAIN:
        assert step.chain_name is not None
        backend.delete_device_child_chain(step.chain_name)
    elif step.kind is CompositeNftStepKind.CREATE_DEVICE_CHAIN:
        assert step.device_chain is not None
        backend.create_device_chain(step.device_chain)
    elif step.kind is CompositeNftStepKind.DELETE_NAT_RULE:
        assert step.handle is not None
        backend.delete_nat_rule(step.handle)
    elif step.kind is CompositeNftStepKind.ADD_NAT_RULE:
        assert step.nat_rule is not None
        backend.add_nat_rule(step.nat_rule)
    elif step.kind is CompositeNftStepKind.APPLY_LOCAL_PUBLICATION:
        assert step.local_publication_step is not None
        backend.apply_local_publication_step(
            step.local_publication_step
        )
    else:
        raise ValueError(f"unsupported composite nft step {step.kind!r}")


def _distance(value: CompositeNftPolicyComparison) -> int:
    return (
        len(value.profile_forward.missing)
        + len(value.profile_forward.stale)
        + len(value.payload_nat.missing)
        + len(value.payload_nat.stale)
        + len(value.device_firewall.missing)
        + len(value.device_firewall.stale_chains)
        + len(value.device_firewall.stale_jumps)
        + len(value.local_publication.missing)
        + len(value.local_publication.stale)
        + len(value.conflicts)
    )


def _strict_progress(
    before: CompositeNftPolicyComparison,
    after: CompositeNftPolicyComparison,
) -> bool:
    return (
        not after.conflicts
        and _distance(after) < _distance(before)
    )


def _gate_lost(gate_backend: ForwardingGateBackend) -> bool:
    try:
        return (
            gate_backend.observe_forwarding_gate()
            is not ForwardingGateState.DISABLED
        )
    except Exception:
        return True
