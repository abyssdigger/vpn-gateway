"""Pure next-step selection for combined NG3 nft structural convergence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .composite_nft_policy import CompositeNftPolicyComparison
from .device_firewall_desired import DeviceFirewallChainSpec
from .local_integration_mutation import (
    IntegrationLocalMutationStep,
    select_integration_local_step,
)
from .local_integration_policy import IntegrationLocalDesiredState
from .local_publication_mutation import (
    LocalPublicationMutationStep,
    select_local_publication_step,
)
from .local_publication_policy import LocalPublicationDesiredState
from .payload_forward_desired import PayloadForwardRuleSpec
from .payload_nat_desired import PayloadMasqueradeSpec


class CompositeNftStepKind(str, Enum):
    DELETE_PROFILE_RULE = "delete_profile_rule"
    DELETE_DEVICE_JUMP = "delete_device_jump"
    DELETE_DEVICE_CHAIN = "delete_device_chain"
    DELETE_NAT_RULE = "delete_nat_rule"
    ADD_NAT_RULE = "add_nat_rule"
    CREATE_DEVICE_CHAIN = "create_device_chain"
    ADD_PROFILE_RULE = "add_profile_rule"
    APPLY_LOCAL_PUBLICATION = "apply_local_publication"
    APPLY_LOCAL_INTEGRATION = "apply_local_integration"


@dataclass(frozen=True, slots=True)
class CompositeNftMutationStep:
    kind: CompositeNftStepKind
    handle: int | None = None
    chain_name: str | None = None
    profile_rule: PayloadForwardRuleSpec | None = None
    nat_rule: PayloadMasqueradeSpec | None = None
    device_chain: DeviceFirewallChainSpec | None = None
    local_publication_step: LocalPublicationMutationStep | None = None
    local_integration_step: IntegrationLocalMutationStep | None = None

    def __post_init__(self) -> None:
        fields = (
            self.handle is not None,
            self.chain_name is not None,
            self.profile_rule is not None,
            self.nat_rule is not None,
            self.device_chain is not None,
            self.local_publication_step is not None,
            self.local_integration_step is not None,
        )
        if sum(fields) != 1:
            raise ValueError("exactly one mutation step operand is required")


class CompositeNftPlanError(ValueError):
    pass


def select_composite_nft_step(
    comparison: CompositeNftPolicyComparison,
    local_publication_desired: LocalPublicationDesiredState | None = None,
    local_integration_desired: IntegrationLocalDesiredState | None = None,
) -> CompositeNftMutationStep | None:
    """Select one fail-closed structural convergence step.

    Stale local publication accepts are removed before payload cleanup because
    ForwardingGate does not protect local traffic. Existing positive Profile
    admission is then removed before other payload cleanup. New positive Profile
    admission is installed after required NAT and Device restriction. Missing
    local publication admission is installed last as its own atomic nft transaction.
    Device jump cleanup precedes child-chain cleanup to preserve nft references.
    """
    if not isinstance(comparison, CompositeNftPolicyComparison):
        raise CompositeNftPlanError(
            "comparison must be CompositeNftPolicyComparison"
        )
    if comparison.conflicts:
        raise CompositeNftPlanError(
            "composite nft policy has unclassified/conflicting objects"
        )
    if (
        comparison.profile_forward.conflicts
        or comparison.payload_nat.conflicts
        or comparison.device_firewall.conflicts
        or comparison.local_publication.conflicts
        or comparison.local_integration.conflicts
    ):
        raise CompositeNftPlanError(
            "sub-policy comparison has conflicts"
        )
    if local_publication_desired is None:
        local_publication_desired = LocalPublicationDesiredState(())
    if not isinstance(local_publication_desired, LocalPublicationDesiredState):
        raise CompositeNftPlanError(
            "local_publication_desired must be LocalPublicationDesiredState"
        )
    if local_integration_desired is None:
        local_integration_desired = IntegrationLocalDesiredState(())
    if not isinstance(local_integration_desired, IntegrationLocalDesiredState):
        raise CompositeNftPlanError(
            "local_integration_desired must be IntegrationLocalDesiredState"
        )

    if comparison.local_integration.stale:
        local_step = select_integration_local_step(
            comparison.local_integration,
            local_integration_desired,
        )
        if local_step is None:
            raise CompositeNftPlanError(
                "stale local integration state has no repair step"
            )
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.APPLY_LOCAL_INTEGRATION,
            local_integration_step=local_step,
        )

    if comparison.local_publication.stale:
        local_step = select_local_publication_step(
            comparison.local_publication,
            local_publication_desired,
        )
        if local_step is None:
            raise CompositeNftPlanError(
                "stale local publication state has no repair step"
            )
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.APPLY_LOCAL_PUBLICATION,
            local_publication_step=local_step,
        )

    if comparison.profile_forward.stale:
        target = min(
            comparison.profile_forward.stale,
            key=lambda item: item.handle,
        )
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.DELETE_PROFILE_RULE,
            handle=target.handle,
        )

    if comparison.device_firewall.stale_jumps:
        target = min(
            comparison.device_firewall.stale_jumps,
            key=lambda item: item.source_order,
        )
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.DELETE_DEVICE_JUMP,
            handle=target.handle,
        )

    if comparison.device_firewall.stale_chains:
        target = min(
            comparison.device_firewall.stale_chains,
            key=lambda item: item.source_order,
        )
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.DELETE_DEVICE_CHAIN,
            chain_name=target.name,
        )

    if comparison.payload_nat.stale:
        target = min(
            comparison.payload_nat.stale,
            key=lambda item: item.handle,
        )
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.DELETE_NAT_RULE,
            handle=target.handle,
        )

    if comparison.payload_nat.missing:
        target = min(
            comparison.payload_nat.missing,
            key=lambda spec: (
                spec.ingress.ifindex,
                spec.egress.ifindex,
                repr(spec.path_id),
            ),
        )
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.ADD_NAT_RULE,
            nat_rule=target,
        )

    if comparison.device_firewall.missing:
        target = comparison.device_firewall.missing[0]
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.CREATE_DEVICE_CHAIN,
            device_chain=target,
        )

    if comparison.profile_forward.missing:
        target = comparison.profile_forward.missing[0]
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.ADD_PROFILE_RULE,
            profile_rule=target,
        )

    if comparison.local_publication.missing:
        local_step = select_local_publication_step(
            comparison.local_publication,
            local_publication_desired,
        )
        if local_step is None:
            raise CompositeNftPlanError(
                "missing local publication state has no repair step"
            )
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.APPLY_LOCAL_PUBLICATION,
            local_publication_step=local_step,
        )

    if comparison.local_integration.missing:
        local_step = select_integration_local_step(
            comparison.local_integration,
            local_integration_desired,
        )
        if local_step is None:
            raise CompositeNftPlanError(
                "missing local integration state has no repair step"
            )
        return CompositeNftMutationStep(
            kind=CompositeNftStepKind.APPLY_LOCAL_INTEGRATION,
            local_integration_step=local_step,
        )

    return None
