"""Read-only exactness gate before physical availability probe execution."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address

from .interface_identity import InterfaceIdentity
from .network_policy_layout import (
    NetworkPolicyPlatformSpace,
    ProbeSemanticOwner,
    is_probe_semantic_owner,
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
    owner: ProbeSemanticOwner
    mechanism: AvailabilityProbeMechanism
    target: IPv4Address
    endpoint: InterfaceIdentity

    def __post_init__(self) -> None:
        if not is_probe_semantic_owner(self.owner):
            raise ValueError("unsupported probe semantic owner")
        if self.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise ValueError("Release 1 probe execution context must use ICMP")
        if not isinstance(self.target, IPv4Address):
            raise ValueError("probe execution target must be IPv4Address")
        if not isinstance(self.endpoint, InterfaceIdentity):
            raise ValueError("probe execution endpoint must be InterfaceIdentity")


@dataclass(frozen=True, slots=True)
class ProbeExecutionPrecondition:
    routing: ProbeRoutingComparison
    local: ProbeLocalComparison
    interfaces_stable_snapshot: tuple[InterfaceIdentity, ...]
    contexts: frozenset[ProbeExecutionContextKey]

    @property
    def owners(self) -> frozenset[ProbeSemanticOwner]:
        return frozenset(context.owner for context in self.contexts)

    @property
    def confirmed(self) -> bool:
        return self.routing.confirmed and self.local.desired_confirmed


def require_probe_execution_context(
    precondition: ProbeExecutionPrecondition,
    context: ProbeExecutionContextKey,
) -> None:
    """Reject physical I/O unless this exact semantic context is freshly confirmed."""
    if not isinstance(precondition, ProbeExecutionPrecondition):
        raise TypeError("precondition must be ProbeExecutionPrecondition")
    if not isinstance(context, ProbeExecutionContextKey):
        raise TypeError("context must be ProbeExecutionContextKey")
    if not precondition.confirmed:
        raise RuntimeError("probe execution precondition is not confirmed")
    if context not in precondition.contexts:
        raise RuntimeError(
            "probe context differs from confirmed execution precondition"
        )
    if context.endpoint not in precondition.interfaces_stable_snapshot:
        raise RuntimeError(
            "probe context endpoint is absent from readiness interface snapshot"
        )


def verify_probe_execution_precondition(
    snapshot: StructuralPolicyPhysicalSnapshot,
    desired: ProbeNetworkPolicyDesiredState,
    platform: NetworkPolicyPlatformSpace,
) -> ProbeExecutionPrecondition:
    """Verify the complete current probe plane without mutating it."""
    _validate_snapshot_desired_platform(snapshot, desired, platform)
    contexts_by_owner = _execution_contexts_by_owner(desired)
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
        contexts=frozenset(contexts_by_owner.values()),
    )


def verify_probe_execution_precondition_scoped(
    snapshot: StructuralPolicyPhysicalSnapshot,
    full_desired: ProbeNetworkPolicyDesiredState,
    requested_owners: frozenset[ProbeSemanticOwner],
    platform: NetworkPolicyPlatformSpace,
) -> ProbeExecutionPrecondition:
    """Verify one semantic owner subset against one full accepted probe union.

    Missing sibling-owner state is irrelevant to the requested readiness verdict.
    Physical state outside the full accepted union remains stale/conflicting and
    therefore blocks every scoped verdict.
    """
    _validate_snapshot_desired_platform(snapshot, full_desired, platform)
    contexts_by_owner = _execution_contexts_by_owner(full_desired)

    if not isinstance(requested_owners, frozenset):
        raise ValueError("requested_owners must be a frozenset")
    if not all(is_probe_semantic_owner(owner) for owner in requested_owners):
        raise ValueError("requested_owners contains unsupported semantic owner")
    unknown = requested_owners - frozenset(contexts_by_owner)
    if unknown:
        raise ValueError("requested_owners must be a subset of full desired owners")

    table_by_owner = {
        rule.owner: rule.table
        for rule in full_desired.rules
    }
    if len(set(table_by_owner.values())) != len(table_by_owner):
        raise ValueError(
            "scoped readiness requires one unique probe table per semantic owner"
        )

    requested_tables = {
        table_by_owner[owner]
        for owner in requested_owners
    }
    requested_desired = ProbeNetworkPolicyDesiredState(
        routes=tuple(
            route
            for route in full_desired.routes
            if route.table in requested_tables
        ),
        rules=tuple(
            rule
            for rule in full_desired.rules
            if rule.owner in requested_owners
        ),
        local_rules=tuple(
            rule
            for rule in full_desired.local_rules
            if rule.owner in requested_owners
        ),
    )

    full_routing = compare_probe_routing(
        full_desired,
        snapshot.routing,
        platform,
    )
    requested_routing = compare_probe_routing(
        requested_desired,
        snapshot.routing,
        platform,
    )
    routing = ProbeRoutingComparison(
        confirmed_routes=requested_routing.confirmed_routes,
        missing_routes=requested_routing.missing_routes,
        stale_routes=full_routing.stale_routes,
        confirmed_rules=requested_routing.confirmed_rules,
        missing_rules=requested_routing.missing_rules,
        stale_rules=full_routing.stale_rules,
        observed_rules=full_routing.observed_rules,
        conflicts=full_routing.conflicts,
    )

    full_local = compare_probe_local(
        snapshot.nft,
        snapshot.interfaces,
        full_desired.local_rules,
    )
    requested_local = compare_probe_local(
        snapshot.nft,
        snapshot.interfaces,
        requested_desired.local_rules,
    )
    local = ProbeLocalComparison(
        confirmed=requested_local.confirmed,
        missing=requested_local.missing,
        stale=full_local.stale,
        conflicts=full_local.conflicts,
    )

    return ProbeExecutionPrecondition(
        routing=routing,
        local=local,
        interfaces_stable_snapshot=snapshot.interfaces,
        contexts=frozenset(
            contexts_by_owner[owner]
            for owner in requested_owners
        ),
    )


def _validate_snapshot_desired_platform(
    snapshot: StructuralPolicyPhysicalSnapshot,
    desired: ProbeNetworkPolicyDesiredState,
    platform: NetworkPolicyPlatformSpace,
) -> None:
    if not isinstance(snapshot, StructuralPolicyPhysicalSnapshot):
        raise ValueError(
            "snapshot must be StructuralPolicyPhysicalSnapshot"
        )
    if not isinstance(desired, ProbeNetworkPolicyDesiredState):
        raise ValueError(
            "desired must be ProbeNetworkPolicyDesiredState"
        )
    if not isinstance(platform, NetworkPolicyPlatformSpace):
        raise ValueError(
            "platform must be NetworkPolicyPlatformSpace"
        )


def _execution_contexts_by_owner(
    desired: ProbeNetworkPolicyDesiredState,
) -> dict[ProbeSemanticOwner, ProbeExecutionContextKey]:
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

    contexts = {}
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
        contexts[owner] = ProbeExecutionContextKey(
            owner=owner,
            mechanism=rule.mechanism,
            target=rule.target,
            endpoint=rule.endpoint,
        )
    return contexts
