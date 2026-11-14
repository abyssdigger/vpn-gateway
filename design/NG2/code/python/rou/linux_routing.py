from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from ipaddress import IPv4Network

from .interface_identity import InterfaceIdentity
from .network_rules import EndpointKind, TrafficProtocol
from .network_rules_composition import (
    ComposedNetworkRules,
    OwnedRoutingDomainRef,
)


RT_TABLE_UNSPEC = 0
RT_TABLE_COMPAT = 252
RT_TABLE_DEFAULT = 253
RT_TABLE_MAIN = 254
RT_TABLE_LOCAL = 255
MAX_TABLE_ID = (1 << 32) - 1

FIRST_RULE_PRIORITY = 1
MAX_RULE_PRIORITY = 32765

FIRST_PATH_METRIC = 10
PATH_METRIC_STEP = 10
TERMINAL_METRIC = 65536

UNICAST_ROUTE_PROTOCOL = 202
TERMINAL_ROUTE_PROTOCOL = 201

_RESERVED_TABLE_IDS = frozenset(
    {
        RT_TABLE_UNSPEC,
        RT_TABLE_COMPAT,
        RT_TABLE_DEFAULT,
        RT_TABLE_MAIN,
        RT_TABLE_LOCAL,
    }
)


class LinuxRoutingError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class DomainTableAllocation:
    domain: OwnedRoutingDomainRef
    table_id: int

    def __post_init__(self) -> None:
        if type(self.table_id) is not int:
            raise LinuxRoutingError("routing table id must be an integer")
        if not 1 <= self.table_id <= MAX_TABLE_ID:
            raise LinuxRoutingError("routing table id is out of range")
        if self.table_id in _RESERVED_TABLE_IDS:
            raise LinuxRoutingError(
                f"routing table id {self.table_id} is reserved"
            )


@dataclass(frozen=True)
class LinuxRoutingAllocationState:
    domain_tables: tuple[DomainTableAllocation, ...] = ()

    def __post_init__(self) -> None:
        domains = [item.domain for item in self.domain_tables]
        tables = [item.table_id for item in self.domain_tables]
        if len(set(domains)) != len(domains):
            raise LinuxRoutingError("duplicate domain table allocation")
        if len(set(tables)) != len(tables):
            raise LinuxRoutingError("duplicate routing table id allocation")

    @property
    def table_by_domain(self) -> dict[OwnedRoutingDomainRef, int]:
        return {
            item.domain: item.table_id
            for item in self.domain_tables
        }


class LinuxRouteKind(str, Enum):
    UNICAST = "unicast"
    BLACKHOLE = "blackhole"


@dataclass(frozen=True)
class LinuxRouteSpec:
    domain: OwnedRoutingDomainRef
    table_id: int
    destination: IPv4Network
    kind: LinuxRouteKind
    protocol: int
    metric: int
    path: InterfaceIdentity | None = None

    def __post_init__(self) -> None:
        if self.kind is LinuxRouteKind.UNICAST:
            if self.path is None:
                raise LinuxRoutingError(
                    "unicast route requires concrete path identity"
                )
            if self.protocol != UNICAST_ROUTE_PROTOCOL:
                raise LinuxRoutingError(
                    "unicast route must use owned unicast protocol"
                )
            if not 0 < self.metric < TERMINAL_METRIC:
                raise LinuxRoutingError(
                    "unicast route metric must be below terminal metric"
                )
            return

        if self.kind is LinuxRouteKind.BLACKHOLE:
            if self.path is not None:
                raise LinuxRoutingError(
                    "blackhole route must not carry path identity"
                )
            if self.protocol != TERMINAL_ROUTE_PROTOCOL:
                raise LinuxRoutingError(
                    "terminal blackhole must use owned terminal protocol"
                )
            if self.metric != TERMINAL_METRIC:
                raise LinuxRoutingError(
                    "terminal blackhole must use terminal metric"
                )
            return

        raise LinuxRoutingError(f"unsupported route kind {self.kind!r}")


