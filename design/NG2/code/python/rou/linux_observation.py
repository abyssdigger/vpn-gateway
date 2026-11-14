from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network
import json

from .interface_identity import InterfaceIdentity
from .linux_routing import (
    FIRST_RULE_PRIORITY,
    MAX_RULE_PRIORITY,
    TERMINAL_ROUTE_PROTOCOL,
    UNICAST_ROUTE_PROTOCOL,
    LinuxRouteKind,
    LinuxRoutingDesired,
)


class LinuxObservationError(ValueError):
    pass


@dataclass(frozen=True)
class ObservedRoute:
    table_id: int
    destination: IPv4Network
    kind: str
    protocol: int | str | None
    metric: int | None
    ifname: str | None


@dataclass(frozen=True)
class ObservedRule:
    priority: int
    source_ifname: str | None
    destination: IPv4Network | None
    table_id: int | None
    action: str


@dataclass(frozen=True)
class LinuxRoutingObservation:
    interfaces: tuple[InterfaceIdentity, ...]
    routes: tuple[ObservedRoute, ...]
    rules: tuple[ObservedRule, ...]
    ip_forward: bool


@dataclass(frozen=True)
class LinuxRoutingVerification:
    ok: bool
    errors: tuple[str, ...]
    tagged_tables: tuple[int, ...]


def _json_array(text: str, what: str) -> list:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LinuxObservationError(
            f"invalid {what} JSON: {exc}"
        ) from None
    if not isinstance(value, list):
        raise LinuxObservationError(
            f"{what} JSON root must be an array"
        )
    return value


def _table_id(value: object, what: str) -> int:
    aliases = {
        "unspec": 0,
        "default": 253,
        "main": 254,
        "local": 255,
    }
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str):
        if value in aliases:
            return aliases[value]
        if value.isdecimal():
            return int(value)
    raise LinuxObservationError(
        f"{what} has unsupported table {value!r}"
    )


def _protocol(value: object) -> int | str | None:
    if value is None:
        return None
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value:
        if value.isdecimal():
            return int(value)
        return value
    raise LinuxObservationError(
        f"unsupported route protocol {value!r}"
    )


def _network(
    value: object,
    *,
    default: str,
    what: str,
) -> IPv4Network:
    if value in (None, "default", "all"):
        value = default
    if not isinstance(value, str):
        raise LinuxObservationError(
            f"{what} must be an IPv4 prefix"
        )
    try:
        return IPv4Network(value, strict=True)
    except Exception:
        raise LinuxObservationError(
            f"{what} is not a strict IPv4 prefix: {value!r}"
        ) from None


def parse_link_json(text: str) -> tuple[InterfaceIdentity, ...]:
    raw = _json_array(text, "ip-link")
    out: list[InterfaceIdentity] = []
    names: set[str] = set()
    indexes: set[int] = set()

    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            raise LinuxObservationError(
                f"interface[{position}] must be an object"
            )
        name = item.get("ifname")
        index = item.get("ifindex")
        try:
            identity = InterfaceIdentity(name, index)
        except Exception as exc:
            raise LinuxObservationError(
                f"invalid interface[{position}]: {exc}"
            ) from None
        if identity.ifname in names:
            raise LinuxObservationError(
                f"duplicate interface name {identity.ifname!r}"
            )
        if identity.ifindex in indexes:
            raise LinuxObservationError(
                f"duplicate interface ifindex {identity.ifindex}"
            )
        names.add(identity.ifname)
        indexes.add(identity.ifindex)
        out.append(identity)

    return tuple(out)


def parse_route_json(text: str) -> tuple[ObservedRoute, ...]:
    raw = _json_array(text, "ip-route")
    out: list[ObservedRoute] = []

    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            raise LinuxObservationError(
                f"route[{position}] must be an object"
            )

        metric = item.get("metric")
        if metric is not None and (
            type(metric) is not int or metric < 0
        ):
            raise LinuxObservationError(
                f"route[{position}].metric must be non-negative"
            )

        ifname = item.get("dev")
        if ifname is not None and (
            not isinstance(ifname, str) or not ifname
        ):
            raise LinuxObservationError(
                f"route[{position}].dev must be a non-empty string"
            )

        kind = item.get("type", "unicast")
        if not isinstance(kind, str) or not kind:
            raise LinuxObservationError(
                f"route[{position}].type must be a string"
            )

        out.append(
            ObservedRoute(
                table_id=_table_id(
                    item.get("table", "main"),
                    f"route[{position}]",
                ),
                destination=_network(
                    item.get("dst"),
                    default="0.0.0.0/0",
                    what=f"route[{position}].dst",
                ),
                kind=kind,
                protocol=_protocol(item.get("protocol")),
                metric=metric,
                ifname=ifname,
            )
        )

    return tuple(out)


def _rule_destination(
    item: dict,
    *,
    position: int,
) -> IPv4Network | None:
    raw = item.get("dst")
    if raw in (None, "all"):
        return None
    if not isinstance(raw, str) or not raw:
        raise LinuxObservationError(
            f"rule[{position}].dst must be an IPv4 prefix"
        )

    raw_len = item.get("dstlen")
    if raw_len is not None and (
        type(raw_len) is not int or not 0 <= raw_len <= 32
    ):
        raise LinuxObservationError(
            f"rule[{position}].dstlen must be 0..32"
        )

    if "/" in raw:
        network = _network(
            raw,
            default="0.0.0.0/0",
            what=f"rule[{position}].dst",
        )
        if raw_len is not None and raw_len != network.prefixlen:
            raise LinuxObservationError(
                f"rule[{position}] dst/dstlen mismatch"
            )
        return network

    prefixlen = 32 if raw_len is None else raw_len
    return _network(
        f"{raw}/{prefixlen}",
        default="0.0.0.0/0",
        what=f"rule[{position}].dst",
    )


