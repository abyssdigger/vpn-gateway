"""Pure assembly of current payload network-policy lower desired state."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import Iterable, Mapping

from .composite_nft_policy import CompositeNftDesiredState
from .device_firewall_policy_compiler import (
    DeviceFirewallPolicyCompileError,
    compile_device_firewall_policies,
)
from .device_policy import (
    DeviceFirewallPolicyIntent,
    DeviceNatPolicyIntent,
)
from .interface_identity import InterfaceIdentity
from .local_integration_policy import (
    IntegrationLocalTransportIntent,
    build_integration_local_desired,
)
from .local_publication_policy import (
    PublicationLocalEndpointIntent,
    build_local_publication_desired,
)
from .network_policy_layout import NetworkPolicyLayout
from .payload_forward_compiler import (
    PayloadForwardCompileError,
    compile_payload_forward_policy,
)
from .payload_nat_desired import (
    PayloadNatProjectionError,
    ProfileSnatPolicyIntent,
    build_payload_nat_desired_state,
)
from .payload_profile import PayloadProfileRequest
from .payload_routing_desired import (
    PayloadRoutingDesiredState,
    PayloadRoutingProjectionError,
    build_payload_routing_desired_state,
)
from .route_priority_inventory import RoutePriorityPathRoute
from .probe_policy import ProbeLocalRuleSpec
from .stack_return_affinity import (
    StackReturnAffinityDesired,
    StackReturnAffinityPlatformSpace,
    allocate_stack_return_affinity,
    build_stack_return_affinity_desired,
)


class PayloadNetworkPolicyProjectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PayloadNetworkPolicyDesiredState:
    routing: PayloadRoutingDesiredState
    nft: CompositeNftDesiredState
    stack_return_affinity: StackReturnAffinityDesired | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.routing, PayloadRoutingDesiredState):
            raise PayloadNetworkPolicyProjectionError(
                "routing must be PayloadRoutingDesiredState"
            )
        if not isinstance(self.nft, CompositeNftDesiredState):
            raise PayloadNetworkPolicyProjectionError(
                "nft must be CompositeNftDesiredState"
            )
        if (
            self.stack_return_affinity is not None
            and not isinstance(self.stack_return_affinity, StackReturnAffinityDesired)
        ):
            raise PayloadNetworkPolicyProjectionError(
                "stack_return_affinity must be StackReturnAffinityDesired or None"
            )


def build_payload_network_policy_desired_state(
    profiles: Iterable[PayloadProfileRequest],
    layout: NetworkPolicyLayout,
    path_routes: Iterable[RoutePriorityPathRoute],
    host_boundary: InterfaceIdentity,
    nat_policies: Iterable[DeviceNatPolicyIntent],
    firewall_policies: Iterable[DeviceFirewallPolicyIntent],
    publication_intents: Iterable[PublicationLocalEndpointIntent],
    integration_intents: Iterable[IntegrationLocalTransportIntent] = (),
    probe_local_rules: Iterable[ProbeLocalRuleSpec] = (),
    stack_return_affinity_platform: StackReturnAffinityPlatformSpace | None = None,
    profile_snat_policies: Iterable[ProfileSnatPolicyIntent] = (),
    path_private_peers: Mapping[InterfaceIdentity, IPv4Address | None] | None = None,
) -> PayloadNetworkPolicyDesiredState:
    """Compose exact current payload lower desired state without I/O."""
    if not isinstance(layout, NetworkPolicyLayout):
        raise PayloadNetworkPolicyProjectionError(
            "layout must be NetworkPolicyLayout"
        )
    if not isinstance(host_boundary, InterfaceIdentity):
        raise PayloadNetworkPolicyProjectionError(
            "host_boundary must be InterfaceIdentity"
        )

    current_profiles = tuple(profiles)
    current_path_routes = tuple(path_routes)
    current_nat_policies = tuple(nat_policies)
    current_firewall_policies = tuple(firewall_policies)
    current_publications = tuple(publication_intents)
    current_integrations = tuple(integration_intents)
    current_probe_local = tuple(probe_local_rules)
    current_profile_snat = tuple(profile_snat_policies)
    if any(not isinstance(item, ProfileSnatPolicyIntent) for item in current_profile_snat):
        raise PayloadNetworkPolicyProjectionError(
            "profile_snat_policies must contain ProfileSnatPolicyIntent"
        )
    if current_profile_snat and stack_return_affinity_platform is None:
        raise PayloadNetworkPolicyProjectionError(
            "Profile SNAT requires stack Profile-association allocation"
        )
    if any(
        not isinstance(rule, ProbeLocalRuleSpec)
        for rule in current_probe_local
    ):
        raise PayloadNetworkPolicyProjectionError(
            "probe_local_rules must contain ProbeLocalRuleSpec"
        )

    for intent in current_publications:
        if not isinstance(intent, PublicationLocalEndpointIntent):
            raise PayloadNetworkPolicyProjectionError(
                "publication_intents must contain PublicationLocalEndpointIntent"
            )
        if intent.host_boundary != host_boundary:
            raise PayloadNetworkPolicyProjectionError(
                "publication intent host boundary does not match current payload host boundary"
            )

    for intent in current_integrations:
        if not isinstance(intent, IntegrationLocalTransportIntent):
            raise PayloadNetworkPolicyProjectionError(
                "integration_intents must contain IntegrationLocalTransportIntent"
            )
        if intent.host_boundary != host_boundary:
            raise PayloadNetworkPolicyProjectionError(
                "integration intent host boundary does not match current payload host boundary"
            )

    try:
        routing = build_payload_routing_desired_state(
            current_profiles,
            layout,
            current_path_routes,
            host_boundary,
        )
    except PayloadRoutingProjectionError as exc:
        raise PayloadNetworkPolicyProjectionError(
            f"payload routing projection failed: {exc}"
        ) from exc

    try:
        forward = compile_payload_forward_policy(
            current_profiles,
            current_path_routes,
            host_boundary,
        )
    except PayloadForwardCompileError as exc:
        raise PayloadNetworkPolicyProjectionError(
            f"Profile forward projection failed: {exc}"
        ) from exc

    allocations = ()
    if stack_return_affinity_platform is not None:
        try:
            allocations = allocate_stack_return_affinity(
                current_profiles,
                layout,
                stack_return_affinity_platform,
            )
        except ValueError as exc:
            raise PayloadNetworkPolicyProjectionError(
                f"stack Profile-association allocation failed: {exc}"
            ) from exc

    try:
        nat = build_payload_nat_desired_state(
            current_profiles,
            current_path_routes,
            current_nat_policies,
            host_boundary,
            current_profile_snat,
            allocations,
        )
    except PayloadNatProjectionError as exc:
        raise PayloadNetworkPolicyProjectionError(
            f"payload NAT projection failed: {exc}"
        ) from exc

    try:
        firewall = compile_device_firewall_policies(
            current_firewall_policies,
            current_path_routes,
            host_boundary,
            path_private_peers,
        )
    except DeviceFirewallPolicyCompileError as exc:
        raise PayloadNetworkPolicyProjectionError(
            f"Device firewall projection failed: {exc}"
        ) from exc

    try:
        local_publication = build_local_publication_desired(
            current_publications,
        )
    except ValueError as exc:
        raise PayloadNetworkPolicyProjectionError(
            f"publication-local projection failed: {exc}"
        ) from exc

    try:
        local_integration = build_integration_local_desired(
            current_integrations,
        )
    except ValueError as exc:
        raise PayloadNetworkPolicyProjectionError(
            f"integration-local projection failed: {exc}"
        ) from exc

    stack_return_affinity = None
    if stack_return_affinity_platform is not None:
        try:
            stack_return_affinity = build_stack_return_affinity_desired(
                current_profiles,
                current_path_routes,
                host_boundary,
                layout,
                allocations,
            )
        except ValueError as exc:
            raise PayloadNetworkPolicyProjectionError(
                f"stack return-affinity projection failed: {exc}"
            ) from exc

    return PayloadNetworkPolicyDesiredState(
        routing=routing,
        nft=CompositeNftDesiredState(
            profile_forward=forward,
            payload_nat=nat,
            device_firewall=firewall,
            local_publication=local_publication,
            local_integration=local_integration,
            probe_local=current_probe_local,
        ),
        stack_return_affinity=stack_return_affinity,
    )
