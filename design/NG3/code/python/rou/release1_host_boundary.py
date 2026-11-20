"""Release-1 config -> postponed aggressive host-routing prototype intent.

The historical module name is retained only for the executable aggressive-helper evidence
path. The alpha runtime does not import this module for Release-1 peaceful host routing.
"""

from __future__ import annotations

from .host_managed_routing import (
    HostManagedRoutingPlan,
    HostManagedRoutingProfile,
    build_host_managed_routing_plan,
)
from .release1_config import Release1Config


def build_release1_host_boundary_plan(
    config: Release1Config,
) -> HostManagedRoutingPlan:
    """Project enabled Profiles into the authoritative alpha prototype route set."""
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")

    profiles = tuple(
        HostManagedRoutingProfile(
            profile_id=profile_id,
            direction=structural.direction,
            destinations=structural.destinations,
            effective_snat_address=(
                config.profiles[profile_id].effective_snat_address
            ),
        )
        for profile_id, structural in config.structural.profiles.items()
        if structural.enabled
    )
    return build_host_managed_routing_plan(profiles)
