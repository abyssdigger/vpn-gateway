"""Semantic host-publication Adapter.

Architecture: structured Annex E, E.001 HostPublicationAdapter.
Requirement traceability: VPNG-U001-R1.R3.R6.R1, VPNG-U001-R4.R4.R6.R3,
VPNG-U004-R4.R6, VPNG-M001-R1.R1.R1/R4/R5, VPNG-D001-R1.R1.R3/R7.
"""

from __future__ import annotations

from dataclasses import dataclass

from .host_publication_policy import HostPublicationDesiredState
from .linux_host_publication import (
    HostPublicationConvergenceResult,
    HostPublicationPhysicalObservation,
    LinuxHostPublicationDriver,
    converge_host_publication_once,
)


@dataclass(slots=True)
class HostPublicationAdapter:
    """Own the semantic observe/apply/cleanup boundary for host publication."""

    driver: LinuxHostPublicationDriver

    def observe(self) -> HostPublicationPhysicalObservation:
        return self.driver.observe()

    def apply(
        self,
        desired: HostPublicationDesiredState,
    ) -> HostPublicationConvergenceResult:
        if not isinstance(desired, HostPublicationDesiredState):
            raise ValueError("desired must be HostPublicationDesiredState")
        return converge_host_publication_once(self.driver, desired)

    def cleanup(self) -> HostPublicationConvergenceResult:
        return converge_host_publication_once(
            self.driver,
            HostPublicationDesiredState(()),
        )
