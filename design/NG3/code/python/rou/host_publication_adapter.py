"""Semantic host-publication Adapter.

Architecture: structured Annex E, E.001 HostPublicationAdapter.
Requirement traceability: VPNG0001-R1.R3.R6.R1, VPNG0001-R4.R4.R6.R3,
VPNG0004-R4.R6, VPNG0005-R5.R1/R4/R5, VPNG0007-R7.R3/R7.
"""

from __future__ import annotations

from dataclasses import dataclass

from .host_publication_policy import HostPublicationDesiredState
from .linux_host_publication import (
    HostPublicationConvergenceResult,
    HostPublicationPhysicalObservation,
    LinuxHostPublicationBackend,
    converge_host_publication_once,
)


@dataclass(slots=True)
class HostPublicationAdapter:
    """Own the semantic observe/apply/cleanup boundary for host publication."""

    backend: LinuxHostPublicationBackend

    def observe(self) -> HostPublicationPhysicalObservation:
        return self.backend.observe()

    def apply(
        self,
        desired: HostPublicationDesiredState,
    ) -> HostPublicationConvergenceResult:
        if not isinstance(desired, HostPublicationDesiredState):
            raise ValueError("desired must be HostPublicationDesiredState")
        return converge_host_publication_once(self.backend, desired)

    def cleanup(self) -> HostPublicationConvergenceResult:
        return converge_host_publication_once(
            self.backend,
            HostPublicationDesiredState(()),
        )
