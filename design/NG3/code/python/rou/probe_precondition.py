"""Read-only exactness gate before physical availability probe execution."""

from __future__ import annotations

from dataclasses import dataclass

from .composite_nft_policy import ProbeLocalComparison
from .network_policy_layout import NetworkPolicyPlatformSpace
from .probe_local_observation import compare_probe_local
from .probe_policy import ProbeNetworkPolicyDesiredState
from .probe_routing_compare import (
    ProbeRoutingComparison,
    compare_probe_routing,
)
from .structural_policy_mutation import StructuralPolicyPhysicalSnapshot


@dataclass(frozen=True, slots=True)
class ProbeExecutionPrecondition:
    routing: ProbeRoutingComparison
    local: ProbeLocalComparison
    interfaces_stable_snapshot: tuple

    @property
    def confirmed(self) -> bool:
        return self.routing.confirmed and self.local.desired_confirmed


def verify_probe_execution_precondition(
    snapshot: StructuralPolicyPhysicalSnapshot,
    desired: ProbeNetworkPolicyDesiredState,
    platform: NetworkPolicyPlatformSpace,
) -> ProbeExecutionPrecondition:
    """Verify the complete current probe plane without mutating it."""
    if not isinstance(snapshot, StructuralPolicyPhysicalSnapshot):
        raise ValueError(
            "snapshot must be StructuralPolicyPhysicalSnapshot"
        )
    if not isinstance(desired, ProbeNetworkPolicyDesiredState):
        raise ValueError(
            "desired must be ProbeNetworkPolicyDesiredState"
        )
    routing = compare_probe_routing(
        desired,
        snapshot.routing,
        platform,
    )
    local = compare_probe_local(
        snapshot.nft,
        snapshot.interfaces,
        desired.local_rules,
    )
    return ProbeExecutionPrecondition(
        routing=routing,
        local=local,
        interfaces_stable_snapshot=snapshot.interfaces,
    )
