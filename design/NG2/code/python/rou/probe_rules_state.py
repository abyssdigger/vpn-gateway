from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .network_rules import (
    NetworkRulesSpec,
    NetworkRulesState,
    StateKnowledge,
    network_rules_semantically_equal,
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
        if network_rules_semantically_equal(observed.rules, desired):
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
