"""D.002 current-only WireGuard peer selection and realization Manager.

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
    ManagedWireGuardPeerConfig,
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
class WireGuardPeerRealization:
    device_id: str
    base_generation: str
    interface_ifname: str
    interface_ifindex: int
    selected_peer_id: str | None
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
        if self.selected_peer_id is not None and (
            not isinstance(self.selected_peer_id, str)
            or not self.selected_peer_id
        ):
            raise WireGuardPeerManagerError(
                "selected_peer_id must be non-empty text or None"
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
            if self.generation is not None or self.selected_peer_id is not None:
                raise WireGuardPeerManagerError(
                    "problem realization cannot claim current owner/generation"
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
            and self.selected_peer_id is not None
        )


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
    shared_prefixes: tuple[IPv4Network, ...]


@dataclass(slots=True)
class WireGuardPeerManager:
    """Own current peer selection/generation for one managed WireGuard Device."""

    _context: _PeerContext | None = field(default=None, init=False, repr=False)
    _confirmed_owner_id: str | None = field(default=None, init=False, repr=False)
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
            self._confirmed_owner_id,
            generation,
            (),
        )

    def reconcile(
        self,
        device_id: str,
        config: ManagedWireGuardConfig,
        *,
        base_generation: str,
        path_route: RoutePriorityPathRoute,
        probe: WireGuardPeerProbePort,
        ownership: WireGuardPeerOwnershipPort,
    ) -> WireGuardPeerRealization:
        context = self._validated_context(
            device_id,
            config,
            base_generation,
            path_route,
        )
        same_context = self._context == context
        current_owner = (
            self._confirmed_owner_id
            if same_context and self._confirmed_generation is not None
            else None
        )

        records: list[WireGuardPeerProbeRecord] = []
        desired_owner: str | None = None

        if current_owner is not None:
            peer = self._peer_by_id(context, current_owner)
            observation = self._probe(peer, context, probe)
            records.append(WireGuardPeerProbeRecord(peer.peer_id, observation))
            if observation.outcome is ProbeTechnicalOutcome.REPLY:
                desired_owner = current_owner
            elif observation.outcome is ProbeTechnicalOutcome.LOCAL_ERROR:
                return self._problem(
                    context,
                    records,
                    (
                        f"current peer {current_owner!r} technical check is "
                        "unconfirmed"
                        + (
                            f": {observation.diagnostic}"
                            if observation.diagnostic
                            else ""
                        )
                    ),
                )

        if desired_owner is None:
            for peer in context.ordered_peers:
                if peer.peer_id == current_owner:
                    continue
                observation = self._probe(peer, context, probe)
                records.append(
                    WireGuardPeerProbeRecord(peer.peer_id, observation)
                )
                if observation.outcome is ProbeTechnicalOutcome.REPLY:
                    desired_owner = peer.peer_id
                    break

        desired = self._ownership_desired(context, desired_owner)
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

        generation = _generation_token(context, desired_owner)
        self._context = context
        self._confirmed_owner_id = desired_owner
        self._confirmed_generation = generation
        return self._projection(
            context,
            desired_owner,
            generation,
            tuple(records),
        )

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
        # A failed or ambiguous current reaction cannot retain an old generation
        # as current evidence. The next trigger starts from fresh lower facts.
        self._context = context
        self._confirmed_owner_id = None
        self._confirmed_generation = None
        return self._projection(
            context,
            None,
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
            f"current peer {peer_id!r} is absent from current context"
        )

    @staticmethod
    def _validated_context(
        device_id: str,
        config: ManagedWireGuardConfig,
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
        return _PeerContext(
            device_id=device_id,
            base_generation=base_generation,
            path_route=path_route,
            ordered_peers=config.peers,
            shared_prefixes=tuple(config.shared_prefixes),
        )

    @staticmethod
    def _ownership_desired(
        context: _PeerContext,
        owner_id: str | None,
    ) -> WireGuardPeerOwnershipDesired:
        peers = []
        for peer in context.ordered_peers:
            allowed = [IPv4Network(f"{peer.probe_target}/32")]
            if peer.peer_id == owner_id:
                allowed.extend(context.shared_prefixes)
            peers.append(
                WireGuardPeerAllowedIPs(
                    peer.public_key,
                    tuple(sorted(allowed)),
                )
            )
        return WireGuardPeerOwnershipDesired(
            context.device_id,
            context.path_route.endpoint,
            tuple(sorted(peers, key=lambda item: item.public_key)),
        )

    @staticmethod
    def _projection(
        context: _PeerContext,
        owner_id: str | None,
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
            selected_peer_id=owner_id,
            generation=generation,
            probes=probes,
            problem=problem,
        )


def _generation_token(
    context: _PeerContext,
    owner_id: str | None,
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
        "shared_prefixes": [
            str(prefix)
            for prefix in context.shared_prefixes
        ],
        "selected_peer_id": owner_id,
    }
    return hashlib.sha256(
        json.dumps(
            facts,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
