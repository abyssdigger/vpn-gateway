"""Linux fresh-observation boundary for current VPN path endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

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
    ) -> VpnPathInterfaceObservation:
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

        return VpnPathInterfaceObservation(interfaces=interfaces)
