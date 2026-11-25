"""D.002 peer technical-probe execution over confirmed C.001/C.008 lower seams.

Architecture: D.002 WireGuardPeerManager, C.001 NetworkPolicyAdapter,
C.008 ActiveProbeDriver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .icmp_probe_driver import IcmpProbePhysicalContext
from .network_policy_layout import WireGuardPeerProbeOwner
from .probe_policy import AvailabilityProbeMechanism
from .probe_precondition import (
    ProbeExecutionContextKey,
    ProbeExecutionPrecondition,
    require_probe_execution_context,
)
from .probe_runtime import ProbeTechnicalObservation
from .release1_config import ManagedWireGuardPeerConfig
from .route_priority_inventory import RoutePriorityPathRoute


class PhysicalIcmpProbePort(Protocol):
    def execute(
        self,
        context: IcmpProbePhysicalContext,
    ) -> ProbeTechnicalObservation:
        """Execute one bounded physical ICMP attempt."""


@dataclass(slots=True)
class WireGuardPeerProbeExecutor:
    """Execute one D.002 peer check only from an exact confirmed peer precondition."""

    precondition: ProbeExecutionPrecondition
    driver: PhysicalIcmpProbePort

    def __post_init__(self) -> None:
        if not isinstance(self.precondition, ProbeExecutionPrecondition):
            raise ValueError(
                "precondition must be ProbeExecutionPrecondition"
            )

    def check(
        self,
        owner: WireGuardPeerProbeOwner,
        peer: ManagedWireGuardPeerConfig,
        path_route: RoutePriorityPathRoute,
    ) -> ProbeTechnicalObservation:
        if not isinstance(owner, WireGuardPeerProbeOwner):
            raise TypeError("owner must be WireGuardPeerProbeOwner")
        if not isinstance(peer, ManagedWireGuardPeerConfig):
            raise TypeError("peer must be ManagedWireGuardPeerConfig")
        if not isinstance(path_route, RoutePriorityPathRoute):
            raise TypeError("path_route must be RoutePriorityPathRoute")
        if owner.peer_id != peer.peer_id:
            raise ValueError(
                "peer probe owner differs from requested peer"
            )
        if owner.device_id != path_route.path_id.device_id:
            raise ValueError(
                "peer probe owner Device differs from current path Device"
            )

        context_key = ProbeExecutionContextKey(
            owner=owner,
            mechanism=AvailabilityProbeMechanism.ICMP,
            target=peer.probe_target,
            endpoint=path_route.endpoint,
        )
        require_probe_execution_context(
            self.precondition,
            context_key,
        )
        result = self.driver.execute(
            IcmpProbePhysicalContext(
                endpoint=path_route.endpoint,
                target=peer.probe_target,
            )
        )
        if not isinstance(result, ProbeTechnicalObservation):
            raise TypeError(
                "physical ICMP Driver returned invalid observation type"
            )
        return result
