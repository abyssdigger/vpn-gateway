"""Managed L3 boundary backend selection for NG3.

This module is intentionally policy-light. It defines one semantic boundary endpoint
contract with multiple Linux realizations. Device/Profile policy must not branch on the
selected lower backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ManagedL3BoundaryBackend(str, Enum):
    ROUTED_VETH_PROXY_ARP = "routed-veth-proxy-arp"
    NETKIT_L3 = "netkit-l3"


@dataclass(frozen=True, slots=True)
class ManagedL3BoundaryCapabilities:
    routed_veth_proxy_arp: bool
    netkit_l3: bool

    def supports(self, backend: ManagedL3BoundaryBackend) -> bool:
        if not isinstance(backend, ManagedL3BoundaryBackend):
            raise ValueError("backend must be ManagedL3BoundaryBackend")
        if backend is ManagedL3BoundaryBackend.ROUTED_VETH_PROXY_ARP:
            return self.routed_veth_proxy_arp
        if backend is ManagedL3BoundaryBackend.NETKIT_L3:
            return self.netkit_l3
        raise AssertionError(f"unhandled backend {backend!r}")


class ManagedL3BoundarySelectionError(RuntimeError):
    pass


def select_managed_l3_boundary_backend(
    capabilities: ManagedL3BoundaryCapabilities,
    *,
    override: ManagedL3BoundaryBackend | None = None,
) -> ManagedL3BoundaryBackend:
    """Select one lower backend without exposing the choice to product policy.

    Release 1 deliberately prefers routed veth + Proxy ARP even when netkit is
    available: it is supported by the Debian-12/Linux-6.1 floor already proven
    by EXP-070 and EXP-071 found no material dataplane penalty.

    override is a lower/admin/platform realization control. It is not part of
    the Device/Profile configuration grammar.
    """
    if not isinstance(capabilities, ManagedL3BoundaryCapabilities):
        raise ValueError("capabilities must be ManagedL3BoundaryCapabilities")
    if override is not None:
        if not isinstance(override, ManagedL3BoundaryBackend):
            raise ValueError("override must be ManagedL3BoundaryBackend or None")
        if not capabilities.supports(override):
            raise ManagedL3BoundarySelectionError(
                f"requested managed L3 boundary backend {override.value!r} "
                "is not available"
            )
        return override

    if capabilities.routed_veth_proxy_arp:
        return ManagedL3BoundaryBackend.ROUTED_VETH_PROXY_ARP
    if capabilities.netkit_l3:
        return ManagedL3BoundaryBackend.NETKIT_L3
    raise ManagedL3BoundarySelectionError(
        "no supported managed L3 boundary backend is available"
    )
