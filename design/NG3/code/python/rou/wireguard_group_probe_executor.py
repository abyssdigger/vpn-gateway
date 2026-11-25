"""D.002 group endpoint probe execution over confirmed C.001/C.008 seams.

Architecture: D.002 WireGuardPeerManager, C.001 NetworkPolicyAdapter,
C.008 ActiveProbeDriver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .icmp_probe_driver import IcmpProbePhysicalContext
from .network_policy_layout import WireGuardGroupProbeOwner
from .probe_policy import AvailabilityProbeMechanism
from .probe_precondition import (
    ProbeExecutionContextKey,
    ProbeExecutionPrecondition,
    require_probe_execution_context,
)
from .probe_runtime import ProbeTechnicalObservation
from .release1_config import ManagedWireGuardGroupConfig
from .route_priority_inventory import RoutePriorityPathRoute


class PhysicalIcmpGroupProbePort(Protocol):
    def execute(
        self,
        context: IcmpProbePhysicalContext,
    ) -> ProbeTechnicalObservation:
        """Execute one bounded physical ICMP attempt."""


@dataclass(slots=True)
class WireGuardGroupProbeExecutor:
    """Execute one recoverable-group endpoint check from an exact precondition."""

    precondition: ProbeExecutionPrecondition
    driver: PhysicalIcmpGroupProbePort

    def __post_init__(self) -> None:
        if not isinstance(self.precondition, ProbeExecutionPrecondition):
            raise ValueError(
                "precondition must be ProbeExecutionPrecondition"
            )

    def check(
        self,
        owner: WireGuardGroupProbeOwner,
        group: ManagedWireGuardGroupConfig,
        path_route: RoutePriorityPathRoute,
    ) -> ProbeTechnicalObservation:
        if not isinstance(owner, WireGuardGroupProbeOwner):
            raise TypeError("owner must be WireGuardGroupProbeOwner")
        if not isinstance(group, ManagedWireGuardGroupConfig):
            raise TypeError("group must be ManagedWireGuardGroupConfig")
        if not isinstance(path_route, RoutePriorityPathRoute):
            raise TypeError("path_route must be RoutePriorityPathRoute")
        if (
            owner.profile_id != group.profile_id
            or owner.device_id != group.device_id
        ):
            raise ValueError(
                "group probe owner differs from requested recoverable group"
            )
        if owner.device_id != path_route.path_id.device_id:
            raise ValueError(
                "group probe owner Device differs from current path Device"
            )

        check = group.availability_check
        if check is None:
            raise ValueError(
                "recoverable group has no endpoint availability check"
            )
        if check.mechanism != "icmp" or check.target is None:
            raise ValueError(
                "recoverable group endpoint check must be concrete ICMP"
            )
        if not any(check.target in prefix for prefix in group.prefixes):
            raise ValueError(
                "recoverable group endpoint target is outside group prefixes"
            )

        context_key = ProbeExecutionContextKey(
            owner=owner,
            mechanism=AvailabilityProbeMechanism.ICMP,
            target=check.target,
            endpoint=path_route.endpoint,
        )
        require_probe_execution_context(
            self.precondition,
            context_key,
        )
        result = self.driver.execute(
            IcmpProbePhysicalContext(
                endpoint=path_route.endpoint,
                target=check.target,
            )
        )
        if not isinstance(result, ProbeTechnicalObservation):
            raise TypeError(
                "physical ICMP Driver returned invalid observation type"
            )
        return result
