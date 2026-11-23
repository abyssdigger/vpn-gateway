"""Linux fresh-observation boundary for current VPN path endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Address
import json
from types import MappingProxyType
from typing import Mapping, Protocol, Sequence

from .interface_identity import InterfaceIdentity
from .interface_inventory import InterfaceInventoryError, parse_ip_link_inventory


class VpnPathObservationError(RuntimeError):
    """Fresh lower endpoint inventory could not be authoritatively established."""


class VpnPathObservationRunner(Protocol):
    def run(self, argv: Sequence[str]) -> str:
        """Run one argv-only observation command or raise; return stdout text."""


@dataclass(frozen=True, slots=True)
class VpnPathInterfaceObservation:
    interfaces: tuple[InterfaceIdentity, ...]
    private_peers: Mapping[InterfaceIdentity, IPv4Address | None] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "private_peers",
            MappingProxyType(dict(self.private_peers)),
        )


@dataclass(slots=True)
class LinuxVpnPathAdapter:
    """Stateless Adapter: each call obtains one complete fresh managed-netns inventory."""

    runner: VpnPathObservationRunner
    network_namespace: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.network_namespace, str)
            or not self.network_namespace
        ):
            raise ValueError("network_namespace must be non-empty text")

    def observe_interfaces(
        self,
        *,
        required_host_boundary: InterfaceIdentity | None = None,
        require_private_peer: bool = False,
    ) -> VpnPathInterfaceObservation:
        """Fresh-observe exact link generations and, on demand, coherent P2P peers."""

        if (
            required_host_boundary is not None
            and not isinstance(required_host_boundary, InterfaceIdentity)
        ):
            raise ValueError(
                "required_host_boundary must be InterfaceIdentity or None"
            )

        try:
            raw = self.runner.run(
                (
                    "ip",
                    "-n",
                    self.network_namespace,
                    "-j",
                    "link",
                    "show",
                )
            )
        except Exception as exc:
            raise VpnPathObservationError(
                "managed-domain interface observation command failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        try:
            interfaces = parse_ip_link_inventory(raw)
        except InterfaceInventoryError as exc:
            raise VpnPathObservationError(
                f"managed-domain interface inventory is invalid: {exc}"
            ) from exc

        if (
            required_host_boundary is not None
            and required_host_boundary not in interfaces
        ):
            same_name = tuple(
                item
                for item in interfaces
                if item.ifname == required_host_boundary.ifname
            )
            detail = (
                "same-name different generation is present"
                if same_name
                else "interface is absent"
            )
            raise VpnPathObservationError(
                "fresh managed-domain interface inventory does not contain "
                "the verified host-boundary generation; "
                + detail
            )

        if not require_private_peer:
            return VpnPathInterfaceObservation(interfaces=interfaces)

        try:
            raw_addr = self.runner.run(
                (
                    "ip",
                    "-n",
                    self.network_namespace,
                    "-j",
                    "addr",
                    "show",
                )
            )
        except Exception as exc:
            raise VpnPathObservationError(
                "managed-domain private-peer observation command failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        private_peers = _parse_private_peer_inventory(
            raw_addr,
            interfaces,
        )
        return VpnPathInterfaceObservation(
            interfaces=interfaces,
            private_peers=private_peers,
        )


def _parse_private_peer_inventory(
    text: str,
    interfaces: tuple[InterfaceIdentity, ...],
) -> Mapping[InterfaceIdentity, IPv4Address | None]:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VpnPathObservationError(
            f"managed-domain private-peer inventory is invalid JSON: {exc}"
        ) from None
    if not isinstance(raw, list):
        raise VpnPathObservationError(
            "managed-domain private-peer inventory root must be an array"
        )

    expected = set(interfaces)
    seen: set[InterfaceIdentity] = set()
    result: dict[InterfaceIdentity, IPv4Address | None] = {}

    for position, row in enumerate(raw):
        if not isinstance(row, dict):
            raise VpnPathObservationError(
                f"private-peer inventory[{position}] must be an object"
            )
        ifname = row.get("ifname")
        ifindex = row.get("ifindex")
        if not isinstance(ifname, str) or not ifname:
            raise VpnPathObservationError(
                f"private-peer inventory[{position}] has invalid ifname"
            )
        if type(ifindex) is not int or ifindex <= 0:
            raise VpnPathObservationError(
                f"private-peer inventory[{position}] has invalid ifindex"
            )

        identity = InterfaceIdentity(ifname, ifindex)
        if identity not in expected:
            raise VpnPathObservationError(
                "link/address snapshots disagree on interface generation: "
                f"{identity!r}"
            )
        if identity in seen:
            raise VpnPathObservationError(
                f"private-peer inventory repeats {identity!r}"
            )
        seen.add(identity)

        peer_candidates: set[IPv4Address] = set()
        addr_info = row.get("addr_info", [])
        if not isinstance(addr_info, list):
            raise VpnPathObservationError(
                f"private-peer inventory has invalid addr_info for {ifname!r}"
            )
        for info in addr_info:
            if not isinstance(info, dict):
                raise VpnPathObservationError(
                    f"private-peer inventory has invalid address row for {ifname!r}"
                )
            if info.get("family") != "inet":
                continue
            local_text = info.get("local")
            if not isinstance(local_text, str) or not local_text:
                raise VpnPathObservationError(
                    f"private-peer inventory has missing local IPv4 for {ifname!r}"
                )
            try:
                local = IPv4Address(local_text)
            except ValueError as exc:
                raise VpnPathObservationError(
                    f"private-peer inventory has invalid local IPv4 for {ifname!r}: "
                    f"{local_text!r}"
                ) from exc

            remote_text = info.get("peer")
            if remote_text is None:
                remote_text = info.get("address")
            if remote_text is None:
                continue
            if not isinstance(remote_text, str) or not remote_text:
                raise VpnPathObservationError(
                    f"private-peer inventory has invalid peer/address for {ifname!r}"
                )
            remote_host = remote_text.split("/", 1)[0]
            try:
                remote = IPv4Address(remote_host)
            except ValueError as exc:
                raise VpnPathObservationError(
                    f"private-peer inventory has invalid peer IPv4 for {ifname!r}: "
                    f"{remote_text!r}"
                ) from exc
            if remote != local:
                peer_candidates.add(remote)

        if len(peer_candidates) > 1:
            raise VpnPathObservationError(
                "private-peer observation is ambiguous for "
                f"{identity!r}: {sorted(str(item) for item in peer_candidates)!r}"
            )
        result[identity] = (
            next(iter(peer_candidates))
            if peer_candidates
            else None
        )

    if seen != expected:
        missing = tuple(sorted(expected - seen))
        raise VpnPathObservationError(
            "link/address snapshots disagree; address observation is missing "
            f"current interface generation(s): {missing!r}"
        )

    return MappingProxyType(result)
