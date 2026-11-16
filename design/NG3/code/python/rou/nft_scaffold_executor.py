from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .forwarding_gate import (
    ForwardingGateBackend,
    ForwardingGateExecutionResult,
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .nft_namespace_inventory import (
    NftNamespaceObservation,
    NftNamespaceStatus,
)
from .nft_payload_scaffold import (
    NftBaseChainSpec,
    NftPayloadScaffoldComparison,
    compare_payload_nft_scaffold,
)


class PayloadNftScaffoldBackend(Protocol):
    def observe_nft_namespace(self) -> NftNamespaceObservation:
        """Return one fresh full-ruleset ownership observation."""

    def create_payload_scaffold(self) -> None:
        """Create the marked table and both invariant chains atomically."""

    def add_payload_scaffold_chains(
        self,
        missing: tuple[NftBaseChainSpec, ...],
    ) -> None:
        """Add only already-proved missing invariant chains atomically."""


class PayloadNftScaffoldPrepareStatus(str, Enum):
    SUCCESS = "success"
    BARRIER_FAILED = "barrier_failed"
    BARRIER_LOST = "barrier_lost"
    OBSERVATION_FAILED = "observation_failed"
    CONFLICT = "conflict"
    APPLY_FAILED = "apply_failed"
    POSTCONDITION_FAILED = "postcondition_failed"


@dataclass(frozen=True, slots=True)
class PayloadNftScaffoldPrepareResult:
    status: PayloadNftScaffoldPrepareStatus
    barrier: ForwardingGateExecutionResult
    initial: NftPayloadScaffoldComparison | None
    final: NftPayloadScaffoldComparison | None
    mutation_attempted: bool
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status is PayloadNftScaffoldPrepareStatus.SUCCESS
            and self.final is not None
            and self.final.scaffold_confirmed
            and self.final.full_policy_classified
        )