@dataclass(frozen=True)
class LinuxRouteSlotGapSpec:
    domain: OwnedRoutingDomainRef
    table_id: int
    destination: IPv4Network
    metric: int

    def __post_init__(self) -> None:
        if not 0 < self.metric < TERMINAL_METRIC:
            raise LinuxRoutingError(
                "route-slot gap metric must be below terminal metric"
            )


@dataclass(frozen=True)
class LinuxRouteSlotMove:
    source: LinuxRouteSpec
    target_metric: int

    def __post_init__(self) -> None:
        if self.source.kind is not LinuxRouteKind.UNICAST:
            raise LinuxRoutingError("route-slot move requires unicast source")
        if not 0 < self.target_metric < TERMINAL_METRIC:
            raise LinuxRoutingError(
                "route-slot move target metric must be below terminal metric"
            )
        if self.source.metric == self.target_metric:
            raise LinuxRoutingError("route-slot move must change metric")


@dataclass(frozen=True)
class LinuxDispatchRuleSpec:
    priority: int
    domain: OwnedRoutingDomainRef
    destination: IPv4Network
    table_id: int
    source_ifname: str | None = None
    local_process_uid: int | None = None
    protocol: TrafficProtocol | None = None
    bound_output: InterfaceIdentity | None = None

    def __post_init__(self) -> None:
        if not FIRST_RULE_PRIORITY <= self.priority <= MAX_RULE_PRIORITY:
            raise LinuxRoutingError("RPDB priority is out of owned range")

        local_network = self.source_ifname is not None
        local_process = (
            self.local_process_uid is not None
            or self.protocol is not None
            or self.bound_output is not None
        )
        if local_network == local_process:
            raise LinuxRoutingError(
                "dispatch must select exactly one Linux source mode"
            )

        if local_network:
            assert self.source_ifname is not None
            _validate_ifname(self.source_ifname)
            return

        if (
            type(self.local_process_uid) is not int
            or not 1 <= self.local_process_uid < (1 << 32) - 1
        ):
            raise LinuxRoutingError(
                "local-process dispatch requires non-root 32-bit uid"
            )
        if self.protocol is None:
            raise LinuxRoutingError(
                "local-process dispatch requires protocol"
            )
        if self.protocol is not TrafficProtocol.ICMP:
            raise LinuxRoutingError(
                "current Linux local-process backend is target-proven only for ICMP"
            )
        if self.bound_output is None:
            raise LinuxRoutingError(
                "local-process dispatch requires bound output generation"
            )


@dataclass(frozen=True)
class LinuxTerminalRuleSpec:
    priority: int
    source_ifname: str

    def __post_init__(self) -> None:
        if not FIRST_RULE_PRIORITY <= self.priority <= MAX_RULE_PRIORITY:
            raise LinuxRoutingError("terminal RPDB priority is out of owned range")
        _validate_ifname(self.source_ifname)


@dataclass(frozen=True)
class LinuxRoutingDesired:
    allocation: LinuxRoutingAllocationState
    routes: tuple[LinuxRouteSpec, ...]
    dispatch_rules: tuple[LinuxDispatchRuleSpec, ...]
    terminal_rule: LinuxTerminalRuleSpec | None
    verification_tables: tuple[int, ...]
    route_slot_gaps: tuple[LinuxRouteSlotGapSpec, ...] = ()


def _validate_ifname(ifname: str) -> None:
    if not ifname:
        raise LinuxRoutingError("Linux interface name must be non-empty")
    if len(ifname.encode("utf-8")) > 15:
        raise LinuxRoutingError("Linux interface name exceeds IFNAMSIZ-1")


def _desired_domains(
    composed: ComposedNetworkRules,
) -> tuple[OwnedRoutingDomainRef, ...]:
    out: list[OwnedRoutingDomainRef] = []
    for owned in composed.owners:
        for domain in owned.rules.routing_domains:
            out.append(
                OwnedRoutingDomainRef(
                    owned.owner,
                    domain.name,
                )
            )
    return tuple(sorted(out))


