from __future__ import annotations

from dataclasses import dataclass

from .interface_identity import InterfaceIdentity
from .linux_nft import (
    NftFilterDesired,
    NftNatDesired,
    compile_nft_filter_desired,
    compile_nft_nat_desired,
)
from .linux_prerequisites import LinuxNamespacePrerequisites
from .linux_routing import (
    LinuxRoutingAllocationState,
    LinuxRoutingDesired,
    compile_linux_routing_desired,
)
from .network_rules import (
    EndpointKind,
    NetworkEndpoint,
    NetworkRulesSpec,
    RoutingDomainSpec,
)
from .network_rules_composition import (
    ComposedNetworkRules,
    OwnedNetworkRules,
    compose_network_rules,
)


class LinuxNetworkDesiredError(ValueError):
    pass


@dataclass(frozen=True)
class LinuxNetworkDesired:
    prerequisites: LinuxNamespacePrerequisites
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

        for rule in owned.rules.dispatch_rules:
            _visit_endpoint(rule.source, by_name, by_index)
            if rule.bound_output is not None:
                _visit_endpoint(rule.bound_output, by_name, by_index)

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


def _endpoint_present(
    endpoint: NetworkEndpoint,
    available: set[InterfaceIdentity],
) -> bool:
    if endpoint.kind in {
        EndpointKind.LOCAL_NETWORK,
        EndpointKind.LOCAL_PROCESS,
    }:
        return True
    assert endpoint.interface is not None
    return endpoint.interface in available


def project_network_rules_to_interfaces(
    composed: ComposedNetworkRules,
    interfaces: tuple[InterfaceIdentity, ...],
) -> ComposedNetworkRules:
    """Fail-close owner rules that reference absent concrete generations."""

    available = set(interfaces)
    projected: list[OwnedNetworkRules] = []

    for owned in composed.owners:
        rules = owned.rules
        routing_domains = tuple(
            RoutingDomainSpec(
                name=domain.name,
                destinations=domain.destinations,
                ordered_paths=tuple(
                    path
                    for path in domain.ordered_paths
                    if path in available
                ),
                terminal_disposition=domain.terminal_disposition,
            )
            for domain in rules.routing_domains
        )

        dispatch_rules = tuple(
            rule
            for rule in rules.dispatch_rules
            if _endpoint_present(rule.source, available)
            and (
                rule.bound_output is None
                or _endpoint_present(rule.bound_output, available)
            )
        )
        traffic_allows = tuple(
            rule
            for rule in rules.traffic_allows
            if _endpoint_present(rule.source, available)
            and _endpoint_present(rule.destination, available)
        )
        flow_allows = tuple(
            rule
            for rule in rules.flow_initiation_allows
            if _endpoint_present(rule.source, available)
            and _endpoint_present(rule.destination, available)
        )
        source_nat = tuple(
            rule
            for rule in rules.source_nat
            if _endpoint_present(rule.source, available)
            and _endpoint_present(rule.egress, available)
        )

        projected.append(
            OwnedNetworkRules(
                owned.owner,
                NetworkRulesSpec(
                    routing_domains=routing_domains,
                    dispatch_rules=dispatch_rules,
                    traffic_allows=traffic_allows,
                    flow_initiation_allows=flow_allows,
                    source_nat=source_nat,
                ),
            )
        )

    return compose_network_rules(tuple(projected))


def compile_linux_network_desired(
    composed: ComposedNetworkRules,
    committed_routing: LinuxRoutingAllocationState,
    *,
    local_interface: str,
) -> LinuxNetworkDesired:
    interface_identities = validate_linux_interface_generations(composed)
    prerequisites = LinuxNamespacePrerequisites(
        tuple(
            dict.fromkeys(
                (
                    local_interface,
                    *(item.ifname for item in interface_identities),
                )
            )
        )
    )

    routing = compile_linux_routing_desired(
        composed,
        committed_routing,
        local_interface=local_interface,
    )

    if not composed.owners:
        return LinuxNetworkDesired(
            prerequisites=prerequisites,
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
        prerequisites=prerequisites,
        routing=routing,
        filter=filter_desired,
        nat=nat_desired,
        ip_forward_required=ip_forward_required,
    )