def prepare_payload_nft_scaffold_once(
    gate_backend: ForwardingGateBackend,
    nft_backend: PayloadNftScaffoldBackend,
) -> PayloadNftScaffoldPrepareResult:
    """Close root forwarding, then bootstrap/repair only the invariant nft scaffold.

    The function intentionally never re-enables forwarding.
    """
    barrier = converge_forwarding_gate_once(
        gate_backend,
        ForwardingGateState.DISABLED,
    )
    if not barrier.confirmed:
        return PayloadNftScaffoldPrepareResult(
            status=PayloadNftScaffoldPrepareStatus.BARRIER_FAILED,
            barrier=barrier,
            initial=None,
            final=None,
            mutation_attempted=False,
            diagnostic="root forwarding barrier is not confirmed disabled",
        )

    try:
        initial_observation = nft_backend.observe_nft_namespace()
    except Exception as exc:
        return PayloadNftScaffoldPrepareResult(
            status=PayloadNftScaffoldPrepareStatus.OBSERVATION_FAILED,
            barrier=barrier,
            initial=None,
            final=None,
            mutation_attempted=False,
            diagnostic=f"initial nft observation failed: {type(exc).__name__}: {exc}",
        )

    initial = compare_payload_nft_scaffold(initial_observation)

    if (
        initial.namespace_status is NftNamespaceStatus.CONFLICT
        or initial.conflicts
        or initial.unclassified_objects
    ):
        return PayloadNftScaffoldPrepareResult(
            status=PayloadNftScaffoldPrepareStatus.CONFLICT,
            barrier=barrier,
            initial=initial,
            final=initial,
            mutation_attempted=False,
            diagnostic="nft namespace is not fully classified for scaffold-only repair",
        )

    mutation_needed = bool(initial.missing_chains)

    if mutation_needed:
        try:
            pre_mutation_gate = gate_backend.observe_forwarding_gate()
        except Exception as exc:
            return PayloadNftScaffoldPrepareResult(
                status=PayloadNftScaffoldPrepareStatus.BARRIER_LOST,
                barrier=barrier,
                initial=initial,
                final=None,
                mutation_attempted=False,
                diagnostic=(
                    "root barrier could not be re-observed immediately before nft mutation: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        if pre_mutation_gate is not ForwardingGateState.DISABLED:
            return PayloadNftScaffoldPrepareResult(
                status=PayloadNftScaffoldPrepareStatus.BARRIER_LOST,
                barrier=barrier,
                initial=initial,
                final=None,
                mutation_attempted=False,
                diagnostic="root forwarding barrier was lost before nft mutation",
            )

    apply_error: Exception | None = None
    if mutation_needed:
        try:
            if initial.namespace_status is NftNamespaceStatus.ABSENT:
                nft_backend.create_payload_scaffold()
            else:
                nft_backend.add_payload_scaffold_chains(
                    initial.missing_chains
                )
        except Exception as exc:
            apply_error = exc

    try:
        final_observation = nft_backend.observe_nft_namespace()
        final = compare_payload_nft_scaffold(final_observation)
    except Exception as exc:
        return PayloadNftScaffoldPrepareResult(
            status=(
                PayloadNftScaffoldPrepareStatus.APPLY_FAILED
                if apply_error is not None
                else PayloadNftScaffoldPrepareStatus.OBSERVATION_FAILED
            ),
            barrier=barrier,
            initial=initial,
            final=None,
            mutation_attempted=mutation_needed,
            diagnostic=(
                (f"nft apply failed: {type(apply_error).__name__}: {apply_error}; "
                 if apply_error is not None else "")
                + f"final nft observation failed: {type(exc).__name__}: {exc}"
            ),
        )

    try:
        final_gate = gate_backend.observe_forwarding_gate()
    except Exception as exc:
        return PayloadNftScaffoldPrepareResult(
            status=PayloadNftScaffoldPrepareStatus.BARRIER_LOST,
            barrier=barrier,
            initial=initial,
            final=final,
            mutation_attempted=mutation_needed,
            diagnostic=(
                "root barrier could not be re-observed after nft preparation: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if final_gate is not ForwardingGateState.DISABLED:
        return PayloadNftScaffoldPrepareResult(
            status=PayloadNftScaffoldPrepareStatus.BARRIER_LOST,
            barrier=barrier,
            initial=initial,
            final=final,
            mutation_attempted=mutation_needed,
            diagnostic="root forwarding barrier was lost during nft preparation",
        )

    exact_final = (
        final.namespace_status is NftNamespaceStatus.OWNED
        and final.scaffold_confirmed
        and final.full_policy_classified
        and not final.conflicts
    )

    if exact_final:
        diagnostic = None
        if apply_error is not None:
            diagnostic = (
                f"nft apply raised {type(apply_error).__name__}: {apply_error}; "
                "exact scaffold postcondition independently confirmed"
            )
        return PayloadNftScaffoldPrepareResult(
            status=PayloadNftScaffoldPrepareStatus.SUCCESS,
            barrier=barrier,
            initial=initial,
            final=final,
            mutation_attempted=mutation_needed,
            diagnostic=diagnostic,
        )

    if apply_error is not None:
        return PayloadNftScaffoldPrepareResult(
            status=PayloadNftScaffoldPrepareStatus.APPLY_FAILED,
            barrier=barrier,
            initial=initial,
            final=final,
            mutation_attempted=mutation_needed,
            diagnostic=(
                f"nft apply failed: {type(apply_error).__name__}: {apply_error}; "
                "exact scaffold postcondition is not confirmed"
            ),
        )

    return PayloadNftScaffoldPrepareResult(
        status=PayloadNftScaffoldPrepareStatus.POSTCONDITION_FAILED,
        barrier=barrier,
        initial=initial,
        final=final,
        mutation_attempted=mutation_needed,
        diagnostic="fresh final nft state is not the exact classified scaffold",
    )