def _usable_table_ids(reserved: set[int]):
    for table_id in range(1, MAX_TABLE_ID + 1):
        if (
            table_id not in _RESERVED_TABLE_IDS
            and table_id not in reserved
        ):
            yield table_id


def project_linux_routing_allocation(
    composed: ComposedNetworkRules,
    committed: LinuxRoutingAllocationState,
) -> LinuxRoutingAllocationState:
    """Project table IDs without reusing an uncommitted removal."""

    desired_domains = _desired_domains(composed)
    desired_set = set(desired_domains)
    previous = committed.table_by_domain

    out: list[DomainTableAllocation] = []
    for domain in desired_domains:
        table = previous.get(domain)
        if table is not None:
            out.append(DomainTableAllocation(domain, table))

    # All previously committed IDs remain reserved for this projection, including
    # domains that are about to be removed. They become reusable only after the
    # resulting projection crosses the verified commit boundary.
    reserved = {
        item.table_id
        for item in committed.domain_tables
    }
    reserved.update(item.table_id for item in out)

    free = _usable_table_ids(reserved)
    already = {item.domain for item in out}
    for domain in desired_domains:
        if domain in already:
            continue
        try:
            table_id = next(free)
        except StopIteration:
            raise LinuxRoutingError(
                "routing table id space exhausted"
            ) from None
        out.append(DomainTableAllocation(domain, table_id))
        reserved.add(table_id)

    if {item.domain for item in out} != desired_set:
        raise AssertionError("allocation projection lost desired routing domain")

    out.sort(key=lambda item: item.domain)
    return LinuxRoutingAllocationState(tuple(out))


def _missing_local_process_uid() -> int:
    raise LinuxRoutingError(
        "LOCAL_PROCESS routing requires configured Linux local-process uid"
    )


def _path_metric(index: int) -> int:
    metric = FIRST_PATH_METRIC + index * PATH_METRIC_STEP
    if metric >= TERMINAL_METRIC:
        raise LinuxRoutingError(
            "ordered path count exhausts normal metric space below "
            f"terminal metric {TERMINAL_METRIC}"
        )
    return metric


def _route_group_key(route: LinuxRouteSpec) -> tuple[OwnedRoutingDomainRef, int, IPv4Network]:
    return (route.domain, route.table_id, route.destination)


def _gap_group_key(gap: LinuxRouteSlotGapSpec) -> tuple[OwnedRoutingDomainRef, int, IPv4Network]:
    return (gap.domain, gap.table_id, gap.destination)


