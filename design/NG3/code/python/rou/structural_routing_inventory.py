from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
import json
from typing import Iterable

from .interface_identity import InterfaceIdentity
from .network_policy_layout import NetworkPolicyPlatformSpace
from .payload_routing_desired import ManagedRouteType


class StructuralRoutingInventoryError(ValueError):
    pass


class ReservedOwnerKind(str, Enum):
    PAYLOAD = "payload"
    PROBE = "probe"


@dataclass(frozen=True, slots=True)
class ObservedManagedRoute:
    table: int
    destination: IPv4Network
    route_type: ManagedRouteType
    protocol: int
    metric: int
    scope: int | None
    endpoint: InterfaceIdentity | None
    gateway: IPv4Address | None
    onlink: bool


@dataclass(frozen=True, slots=True)
class ObservedManagedRule:
    priority: int
    table: int
    ingress: InterfaceIdentity | None
    destination: IPv4Network | None
    fwmark: int | None
    fwmask: int | None


@dataclass(frozen=True, slots=True)
class ReservedPolicyConflict:
    owner: ReservedOwnerKind
    resource: str
    reason: str


@dataclass(frozen=True, slots=True)
class StructuralRoutingObservation:
    routes: tuple[ObservedManagedRoute, ...]
    rules: tuple[ObservedManagedRule, ...]
    conflicts: tuple[ReservedPolicyConflict, ...]


def parse_structural_routing_inventory(
    route_json: str,
    rule_json: str,
    interfaces: Iterable[InterfaceIdentity],
    platform: NetworkPolicyPlatformSpace,
) -> StructuralRoutingObservation:
    if not isinstance(platform, NetworkPolicyPlatformSpace):
        raise StructuralRoutingInventoryError(
            "platform must be NetworkPolicyPlatformSpace"
        )

    route_rows = _load_array(route_json, "route")
    rule_rows = _load_array(rule_json, "rule")
    interface_by_name = _index_interfaces(tuple(interfaces))

    routes: list[ObservedManagedRoute] = []
    rules: list[ObservedManagedRule] = []
    conflicts: list[ReservedPolicyConflict] = []

    for index, row in enumerate(route_rows):
        table = _parse_optional_decimal(row.get("table"))
        if table is None:
            continue
        owner = _table_owner(table, platform)
        if owner is None:
            continue
        resource = f"route[{index}] table={table}"
        try:
            routes.append(
                _parse_reserved_route(
                    row,
                    table,
                    interface_by_name,
                    platform,
                )
            )
        except StructuralRoutingInventoryError as exc:
            conflicts.append(
                ReservedPolicyConflict(
                    owner=owner,
                    resource=resource,
                    reason=str(exc),
                )
            )

    for index, row in enumerate(rule_rows):
        priority = _parse_optional_decimal(row.get("priority"))
        if priority is None:
            continue
        owner = _rule_owner(priority, platform)
        if owner is None:
            continue
        resource = f"rule[{index}] priority={priority}"
        try:
            rules.append(
                _parse_reserved_rule(
                    row,
                    priority,
                    owner,
                    interface_by_name,
                    platform,
                )
            )
        except StructuralRoutingInventoryError as exc:
            conflicts.append(
                ReservedPolicyConflict(
                    owner=owner,
                    resource=resource,
                    reason=str(exc),
                )
            )

    duplicate_routes = _duplicates(routes)
    for route in duplicate_routes:
        owner = _table_owner(route.table, platform)
        assert owner is not None
        conflicts.append(
            ReservedPolicyConflict(
                owner=owner,
                resource=f"route table={route.table}",
                reason="reserved inventory contains duplicate normalized route",
            )
        )
    duplicate_rules = _duplicates(rules)
    for rule in duplicate_rules:
        owner = _rule_owner(rule.priority, platform)
        assert owner is not None
        conflicts.append(
            ReservedPolicyConflict(
                owner=owner,
                resource=f"rule priority={rule.priority}",
                reason="reserved inventory contains duplicate normalized rule",
            )
        )

    return StructuralRoutingObservation(
        routes=tuple(sorted(routes, key=_route_key)),
        rules=tuple(sorted(rules, key=lambda value: value.priority)),
        conflicts=tuple(conflicts),
    )


