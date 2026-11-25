"""D.002 current-only WireGuard peer/group realization Manager.

Architecture: D.002 WireGuardPeerManager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from ipaddress import IPv4Network
import json
from typing import Protocol

from .network_policy_layout import WireGuardPeerProbeOwner
from .probe_runtime import (
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)
from .release1_config import (
    ManagedWireGuardConfig,
    ManagedWireGuardGroupConfig,
    ManagedWireGuardPeerConfig,
    WireGuardPeerMembershipConfig,
)
from .route_priority_inventory import RoutePriorityPathRoute
from .wireguard_peer_ownership import (
    WireGuardPeerAllowedIPs,
    WireGuardPeerOwnershipDesired,
    WireGuardPeerOwnershipResult,
)


class WireGuardPeerManagerError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WireGuardPeerProbeRecord:
    peer_id: str
    observation: ProbeTechnicalObservation

    def __post_init__(self) -> None:
        if not isinstance(self.peer_id, str) or not self.peer_id:
            raise WireGuardPeerManagerError(
                "peer_id must be non-empty text"
            )
        if not isinstance(self.observation, ProbeTechnicalObservation):
            raise WireGuardPeerManagerError(
                "observation must be ProbeTechnicalObservation"
            )


@dataclass(frozen=True, slots=True)
class WireGuardGroupOwnershipRecord:
    profile_id: str
    owner_peer_id: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise WireGuardPeerManagerError(
                "profile_id must be non-empty text"
            )
        if self.owner_peer_id is not None and (
            not isinstance(self.owner_peer_id, str)
            or not self.owner_peer_id
        ):
            raise WireGuardPeerManagerError(
                "owner_peer_id must be non-empty text or None"
            )


@dataclass(frozen=True, slots=True)
class WireGuardPeerRealization:
    device_id: str
    base_generation: str
    interface_ifname: str
    interface_ifindex: int
    group_owners: tuple[WireGuardGroupOwnershipRecord, ...]
    generation: str | None
    probes: tuple[WireGuardPeerProbeRecord, ...] = ()
    problem: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id:
            raise WireGuardPeerManagerError(
                "device_id must be non-empty text"
            )
        if not isinstance(self.base_generation, str) or not self.base_generation:
            raise WireGuardPeerManagerError(
                "base_generation must be non-empty text"
            )
        if not isinstance(self.interface_ifname, str) or not self.interface_ifname:
            raise WireGuardPeerManagerError(
                "interface_ifname must be non-empty text"
            )
        if type(self.interface_ifindex) is not int or self.interface_ifindex <= 0:
            raise WireGuardPeerManagerError(
                "interface_ifindex must be a positive integer"
            )
        profile_ids = [item.profile_id for item in self.group_owners]
        if len(profile_ids) != len(set(profile_ids)):
            raise WireGuardPeerManagerError(
                "group ownership records must not repeat profile_id"
            )
        if self.problem is None and self.generation is None:
            raise WireGuardPeerManagerError(
                "confirmed realization requires generation"
            )
        if self.problem is not None:
            if not isinstance(self.problem, str) or not self.problem:
                raise WireGuardPeerManagerError(
                    "problem must be non-empty text"
                )
            if self.generation is not None or self.group_owners:
                raise WireGuardPeerManagerError(
                    "problem realization cannot claim current ownership/generation"
                )
        peer_ids = [item.peer_id for item in self.probes]
        if len(peer_ids) != len(set(peer_ids)):
            raise WireGuardPeerManagerError(
                "probe records must not repeat peer_id"
            )

    @property
    def ready(self) -> bool:
        return (
            self.problem is None
            and self.generation is not None
            and all(
                item.owner_peer_id is not None
                for item in self.group_owners
            )
        )

    def owner_for(self, profile_id: str) -> str | None:
        for item in self.group_owners:
            if item.profile_id == profile_id:
                return item.owner_peer_id
        raise KeyError(profile_id)


class WireGuardPeerProbePort(Protocol):
    def check(
        self,
        owner: WireGuardPeerProbeOwner,
        peer: ManagedWireGuardPeerConfig,
        path_route: RoutePriorityPathRoute,
    ) -> ProbeTechnicalObservation:
        """Fresh-check one peer after its exact C.001 precondition is confirmed."""


class WireGuardPeerOwnershipPort(Protocol):
    def converge(
        self,
        desired: WireGuardPeerOwnershipDesired,
    ) -> WireGuardPeerOwnershipResult:
        """Converge and fresh-confirm one complete D.003 owner state."""


@dataclass(frozen=True, slots=True)
class _PeerContext:
    device_id: str
    base_generation: str
    path_route: RoutePriorityPathRoute
    ordered_peers: tuple[ManagedWireGuardPeerConfig, ...]
    groups: tuple[ManagedWireGuardGroupConfig, ...]


@dataclass(slots=True)
class WireGuardPeerManager:
    """Own current group -> peer selection/generation for one managed WG Device."""

    _context: _PeerContext | None = field(default=None, init=False, repr=False)
    _confirmed_group_owners: tuple[
        WireGuardGroupOwnershipRecord, ...
    ] = field(default=(), init=False, repr=False)
    _confirmed_generation: str | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def current_state(self) -> WireGuardPeerRealization | None:
        context = self._context
        generation = self._confirmed_generation
        if context is None or generation is None:
            return None
        return self._projection(
            context,
            self._confirmed_group_owners,
            generation,
            (),
        )

    def reconcile(
        self,
        device_id: str,
        config: ManagedWireGuardConfig,
        groups: tuple[ManagedWireGuardGroupConfig, ...],
        *,
        base_generation: str,
        path_route: RoutePriorityPathRoute,
        probe: WireGuardPeerProbePort,
        ownership: WireGuardPeerOwnershipPort,
    ) -> WireGuardPeerRealization:
        context = self._validated_context(
            device_id,
            config,
            groups,
            base_generation,
            path_route,
        )
        same_context = self._context == context
        current_owners = (
            {
                item.profile_id: item.owner_peer_id
                for item in self._confirmed_group_owners
            }
            if same_context and self._confirmed_generation is not None
            else {}
        )

        records: list[WireGuardPeerProbeRecord] = []
        probe_cache: dict[str, ProbeTechnicalObservation] = {}

        def observe(peer_id: str) -> ProbeTechnicalObservation:
            cached = probe_cache.get(peer_id)
            if cached is not None:
                return cached
            peer = self._peer_by_id(context, peer_id)
            observation = self._probe(peer, context, probe)
            probe_cache[peer_id] = observation
            records.append(WireGuardPeerProbeRecord(peer_id, observation))
            return observation

        desired_owners: list[WireGuardGroupOwnershipRecord] = []
        for group in context.groups:
            current_owner = current_owners.get(group.profile_id)
            owner, diagnostic = self._select_group_owner(
                group,
                current_owner,
                observe,
            )
            if diagnostic is not None:
                return self._problem(context, records, diagnostic)
            desired_owners.append(
                WireGuardGroupOwnershipRecord(group.profile_id, owner)
            )

        desired_owner_tuple = tuple(desired_owners)
        desired = self._ownership_desired(context, desired_owner_tuple)
        result = ownership.converge(desired)
        if not isinstance(result, WireGuardPeerOwnershipResult):
            return self._problem(
                context,
                records,
                "D.003 returned invalid result type",
            )
        if not result.confirmed:
            return self._problem(
                context,
                records,
                "D.003 owner-state confirmation failed"
                + (
                    f": {result.diagnostic}"
                    if result.diagnostic
                    else ""
                ),
            )

        generation = _generation_token(context, desired_owner_tuple)
        self._context = context
        self._confirmed_group_owners = desired_owner_tuple
        self._confirmed_generation = generation
        return self._projection(
            context,
            desired_owner_tuple,
            generation,
            tuple(records),
        )

    @staticmethod
    def _select_group_owner(
        group: ManagedWireGuardGroupConfig,
        current_owner: str | None,
        observe,
    ) -> tuple[str | None, str | None]:
        memberships = group.peer_memberships

        if current_owner is not None:
            current_observation = observe(current_owner)
            if current_observation.outcome is ProbeTechnicalOutcome.LOCAL_ERROR:
                return (
                    None,
                    (
                        f"group {group.profile_id!r} current peer "
                        f"{current_owner!r} technical check is unconfirmed"
                        + (
                            f": {current_observation.diagnostic}"
                            if current_observation.diagnostic
                            else ""
                        )
                    ),
                )
            if current_observation.outcome is ProbeTechnicalOutcome.REPLY:
                current_index = next(
                    index
                    for index, membership in enumerate(memberships)
                    if membership.peer_id == current_owner
                )
                current_membership = memberships[current_index]
                if not current_membership.reserve:
                    return current_owner, None

                # A usable reserve owner can be displaced only by a
                # more-preferred usable ordinary candidate.
                for membership in memberships[:current_index]:
                    if membership.reserve:
                        continue
                    observation = observe(membership.peer_id)
                    if observation.outcome is ProbeTechnicalOutcome.REPLY:
                        return membership.peer_id, None
                return current_owner, None

        for membership in memberships:
            if membership.peer_id == current_owner:
                continue
            observation = observe(membership.peer_id)
            if observation.outcome is ProbeTechnicalOutcome.REPLY:
                return membership.peer_id, None

        return None, None

    def _probe(
        self,
        peer: ManagedWireGuardPeerConfig,
        context: _PeerContext,
        probe: WireGuardPeerProbePort,
    ) -> ProbeTechnicalObservation:
        try:
            value = probe.check(
                WireGuardPeerProbeOwner(
                    context.device_id,
                    peer.peer_id,
                ),
                peer,
                context.path_route,
            )
        except Exception as exc:
            return ProbeTechnicalObservation(
                ProbeTechnicalOutcome.LOCAL_ERROR,
                f"{type(exc).__name__}: {exc}",
            )
        if not isinstance(value, ProbeTechnicalObservation):
            return ProbeTechnicalObservation(
                ProbeTechnicalOutcome.LOCAL_ERROR,
                "peer probe port returned invalid observation type",
            )
        return value

    def _problem(
        self,
        context: _PeerContext,
        records: list[WireGuardPeerProbeRecord],
        diagnostic: str,
    ) -> WireGuardPeerRealization:
        # An ambiguous current reaction cannot retain an old generation as
        # current evidence. The next trigger starts from fresh lower facts.
        self._context = context
        self._confirmed_group_owners = ()
        self._confirmed_generation = None
        return self._projection(
            context,
            (),
            None,
            tuple(records),
            problem=diagnostic,
        )

    @staticmethod
    def _peer_by_id(
        context: _PeerContext,
        peer_id: str,
    ) -> ManagedWireGuardPeerConfig:
        for peer in context.ordered_peers:
            if peer.peer_id == peer_id:
                return peer
        raise WireGuardPeerManagerError(
            f"peer {peer_id!r} is absent from current context"
        )

    @staticmethod
    def _validated_context(
        device_id: str,
        config: ManagedWireGuardConfig,
        groups: tuple[ManagedWireGuardGroupConfig, ...],
        base_generation: str,
        path_route: RoutePriorityPathRoute,
    ) -> _PeerContext:
        if not isinstance(device_id, str) or not device_id:
            raise WireGuardPeerManagerError(
                "device_id must be non-empty text"
            )
        if not isinstance(config, ManagedWireGuardConfig):
            raise WireGuardPeerManagerError(
                "config must be ManagedWireGuardConfig"
            )
        if not isinstance(groups, tuple):
            raise WireGuardPeerManagerError(
                "groups must be a tuple of ManagedWireGuardGroupConfig"
            )
        if not isinstance(base_generation, str) or not base_generation:
            raise WireGuardPeerManagerError(
                "base_generation must be non-empty text"
            )
        if not isinstance(path_route, RoutePriorityPathRoute):
            raise WireGuardPeerManagerError(
                "path_route must be RoutePriorityPathRoute"
            )
        if path_route.path_id.device_id != device_id:
            raise WireGuardPeerManagerError(
                "current path Device differs from managed WireGuard Device"
            )
        if path_route.endpoint.ifname != config.interface:
            raise WireGuardPeerManagerError(
                "current path interface differs from managed WireGuard interface"
            )
        if not config.peers:
            raise WireGuardPeerManagerError(
                "managed WireGuard peer set must not be empty"
            )
        peer_ids = tuple(peer.peer_id for peer in config.peers)
        if len(peer_ids) != len(set(peer_ids)):
            raise WireGuardPeerManagerError(
                "managed WireGuard peer IDs must be unique"
            )
        known_peers = set(peer_ids)

        profile_ids: list[str] = []
        exact_prefix_owners: dict[IPv4Network, str] = {}
        for group in groups:
            if not isinstance(group, ManagedWireGuardGroupConfig):
                raise WireGuardPeerManagerError(
                    "groups must contain ManagedWireGuardGroupConfig"
                )
            if group.device_id != device_id:
                raise WireGuardPeerManagerError(
                    "recoverable group Device differs from managed WireGuard Device"
                )
            if group.availability_check is not None:
                raise WireGuardPeerManagerError(
                    "group endpoint probing is not materialized by D.002 yet"
                )
            if not group.prefixes:
                raise WireGuardPeerManagerError(
                    "recoverable group prefix bundle must not be empty"
                )
            if not group.peer_memberships:
                raise WireGuardPeerManagerError(
                    "recoverable group peer membership must not be empty"
                )
            for membership in group.peer_memberships:
                if not isinstance(membership, WireGuardPeerMembershipConfig):
                    raise WireGuardPeerManagerError(
                        "recoverable group peer membership has invalid type"
                    )
            membership_ids = [
                membership.peer_id
                for membership in group.peer_memberships
            ]
            if len(membership_ids) != len(set(membership_ids)):
                raise WireGuardPeerManagerError(
                    "recoverable group peer membership must be unique"
                )
            unknown = [peer_id for peer_id in membership_ids if peer_id not in known_peers]
            if unknown:
                raise WireGuardPeerManagerError(
                    f"recoverable group references unknown peer {unknown[0]!r}"
                )
            for prefix in group.prefixes:
                if not isinstance(prefix, IPv4Network):
                    raise WireGuardPeerManagerError(
                        "recoverable group prefix bundle has invalid type"
                    )
                previous = exact_prefix_owners.get(prefix)
                if previous is not None:
                    raise WireGuardPeerManagerError(
                        f"payload prefix {prefix} appears in groups "
                        f"{previous!r} and {group.profile_id!r}"
                    )
                exact_prefix_owners[prefix] = group.profile_id
            profile_ids.append(group.profile_id)

        if len(profile_ids) != len(set(profile_ids)):
            raise WireGuardPeerManagerError(
                "recoverable groups must not repeat profile_id"
            )

        return _PeerContext(
            device_id=device_id,
            base_generation=base_generation,
            path_route=path_route,
            ordered_peers=config.peers,
            groups=groups,
        )

    @staticmethod
    def _ownership_desired(
        context: _PeerContext,
        group_owners: tuple[WireGuardGroupOwnershipRecord, ...],
    ) -> WireGuardPeerOwnershipDesired:
        allowed_by_peer: dict[str, set[IPv4Network]] = {
            peer.peer_id: {IPv4Network(f"{peer.probe_target}/32")}
            for peer in context.ordered_peers
        }
        owner_by_profile = {
            item.profile_id: item.owner_peer_id
            for item in group_owners
        }
        for group in context.groups:
            owner_id = owner_by_profile[group.profile_id]
            if owner_id is not None:
                allowed_by_peer[owner_id].update(group.prefixes)

        peers = [
            WireGuardPeerAllowedIPs(
                peer.public_key,
                tuple(sorted(allowed_by_peer[peer.peer_id])),
            )
            for peer in context.ordered_peers
        ]
        return WireGuardPeerOwnershipDesired(
            context.device_id,
            context.path_route.endpoint,
            tuple(sorted(peers, key=lambda item: item.public_key)),
        )

    @staticmethod
    def _projection(
        context: _PeerContext,
        group_owners: tuple[WireGuardGroupOwnershipRecord, ...],
        generation: str | None,
        probes: tuple[WireGuardPeerProbeRecord, ...],
        *,
        problem: str | None = None,
    ) -> WireGuardPeerRealization:
        endpoint = context.path_route.endpoint
        return WireGuardPeerRealization(
            device_id=context.device_id,
            base_generation=context.base_generation,
            interface_ifname=endpoint.ifname,
            interface_ifindex=endpoint.ifindex,
            group_owners=group_owners,
            generation=generation,
            probes=probes,
            problem=problem,
        )


def _generation_token(
    context: _PeerContext,
    group_owners: tuple[WireGuardGroupOwnershipRecord, ...],
) -> str:
    facts = {
        "device_id": context.device_id,
        "base_generation": context.base_generation,
        "interface": {
            "ifname": context.path_route.endpoint.ifname,
            "ifindex": context.path_route.endpoint.ifindex,
        },
        "ordered_peers": [
            {
                "peer_id": peer.peer_id,
                "public_key": peer.public_key,
                "probe_target": str(peer.probe_target),
            }
            for peer in context.ordered_peers
        ],
        "groups": [
            {
                "profile_id": group.profile_id,
                "prefixes": [str(prefix) for prefix in group.prefixes],
                "peer_memberships": [
                    {
                        "peer_id": membership.peer_id,
                        "reserve": membership.reserve,
                    }
                    for membership in group.peer_memberships
                ],
            }
            for group in context.groups
        ],
        "group_owners": [
            {
                "profile_id": item.profile_id,
                "owner_peer_id": item.owner_peer_id,
            }
            for item in group_owners
        ],
    }
    return hashlib.sha256(
        json.dumps(
            facts,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