def parse_rule_json(text: str) -> tuple[ObservedRule, ...]:
    raw = _json_array(text, "ip-rule")
    out: list[ObservedRule] = []

    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            raise LinuxObservationError(
                f"rule[{position}] must be an object"
            )

        priority = item.get("priority", item.get("pref"))
        if type(priority) is not int or priority < 0:
            raise LinuxObservationError(
                f"rule[{position}].priority must be non-negative"
            )

        action = item.get("action", "to_tbl")
        if not isinstance(action, str) or not action:
            raise LinuxObservationError(
                f"rule[{position}].action must be a string"
            )

        raw_table = item.get("table")
        table = (
            None
            if raw_table is None
            else _table_id(raw_table, f"rule[{position}]")
        )

        iif = item.get("iif")
        if iif is not None and (
            not isinstance(iif, str) or not iif
        ):
            raise LinuxObservationError(
                f"rule[{position}].iif must be a string"
            )

        destination = _rule_destination(
            item,
            position=position,
        )
        if destination is None and action == "to_tbl":
            destination = IPv4Network("0.0.0.0/0")

        out.append(
            ObservedRule(
                priority=priority,
                source_ifname=iif,
                destination=destination,
                table_id=table,
                action=action,
            )
        )

    return tuple(out)


def _desired_route_key(route) -> tuple:
    return (
        route.table_id,
        route.destination,
        route.kind.value,
        route.protocol,
        route.metric,
        None if route.path is None else route.path.ifname,
    )


def _observed_route_key(route: ObservedRoute) -> tuple:
    return (
        route.table_id,
        route.destination,
        route.kind,
        route.protocol,
        route.metric,
        route.ifname,
    )


def _desired_rule_key(rule) -> tuple:
    return (
        rule.priority,
        rule.source_ifname,
        rule.destination,
        rule.table_id,
        "to_tbl",
    )


def _desired_terminal_rule_key(rule) -> tuple:
    return (
        rule.priority,
        rule.source_ifname,
        None,
        None,
        "unreachable",
    )


def _observed_rule_key(rule: ObservedRule) -> tuple:
    return (
        rule.priority,
        rule.source_ifname,
        rule.destination,
        rule.table_id,
        rule.action,
    )


def verify_linux_routing(
    desired: LinuxRoutingDesired,
    observed: LinuxRoutingObservation,
    *,
    expected_ip_forward: bool | None = None,
) -> LinuxRoutingVerification:
    errors: list[str] = []

    interfaces_by_name = {
        item.ifname: item.ifindex
        for item in observed.interfaces
    }

    for rule in desired.dispatch_rules:
        if rule.source_ifname not in interfaces_by_name:
            errors.append(
                f"dispatch source interface {rule.source_ifname!r} is absent"
            )

    for route in desired.routes:
        if route.path is None:
            continue
        actual_ifindex = interfaces_by_name.get(route.path.ifname)
        if actual_ifindex != route.path.ifindex:
            errors.append(
                "route path generation mismatch for "
                f"{route.path.ifname!r}: expected ifindex "
                f"{route.path.ifindex}, observed {actual_ifindex!r}"
            )

    expected_routes = {
        _desired_route_key(item)
        for item in desired.routes
    }
    observed_owned_routes = {
        _observed_route_key(item)
        for item in observed.routes
        if item.table_id in set(desired.verification_tables)
    }

    missing_routes = expected_routes - observed_owned_routes
    extra_routes = observed_owned_routes - expected_routes
    if missing_routes:
        errors.append(
            f"missing owned routes: {sorted(map(str, missing_routes))}"
        )
    if extra_routes:
        errors.append(
            f"unexpected routes in owned tables: "
            f"{sorted(map(str, extra_routes))}"
        )

    tagged_tables = tuple(
        sorted(
            {
                item.table_id
                for item in observed.routes
                if item.protocol
                in {
                    UNICAST_ROUTE_PROTOCOL,
                    TERMINAL_ROUTE_PROTOCOL,
                }
            }
        )
    )
    tracked = set(desired.verification_tables)
    stale_tagged = [
        table
        for table in tagged_tables
        if table not in tracked
    ]
    if stale_tagged:
        errors.append(
            "owned-protocol routes exist outside tracked tables: "
            + repr(stale_tagged)
        )

    expected_rules = {
        _desired_rule_key(item)
        for item in desired.dispatch_rules
    }
    if desired.terminal_rule is not None:
        expected_rules.add(
            _desired_terminal_rule_key(desired.terminal_rule)
        )
    observed_owned_rules = {
        _observed_rule_key(item)
        for item in observed.rules
        if FIRST_RULE_PRIORITY
        <= item.priority
        <= MAX_RULE_PRIORITY
    }
    missing_rules = expected_rules - observed_owned_rules
    extra_rules = observed_owned_rules - expected_rules
    if missing_rules:
        errors.append(
            f"missing owned RPDB rules: {sorted(map(str, missing_rules))}"
        )
    if extra_rules:
        errors.append(
            f"unexpected RPDB rules in owned window: "
            f"{sorted(map(str, extra_rules))}"
        )

    if (
        expected_ip_forward is not None
        and observed.ip_forward is not expected_ip_forward
    ):
        errors.append(
            "net.ipv4.ip_forward mismatch: expected "
            f"{int(expected_ip_forward)}, observed "
            f"{int(observed.ip_forward)}"
        )

    return LinuxRoutingVerification(
        ok=not errors,
        errors=tuple(errors),
        tagged_tables=tagged_tables,
    )
