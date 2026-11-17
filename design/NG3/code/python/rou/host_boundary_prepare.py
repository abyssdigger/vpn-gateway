"""Read-only preparation of complete Linux host-boundary desired state."""

from __future__ import annotations

from ipaddress import IPv4Address

from .linux_host_boundary_policy import (
    HostBoundaryLinuxAllocation,
    HostBoundaryLinuxDesired,
    build_linux_host_boundary_desired,
)
from .linux_host_boundary_routes import LinuxHostBoundaryRouteBackend
from .release1_config import Release1Config
from .release1_host_boundary import build_release1_host_boundary_intent


def prepare_linux_host_boundary_desired(
    config: Release1Config,
    *,
    route_backend: LinuxHostBoundaryRouteBackend,
    host_interface: str,
    inner_gateway: IPv4Address,
    allocation: HostBoundaryLinuxAllocation,
) -> HostBoundaryLinuxDesired:
    """Observe every required ordinary underlay path before returning any mutable plan."""
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")
    if not isinstance(route_backend, LinuxHostBoundaryRouteBackend):
        raise ValueError("route_backend must be LinuxHostBoundaryRouteBackend")

    intent = build_release1_host_boundary_intent(config)
    pins = tuple(
        route_backend.observe_underlay_pin(
            endpoint,
            managed_interface=host_interface,
            owner_protocol=allocation.route_protocol,
        )
        for endpoint in intent.required_underlay_endpoints
    )

    return build_linux_host_boundary_desired(
        intent.plan,
        host_interface=host_interface,
        inner_gateway=inner_gateway,
        allocation=allocation,
        required_underlay_endpoints=intent.required_underlay_endpoints,
        underlay_pins=pins,
    )