def plan_linux_route_priority_moves(
    current: LinuxRoutingDesired,
    desired: LinuxRoutingDesired,
) -> tuple[LinuxRouteSlotMove, ...]:
    """Plan one-empty-slot permutations using add-duplicate/delete-old moves.

    Each completed move transfers the EMPTY slot from target_metric to the source
    metric. During the add/delete pair every eligible path remains represented and
    exactly one path is temporarily duplicated.
    """

    def grouped(routing: LinuxRoutingDesired):
        out: dict[
            tuple[OwnedRoutingDomainRef, int, IPv4Network],
            dict[int, LinuxRouteSpec],
        ] = {}
        for route in routing.routes:
            if route.kind is not LinuxRouteKind.UNICAST:
                continue
            group = _route_group_key(route)
            by_metric = out.setdefault(group, {})
            if route.metric in by_metric:
                raise LinuxRoutingError(
                    f"duplicate unicast metric {route.metric} in route group {group!r}"
                )
            by_metric[route.metric] = route
        return out

    def gaps(routing: LinuxRoutingDesired):
        out = {}
        for gap in routing.route_slot_gaps:
            group = _gap_group_key(gap)
            if group in out:
                raise LinuxRoutingError(
                    f"duplicate route-slot gap in group {group!r}"
                )
            out[group] = gap
        return out

    current_groups = grouped(current)
    desired_groups = grouped(desired)
    if current_groups.keys() != desired_groups.keys():
        raise LinuxRoutingError("route-priority groups changed")

    current_gaps = gaps(current)
    desired_gaps = gaps(desired)
    if current_gaps.keys() != desired_gaps.keys():
        raise LinuxRoutingError("route-slot gap groups changed")

    moves: list[LinuxRouteSlotMove] = []

    def group_sort_key(group):
        domain, table_id, destination = group
        return (
            table_id,
            -destination.prefixlen,
            int(destination.network_address),
            domain,
        )

    for group in sorted(current_groups, key=group_sort_key):
        current_routes = current_groups[group]
        desired_routes = desired_groups[group]
        current_gap = current_gaps.get(group)
        desired_gap = desired_gaps.get(group)

        if current_gap is None or desired_gap is None:
            if set(current_routes.values()) != set(desired_routes.values()):
                raise LinuxRoutingError(
                    "unslotted route group changed during priority transition"
                )
            continue

        current_metrics = set(current_routes) | {current_gap.metric}
        desired_metrics = set(desired_routes) | {desired_gap.metric}
        if current_metrics != desired_metrics:
            raise LinuxRoutingError("route-slot metric universe changed")

        current_paths = {route.path for route in current_routes.values()}
        desired_paths = {route.path for route in desired_routes.values()}
        if current_paths != desired_paths:
            raise LinuxRoutingError("route-priority path membership changed")
        if None in current_paths:
            raise AssertionError("unicast route unexpectedly lacks path")

        slot_paths = {
            metric: route.path
            for metric, route in current_routes.items()
        }
        slot_paths[current_gap.metric] = None
        target_paths = {
            metric: route.path
            for metric, route in desired_routes.items()
        }
        target_paths[desired_gap.metric] = None
        route_by_metric = dict(current_routes)

        while slot_paths != target_paths:
            empty_metrics = [
                metric for metric, path in slot_paths.items() if path is None
            ]
            if len(empty_metrics) != 1:
                raise LinuxRoutingError(
                    "route-priority transition requires exactly one EMPTY slot"
                )
            empty_metric = empty_metrics[0]
            wanted = target_paths[empty_metric]

            if wanted is not None:
                source_metric = next(
                    metric
                    for metric, path in slot_paths.items()
                    if path == wanted
                )
            else:
                source_metric = next(
                    metric
                    for metric in sorted(slot_paths)
                    if slot_paths[metric] is not None
                    and slot_paths[metric] != target_paths[metric]
                )

            source = route_by_metric[source_metric]
            moves.append(LinuxRouteSlotMove(source, empty_metric))

            duplicate = replace(source, metric=empty_metric)
            route_by_metric[empty_metric] = duplicate
            del route_by_metric[source_metric]
            slot_paths[empty_metric] = source.path
            slot_paths[source_metric] = None

    return tuple(moves)


