from __future__ import annotations

from dataclasses import dataclass

from .interface_identity import InterfaceIdentity
from .linux_nft import (
    NftFilterDesired,
    NftNatDesired,
    compile_nft_filter_desired,
    compile_nft_nat_desired,
)
from .linux_routing import (
    LinuxRoutingAllocationState,
    LinuxRoutingDesired,
    compile_linux_routing_desired,
)
from .network_rules import EndpointKind, NetworkEndpoint
from .network_rules_composition import ComposedNetworkRules


class LinuxNetworkDesiredError(ValueError):
    pass


@dataclass(frozen=True)
class LinuxNetworkDesired:
    routing: LinuxRoutingDesired
    filter: NftFilterDesired | None
    nat: NftNatDesired | None
    ip_forward_required: bool


def _register(
    identity: InterfaceIdentity,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> None:
    previous_name = by_name.get(identity.ifname)
    if (
        previous_name is not None
        and previous_name.ifindex != identity.ifindex
    ):
        raise LinuxNetworkDesiredError(
            "multiple live generations with the same interface name are "
            f"unrepresentable: {previous_name!r} vs {identity!r}"
        )

    previous_index = by_index.get(identity.ifindex)
    if (
        previous_index is not None
        and previous_index.ifname != identity.ifname
    ):
        raise LinuxNetworkDesiredError(
            "one ifindex cannot identify multiple interface names: "
            f"{previous_index!r} vs {identity!r}"
        )

    by_name[identity.ifname] = identity
    by_index[identity.ifindex] = identity


def _visit_endpoint(
    endpoint: NetworkEndpoint,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> None:
    if endpoint.kind is EndpointKind.INTERFACE:
        assert endpoint.interface is not None
        _register(endpoint.interface, by_name, by_index)


def validate_linux_interface_generations(
    composed: ComposedNetworkRules,
) -> tuple[InterfaceIdentity, ...]:
    """Validate that one physical snapshot can contain all referenced identities."""

    by_name: dict[str, InterfaceIdentity] = {}
    by_index: dict[int, InterfaceIdentity] = {}

    for owned in composed.owners:
        for domain in owned.rules.routing_domains:
            for path in domain.ordered_paths:
                _register(path, by_name, by_index)

        for rule in owned.rules.traffic_allows:
            _visit_endpoint(rule.source, by_name, by_index)
            _visit_endpoint(rule.destination, by_name, by_index)

        for rule in owned.rules.flow_initiation_allows:
            _visit_endpoint(rule.source, by_name, by_index)
            _visit_endpoint(rule.destination, by_name, by_index)

        for rule in owned.rules.source_nat:
            _visit_endpoint(rule.source, by_name, by_index)
            _visit_endpoint(rule.egress, by_name, by_index)

    return tuple(
        sorted(
            by_index.values(),
            key=lambda item: (item.ifindex, item.ifname),
        )
    )


def compile_linux_network_desired(
    composed: ComposedNetworkRules,
    committed_routing: LinuxRoutingAllocationState,
    *,
    local_interface: str,
) -> LinuxNetworkDesired:
    validate_linux_interface_generations(composed)

    routing = compile_linux_routing_desired(
        composed,
        committed_routing,
        local_interface=local_interface,
    )

    if not composed.owners:
        return LinuxNetworkDesired(
            routing=routing,
            filter=None,
            nat=None,
            ip_forward_required=False,
        )

    filter_desired = compile_nft_filter_desired(
        composed,
        local_interface=local_interface,
    )
    nat_desired = compile_nft_nat_desired(
        composed,
        local_interface=local_interface,
    )

    ip_forward_required = any(
        marker.policy == "traffic"
        for marker in filter_desired.markers
    )

    return LinuxNetworkDesired(
        routing=routing,
        filter=filter_desired,
        nat=nat_desired,
        ip_forward_required=ip_forward_required,
    )
