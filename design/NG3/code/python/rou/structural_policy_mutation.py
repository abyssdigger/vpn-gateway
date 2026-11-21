"""Guarded one-step cross-domain structural NetworkPolicy convergence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .composite_nft_mutation import apply_composite_nft_step
from .composite_nft_policy import (
    CompositeNftDesiredState,
    CompositeNftPolicyComparison,
    compare_composite_nft_policy,
)
from .device_firewall_desired import DeviceFirewallChainSpec
from .forwarding_gate import (
    ForwardingGateDriver,
    ForwardingGateEnforcementResult,
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .interface_identity import InterfaceIdentity
from .local_integration_mutation import IntegrationLocalMutationStep
from .local_publication_mutation import LocalPublicationMutationStep
from .probe_local_mutation import ProbeLocalMutationStep
from .network_policy_layout import NetworkPolicyPlatformSpace
from .nft_namespace_inventory import (
    NftNamespaceObservation,
    NftNamespaceStatus,
)
from .nft_payload_scaffold import compare_payload_nft_scaffold
from .payload_forward_desired import PayloadForwardRuleSpec
from .payload_nat_desired import PayloadMasqueradeSpec
from .payload_routing_compare import (
    PayloadRoutingComparison,
    compare_payload_routing,
)
from .payload_routing_desired import (
    ManagedRouteSpec,
    ManagedRuleSpec,
    PayloadRoutingDesiredState,
)
from .structural_policy_plan import (
    StructuralPolicyMutationStep,
    StructuralPolicyPlanError,
    StructuralPolicyStepKind,
    select_structural_policy_step,
)
from .structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
    StructuralRoutingObservation,
)


@dataclass(frozen=True, slots=True)
class StructuralPolicyPhysicalSnapshot:
    interfaces: tuple[InterfaceIdentity, ...]
    routing: StructuralRoutingObservation
    nft: NftNamespaceObservation


@dataclass(frozen=True, slots=True)
class StructuralPolicyComparison:
    routing: PayloadRoutingComparison
    nft: CompositeNftPolicyComparison

    @property
    def desired_confirmed(self) -> bool:
        return self.routing.confirmed and self.nft.desired_confirmed


class StructuralPolicyMutationBackend(Protocol):
    def observe_structural_snapshot(self) -> StructuralPolicyPhysicalSnapshot:
        """Observe route/RPDB+nft inside one stable link-identity bracket."""

    def add_route(self, spec: ManagedRouteSpec) -> None: ...
    def delete_route(self, route: ObservedManagedRoute) -> None: ...
    def add_rule(self, spec: ManagedRuleSpec) -> None: ...
    def delete_rule(self, rule: ObservedManagedRule) -> None: ...

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
    def apply_integration_local_step(
        self,
        step: IntegrationLocalMutationStep,
    ) -> None: ...
    def apply_probe_local_step(
        self,
        step: ProbeLocalMutationStep,
    ) -> None: ...


class StructuralPolicyPreconditionError(ValueError):
    pass


class StructuralPolicyConflictError(ValueError):
    pass


class StructuralPolicyMutationStatus(str, Enum):
    CONFIRMED = "confirmed"
    PRECONDITION_FAILED = "precondition_failed"
    STEP_APPLIED = "step_applied"
    BARRIER_FAILED = "barrier_failed"
    BARRIER_LOST = "barrier_lost"
    OBSERVATION_FAILED = "observation_failed"
    CONFLICT = "conflict"
    APPLY_FAILED = "apply_failed"
    POSTCONDITION_FAILED = "postcondition_failed"
    ACTIVATION_FAILED = "activation_failed"
    FINAL_VERIFICATION_FAILED = "final_verification_failed"
    SAFETY_RECLOSE_FAILED = "safety_reclose_failed"


@dataclass(frozen=True, slots=True)
class StructuralPolicyMutationResult:
    status: StructuralPolicyMutationStatus
    barrier: ForwardingGateEnforcementResult
    initial: StructuralPolicyComparison | None
    final: StructuralPolicyComparison | None
    mutation_attempted: bool
    step: StructuralPolicyMutationStep | None = None
    activation: ForwardingGateEnforcementResult | None = None
    safety_reclose: ForwardingGateEnforcementResult | None = None
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status is StructuralPolicyMutationStatus.CONFIRMED
            and self.final is not None
            and self.final.desired_confirmed
            and self.activation is not None
            and self.activation.confirmed
            and self.activation.desired is ForwardingGateState.ENABLED
        )


def compare_structural_policy(
    snapshot: StructuralPolicyPhysicalSnapshot,
    routing_desired: PayloadRoutingDesiredState,
    nft_desired: CompositeNftDesiredState,
    platform: NetworkPolicyPlatformSpace,
) -> StructuralPolicyComparison:
    if not isinstance(snapshot, StructuralPolicyPhysicalSnapshot):
        raise ValueError("snapshot must be StructuralPolicyPhysicalSnapshot")

    scaffold = compare_payload_nft_scaffold(snapshot.nft)
    if (
        scaffold.namespace_status is NftNamespaceStatus.CONFLICT
        or scaffold.conflicts
    ):
        reason = (
            scaffold.conflicts[0].reason
            if scaffold.conflicts
            else "reserved nft namespace ownership conflict"
        )
        raise StructuralPolicyConflictError(reason)
    if not scaffold.scaffold_confirmed:
        raise StructuralPolicyPreconditionError(
            "invariant nft scaffold is not confirmed"
        )

    try:
        routing = compare_payload_routing(
            routing_desired,
            snapshot.routing,
            platform,
        )
        nft = compare_composite_nft_policy(
            snapshot.nft,
            snapshot.interfaces,
            nft_desired,
        )
    except ValueError as exc:
        raise StructuralPolicyConflictError(str(exc)) from exc

    return StructuralPolicyComparison(
        routing=routing,
        nft=nft,
    )


def converge_structural_policy_step_once(
    gate_backend: ForwardingGateDriver,
    backend: StructuralPolicyMutationBackend,
    routing_desired: PayloadRoutingDesiredState,
    nft_desired: CompositeNftDesiredState,
    platform: NetworkPolicyPlatformSpace,
) -> StructuralPolicyMutationResult:
    """Perform at most one structural write, then activate only from exact state.

    No hidden retry loop is used. A caller may invoke this again after STEP_APPLIED,
    and every invocation replans from a fresh whole-scope observation.
    """
    if not isinstance(routing_desired, PayloadRoutingDesiredState):
        raise ValueError("routing_desired must be PayloadRoutingDesiredState")
    if not isinstance(nft_desired, CompositeNftDesiredState):
        raise ValueError("nft_desired must be CompositeNftDesiredState")
    if not isinstance(platform, NetworkPolicyPlatformSpace):
        raise ValueError("platform must be NetworkPolicyPlatformSpace")

    barrier = converge_forwarding_gate_once(
        gate_backend,
        ForwardingGateState.DISABLED,
    )

    def result(
        status: StructuralPolicyMutationStatus,
        initial: StructuralPolicyComparison | None = None,
        final: StructuralPolicyComparison | None = None,
        *,
        attempted: bool = False,
        step: StructuralPolicyMutationStep | None = None,
        activation: ForwardingGateEnforcementResult | None = None,
        safety_reclose: ForwardingGateEnforcementResult | None = None,
        diagnostic: str | None = None,
    ) -> StructuralPolicyMutationResult:
        return StructuralPolicyMutationResult(
            status=status,
            barrier=barrier,
            initial=initial,
            final=final,
            mutation_attempted=attempted,
            step=step,
            activation=activation,
            safety_reclose=safety_reclose,
            diagnostic=diagnostic,
        )

    if not barrier.confirmed:
        return result(
            StructuralPolicyMutationStatus.BARRIER_FAILED,
            diagnostic="managed IPv4 forwarding barrier is not confirmed closed",
        )

    try:
        before = backend.observe_structural_snapshot()
        initial = compare_structural_policy(
            before,
            routing_desired,
            nft_desired,
            platform,
        )
    except StructuralPolicyPreconditionError as exc:
        return result(
            StructuralPolicyMutationStatus.PRECONDITION_FAILED,
            diagnostic=str(exc),
        )
    except StructuralPolicyConflictError as exc:
        return result(
            StructuralPolicyMutationStatus.CONFLICT,
            diagnostic=str(exc),
        )
    except Exception as exc:
        return result(
            StructuralPolicyMutationStatus.OBSERVATION_FAILED,
            diagnostic=(
                "initial structural observation failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if initial.desired_confirmed:
        return _activate_exact(
            gate_backend,
            backend,
            routing_desired,
            nft_desired,
            platform,
            before,
            initial,
            initial,
            result,
        )

    try:
        step = select_structural_policy_step(
            initial.routing,
            initial.nft,
            nft_desired,
        )
    except StructuralPolicyPlanError as exc:
        return result(
            StructuralPolicyMutationStatus.CONFLICT,
            initial,
            diagnostic=str(exc),
        )
    if step is None:
        return result(
            StructuralPolicyMutationStatus.CONFLICT,
            initial,
            diagnostic="structural state is not exact but no safe step exists",
        )

    if _gate_lost(gate_backend):
        return result(
            StructuralPolicyMutationStatus.BARRIER_LOST,
            initial,
            step=step,
            diagnostic="forwarding barrier lost before structural write",
        )

    apply_error: Exception | None = None
    try:
        _apply_step(backend, step)
    except Exception as exc:
        apply_error = exc

    try:
        after = backend.observe_structural_snapshot()
        final = compare_structural_policy(
            after,
            routing_desired,
            nft_desired,
            platform,
        )
    except StructuralPolicyPreconditionError as exc:
        return result(
            (
                StructuralPolicyMutationStatus.APPLY_FAILED
                if apply_error is not None
                else StructuralPolicyMutationStatus.POSTCONDITION_FAILED
            ),
            initial,
            attempted=True,
            step=step,
            diagnostic=(
                f"after-write scaffold precondition failed: {exc}"
                + (
                    f"; apply error: {type(apply_error).__name__}: {apply_error}"
                    if apply_error is not None
                    else ""
                )
            ),
        )
    except StructuralPolicyConflictError as exc:
        return result(
            (
                StructuralPolicyMutationStatus.APPLY_FAILED
                if apply_error is not None
                else StructuralPolicyMutationStatus.CONFLICT
            ),
            initial,
            attempted=True,
            step=step,
            diagnostic=(
                f"after-write comparison failed: {exc}"
                + (
                    f"; apply error: {type(apply_error).__name__}: {apply_error}"
                    if apply_error is not None
                    else ""
                )
            ),
        )
    except Exception as exc:
        return result(
            (
                StructuralPolicyMutationStatus.APPLY_FAILED
                if apply_error is not None
                else StructuralPolicyMutationStatus.POSTCONDITION_FAILED
            ),
            initial,
            attempted=True,
            step=step,
            diagnostic=(
                "after-write structural observation failed: "
                f"{type(exc).__name__}: {exc}"
                + (
                    f"; apply error: {type(apply_error).__name__}: {apply_error}"
                    if apply_error is not None
                    else ""
                )
            ),
        )

    if _gate_lost(gate_backend):
        return result(
            StructuralPolicyMutationStatus.BARRIER_LOST,
            initial,
            final,
            attempted=True,
            step=step,
            diagnostic="forwarding barrier lost during structural write",
        )

    if (
        before.interfaces != after.interfaces
        or not _strict_progress(initial, final)
    ):
        return result(
            (
                StructuralPolicyMutationStatus.APPLY_FAILED
                if apply_error is not None
                else StructuralPolicyMutationStatus.POSTCONDITION_FAILED
            ),
            initial,
            final,
            attempted=True,
            step=step,
            diagnostic=(
                "fresh structural postcondition did not make strict progress"
                + (
                    f"; apply error: {type(apply_error).__name__}: {apply_error}"
                    if apply_error is not None
                    else ""
                )
            ),
        )

    progress_diagnostic = (
        f"apply raised {type(apply_error).__name__}: {apply_error}; "
        "fresh structural postcondition independently made strict progress"
        if apply_error is not None
        else None
    )

    if final.desired_confirmed:
        return _activate_exact(
            gate_backend,
            backend,
            routing_desired,
            nft_desired,
            platform,
            after,
            final,
            initial,
            result,
            attempted=True,
            step=step,
            inherited_diagnostic=progress_diagnostic,
        )

    return result(
        StructuralPolicyMutationStatus.STEP_APPLIED,
        initial,
        final,
        attempted=True,
        step=step,
        diagnostic=progress_diagnostic,
    )


def _activate_exact(
    gate_backend: ForwardingGateDriver,
    backend: StructuralPolicyMutationBackend,
    routing_desired: PayloadRoutingDesiredState,
    nft_desired: CompositeNftDesiredState,
    platform: NetworkPolicyPlatformSpace,
    exact_snapshot: StructuralPolicyPhysicalSnapshot,
    exact_comparison: StructuralPolicyComparison,
    initial_comparison: StructuralPolicyComparison,
    result_factory,
    *,
    attempted: bool = False,
    step: StructuralPolicyMutationStep | None = None,
    inherited_diagnostic: str | None = None,
) -> StructuralPolicyMutationResult:
    if _gate_lost(gate_backend):
        return result_factory(
            StructuralPolicyMutationStatus.BARRIER_LOST,
            initial_comparison,
            exact_comparison,
            attempted=attempted,
            step=step,
            diagnostic="forwarding barrier lost before activation",
        )

    activation = converge_forwarding_gate_once(
        gate_backend,
        ForwardingGateState.ENABLED,
    )
    if not activation.confirmed:
        safety = converge_forwarding_gate_once(
            gate_backend,
            ForwardingGateState.DISABLED,
        )
        return result_factory(
            (
                StructuralPolicyMutationStatus.ACTIVATION_FAILED
                if safety.confirmed
                else StructuralPolicyMutationStatus.SAFETY_RECLOSE_FAILED
            ),
            initial_comparison,
            exact_comparison,
            attempted=attempted,
            step=step,
            activation=activation,
            safety_reclose=safety,
            diagnostic=(
                "forwarding activation not confirmed"
                + (
                    f"; prior diagnostic: {inherited_diagnostic}"
                    if inherited_diagnostic
                    else ""
                )
            ),
        )

    verification_error: Exception | None = None
    final_snapshot: StructuralPolicyPhysicalSnapshot | None = None
    final_comparison: StructuralPolicyComparison | None = None
    try:
        final_snapshot = backend.observe_structural_snapshot()
        final_comparison = compare_structural_policy(
            final_snapshot,
            routing_desired,
            nft_desired,
            platform,
        )
    except Exception as exc:
        verification_error = exc

    gate_enabled = False
    try:
        gate_enabled = (
            gate_backend.observe_forwarding_gate()
            is ForwardingGateState.ENABLED
        )
    except Exception as exc:
        if verification_error is None:
            verification_error = exc

    verified = (
        verification_error is None
        and final_snapshot is not None
        and final_comparison is not None
        and exact_snapshot.interfaces == final_snapshot.interfaces
        and final_comparison.desired_confirmed
        and gate_enabled
    )
    if verified:
        return result_factory(
            StructuralPolicyMutationStatus.CONFIRMED,
            initial_comparison,
            final_comparison,
            attempted=attempted,
            step=step,
            activation=activation,
            diagnostic=inherited_diagnostic,
        )

    safety = converge_forwarding_gate_once(
        gate_backend,
        ForwardingGateState.DISABLED,
    )
    detail = (
        f"{type(verification_error).__name__}: {verification_error}"
        if verification_error is not None
        else "fresh post-activation state is not exact/stable"
    )
    return result_factory(
        (
            StructuralPolicyMutationStatus.FINAL_VERIFICATION_FAILED
            if safety.confirmed
            else StructuralPolicyMutationStatus.SAFETY_RECLOSE_FAILED
        ),
        initial_comparison,
        final_comparison,
        attempted=attempted,
        step=step,
        activation=activation,
        safety_reclose=safety,
        diagnostic=(
            f"final post-activation verification failed: {detail}"
            + (
                f"; prior diagnostic: {inherited_diagnostic}"
                if inherited_diagnostic
                else ""
            )
        ),
    )


def _apply_step(
    backend: StructuralPolicyMutationBackend,
    step: StructuralPolicyMutationStep,
) -> None:
    if step.kind in {
        StructuralPolicyStepKind.ADD_GUARD_ROUTE,
        StructuralPolicyStepKind.ADD_PATH_ROUTE,
    }:
        assert step.desired_route is not None
        backend.add_route(step.desired_route)
    elif step.kind is StructuralPolicyStepKind.DELETE_ROUTING_RULE:
        assert step.observed_rule is not None
        backend.delete_rule(step.observed_rule)
    elif step.kind is StructuralPolicyStepKind.DELETE_ROUTING_ROUTE:
        assert step.observed_route is not None
        backend.delete_route(step.observed_route)
    elif step.kind is StructuralPolicyStepKind.ADD_ROUTING_RULE:
        assert step.desired_rule is not None
        backend.add_rule(step.desired_rule)
    elif step.kind is StructuralPolicyStepKind.APPLY_NFT_STEP:
        assert step.nft_step is not None
        apply_composite_nft_step(backend, step.nft_step)
    else:
        raise ValueError(f"unsupported structural step {step.kind!r}")


def structural_policy_distance(value: StructuralPolicyComparison) -> int:
    return (
        len(value.routing.missing_routes)
        + len(value.routing.stale_routes)
        + len(value.routing.missing_rules)
        + len(value.routing.stale_rules)
        + len(value.routing.conflicts)
        + len(value.nft.profile_forward.missing)
        + len(value.nft.profile_forward.stale)
        + len(value.nft.payload_nat.missing)
        + len(value.nft.payload_nat.stale)
        + len(value.nft.device_firewall.missing)
        + len(value.nft.device_firewall.stale_chains)
        + len(value.nft.device_firewall.stale_jumps)
        + len(value.nft.local_publication.missing)
        + len(value.nft.local_publication.stale)
        + len(value.nft.local_integration.missing)
        + len(value.nft.local_integration.stale)
        + len(value.nft.probe_local.missing)
        + len(value.nft.probe_local.stale)
        + len(value.nft.conflicts)
    )


def _strict_progress(
    before: StructuralPolicyComparison,
    after: StructuralPolicyComparison,
) -> bool:
    return (
        not after.routing.conflicts
        and not after.nft.conflicts
        and structural_policy_distance(after) < structural_policy_distance(before)
    )


def _gate_lost(gate_backend: ForwardingGateDriver) -> bool:
    try:
        return (
            gate_backend.observe_forwarding_gate()
            is not ForwardingGateState.DISABLED
        )
    except Exception:
        return True
