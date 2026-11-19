"""Read-only exactness gate before physical availability probe execution."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address

from .interface_identity import InterfaceIdentity
from .network_policy_layout import (
    NetworkPolicyPlatformSpace,
    ProbePolicyOwner,
)
from .probe_local_observation import (
    ProbeLocalComparison,
    compare_probe_local,
)
from .probe_policy import (
    AvailabilityProbeMechanism,
    ProbeLocalHook,
    ProbeNetworkPolicyDesiredState,
)
from .probe_routing_compare import (
    ProbeRoutingComparison,
    compare_probe_routing,
)
from .structural_policy_mutation import StructuralPolicyPhysicalSnapshot


@dataclass(frozen=True, slots=True)
class ProbeExecutionContextKey:
    owner: ProbePolicyOwner
    mechanism: AvailabilityProbeMechanism
    target: IPv4Address
    endpoint: InterfaceIdentity


@dataclass(frozen=True, slots=True)
class ProbeExecutionPrecondition:
    routing: ProbeRoutingComparison
    local: ProbeLocalComparison
    interfaces_stable_snapshot: tuple[InterfaceIdentity, ...]
    contexts: frozenset[ProbeExecutionContextKey]

    @property
    def owners(self) -> frozenset[ProbePolicyOwner]:
        return frozenset(context.owner for context in self.contexts)

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
    rule_by_owner = {}
    for rule in desired.rules:
        if rule.owner in rule_by_owner:
            raise ValueError(
                "probe desired routing contains duplicate semantic owner"
            )
        rule_by_owner[rule.owner] = rule

    local_by_owner = {}
    for rule in desired.local_rules:
        local_by_owner.setdefault(rule.owner, []).append(rule)

    if set(local_by_owner) != set(rule_by_owner):
        raise ValueError(
            "probe routing and local desired owner sets do not match"
        )

    contexts = set()
    for owner, rule in rule_by_owner.items():
        local_rules = local_by_owner[owner]
        if (
            len(local_rules) != 2
            or {item.hook for item in local_rules}
            != {ProbeLocalHook.INPUT, ProbeLocalHook.OUTPUT}
        ):
            raise ValueError(
                "probe desired owner must have exact INPUT and OUTPUT local rules"
            )
        for local_rule in local_rules:
            if (
                local_rule.endpoint != rule.endpoint
                or local_rule.target != rule.target
                or local_rule.mechanism is not rule.mechanism
            ):
                raise ValueError(
                    "probe routing and local desired context identities do not match"
                )
        contexts.add(
            ProbeExecutionContextKey(
                owner=owner,
                mechanism=rule.mechanism,
                target=rule.target,
                endpoint=rule.endpoint,
            )
        )

    return ProbeExecutionPrecondition(
        routing=routing,
        local=local,
        interfaces_stable_snapshot=snapshot.interfaces,
        contexts=frozenset(contexts),
    )
