"""Deterministic mutation ordering for ordinary-host boundary policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .linux_host_boundary_policy import HostBoundaryLinuxDesired


class HostBoundaryMutationKind(str, Enum):
    UNDERLAY_PIN = "underlay_pin"
    RETURN_ROUTE = "return_route"
    RETURN_RULE = "return_rule"
    RETURN_NFT = "return_nft"
    BOOTSTRAP_ROUTE = "bootstrap_route"


@dataclass(frozen=True, slots=True)
class HostBoundaryMutationStep:
    kind: HostBoundaryMutationKind
    payload: object


def build_host_boundary_apply_plan(
    desired: HostBoundaryLinuxDesired,
) -> tuple[HostBoundaryMutationStep, ...]:
    """Prepare dependencies before any route can capture VPN underlay traffic."""
    if not isinstance(desired, HostBoundaryLinuxDesired):
        raise ValueError("desired must be HostBoundaryLinuxDesired")

    steps: list[HostBoundaryMutationStep] = []
    steps.extend(
        HostBoundaryMutationStep(HostBoundaryMutationKind.UNDERLAY_PIN, item)
        for item in desired.underlay_pins
    )
    if desired.return_route is not None:
        steps.append(
            HostBoundaryMutationStep(
                HostBoundaryMutationKind.RETURN_ROUTE,
                desired.return_route,
            )
        )
    if desired.return_rule is not None:
        steps.append(
            HostBoundaryMutationStep(
                HostBoundaryMutationKind.RETURN_RULE,
                desired.return_rule,
            )
        )
    if desired.nft_script is not None:
        steps.append(
            HostBoundaryMutationStep(
                HostBoundaryMutationKind.RETURN_NFT,
                desired.nft_script,
            )
        )
    steps.extend(
        HostBoundaryMutationStep(HostBoundaryMutationKind.BOOTSTRAP_ROUTE, item)
        for item in desired.bootstrap_routes
    )
    return tuple(steps)


def build_host_boundary_cleanup_plan(
    current: HostBoundaryLinuxDesired,
) -> tuple[HostBoundaryMutationStep, ...]:
    """Stop new managed capture first; remove underlay pins last."""
    if not isinstance(current, HostBoundaryLinuxDesired):
        raise ValueError("current must be HostBoundaryLinuxDesired")

    steps: list[HostBoundaryMutationStep] = []
    steps.extend(
        HostBoundaryMutationStep(HostBoundaryMutationKind.BOOTSTRAP_ROUTE, item)
        for item in reversed(current.bootstrap_routes)
    )
    if current.nft_script is not None:
        steps.append(
            HostBoundaryMutationStep(
                HostBoundaryMutationKind.RETURN_NFT,
                current.nft_script,
            )
        )
    if current.return_rule is not None:
        steps.append(
            HostBoundaryMutationStep(
                HostBoundaryMutationKind.RETURN_RULE,
                current.return_rule,
            )
        )
    if current.return_route is not None:
        steps.append(
            HostBoundaryMutationStep(
                HostBoundaryMutationKind.RETURN_ROUTE,
                current.return_route,
            )
        )
    steps.extend(
        HostBoundaryMutationStep(HostBoundaryMutationKind.UNDERLAY_PIN, item)
        for item in reversed(current.underlay_pins)
    )
    return tuple(steps)
