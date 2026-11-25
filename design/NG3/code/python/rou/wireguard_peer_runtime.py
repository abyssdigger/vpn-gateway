"""Runtime coordination seam for D.002 WireGuard peer/group reconciliation.

Architecture: A.001 runtime composition, C.001 shared probe plane,
D.001 managed base realization, D.002 WireGuardPeerManager, D.003 ownership enforcer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol

from .managed_device_manager import (
    ManagedDeviceDesiredState,
    ManagedDeviceRealization,
)
from .managed_wireguard_adapter import ManagedWireGuardState
from .network_policy_layout import (
    NetworkPolicyPlatformSpace,
    ProbeSemanticOwner,
    WireGuardGroupProbeOwner,
    WireGuardPeerProbeOwner,
)
from .probe_plane_desired import ProbePlaneDesiredAssembly
from .probe_precondition import (
    ProbeExecutionPrecondition,
    verify_probe_execution_precondition_scoped,
)
from .release1_config import (
    CurrentConfig,
    ManagedWireGuardGroupConfig,
)
from .route_priority_inventory import RoutePriorityPathRoute
from .structural_policy_mutation import StructuralPolicyPhysicalSnapshot
from .wireguard_group_probe_executor import WireGuardGroupProbeExecutor
from .wireguard_peer_manager import (
    WireGuardPeerManager,
    WireGuardPeerOwnershipPort,
    WireGuardPeerRealization,
)
from .wireguard_peer_probe_executor import (
    PhysicalIcmpProbePort,
    WireGuardPeerProbeExecutor,
)


class WireGuardPeerRuntimeError(RuntimeError):
    pass


class StructuralProbeSnapshotObserver(Protocol):
    def observe_structural_snapshot(
        self,
    ) -> StructuralPolicyPhysicalSnapshot:
        """Fresh-observe the complete C.001 structural policy snapshot."""


@dataclass(frozen=True, slots=True)
class WireGuardPeerRuntimeResult:
    realizations: tuple[WireGuardPeerRealization, ...]

    @property
    def confirmed(self) -> bool:
        """True when every active D.002 Manager produced a current realization."""
        return all(item.problem is None for item in self.realizations)

    @property
    def ready(self) -> bool:
        """True when every recoverable group also has a confirmed current owner."""
        return all(item.ready for item in self.realizations)


@dataclass(slots=True)
class _FreshScopedProbePort:
    observer: StructuralProbeSnapshotObserver
    assembly: ProbePlaneDesiredAssembly
    platform: NetworkPolicyPlatformSpace
    driver: PhysicalIcmpProbePort

    def precondition(
        self,
        owner: ProbeSemanticOwner,
    ) -> ProbeExecutionPrecondition:
        snapshot = self.observer.observe_structural_snapshot()
        return verify_probe_execution_precondition_scoped(
            snapshot,
            self.assembly.probe,
            frozenset({owner}),
            self.platform,
        )


@dataclass(slots=True)
class _PeerProbePort:
    scoped: _FreshScopedProbePort

    def check(self, owner, peer, path_route):
        return WireGuardPeerProbeExecutor(
            self.scoped.precondition(owner),
            self.scoped.driver,
        ).check(owner, peer, path_route)


@dataclass(slots=True)
class _GroupProbePort:
    scoped: _FreshScopedProbePort

    def check(self, owner, group, path_route):
        return WireGuardGroupProbeExecutor(
            self.scoped.precondition(owner),
            self.scoped.driver,
        ).check(owner, group, path_route)


@dataclass(slots=True)
class WireGuardPeerRuntimeCoordinator:
    """Retain one current D.002 Manager per active managed WireGuard Device."""

    _managers: dict[str, WireGuardPeerManager] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def reconcile(
        self,
        config: CurrentConfig,
        managed_realizations: Iterable[ManagedDeviceRealization],
        path_routes: Iterable[RoutePriorityPathRoute],
        assembly: ProbePlaneDesiredAssembly,
        *,
        snapshot_observer: StructuralProbeSnapshotObserver,
        probe_driver: PhysicalIcmpProbePort,
        ownership: WireGuardPeerOwnershipPort,
        platform: NetworkPolicyPlatformSpace,
    ) -> WireGuardPeerRuntimeResult:
        if not isinstance(config, CurrentConfig):
            raise WireGuardPeerRuntimeError(
                "config must be CurrentConfig"
            )
        if not isinstance(assembly, ProbePlaneDesiredAssembly):
            raise WireGuardPeerRuntimeError(
                "assembly must be ProbePlaneDesiredAssembly"
            )
        if not isinstance(platform, NetworkPolicyPlatformSpace):
            raise WireGuardPeerRuntimeError(
                "platform must be NetworkPolicyPlatformSpace"
            )

        bases = tuple(managed_realizations)
        if any(not isinstance(item, ManagedDeviceRealization) for item in bases):
            raise WireGuardPeerRuntimeError(
                "managed_realizations must contain ManagedDeviceRealization"
            )
        base_by_device = {item.device_id: item for item in bases}
        if len(base_by_device) != len(bases):
            raise WireGuardPeerRuntimeError(
                "managed_realizations repeats a Device"
            )

        routes = tuple(path_routes)
        if any(not isinstance(item, RoutePriorityPathRoute) for item in routes):
            raise WireGuardPeerRuntimeError(
                "path_routes must contain RoutePriorityPathRoute"
            )
        route_ids = [item.path_id for item in routes]
        if len(route_ids) != len(set(route_ids)):
            raise WireGuardPeerRuntimeError(
                "path_routes repeats a logical path realization"
            )

        groups_by_device: dict[str, list[ManagedWireGuardGroupConfig]] = {}
        for key in sorted(config.wireguard_groups):
            group = config.wireguard_groups[key]
            groups_by_device.setdefault(group.device_id, []).append(group)

        routes_by_device: dict[str, list[RoutePriorityPathRoute]] = {}
        for route in routes:
            routes_by_device.setdefault(
                route.path_id.device_id,
                [],
            ).append(route)

        active_ids: set[str] = set()
        realizations: list[WireGuardPeerRealization] = []
        scoped = _FreshScopedProbePort(
            snapshot_observer,
            assembly,
            platform,
            probe_driver,
        )
        peer_port = _PeerProbePort(scoped)
        group_port = _GroupProbePort(scoped)

        for device_id in sorted(groups_by_device):
            device_routes = tuple(routes_by_device.get(device_id, ()))
            if not device_routes:
                # No accepted current path means no current D.002 execution
                # context. Any previously retained Manager must be discarded.
                continue
            if len(device_routes) != 1:
                raise WireGuardPeerRuntimeError(
                    f"managed WireGuard Device {device_id!r} has ambiguous "
                    "current logical paths"
                )
            path_route = device_routes[0]

            managed = config.managed_vpns.get(device_id)
            if managed is None:
                raise WireGuardPeerRuntimeError(
                    f"WireGuard groups reference unmanaged Device {device_id!r}"
                )
            if path_route.endpoint.ifname != managed.interface:
                raise WireGuardPeerRuntimeError(
                    f"managed WireGuard Device {device_id!r} current path "
                    "does not use its configured interface"
                )

            base = base_by_device.get(device_id)
            if (
                base is None
                or base.desired_state is not ManagedDeviceDesiredState.PRESENT
                or base.confirmed_state is not ManagedWireGuardState.PRESENT
                or base.confirmed_generation is None
                or base.desired_generation != base.confirmed_generation
                or base.problem is not None
                or base.waiting_for_dependencies
            ):
                raise WireGuardPeerRuntimeError(
                    f"managed WireGuard Device {device_id!r} has no "
                    "confirmed current D.001 base generation"
                )

            groups = tuple(groups_by_device[device_id])
            self._verify_probe_owner_union(
                device_id,
                groups,
                path_route,
                assembly,
            )

            manager = self._managers.get(device_id)
            if manager is None:
                manager = WireGuardPeerManager()
                self._managers[device_id] = manager
            active_ids.add(device_id)

            realization = manager.reconcile(
                device_id,
                managed,
                groups,
                base_generation=base.confirmed_generation,
                path_route=path_route,
                probe=peer_port,
                ownership=ownership,
                group_probe=(
                    group_port
                    if any(
                        group.availability_check is not None
                        for group in groups
                    )
                    else None
                ),
            )
            realizations.append(realization)

        self._managers = {
            device_id: self._managers[device_id]
            for device_id in sorted(active_ids)
        }
        return WireGuardPeerRuntimeResult(tuple(realizations))

    @staticmethod
    def _verify_probe_owner_union(
        device_id: str,
        groups: tuple[ManagedWireGuardGroupConfig, ...],
        path_route: RoutePriorityPathRoute,
        assembly: ProbePlaneDesiredAssembly,
    ) -> None:
        expected_peer_owners = frozenset(
            WireGuardPeerProbeOwner(
                device_id,
                membership.peer_id,
            )
            for group in groups
            for membership in group.peer_memberships
        )
        actual_peer_owners = frozenset(
            intent.owner
            for intent in assembly.peer_intents
            if intent.owner.device_id == device_id
        )
        if actual_peer_owners != expected_peer_owners:
            raise WireGuardPeerRuntimeError(
                f"D.002 peer probe owner union is stale for Device {device_id!r}"
            )
        if any(
            intent.path_route != path_route
            for intent in assembly.peer_intents
            if intent.owner.device_id == device_id
        ):
            raise WireGuardPeerRuntimeError(
                f"D.002 peer probe path binding is stale for Device {device_id!r}"
            )

        expected_group_owners = frozenset(
            WireGuardGroupProbeOwner(
                group.profile_id,
                device_id,
            )
            for group in groups
            if group.availability_check is not None
        )
        actual_group_owners = frozenset(
            intent.owner
            for intent in assembly.group_intents
            if intent.owner.device_id == device_id
        )
        if actual_group_owners != expected_group_owners:
            raise WireGuardPeerRuntimeError(
                f"D.002 group probe owner union is stale for Device {device_id!r}"
            )
        if any(
            intent.path_route != path_route
            for intent in assembly.group_intents
            if intent.owner.device_id == device_id
        ):
            raise WireGuardPeerRuntimeError(
                f"D.002 group probe path binding is stale for Device {device_id!r}"
            )
