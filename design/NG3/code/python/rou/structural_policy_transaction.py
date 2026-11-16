"""Explicit bounded coordinator for complete structural policy convergence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .composite_nft_policy import CompositeNftDesiredState
from .forwarding_gate import ForwardingGateBackend
from .network_policy_layout import NetworkPolicyPlatformSpace
from .payload_routing_desired import PayloadRoutingDesiredState
from .structural_policy_mutation import (
    StructuralPolicyMutationBackend,
    StructuralPolicyMutationResult,
    StructuralPolicyMutationStatus,
    converge_structural_policy_step_once,
    structural_policy_distance,
)


class StructuralPolicyTransactionStatus(str, Enum):
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REGRESSED = "regressed"


@dataclass(frozen=True, slots=True)
class StructuralPolicyTransactionResult:
    status: StructuralPolicyTransactionStatus
    attempts: tuple[StructuralPolicyMutationResult, ...]
    initial_distance: int | None
    final_distance: int | None
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status is StructuralPolicyTransactionStatus.CONFIRMED
            and bool(self.attempts)
            and self.attempts[-1].status
            is StructuralPolicyMutationStatus.CONFIRMED
        )


def converge_structural_policy(
    gate_backend: ForwardingGateBackend,
    backend: StructuralPolicyMutationBackend,
    routing_desired: PayloadRoutingDesiredState,
    nft_desired: CompositeNftDesiredState,
    platform: NetworkPolicyPlatformSpace,
) -> StructuralPolicyTransactionResult:
    """Drive fresh one-step convergence until confirmed or the transaction stops.

    This coordinator has no retry budget and no retry-on-error behavior.
    Progress is bounded by the non-negative structural distance:

    - every STEP_APPLIED attempt must strictly reduce distance;
    - the next fresh attempt may start at the same or a lower distance;
    - any inter-attempt distance increase stops an unfinished transaction as
      REGRESSED; an already-CONFIRMED fresh attempt remains authoritative;
    - any terminal one-step status other than STEP_APPLIED/CONFIRMED stops
      immediately as FAILED.

    A later reconciliation cycle may start a new transaction from fresh state.
    """
    attempts: list[StructuralPolicyMutationResult] = []
    initial_distance: int | None = None
    previous_final_distance: int | None = None

    while True:
        attempt = converge_structural_policy_step_once(
            gate_backend,
            backend,
            routing_desired,
            nft_desired,
            platform,
        )
        attempts.append(attempt)

        attempt_initial_distance = (
            structural_policy_distance(attempt.initial)
            if attempt.initial is not None
            else None
        )
        attempt_final_distance = (
            structural_policy_distance(attempt.final)
            if attempt.final is not None
            else None
        )

        if initial_distance is None and attempt_initial_distance is not None:
            initial_distance = attempt_initial_distance

        if attempt.status is StructuralPolicyMutationStatus.CONFIRMED:
            return StructuralPolicyTransactionResult(
                status=StructuralPolicyTransactionStatus.CONFIRMED,
                attempts=tuple(attempts),
                initial_distance=initial_distance,
                final_distance=attempt_final_distance,
                diagnostic=attempt.diagnostic,
            )

        if (
            previous_final_distance is not None
            and attempt_initial_distance is not None
            and attempt_initial_distance > previous_final_distance
        ):
            return StructuralPolicyTransactionResult(
                status=StructuralPolicyTransactionStatus.REGRESSED,
                attempts=tuple(attempts),
                initial_distance=initial_distance,
                final_distance=attempt_initial_distance,
                diagnostic=(
                    "fresh structural state regressed between transaction "
                    f"attempts: previous={previous_final_distance}, "
                    f"current={attempt_initial_distance}"
                ),
            )

        if attempt.status is not StructuralPolicyMutationStatus.STEP_APPLIED:
            return StructuralPolicyTransactionResult(
                status=StructuralPolicyTransactionStatus.FAILED,
                attempts=tuple(attempts),
                initial_distance=initial_distance,
                final_distance=attempt_final_distance,
                diagnostic=(
                    f"structural transaction stopped at "
                    f"{attempt.status.value}"
                    + (
                        f": {attempt.diagnostic}"
                        if attempt.diagnostic
                        else ""
                    )
                ),
            )

        if (
            attempt_initial_distance is None
            or attempt_final_distance is None
            or attempt_final_distance >= attempt_initial_distance
        ):
            return StructuralPolicyTransactionResult(
                status=StructuralPolicyTransactionStatus.REGRESSED,
                attempts=tuple(attempts),
                initial_distance=initial_distance,
                final_distance=attempt_final_distance,
                diagnostic=(
                    "STEP_APPLIED did not expose a strict structural "
                    "distance decrease"
                ),
            )

        previous_final_distance = attempt_final_distance
