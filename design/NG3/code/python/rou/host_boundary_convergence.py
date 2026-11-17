"""Composite ordinary-host boundary convergence.

Safety order:
  apply:   route dependencies -> return nft -> bootstrap capture
  cleanup: bootstrap capture -> return nft -> route dependencies

Dormant dependencies may remain after an apply failure; without bootstrap capture and without
packet marks they do not create a payload path and are reusable on retry.
"""

from __future__ import annotations

from dataclasses import dataclass

from .host_boundary_route_convergence import (
    HostBoundaryRoutePhaseResult,
    activate_host_boundary_bootstrap_once,
    cleanup_host_boundary_route_dependencies_once,
    deactivate_host_boundary_bootstrap_once,
    prepare_host_boundary_route_dependencies_once,
)
from .linux_host_boundary_policy import HostBoundaryLinuxDesired
from .linux_host_boundary_routes import LinuxHostBoundaryRouteBackend
from .linux_host_return_nft import (
    HostReturnNftObservation,
    LinuxHostReturnNftBackend,
    converge_host_return_nft_once,
)


class HostBoundaryConvergenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HostBoundaryConvergenceResult:
    confirmed: bool
    route_dependencies: HostBoundaryRoutePhaseResult | None = None
    nft: HostReturnNftObservation | None = None
    bootstrap: HostBoundaryRoutePhaseResult | None = None


def converge_host_boundary_once(
    route_backend: LinuxHostBoundaryRouteBackend,
    nft_backend: LinuxHostReturnNftBackend,
    desired: HostBoundaryLinuxDesired,
) -> HostBoundaryConvergenceResult:
    if not isinstance(desired, HostBoundaryLinuxDesired):
        raise ValueError("desired must be HostBoundaryLinuxDesired")
    try:
        deps = prepare_host_boundary_route_dependencies_once(route_backend, desired)
    except Exception as exc:
        raise HostBoundaryConvergenceError(
            f"host-boundary route dependency preparation failed: {exc}"
        ) from exc

    try:
        nft = converge_host_return_nft_once(nft_backend, desired.return_nft)
    except Exception as exc:
        # Prepared pins/return RPDB state are deliberately retained: no bootstrap
        # capture is active yet, so they are safe dormant state for a later retry.
        raise HostBoundaryConvergenceError(
            f"host-boundary return nft convergence failed: {exc}"
        ) from exc

    try:
        bootstrap = activate_host_boundary_bootstrap_once(route_backend, desired)
    except Exception as exc:
        # The route activation function removes routes created by its failed attempt.
        # Keep the confirmed return owner/dependencies for retry; they are safe without
        # host bootstrap capture.
        raise HostBoundaryConvergenceError(
            f"host-boundary bootstrap activation failed: {exc}"
        ) from exc

    return HostBoundaryConvergenceResult(
        confirmed=True,
        route_dependencies=deps,
        nft=nft,
        bootstrap=bootstrap,
    )


def cleanup_host_boundary_once(
    route_backend: LinuxHostBoundaryRouteBackend,
    nft_backend: LinuxHostReturnNftBackend,
    desired: HostBoundaryLinuxDesired,
) -> HostBoundaryConvergenceResult:
    if not isinstance(desired, HostBoundaryLinuxDesired):
        raise ValueError("desired must be HostBoundaryLinuxDesired")

    errors = []
    bootstrap = None
    nft = None
    deps = None

    try:
        bootstrap = deactivate_host_boundary_bootstrap_once(route_backend, desired)
    except Exception as exc:
        errors.append(f"bootstrap deactivation: {exc}")

    # Even if one bootstrap delete failed, still attempt to remove return steering and
    # dependencies; collect all cleanup failures for operator diagnosis.
    try:
        nft = converge_host_return_nft_once(nft_backend, None)
    except Exception as exc:
        errors.append(f"return nft cleanup: {exc}")

    try:
        deps = cleanup_host_boundary_route_dependencies_once(route_backend, desired)
    except Exception as exc:
        errors.append(f"route dependency cleanup: {exc}")

    if errors:
        raise HostBoundaryConvergenceError("; ".join(errors))

    return HostBoundaryConvergenceResult(
        confirmed=True,
        route_dependencies=deps,
        nft=nft,
        bootstrap=bootstrap,
    )
