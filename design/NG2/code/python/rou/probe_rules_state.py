from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .network_rules import (
    NetworkRulesSpec,
    NetworkRulesState,
    RoutingDomainSpec,
    StateKnowledge,
)


class Knowledge(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


class Convergence(str, Enum):
    MATCHED = "matched"
    DIVERGED = "diverged"
    UNKNOWN = "unknown"


class Usability(str, Enum):
    READY = "ready"
    INVALID = "invalid"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProbeRulesState:
    """Assessment of whether current network rules can validate probe results.

    INVALID does not mean the remote endpoint is unreachable. It means the local
    network plane differs from desired, so neither success nor failure of an active
    probe is authoritative availability evidence.
    """

    knowledge: Knowledge
    convergence: Convergence
    usability: Usability

    def __post_init__(self) -> None:
        if self.knowledge is Knowledge.UNKNOWN:
            if (
                self.convergence is not Convergence.UNKNOWN
                or self.usability is not Usability.UNKNOWN
            ):
                raise ValueError(
                    "unknown probe-rules knowledge requires unknown dependent axes"
                )
            return

        if self.convergence is Convergence.UNKNOWN:
            raise ValueError(
                "known probe-rules knowledge requires convergence assessment"
            )
        if self.convergence is Convergence.MATCHED:
            if self.usability is not Usability.READY:
                raise ValueError(
                    "matched probe rules must be ready for probe evidence"
                )
            return
        if self.usability is not Usability.INVALID:
            raise ValueError(
                "diverged probe rules must invalidate probe evidence"
            )


def _authoritative(observed: NetworkRulesState) -> bool:
    return (
        observed.knowledge is StateKnowledge.KNOWN
        and observed.fresh
        and observed.rules is not None
    )


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


class ProbeRulesStateCalculator:
    """Assess whether observed rules make active-probe results authoritative."""

    def calculate(
        self,
        desired: NetworkRulesSpec,
        observed: NetworkRulesState,
    ) -> ProbeRulesState:
        if not _authoritative(observed):
            return ProbeRulesState(
                knowledge=Knowledge.UNKNOWN,
                convergence=Convergence.UNKNOWN,
                usability=Usability.UNKNOWN,
            )

        assert observed.rules is not None
        if _semantically_equal(observed.rules, desired):
            return ProbeRulesState(
                knowledge=Knowledge.KNOWN,
                convergence=Convergence.MATCHED,
                usability=Usability.READY,
            )

        return ProbeRulesState(
            knowledge=Knowledge.KNOWN,
            convergence=Convergence.DIVERGED,
            usability=Usability.INVALID,
        )
