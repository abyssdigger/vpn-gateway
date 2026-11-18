"""Canonical Release-1 config -> pure host-boundary policy intent."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address

from .host_boundary_policy import (
    HostBoundaryPolicyPlan,
    HostBoundaryProfileIntent,
    build_host_boundary_policy,
)
from .host_underlay_policy import required_underlay_endpoints
from .release1_config import Release1Config


@dataclass(frozen=True, slots=True)
class Release1HostBoundaryIntent:
    plan: HostBoundaryPolicyPlan
    transport_endpoints: tuple[IPv4Address, ...]
    required_underlay_endpoints: tuple[IPv4Address, ...]


def build_release1_host_boundary_plan(
    config: Release1Config,
) -> HostBoundaryPolicyPlan:
    """Selected mechanism-neutral Profile -> host-boundary semantic plan."""
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")

    profiles = tuple(
        HostBoundaryProfileIntent(
            profile_id=profile_id,
            direction=structural.direction,
            destinations=structural.destinations,
            route_return=config.profiles[profile_id].route_return,
        )
        for profile_id, structural in config.structural.profiles.items()
        if structural.enabled
    )
    return build_host_boundary_policy(profiles)


def build_release1_host_boundary_intent(
    config: Release1Config,
) -> Release1HostBoundaryIntent:
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")

    plan = build_release1_host_boundary_plan(config)

    endpoints = tuple(
        sorted(
            {
                transport.remote_address
                for device_id, device in config.devices.items()
                if config.structural.devices[device_id].enabled
                for transport in device.allow_vpn_client
            },
            key=int,
        )
    )
    required = required_underlay_endpoints(plan, endpoints)
    return Release1HostBoundaryIntent(
        plan=plan,
        transport_endpoints=endpoints,
        required_underlay_endpoints=required,
    )
