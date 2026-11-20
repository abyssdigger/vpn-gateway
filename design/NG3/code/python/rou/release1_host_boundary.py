"""Current alpha config -> authoritative host-routing prototype intent.

Despite the historical module name, this projection now belongs to the postponed aggressive
helper evidence path and is not Release-1 simple-helper closure.
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
