from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .interface_identity import InterfaceIdentity
from .linux_local_process import LinuxLocalProcessConfig
from .linux_nft import (
    NftFilterDesired,
    NftNatDesired,
    compile_nft_filter_desired,
    compile_nft_nat_desired,
)
from .linux_prerequisites import LinuxNamespacePrerequisites
from .linux_route_priority import plan_route_slot_moves
from .linux_routing import (
    FIRST_PATH_METRIC,
    PATH_METRIC_STEP,
    TERMINAL_METRIC,
    LinuxRouteKind,
    LinuxRoutingAllocationState,
    LinuxRoutingDesired,
    compile_linux_routing_desired,
)
from .network_rules import (
    EndpointKind,
    IcmpType,
    NetworkEndpoint,
    NetworkRulesSpec,
    PredicateKind,
    RoutingDomainSpec,
    TrafficPredicate,
    TrafficProtocol,
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


def linux_network_route_priority_only_change(
    current: LinuxNetworkDesired,
    desired: LinuxNetworkDesired,
) -> bool:
    """Return True only for a pure permutation of existing unicast path slots."""

    if (
        current.prerequisites != desired.prerequisites
        or current.filter != desired.filter
        or current.nat != desired.nat
        or current.ip_forward_required != desired.ip_forward_required
        or current.routing.allocation != desired.routing.allocation
        or current.routing.dispatch_rules != desired.routing.dispatch_rules
        or current.routing.terminal_rule != desired.routing.terminal_rule
        or current.routing.verification_tables
        != desired.routing.verification_tables
    ):
        return False

    current_terminal = {
        route
        for route in current.routing.routes
        if route.kind is not LinuxRouteKind.UNICAST
    }
    desired_terminal = {
        route
        for route in desired.routing.routes
        if route.kind is not LinuxRouteKind.UNICAST
    }
    if current_terminal != desired_terminal:
        return False

    def groups(routing: LinuxRoutingDesired):
        out: dict[tuple, dict[int, InterfaceIdentity]] = {}
        for route in routing.routes:
            if route.kind is not LinuxRouteKind.UNICAST:
                continue
            assert route.path is not None
            group = (
                route.domain,
                route.table_id,
                route.destination,
                route.protocol,
            )
            by_metric = out.setdefault(group, {})
            if route.metric in by_metric:
                return None
            by_metric[route.metric] = route.path
        return out

    current_groups = groups(current.routing)
    desired_groups = groups(desired.routing)
    if current_groups is None or desired_groups is None:
        return False
    if current_groups.keys() != desired_groups.keys():
        return False

    changed = False
    for group in current_groups:
        current_by_metric = current_groups[group]
        desired_by_metric = desired_groups[group]
        if set(current_by_metric.values()) != set(desired_by_metric.values()):
            return False
        if len(current_by_metric) != len(desired_by_metric):
            return False

        path_count = len(current_by_metric)
        metrics = tuple(
            FIRST_PATH_METRIC + index * PATH_METRIC_STEP
            for index in range(path_count + 1)
        )
        if metrics[-1] >= TERMINAL_METRIC:
            return False
        if (
            any(metric not in metrics for metric in current_by_metric)
            or any(metric not in metrics for metric in desired_by_metric)
        ):
            return False

        current_slots = tuple(
            current_by_metric.get(metric)
            for metric in metrics
        )
        desired_slots = tuple(
            desired_by_metric.get(metric)
            for metric in metrics
        )
        if current_slots.count(None) != 1 or desired_slots.count(None) != 1:
            return False

        try:
            moves = plan_route_slot_moves(
                current_slots,
                desired_slots,
            )
        except ValueError:
            return False
        if moves:
            changed = True

    return changed


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
                priority_prefix_length=(
                    None
                    if domain.priority_prefix_length is None
                    else sum(
                        1
                        for path in domain.ordered_paths[
                            : domain.priority_prefix_length
                        ]
                        if path in available
                    )
                ),
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


def _probe_target_from_predicate(
    predicate: TrafficPredicate,
    *,
    outbound: bool,
) -> IPv4Network:
    if predicate.kind is not PredicateKind.MATCH or predicate.selector is None:
        raise LinuxNetworkDesiredError(
            "Linux LOCAL_PROCESS backend requires exact probe MATCH predicates"
        )
    selector = predicate.selector
    if selector.protocol is not TrafficProtocol.ICMP:
        raise LinuxNetworkDesiredError(
            "Linux LOCAL_PROCESS backend is target-proven only for ICMP"
        )
    if selector.source_ports or selector.destination_ports:
        raise LinuxNetworkDesiredError(
            "Linux LOCAL_PROCESS ICMP probe predicates must not carry ports"
        )

    if outbound:
        if (
            selector.source is not None
            or selector.destination is None
            or selector.destination.prefixlen != 32
            or selector.icmp_types != (IcmpType.ECHO_REQUEST,)
        ):
            raise LinuxNetworkDesiredError(
                "Linux LOCAL_PROCESS outbound policy must be exact /32 ICMP echo-request"
            )
        return selector.destination

    if (
        selector.destination is not None
        or selector.source is None
        or selector.source.prefixlen != 32
        or selector.icmp_types != (IcmpType.ECHO_REPLY,)
    ):
        raise LinuxNetworkDesiredError(
            "Linux LOCAL_PROCESS inbound policy must be exact /32 ICMP echo-reply"
        )
    return selector.source


def _validate_local_process_probe_policy(
    composed: ComposedNetworkRules,
) -> None:
    planes = {
        (
            rule.owner,
            rule.bound_output.interface,
            rule.destination,
            rule.protocol,
        )
        for rule in composed.dispatch_rules
        if rule.source.kind is EndpointKind.LOCAL_PROCESS
        and rule.bound_output is not None
        and rule.bound_output.kind is EndpointKind.INTERFACE
        and rule.bound_output.interface is not None
    }

    for owned in composed.owners:
        for rule in owned.rules.traffic_allows:
            source_local = rule.source.kind is EndpointKind.LOCAL_PROCESS
            destination_local = (
                rule.destination.kind is EndpointKind.LOCAL_PROCESS
            )
            if not source_local and not destination_local:
                continue
            if source_local == destination_local:
                raise LinuxNetworkDesiredError(
                    "Linux LOCAL_PROCESS traffic must pair with one concrete interface"
                )

            if source_local:
                if rule.destination.kind is not EndpointKind.INTERFACE:
                    raise LinuxNetworkDesiredError(
                        "Linux LOCAL_PROCESS outbound traffic requires interface destination"
                    )
                assert rule.destination.interface is not None
                target = _probe_target_from_predicate(
                    rule.predicate,
                    outbound=True,
                )
                plane = (
                    owned.owner,
                    rule.destination.interface,
                    target,
                    TrafficProtocol.ICMP,
                )
            else:
                if rule.source.kind is not EndpointKind.INTERFACE:
                    raise LinuxNetworkDesiredError(
                        "Linux LOCAL_PROCESS inbound traffic requires interface source"
                    )
                assert rule.source.interface is not None
                target = _probe_target_from_predicate(
                    rule.predicate,
                    outbound=False,
                )
                plane = (
                    owned.owner,
                    rule.source.interface,
                    target,
                    TrafficProtocol.ICMP,
                )

            if plane not in planes:
                raise LinuxNetworkDesiredError(
                    "LOCAL_PROCESS traffic allow lacks matching owner-scoped isolated dispatch"
                )

        for rule in owned.rules.flow_initiation_allows:
            if (
                rule.source.kind is not EndpointKind.LOCAL_PROCESS
                and rule.destination.kind is not EndpointKind.LOCAL_PROCESS
            ):
                continue
            if (
                rule.source.kind is not EndpointKind.LOCAL_PROCESS
                or rule.destination.kind is not EndpointKind.INTERFACE
            ):
                raise LinuxNetworkDesiredError(
                    "Linux LOCAL_PROCESS flow initiation is supported only outbound"
                )
            assert rule.destination.interface is not None
            target = _probe_target_from_predicate(
                rule.predicate,
                outbound=True,
            )
            if (
                owned.owner,
                rule.destination.interface,
                target,
                TrafficProtocol.ICMP,
            ) not in planes:
                raise LinuxNetworkDesiredError(
                    "LOCAL_PROCESS flow initiation lacks matching owner-scoped isolated dispatch"
                )


def compile_linux_network_desired(
    composed: ComposedNetworkRules,
    committed_routing: LinuxRoutingAllocationState,
    *,
    local_interface: str,
    local_process: LinuxLocalProcessConfig | None = None,
    local_process_guard_required: bool = False,
) -> LinuxNetworkDesired:
    _validate_local_process_probe_policy(composed)
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
        local_process_uid=(
            None if local_process is None else local_process.uid
        ),
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
        local_process=local_process,
        local_process_guard_required=local_process_guard_required,
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