def compile_linux_routing_desired(
    composed: ComposedNetworkRules,
    committed: LinuxRoutingAllocationState,
    *,
    local_interface: str,
    local_process_uid: int | None = None,
) -> LinuxRoutingDesired:
    """Compile owner-composed semantic routing into Linux routing intent."""

    _validate_ifname(local_interface)
    allocation = project_linux_routing_allocation(
        composed,
        committed,
    )
    table_by_domain = allocation.table_by_domain

    routes: list[LinuxRouteSpec] = []
    route_slot_gaps: list[LinuxRouteSlotGapSpec] = []
    for owned in composed.owners:
        for domain in owned.rules.routing_domains:
            domain_ref = OwnedRoutingDomainRef(
                owned.owner,
                domain.name,
            )
            table_id = table_by_domain[domain_ref]

            for destination in domain.destinations:
                gap_index = domain.priority_prefix_length
                if gap_index is not None:
                    route_slot_gaps.append(
                        LinuxRouteSlotGapSpec(
                            domain=domain_ref,
                            table_id=table_id,
                            destination=destination,
                            metric=_path_metric(gap_index),
                        )
                    )

                for index, path in enumerate(domain.ordered_paths):
                    slot_index = (
                        index
                        if gap_index is None or index < gap_index
                        else index + 1
                    )
                    routes.append(
                        LinuxRouteSpec(
                            domain=domain_ref,
                            table_id=table_id,
                            destination=destination,
                            kind=LinuxRouteKind.UNICAST,
                            protocol=UNICAST_ROUTE_PROTOCOL,
                            metric=_path_metric(slot_index),
                            path=path,
                        )
                    )

            routes.append(
                LinuxRouteSpec(
                    domain=domain_ref,
                    table_id=table_id,
                    destination=IPv4Network("0.0.0.0/0"),
                    kind=LinuxRouteKind.BLACKHOLE,
                    protocol=TERMINAL_ROUTE_PROTOCOL,
                    metric=TERMINAL_METRIC,
                )
            )

    required_priorities = len(composed.dispatch_rules) + (
        1 if composed.owners else 0
    )
    if required_priorities > MAX_RULE_PRIORITY:
        raise LinuxRoutingError(
            f"{required_priorities} owned RPDB rules exceed capacity "
            f"{MAX_RULE_PRIORITY}"
        )

    dispatch: list[LinuxDispatchRuleSpec] = []
    for offset, rule in enumerate(composed.dispatch_rules):
        table_id = table_by_domain.get(rule.routing_domain)
        if table_id is None:
            raise LinuxRoutingError(
                f"dispatch references unallocated domain {rule.routing_domain!r}"
            )

        common = dict(
            priority=FIRST_RULE_PRIORITY + offset,
            domain=rule.routing_domain,
            destination=rule.destination,
            table_id=table_id,
        )
        if rule.source.kind is EndpointKind.LOCAL_NETWORK:
            dispatch.append(
                LinuxDispatchRuleSpec(
                    **common,
                    source_ifname=local_interface,
                )
            )
            continue

        if rule.source.kind is EndpointKind.LOCAL_PROCESS:
            if rule.bound_output is None or rule.protocol is None:
                raise LinuxRoutingError(
                    "local-process dispatch lacks bound output or protocol"
                )
            assert rule.bound_output.interface is not None
            dispatch.append(
                LinuxDispatchRuleSpec(
                    **common,
                    local_process_uid=(
                        local_process_uid
                        if local_process_uid is not None
                        else _missing_local_process_uid()
                    ),
                    protocol=rule.protocol,
                    bound_output=rule.bound_output.interface,
                )
            )
            continue

        raise LinuxRoutingError(
            "current Linux routing backend does not support dispatch "
            f"from {rule.source.kind.value}"
        )

    terminal_rule = (
        LinuxTerminalRuleSpec(
            priority=FIRST_RULE_PRIORITY + len(dispatch),
            source_ifname=local_interface,
        )
        if composed.owners
        else None
    )

    routes.sort(
        key=lambda item: (
            item.table_id,
            -item.destination.prefixlen,
            int(item.destination.network_address),
            item.metric,
            item.kind.value,
            "" if item.path is None else item.path.ifname,
            -1 if item.path is None else item.path.ifindex,
        )
    )

    verification_tables = tuple(
        sorted(
            {
                *(item.table_id for item in committed.domain_tables),
                *(item.table_id for item in allocation.domain_tables),
            }
        )
    )

    route_slot_gaps.sort(
        key=lambda item: (
            item.table_id,
            -item.destination.prefixlen,
            int(item.destination.network_address),
            item.metric,
        )
    )

    return LinuxRoutingDesired(
        allocation=allocation,
        routes=tuple(routes),
        dispatch_rules=tuple(dispatch),
        terminal_rule=terminal_rule,
        verification_tables=verification_tables,
        route_slot_gaps=tuple(route_slot_gaps),
    )
