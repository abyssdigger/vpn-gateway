"""Exact D.003 WireGuard peer AllowedIPs ownership convergence.

Architecture: D.003 WireGuardPeerOwnershipEnforcer.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network
from typing import Protocol, Sequence

from .interface_identity import InterfaceIdentity
from .managed_wireguard_adapter import (
    ManagedWireGuardObservation,
    ManagedWireGuardState,
)


class WireGuardPeerOwnershipError(RuntimeError):
    """Exact peer ownership state could not be safely observed or converged."""


class WireGuardPeerCommandRunner(Protocol):
    def run(self, argv: Sequence[str]) -> str:
        """Run one argv-only command or raise; return stdout."""


class ManagedWireGuardBaseObserver(Protocol):
    def observe(self, device_id: str) -> ManagedWireGuardObservation:
        """Fresh-observe the D.001-owned base realization."""


@dataclass(frozen=True, slots=True, order=True)
class WireGuardPeerAllowedIPs:
    public_key: str
    allowed_ips: tuple[IPv4Network, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.public_key, str) or not self.public_key:
            raise ValueError("public_key must be non-empty text")
        if not self.allowed_ips:
            raise ValueError("each managed peer must retain at least one AllowedIP")
        if any(not isinstance(item, IPv4Network) for item in self.allowed_ips):
            raise ValueError("allowed_ips must contain IPv4Network values")
        if len(set(self.allowed_ips)) != len(self.allowed_ips):
            raise ValueError("allowed_ips must not contain duplicates")
        if tuple(sorted(self.allowed_ips)) != self.allowed_ips:
            raise ValueError("allowed_ips must use canonical network order")


@dataclass(frozen=True, slots=True)
class WireGuardPeerOwnershipDesired:
    device_id: str
    interface: InterfaceIdentity
    peers: tuple[WireGuardPeerAllowedIPs, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id:
            raise ValueError("device_id must be non-empty text")
        if not isinstance(self.interface, InterfaceIdentity):
            raise ValueError("interface must be InterfaceIdentity")
        if not self.peers:
            raise ValueError("peers must not be empty")
        if any(not isinstance(item, WireGuardPeerAllowedIPs) for item in self.peers):
            raise ValueError("peers must contain WireGuardPeerAllowedIPs")
        keys = [item.public_key for item in self.peers]
        if len(keys) != len(set(keys)):
            raise ValueError("peer public keys must be unique")
        if tuple(sorted(self.peers, key=lambda item: item.public_key)) != self.peers:
            raise ValueError("peers must use canonical public-key order")


@dataclass(frozen=True, slots=True)
class WireGuardPeerOwnershipObservation:
    device_id: str
    interface: InterfaceIdentity
    peers: tuple[WireGuardPeerAllowedIPs, ...]


@dataclass(frozen=True, slots=True)
class WireGuardPeerOwnershipResult:
    confirmed: bool
    changed: bool
    observation: WireGuardPeerOwnershipObservation | None
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if self.confirmed and self.observation is None:
            raise ValueError("confirmed result requires observation")
        if self.confirmed and self.diagnostic is not None:
            raise ValueError("confirmed result must not carry diagnostic")
        if not self.confirmed and (
            not isinstance(self.diagnostic, str) or not self.diagnostic
        ):
            raise ValueError("unconfirmed result requires diagnostic")


@dataclass(slots=True)
class WireGuardPeerOwnershipEnforcer:
    """Converge one complete D.003 AllowedIPs state and fresh-confirm it."""

    runner: WireGuardPeerCommandRunner
    network_namespace: str
    base_observer: ManagedWireGuardBaseObserver

    def __post_init__(self) -> None:
        if not isinstance(self.network_namespace, str) or not self.network_namespace:
            raise ValueError("network_namespace must be non-empty text")

    def observe(
        self,
        desired: WireGuardPeerOwnershipDesired,
    ) -> WireGuardPeerOwnershipObservation:
        if not isinstance(desired, WireGuardPeerOwnershipDesired):
            raise ValueError("desired must be WireGuardPeerOwnershipDesired")
        base = self.base_observer.observe(desired.device_id)
        if (
            base.state is not ManagedWireGuardState.PRESENT
            or base.interface != desired.interface
        ):
            raise WireGuardPeerOwnershipError(
                "D.001 base realization/interface generation is not current"
            )

        raw = self._run(
            self._ns_command(
                "wg", "show", desired.interface.ifname, "dump"
            ),
            "WireGuard AllowedIPs observation",
        )
        return _parse_dump(desired, raw)

    def converge(
        self,
        desired: WireGuardPeerOwnershipDesired,
    ) -> WireGuardPeerOwnershipResult:
        try:
            before = self.observe(desired)
        except Exception as exc:
            return WireGuardPeerOwnershipResult(
                False,
                False,
                None,
                _diagnostic("pre-apply observation failed", exc),
            )

        expected = _as_observation(desired)
        if before == expected:
            return WireGuardPeerOwnershipResult(True, False, before)

        apply_error: Exception | None = None
        try:
            self._run(
                self._apply_command(desired),
                "WireGuard complete AllowedIPs apply",
            )
        except Exception as exc:
            apply_error = exc

        try:
            after = self.observe(desired)
        except Exception as exc:
            text = _diagnostic("post-apply observation failed", exc)
            if apply_error is not None:
                text += "; " + _diagnostic("apply also failed", apply_error)
            return WireGuardPeerOwnershipResult(False, True, None, text)

        if after == expected:
            # A command-side exception is not authoritative when a fresh exact
            # postcondition proves that the desired state nevertheless exists.
            return WireGuardPeerOwnershipResult(True, True, after)

        diagnostic = "fresh post-apply AllowedIPs state is not exact"
        if apply_error is not None:
            diagnostic += "; " + _diagnostic("apply failed", apply_error)
        return WireGuardPeerOwnershipResult(False, True, after, diagnostic)

    def _apply_command(
        self,
        desired: WireGuardPeerOwnershipDesired,
    ) -> tuple[str, ...]:
        argv = list(
            self._ns_command("wg", "set", desired.interface.ifname)
        )
        for peer in desired.peers:
            argv.extend(
                (
                    "peer",
                    peer.public_key,
                    "allowed-ips",
                    ",".join(str(item) for item in peer.allowed_ips),
                )
            )
        return tuple(argv)

    def _run(self, argv: Sequence[str], context: str) -> str:
        try:
            return self.runner.run(argv)
        except WireGuardPeerOwnershipError:
            raise
        except Exception as exc:
            raise WireGuardPeerOwnershipError(
                f"{context} failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _ns_command(self, *argv: str) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.network_namespace, *argv)


def _parse_dump(
    desired: WireGuardPeerOwnershipDesired,
    text: str,
) -> WireGuardPeerOwnershipObservation:
    rows = [line.split("\t") for line in text.splitlines() if line]
    if not rows or len(rows[0]) < 4:
        raise WireGuardPeerOwnershipError(
            "WireGuard dump has invalid interface row"
        )

    expected_keys = {item.public_key for item in desired.peers}
    actual: dict[str, tuple[IPv4Network, ...]] = {}
    for row in rows[1:]:
        if len(row) < 4:
            raise WireGuardPeerOwnershipError(
                "WireGuard dump has invalid peer row"
            )
        public_key = row[0]
        if public_key in actual:
            raise WireGuardPeerOwnershipError(
                "WireGuard dump repeats peer public key"
            )
        if public_key not in expected_keys:
            raise WireGuardPeerOwnershipError(
                "WireGuard dump contains an unexpected peer"
            )
        allowed_text = row[3]
        networks: list[IPv4Network] = []
        if allowed_text not in ("", "(none)"):
            for token in allowed_text.split(","):
                try:
                    value = IPv4Network(token, strict=False)
                except ValueError as exc:
                    raise WireGuardPeerOwnershipError(
                        f"invalid observed AllowedIPs value {token!r}: {exc}"
                    ) from None
                networks.append(value)
        actual[public_key] = tuple(sorted(networks))

    if set(actual) != expected_keys:
        raise WireGuardPeerOwnershipError(
            "WireGuard dump peer set does not match desired base peers"
        )
    peers = tuple(
        WireGuardPeerAllowedIPs(key, actual[key])
        for key in sorted(actual)
    )
    return WireGuardPeerOwnershipObservation(
        desired.device_id,
        desired.interface,
        peers,
    )


def _as_observation(
    desired: WireGuardPeerOwnershipDesired,
) -> WireGuardPeerOwnershipObservation:
    return WireGuardPeerOwnershipObservation(
        desired.device_id,
        desired.interface,
        desired.peers,
    )


def _diagnostic(context: str, exc: Exception) -> str:
    return f"{context}: {type(exc).__name__}: {exc}"
