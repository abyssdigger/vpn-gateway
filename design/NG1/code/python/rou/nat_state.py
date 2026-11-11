from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .device_engine import DeviceBindingSnapshot
from .domain import ActiveConfig
from .firewall_state import normalize_iptables_save


class NatPolicyBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class NatDesiredState:
    restore_text: str
    canonical_save: str


class NatProvider(Protocol):
    def compile(
        self,
        config: ActiveConfig,
        bindings: DeviceBindingSnapshot,
    ) -> NatDesiredState:
        ...


class UnresolvedNatProvider:
    """Production default until the NG1 NAT policy/configuration blocker is resolved."""

    def compile(
        self,
        config: ActiveConfig,
        bindings: DeviceBindingSnapshot,
    ) -> NatDesiredState:
        raise NatPolicyBlocked(
            "production payload NAT policy is unresolved; "
            "see design/NG1/blockers/NG1-NAT-policy-materialization.md"
        )


class ExplicitNoNatProvider:
    """Explicit normalized no-NAT policy for integration and routed deployments."""

    def compile(
        self,
        config: ActiveConfig,
        bindings: DeviceBindingSnapshot,
    ) -> NatDesiredState:
        lines = [
            "*nat",
            ":PREROUTING ACCEPT [0:0]",
            ":INPUT ACCEPT [0:0]",
            ":OUTPUT ACCEPT [0:0]",
            ":POSTROUTING ACCEPT [0:0]",
            "COMMIT",
            "",
        ]
        text = "\n".join(lines)
        return NatDesiredState(text, normalize_iptables_save(text))


class ExperimentalMasqueradeAllBoundProvider:
    """v0-compatible lab provider; not a production configuration semantic.

    This exists only so end-to-end integration can exercise NAT plumbing while the
    administrator-facing NAT scope/grammar remains unresolved.
    """

    def compile(
        self,
        config: ActiveConfig,
        bindings: DeviceBindingSnapshot,
    ) -> NatDesiredState:
        lines = [
            "*nat",
            ":PREROUTING ACCEPT [0:0]",
            ":INPUT ACCEPT [0:0]",
            ":OUTPUT ACCEPT [0:0]",
            ":POSTROUTING ACCEPT [0:0]",
        ]
        seen: set[str] = set()
        for binding in bindings.bound:
            ifname = binding.identity.ifname
            if ifname in seen:
                continue
            seen.add(ifname)
            lines.append(
                f"-A POSTROUTING -o {ifname} "
                "-m addrtype ! --dst-type LOCAL -j MASQUERADE"
            )
        lines.extend(["COMMIT", ""])
        text = "\n".join(lines)
        return NatDesiredState(text, normalize_iptables_save(text))
