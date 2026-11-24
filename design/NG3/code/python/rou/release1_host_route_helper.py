"""Release-1 peaceful ordinary-host routing lifecycle helper."""

from __future__ import annotations

from dataclasses import dataclass

from .host_routing_contribution import HostRoutingContribution
from .host_managed_routing import HostManagedRoutingProfile, build_host_managed_routing_plan
from .linux_host_managed_routing import (
    HostManagedDispatchSelector,
    HostManagedRoutingLinuxDesired,
    build_linux_peaceful_host_routing_desired,
)
from .linux_host_managed_routing_backend import (
    LinuxHostManagedRoutingDriver,
    cleanup_host_managed_routing_once,
    converge_host_managed_routing_once,
)
from .linux_nft_scaffold import NftScriptRunner
from .linux_policy_platform import NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION
from .managed_network_domain import ManagedNetworkDomainSpec
from .release1_config import HelperRoutingSelectorKind, Release1Config

LOG_TAG = "HOST"


def _lower_dispatch_selectors(
    config: Release1Config,
    domain_spec: ManagedNetworkDomainSpec,
) -> tuple[HostManagedDispatchSelector, ...]:
    result = []
    for selector in config.helper_routing_interfaces:
        if selector.kind is HelperRoutingSelectorKind.LOCAL:
            result.append(HostManagedDispatchSelector("lo"))
        elif selector.kind is HelperRoutingSelectorKind.EXTERNAL:
            result.append(HostManagedDispatchSelector("lo", True))
        elif selector.kind is HelperRoutingSelectorKind.ANY:
            result.append(HostManagedDispatchSelector())
        else:
            assert selector.interface is not None
            if selector.interface == domain_spec.host_interface:
                raise ValueError(
                    "managed HOST<->STACK boundary cannot be a helper routing ingress selector"
                )
            result.append(HostManagedDispatchSelector(selector.interface))
    return tuple(result)


def validate_release1_helper_routing_scope(
    config: Release1Config,
    domain_spec: ManagedNetworkDomainSpec,
) -> tuple[HostManagedDispatchSelector, ...]:
    """Validate/lower helper scope before any dependent network mutation."""
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")
    if not isinstance(domain_spec, ManagedNetworkDomainSpec):
        raise ValueError("domain_spec must be ManagedNetworkDomainSpec")
    selectors = _lower_dispatch_selectors(config, domain_spec)
    allocation = NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION
    assert allocation.scope_exit_priority is not None
    assert allocation.preserve_priority is not None
    capacity = (allocation.scope_exit_priority - allocation.preserve_priority) // 2
    if len(selectors) > capacity:
        raise ValueError(
            "helper routing selector count exceeds reserved RPDB priority space"
        )
    return selectors


def helper_routing_uses_external_ingress(config: Release1Config) -> bool:
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")
    return any(
        selector.kind in {
            HelperRoutingSelectorKind.EXTERNAL,
            HelperRoutingSelectorKind.ANY,
        }
        or (
            selector.kind is HelperRoutingSelectorKind.INTERFACE
            and selector.interface != "lo"
        )
        for selector in config.helper_routing_interfaces
    )


def build_release1_peaceful_host_routing_desired(
    config: Release1Config,
    domain_spec: ManagedNetworkDomainSpec,
) -> HostManagedRoutingLinuxDesired | None:
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")
    if not isinstance(domain_spec, ManagedNetworkDomainSpec):
        raise ValueError("domain_spec must be ManagedNetworkDomainSpec")
    if not config.helper_routing_interfaces:
        return None
    dispatch_selectors = validate_release1_helper_routing_scope(
        config,
        domain_spec,
    )

    profiles = tuple(
        HostManagedRoutingProfile(
            profile_id=profile_id,
            direction=structural.direction,
            destinations=structural.destinations,
            effective_snat_address=config.profiles[profile_id].effective_snat_address,
        )
        for profile_id, structural in config.structural.profiles.items()
        if structural.enabled
    )
    plan = build_host_managed_routing_plan(profiles)
    desired = build_linux_peaceful_host_routing_desired(
        plan,
        host_interface=domain_spec.host_interface,
        allocation=NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION,
        dispatch_selectors=dispatch_selectors,
        stack_service_address=domain_spec.inner_address.ip,
    )
    return desired if desired.routes else None


@dataclass(slots=True)
class LinuxPeacefulHostRoutingContribution(HostRoutingContribution):
    backend: LinuxHostManagedRoutingDriver
    desired: HostManagedRoutingLinuxDesired

    def converge(self) -> None:
        converge_host_managed_routing_once(self.backend, self.desired)

    def cleanup(self) -> None:
        cleanup_host_managed_routing_once(
            self.backend,
            self.desired,
            tolerate_foreign_replacements=True,
        )


def build_linux_peaceful_host_routing_contribution(
    config: Release1Config,
    domain_spec: ManagedNetworkDomainSpec,
    runner: NftScriptRunner,
) -> LinuxPeacefulHostRoutingContribution | None:
    desired = build_release1_peaceful_host_routing_desired(config, domain_spec)
    if desired is None:
        return None
    return LinuxPeacefulHostRoutingContribution(
        backend=LinuxHostManagedRoutingDriver(
            runner,
            NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION,
        ),
        desired=desired,
    )