def _load_array(text: str, kind: str) -> list[dict]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StructuralRoutingInventoryError(
            f"invalid {kind} JSON: {exc}"
        ) from None
    if not isinstance(value, list):
        raise StructuralRoutingInventoryError(
            f"{kind} JSON root must be an array"
        )
    if any(not isinstance(row, dict) for row in value):
        raise StructuralRoutingInventoryError(
            f"{kind} JSON rows must be objects"
        )
    return value


def _index_interfaces(
    interfaces: tuple[InterfaceIdentity, ...],
) -> dict[str, InterfaceIdentity]:
    out: dict[str, InterfaceIdentity] = {}
    indexes: set[int] = set()
    for endpoint in interfaces:
        if not isinstance(endpoint, InterfaceIdentity):
            raise StructuralRoutingInventoryError(
                "interfaces must contain InterfaceIdentity"
            )
        if endpoint.ifname in out or endpoint.ifindex in indexes:
            raise StructuralRoutingInventoryError(
                "interface inventory is ambiguous"
            )
        out[endpoint.ifname] = endpoint
        indexes.add(endpoint.ifindex)
    return out


def _parse_reserved_route(
    row: dict,
    table: int,
    interfaces: dict[str, InterfaceIdentity],
    platform: NetworkPolicyPlatformSpace,
) -> ObservedManagedRoute:
    allowed_fields = {
        "type",
        "dst",
        "protocol",
        "scope",
        "metric",
        "flags",
        "table",
        "gateway",
        "dev",
        "nexthops",
        "nhid",
        "multipath",
        "via",
    }
    extras = sorted(set(row) - allowed_fields)
    if extras:
        raise StructuralRoutingInventoryError(
            f"unsupported reserved route fields {extras!r}"
        )

    for unsupported in ("nexthops", "nhid", "multipath", "via"):
        if unsupported in row:
            raise StructuralRoutingInventoryError(
                f"unsupported reserved route field {unsupported!r}"
            )

    route_type = _route_type(row.get("type"))
    protocol = _required_decimal(row.get("protocol"), "route protocol")
    metric = _required_u32(row.get("metric"), "route metric")
    destination = _route_destination(row.get("dst"))
    scope = _optional_scope(row.get("scope"))

    flags = row.get("flags", [])
    if not isinstance(flags, list) or any(
        not isinstance(flag, str) for flag in flags
    ):
        raise StructuralRoutingInventoryError(
            "route flags must be an array of strings"
        )
    unknown_flags = sorted(set(flags) - {"onlink"})
    if unknown_flags:
        raise StructuralRoutingInventoryError(
            f"unsupported reserved route flags {unknown_flags!r}"
        )
    onlink = "onlink" in flags

    if route_type is ManagedRouteType.BLACKHOLE:
        if protocol != platform.guard_route_protocol:
            raise StructuralRoutingInventoryError(
                "blackhole reserved route uses unexpected protocol role"
            )
        if any(key in row for key in ("dev", "gateway")) or onlink:
            raise StructuralRoutingInventoryError(
                "blackhole reserved route carries path next-hop fields"
            )
        return ObservedManagedRoute(
            table=table,
            destination=destination,
            route_type=route_type,
            protocol=protocol,
            metric=metric,
            scope=scope,
            endpoint=None,
            gateway=None,
            onlink=False,
        )

    if protocol != platform.path_route_protocol:
        raise StructuralRoutingInventoryError(
            "unicast reserved route uses unexpected protocol role"
        )
    dev = row.get("dev")
    if not isinstance(dev, str) or not dev:
        raise StructuralRoutingInventoryError(
            "unicast reserved route has no valid dev"
        )
    endpoint = interfaces.get(dev)
    if endpoint is None:
        raise StructuralRoutingInventoryError(
            f"reserved route dev {dev!r} is absent from current interface inventory"
        )
    gateway = _optional_ipv4(row.get("gateway"), "route gateway")
    return ObservedManagedRoute(
        table=table,
        destination=destination,
        route_type=route_type,
        protocol=protocol,
        metric=metric,
        scope=scope,
        endpoint=endpoint,
        gateway=gateway,
        onlink=onlink,
    )


