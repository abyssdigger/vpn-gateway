from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .network_rules import NetworkRulesSpec, NetworkRulesState, StateKnowledge


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

        if actual == desired:
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

        # A syntactic difference is not enough to prove semantic permission widening or
        # a conservative subset. Keep the independent axes unknown until a relation
        # algorithm can prove them.
        return PayloadRulesState(
            knowledge=Knowledge.KNOWN,
            convergence=Convergence.DIVERGED,
            safety=Safety.UNKNOWN,
            service=Service.UNKNOWN,
        )
