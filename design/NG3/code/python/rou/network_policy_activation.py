"""Bounded network-policy activation subassembly.

This is not the product lifecycle/start operation. It composes the already
accepted forwarding containment, invariant nft scaffold preparation and
complete structural transaction boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .composite_nft_policy import CompositeNftDesiredState
from .forwarding_gate import (
    ForwardingGateDriver,
    ForwardingGateEnforcementResult,
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .network_policy_layout import NetworkPolicyPlatformSpace
from .nft_namespace_inventory import NftNamespaceStatus
from .nft_payload_scaffold import (
    NftPayloadScaffoldComparison,
    compare_payload_nft_scaffold,
)
from .nft_scaffold_enforcer import (
    PayloadNftScaffoldDriver,
    PayloadNftScaffoldPrepareResult,
    prepare_payload_nft_scaffold_once,
)
from .payload_routing_desired import PayloadRoutingDesiredState
from .structural_policy_mutation import StructuralPolicyMutationBackend
from .stack_return_affinity import StackReturnAffinityDesired
from .stack_return_affinity_convergence import (
    StackReturnAffinityBackend,
    StackReturnAffinityConvergenceResult,
    converge_stack_return_affinity_once,
)
from .structural_policy_transaction import (
    StructuralPolicyTransactionResult,
    converge_structural_policy,
)

LOG_TAG = "POLICY"


class NetworkPolicyActivationStatus(str, Enum):
    READY = "ready"
    INITIAL_CONTAINMENT_FAILED = "initial_containment_failed"
    SCAFFOLD_OBSERVATION_FAILED = "scaffold_observation_failed"
    SCAFFOLD_CONFLICT = "scaffold_conflict"
    SCAFFOLD_PREPARE_FAILED = "scaffold_prepare_failed"
    STACK_RETURN_AFFINITY_FAILED = "stack_return_affinity_failed"
    STRUCTURAL_FAILED = "structural_failed"
    FAILURE_CONTAINMENT_FAILED = "failure_containment_failed"


@dataclass(frozen=True, slots=True)
class NetworkPolicyActivationResult:
    status: NetworkPolicyActivationStatus
    initial_containment: ForwardingGateEnforcementResult
    scaffold: NftPayloadScaffoldComparison | None
    scaffold_prepare: PayloadNftScaffoldPrepareResult | None
    structural: StructuralPolicyTransactionResult | None
    stack_return_affinity: StackReturnAffinityConvergenceResult | None = None
    failure_containment: ForwardingGateEnforcementResult | None = None
    failure_status: NetworkPolicyActivationStatus | None = None
    diagnostic: str | None = None

    @property
    def ready(self) -> bool:
        return (
            self.status is NetworkPolicyActivationStatus.READY
            and self.structural is not None
            and self.structural.confirmed
        )


def activate_network_policy(
    gate_backend: ForwardingGateDriver,
    scaffold_backend: PayloadNftScaffoldDriver,
    structural_backend: StructuralPolicyMutationBackend,
    routing_desired: PayloadRoutingDesiredState,
    nft_desired: CompositeNftDesiredState,
    platform: NetworkPolicyPlatformSpace,
    stack_return_affinity_backend: StackReturnAffinityBackend | None = None,
    stack_return_affinity_desired: StackReturnAffinityDesired | None = None,
) -> NetworkPolicyActivationResult:
    """Contain, prepare the invariant scaffold if safely bounded, then converge.

    No failed lower operation is retried here. After any failure following the
    initial containment phase, one independent ForwardingGate=DISABLED
    convergence attempt is used only to confirm/re-establish fail-closed
    containment.
    """
    initial_containment = converge_forwarding_gate_once(
        gate_backend,
        ForwardingGateState.DISABLED,
    )
    if not initial_containment.confirmed:
        return NetworkPolicyActivationResult(
            status=NetworkPolicyActivationStatus.INITIAL_CONTAINMENT_FAILED,
            initial_containment=initial_containment,
            scaffold=None,
            scaffold_prepare=None,
            structural=None,
            diagnostic="initial payload forwarding containment is not confirmed",
        )

    try:
        scaffold = compare_payload_nft_scaffold(
            scaffold_backend.observe_nft_namespace()
        )
    except Exception as exc:
        return _failed_after_containment(
            gate_backend,
            initial_containment,
            NetworkPolicyActivationStatus.SCAFFOLD_OBSERVATION_FAILED,
            scaffold=None,
            diagnostic=(
                "invariant nft scaffold observation failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if (
        scaffold.namespace_status is NftNamespaceStatus.CONFLICT
        or scaffold.conflicts
    ):
        reason = (
            scaffold.conflicts[0].reason
            if scaffold.conflicts
            else "reserved nft namespace ownership conflict"
        )
        return _failed_after_containment(
            gate_backend,
            initial_containment,
            NetworkPolicyActivationStatus.SCAFFOLD_CONFLICT,
            scaffold=scaffold,
            diagnostic=reason,
        )

    scaffold_prepare: PayloadNftScaffoldPrepareResult | None = None
    if not scaffold.scaffold_confirmed:
        if scaffold.unclassified_objects:
            return _failed_after_containment(
                gate_backend,
                initial_containment,
                NetworkPolicyActivationStatus.SCAFFOLD_CONFLICT,
                scaffold=scaffold,
                diagnostic=(
                    "incomplete invariant nft scaffold coexists with "
                    "non-scaffold objects; scaffold-only repair is not proven"
                ),
            )

        scaffold_prepare = prepare_payload_nft_scaffold_once(
            gate_backend,
            scaffold_backend,
        )
        if not scaffold_prepare.confirmed:
            return _failed_after_containment(
                gate_backend,
                initial_containment,
                NetworkPolicyActivationStatus.SCAFFOLD_PREPARE_FAILED,
                scaffold=scaffold,
                scaffold_prepare=scaffold_prepare,
                diagnostic=(
                    "invariant nft scaffold preparation failed"
                    + (
                        f": {scaffold_prepare.diagnostic}"
                        if scaffold_prepare.diagnostic
                        else ""
                    )
                ),
            )

        assert scaffold_prepare.final is not None
        scaffold = scaffold_prepare.final

    affinity_result: StackReturnAffinityConvergenceResult | None = None
    if stack_return_affinity_desired is not None:
        if stack_return_affinity_backend is None:
            return _failed_after_containment(
                gate_backend,
                initial_containment,
                NetworkPolicyActivationStatus.STACK_RETURN_AFFINITY_FAILED,
                scaffold=scaffold,
                scaffold_prepare=scaffold_prepare,
                diagnostic="stack return-affinity desired state has no backend",
            )
        affinity_result = converge_stack_return_affinity_once(
            gate_backend,
            stack_return_affinity_backend,
            stack_return_affinity_desired,
        )
        if not affinity_result.confirmed:
            return _failed_after_containment(
                gate_backend,
                initial_containment,
                NetworkPolicyActivationStatus.STACK_RETURN_AFFINITY_FAILED,
                scaffold=scaffold,
                scaffold_prepare=scaffold_prepare,
                stack_return_affinity=affinity_result,
                diagnostic=(
                    "stack return-affinity convergence failed"
                    + (
                        f": {affinity_result.diagnostic}"
                        if affinity_result.diagnostic
                        else ""
                    )
                ),
            )

    structural = converge_structural_policy(
        gate_backend,
        structural_backend,
        routing_desired,
        nft_desired,
        platform,
    )
    if not structural.confirmed:
        return _failed_after_containment(
            gate_backend,
            initial_containment,
            NetworkPolicyActivationStatus.STRUCTURAL_FAILED,
            scaffold=scaffold,
            scaffold_prepare=scaffold_prepare,
            structural=structural,
            diagnostic=(
                "structural network-policy transaction failed"
                + (
                    f": {structural.diagnostic}"
                    if structural.diagnostic
                    else ""
                )
            ),
        )

    return NetworkPolicyActivationResult(
        status=NetworkPolicyActivationStatus.READY,
        initial_containment=initial_containment,
        scaffold=scaffold,
        scaffold_prepare=scaffold_prepare,
        structural=structural,
        stack_return_affinity=affinity_result,
        diagnostic=structural.diagnostic,
    )


def _failed_after_containment(
    gate_backend: ForwardingGateDriver,
    initial_containment: ForwardingGateEnforcementResult,
    failure_status: NetworkPolicyActivationStatus,
    *,
    scaffold: NftPayloadScaffoldComparison | None,
    scaffold_prepare: PayloadNftScaffoldPrepareResult | None = None,
    structural: StructuralPolicyTransactionResult | None = None,
    stack_return_affinity: StackReturnAffinityConvergenceResult | None = None,
    diagnostic: str,
) -> NetworkPolicyActivationResult:
    failure_containment = converge_forwarding_gate_once(
        gate_backend,
        ForwardingGateState.DISABLED,
    )
    if not failure_containment.confirmed:
        return NetworkPolicyActivationResult(
            status=NetworkPolicyActivationStatus.FAILURE_CONTAINMENT_FAILED,
            initial_containment=initial_containment,
            scaffold=scaffold,
            scaffold_prepare=scaffold_prepare,
            structural=structural,
            stack_return_affinity=stack_return_affinity,
            failure_containment=failure_containment,
            failure_status=failure_status,
            diagnostic=(
                f"{diagnostic}; failure containment is not confirmed"
            ),
        )

    return NetworkPolicyActivationResult(
        status=failure_status,
        initial_containment=initial_containment,
        scaffold=scaffold,
        scaffold_prepare=scaffold_prepare,
        structural=structural,
        stack_return_affinity=stack_return_affinity,
        failure_containment=failure_containment,
        failure_status=failure_status,
        diagnostic=diagnostic,
    )
