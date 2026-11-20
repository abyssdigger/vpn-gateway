"""Release-1 peaceful ordinary-host routing lifecycle helper."""

from __future__ import annotations

from dataclasses import dataclass

from .controller_boundary_contribution import ControllerBoundaryContribution
from .host_managed_routing import (
    HostManagedRoutingProfile,
    build_host_managed_routing_plan,
)
from .linux_host_managed_routing import (
    HostManagedRoutingLinuxDesired,
    build_linux_peaceful_host_routing_desired,
)
from .linux_host_managed_routing_backend import (
    LinuxHostManagedRoutingBackend,
    cleanup_host_managed_routing_once,
    converge_host_managed_routing_once,
)
from .linux_nft_scaffold import NftScriptRunner
from .linux_policy_platform import NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION
from .managed_network_domain import ManagedNetworkDomainSpec
from .release1_config import HostRoutingMode, Release1Config


def build_release1_peaceful_host_routing_desired(
    config: Release1Config,
    domain_spec: ManagedNetworkDomainSpec,
) -> HostManagedRoutingLinuxDesired | None:
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")
    if not isinstance(domain_spec, ManagedNetworkDomainSpec):
        raise ValueError("domain_spec must be ManagedNetworkDomainSpec")
    if config.host_routing is HostRoutingMode.MANUAL:
        return None

    profiles = tuple(
        HostManagedRoutingProfile(
            profile_id=profile_id,
            direction=structural.direction,
            destinations=structural.destinations,
            effective_snat_address=config.profiles[
                profile_id
            ].effective_snat_address,
        )
        for profile_id, structural in config.structural.profiles.items()
        if structural.enabled
    )
    plan = build_host_managed_routing_plan(profiles)
    return build_linux_peaceful_host_routing_desired(
        plan,
        host_interface=domain_spec.host_interface,
        allocation=NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION,
        stack_service_address=domain_spec.inner_address.ip,
    )


@dataclass(slots=True)
class LinuxPeacefulHostRoutingContribution(ControllerBoundaryContribution):
    backend: LinuxHostManagedRoutingBackend
    desired: HostManagedRoutingLinuxDesired

    def converge(self) -> None:
        converge_host_managed_routing_once(self.backend, self.desired)

    def cleanup(self) -> None:
        cleanup_host_managed_routing_once(self.backend, self.desired)


def build_linux_peaceful_host_routing_contribution(
    config: Release1Config,
    domain_spec: ManagedNetworkDomainSpec,
    runner: NftScriptRunner,
) -> LinuxPeacefulHostRoutingContribution | None:
    desired = build_release1_peaceful_host_routing_desired(config, domain_spec)
    if desired is None:
        return None
    return LinuxPeacefulHostRoutingContribution(
        backend=LinuxHostManagedRoutingBackend(
            runner,
            NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION,
        ),
        desired=desired,
    )