def _parse_reserved_rule(
    row: dict,
    priority: int,
    owner: str,
    interfaces: dict[str, InterfaceIdentity],
    platform: NetworkPolicyPlatformSpace,
) -> ObservedManagedRule:
    table = _required_decimal(row.get("table"), "rule table")
    if row.get("src") not in (None, "all"):
        raise StructuralRoutingInventoryError(
            "reserved rule has unsupported source selector"
        )

    if owner is ReservedOwnerKind.PAYLOAD:
        allowed = {"priority", "src", "table", "dst", "dstlen", "iif"}
        extras = sorted(set(row) - allowed)
        if extras:
            raise StructuralRoutingInventoryError(
                f"payload reserved rule has unsupported fields {extras!r}"
            )
        if not platform.payload_tables.contains(table):
            raise StructuralRoutingInventoryError(
                "payload rule points outside payload table pool"
            )
        iif = row.get("iif")
        if not isinstance(iif, str) or not iif:
            raise StructuralRoutingInventoryError(
                "payload rule has no valid iif"
            )
        ingress = interfaces.get(iif)
        if ingress is None:
            raise StructuralRoutingInventoryError(
                f"payload rule iif {iif!r} is absent from current interface inventory"
            )
        destination = _rule_destination(row.get("dst"), row.get("dstlen"))
        return ObservedManagedRule(
            priority=priority,
            table=table,
            ingress=ingress,
            destination=destination,
            fwmark=None,
            fwmask=None,
        )

    allowed = {"priority", "src", "table", "fwmark", "fwmask"}
    extras = sorted(set(row) - allowed)
    if extras:
        raise StructuralRoutingInventoryError(
            f"probe reserved rule has unsupported fields {extras!r}"
        )
    if not platform.probe_tables.contains(table):
        raise StructuralRoutingInventoryError(
            "probe rule points outside probe table pool"
        )
    fwmark = _required_hex_or_int(row.get("fwmark"), "fwmark")
    fwmask = _required_hex_or_int(row.get("fwmask"), "fwmask")
    return ObservedManagedRule(
        priority=priority,
        table=table,
        ingress=None,
        destination=None,
        fwmark=fwmark,
        fwmask=fwmask,
    )


def _table_owner(
    table: int,
    platform: NetworkPolicyPlatformSpace,
) -> ReservedOwnerKind | None:
    if platform.payload_tables.contains(table):
        return ReservedOwnerKind.PAYLOAD
    if platform.probe_tables.contains(table):
        return ReservedOwnerKind.PROBE
    return None


def _rule_owner(
    priority: int,
    platform: NetworkPolicyPlatformSpace,
) -> ReservedOwnerKind | None:
    if platform.probe_rule_priorities.contains(priority):
        return ReservedOwnerKind.PROBE
    if platform.payload_rule_priorities.contains(priority):
        return ReservedOwnerKind.PAYLOAD
    return None


def _parse_optional_decimal(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value, 10)
    raise StructuralRoutingInventoryError(
        f"non-numeric identifier {value!r} in numeric inventory"
    )


def _required_decimal(value: object, label: str) -> int:
    result = _parse_optional_decimal(value)
    if result is None:
        raise StructuralRoutingInventoryError(f"{label} is missing")
    if not 0 <= result <= 0xFFFFFFFF:
        raise StructuralRoutingInventoryError(f"{label} is outside u32")
    return result


