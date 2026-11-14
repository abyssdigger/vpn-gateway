from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .network_rules import (
    NetworkRulesSpec,
    NetworkRulesState,
    PredicateKind,
    RoutingDomainSpec,
    StateKnowledge,
    TrafficPredicate,
)


class Knowledge(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


class Convergence(str, Enum):
    MATCHED = "matched"
    DIVERGED = "diverged"
    UNKNOWN = "unknown"


class Safety(str, Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    UNKNOWN = "unknown"


class Service(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    ISOLATED = "isolated"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PayloadRulesState:
    knowledge: Knowledge
    convergence: Convergence
    safety: Safety
    service: Service


def _authoritative(observed: NetworkRulesState) -> bool:
    return (
        observed.knowledge is StateKnowledge.KNOWN
        and observed.fresh
        and observed.rules is not None
    )


def _isolated(rules: NetworkRulesSpec) -> bool:
    # Filtering is default-deny. With no allowed payload bytes the payload plane is
    # proven closed regardless of inert routing/NAT objects that may also be present.
    return not rules.traffic_allows


def _matched_service(rules: NetworkRulesSpec) -> Service:
    if _isolated(rules):
        return Service.ISOLATED

    if rules.routing_domains and any(
        not domain.ordered_paths
        for domain in rules.routing_domains
    ):
        return Service.DEGRADED

    return Service.READY


def _ordered_subsequence[T](actual: tuple[T, ...], desired: tuple[T, ...]) -> bool:
    if not actual:
        return True

    wanted = iter(desired)
    for item in actual:
        for candidate in wanted:
            if candidate == item:
                break
        else:
            return False
    return True


def _routing_is_restrictive(
    actual: tuple[RoutingDomainSpec, ...],
    desired: tuple[RoutingDomainSpec, ...],
) -> bool:
    actual_by_name = {item.name: item for item in actual}
    desired_by_name = {item.name: item for item in desired}

    if actual_by_name.keys() != desired_by_name.keys():
        return False

    for name, wanted in desired_by_name.items():
        observed = actual_by_name[name]
        if observed.destinations != wanted.destinations:
            return False
        if observed.terminal_disposition is not wanted.terminal_disposition:
            return False
        if not _ordered_subsequence(
            observed.ordered_paths,
            wanted.ordered_paths,
        ):
            return False

    return True


def _routing_semantically_equal(
    actual: tuple[RoutingDomainSpec, ...],
    desired: tuple[RoutingDomainSpec, ...],
) -> bool:
    actual_by_name = {item.name: item for item in actual}
    desired_by_name = {item.name: item for item in desired}

    if actual_by_name.keys() != desired_by_name.keys():
        return False

    for name, wanted in desired_by_name.items():
        observed = actual_by_name[name]
        if set(observed.destinations) != set(wanted.destinations):
            return False
        if observed.ordered_paths != wanted.ordered_paths:
            return False
        if observed.terminal_disposition is not wanted.terminal_disposition:
            return False

    return True


def _semantically_equal(
    actual: NetworkRulesSpec,
    desired: NetworkRulesSpec,
) -> bool:
    return (
        _routing_semantically_equal(
            actual.routing_domains,
            desired.routing_domains,
        )
        and actual.dispatch_rules == desired.dispatch_rules
        and set(actual.traffic_allows) == set(desired.traffic_allows)
        and set(actual.flow_initiation_allows)
        == set(desired.flow_initiation_allows)
        and actual.source_nat == desired.source_nat
    )


def _provably_restrictive(
    actual: NetworkRulesSpec,
    desired: NetworkRulesSpec,
) -> bool:
    """Prove a narrow class of conservative divergence.

    This intentionally does not attempt general predicate implication.
    """

    if not _routing_is_restrictive(
        actual.routing_domains,
        desired.routing_domains,
    ):
        return False

    if actual.dispatch_rules != desired.dispatch_rules:
        # Missing/changing dispatch may fall through to unrelated routing, so it is not
        # safe to interpret as a restriction.
        return False

    if not set(actual.traffic_allows).issubset(desired.traffic_allows):
        return False

    if not set(actual.flow_initiation_allows).issubset(
        desired.flow_initiation_allows
    ):
        return False

    if actual.source_nat != desired.source_nat:
        # NAT order is not yet defined as commutative in the generic contract. Require
        # exact equality rather than assuming reordering is harmless.
        return False

    return True


def _predicate_provably_nonempty(predicate: TrafficPredicate) -> bool:
    if predicate.kind in {PredicateKind.ALWAYS, PredicateKind.MATCH}:
        return True
    if predicate.kind is PredicateKind.ANY:
        return any(_predicate_provably_nonempty(item) for item in predicate.children)
    return False


def _provably_permission_widened(
    actual: NetworkRulesSpec,
    desired: NetworkRulesSpec,
) -> bool:
    """Prove only endpoint-pair permission widening.

    If desired has no byte-level allow at all for an endpoint pair and actual has a
    provably non-empty allow there, actual permits behavior desired forbids. More subtle
    predicate widening is deliberately left UNKNOWN.
    """

    desired_pairs = {
        (item.source, item.destination)
        for item in desired.traffic_allows
    }

    return any(
        (item.source, item.destination) not in desired_pairs
        and _predicate_provably_nonempty(item.predicate)
        for item in actual.traffic_allows
    )


class PayloadRulesStateCalculator:
    """Conservatively assess observed rules against desired payload rules."""

    def calculate(
        self,
        desired: NetworkRulesSpec,
        observed: NetworkRulesState,
    ) -> PayloadRulesState:
        if not _authoritative(observed):
            return PayloadRulesState(
                knowledge=Knowledge.UNKNOWN,
                convergence=Convergence.UNKNOWN,
                safety=Safety.UNKNOWN,
                service=Service.UNKNOWN,
            )

        assert observed.rules is not None
        actual = observed.rules

        if _semantically_equal(actual, desired):
            return PayloadRulesState(
                knowledge=Knowledge.KNOWN,
                convergence=Convergence.MATCHED,
                safety=Safety.SAFE,
                service=_matched_service(actual),
            )

        if _isolated(actual):
            return PayloadRulesState(
                knowledge=Knowledge.KNOWN,
                convergence=Convergence.DIVERGED,
                safety=Safety.SAFE,
                service=Service.ISOLATED,
            )

        if _provably_restrictive(actual, desired):
            return PayloadRulesState(
                knowledge=Knowledge.KNOWN,
                convergence=Convergence.DIVERGED,
                safety=Safety.SAFE,
                service=Service.DEGRADED,
            )

        if _provably_permission_widened(actual, desired):
            return PayloadRulesState(
                knowledge=Knowledge.KNOWN,
                convergence=Convergence.DIVERGED,
                safety=Safety.UNSAFE,
                service=Service.UNKNOWN,
            )

        return PayloadRulesState(
            knowledge=Knowledge.KNOWN,
            convergence=Convergence.DIVERGED,
            safety=Safety.UNKNOWN,
            service=Service.UNKNOWN,
        )