def _optional_scope(value: object) -> int | None:
    if value is None:
        return None
    scope = _required_decimal(value, "route scope")
    if not 0 <= scope <= 255:
        raise StructuralRoutingInventoryError(
            "route scope is outside u8"
        )
    return scope


def _required_u32(value: object, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise StructuralRoutingInventoryError(
            f"{label} must be an integer in [0, 2^32-1]"
        )
    return value


def _route_type(value: object) -> ManagedRouteType:
    if value in (None, "unicast", 1, "1"):
        return ManagedRouteType.UNICAST
    if value in ("blackhole", 6, "6"):
        return ManagedRouteType.BLACKHOLE
    raise StructuralRoutingInventoryError(
        f"unsupported reserved route type {value!r}"
    )


def _route_destination(value: object) -> IPv4Network:
    if value == "default":
        return IPv4Network("0.0.0.0/0")
    if not isinstance(value, str) or not value:
        raise StructuralRoutingInventoryError(
            "route destination is missing/invalid"
        )
    candidate = value if "/" in value else value + "/32"
    try:
        network = ip_network(candidate, strict=True)
    except ValueError as exc:
        raise StructuralRoutingInventoryError(
            f"invalid route destination {value!r}: {exc}"
        ) from None
    if not isinstance(network, IPv4Network):
        raise StructuralRoutingInventoryError(
            "route destination must be IPv4"
        )
    return network


def _rule_destination(dst: object, dstlen: object) -> IPv4Network:
    if not isinstance(dst, str) or not dst:
        raise StructuralRoutingInventoryError(
            "payload rule destination is missing"
        )
    if dstlen is None:
        if "/" in dst:
            raise StructuralRoutingInventoryError(
                "payload rule without dstlen must use bare IPv4 host destination"
            )
        effective_dstlen = 32
    elif type(dstlen) is int and 0 <= dstlen <= 32:
        effective_dstlen = dstlen
    else:
        raise StructuralRoutingInventoryError(
            "payload rule dstlen must be integer in [0, 32] or omitted for bare /32"
        )
    try:
        network = ip_network(f"{dst}/{effective_dstlen}", strict=True)
    except ValueError as exc:
        raise StructuralRoutingInventoryError(
            f"invalid payload rule destination: {exc}"
        ) from None
    if not isinstance(network, IPv4Network):
        raise StructuralRoutingInventoryError(
            "payload rule destination must be IPv4"
        )
    return network


def _optional_ipv4(value: object, label: str) -> IPv4Address | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StructuralRoutingInventoryError(
            f"{label} must be IPv4 text"
        )
    try:
        address = ip_address(value)
    except ValueError as exc:
        raise StructuralRoutingInventoryError(
            f"invalid {label}: {exc}"
        ) from None
    if not isinstance(address, IPv4Address):
        raise StructuralRoutingInventoryError(
            f"{label} must be IPv4"
        )
    return address


def _required_hex_or_int(value: object, label: str) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, str):
        try:
            result = int(value, 0)
        except ValueError:
            raise StructuralRoutingInventoryError(
                f"{label} is not numeric"
            ) from None
    else:
        raise StructuralRoutingInventoryError(
            f"{label} is missing/non-numeric"
        )
    if not 0 <= result <= 0xFFFFFFFF:
        raise StructuralRoutingInventoryError(
            f"{label} is outside u32"
        )
    return result


def _duplicates(values):
    seen = set()
    duplicates = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)
    return tuple(duplicates)


def _route_key(route: ObservedManagedRoute) -> tuple[object, ...]:
    return (
        route.table,
        int(route.destination.network_address),
        route.destination.prefixlen,
        route.route_type.value,
        route.protocol,
        route.metric,
        route.scope if route.scope is not None else -1,
        route.endpoint.ifname if route.endpoint else "",
        route.endpoint.ifindex if route.endpoint else -1,
        str(route.gateway) if route.gateway else "",
        route.onlink,
    )
