from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
import json
from typing import Iterable

from .binding import LogicalPathId
from .interface_identity import InterfaceIdentity
from .route_priority_executor import RoutePrioritySnapshot


class RoutePriorityInventoryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RoutePriorityPathRoute:
    """Expected non-metric identity of one logical path in one route-key domain."""

    path_id: LogicalPathId
    endpoint: InterfaceIdentity
    gateway: IPv4Address | None = None
    onlink: bool = False


def parse_ip_route_priority_snapshot(
    text: str,
    *,
    destination: IPv4Network,
    owner_protocol: int,
    path_routes: Iterable[RoutePriorityPathRoute],
    interfaces: Iterable[InterfaceIdentity],
) -> RoutePrioritySnapshot:
    """Project one owned route-key domain from iproute2 JSON.

    Rows outside the selected destination/protocol are ignored. Rows inside the
    selected owned domain must match exactly one expected logical path by current
    interface identity plus path-specific gateway/onlink semantics.

    Missing path rows are preserved as empty metric sets so the convergence
    planner can reject the state from the priority-only continuity boundary
    rather than mistaking absence for observation failure.
    """
    _validate_domain(destination, owner_protocol)

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RoutePriorityInventoryError(
            f"invalid ip-route JSON: {exc}"
        ) from None
    if not isinstance(raw, list):
        raise RoutePriorityInventoryError("ip-route JSON root must be an array")

    interface_by_name = _index_interfaces(tuple(interfaces))
    expected = _index_path_routes(tuple(path_routes), interface_by_name)
    metrics_by_path: dict[LogicalPathId, list[int]] = {
        path_id: []
        for path_id in expected
    }

    for position, row in enumerate(raw):
        if not isinstance(row, dict):
            raise RoutePriorityInventoryError(
                f"route[{position}] must be an object"
            )

        protocol = _parse_protocol(row.get("protocol"), position)
        row_destination = _parse_destination(row.get("dst"), position)

        if protocol != owner_protocol or row_destination != destination:
            continue

        route_type = row.get("type")
        if route_type not in (None, "unicast"):
            raise RoutePriorityInventoryError(
                f"route[{position}] in owned priority domain is not unicast"
            )

        nexthops = row.get("nexthops")
        if nexthops not in (None, []):
            raise RoutePriorityInventoryError(
                f"route[{position}] uses multipath/nexthops and is not a single-path priority route"
            )

        dev = row.get("dev")
        if not isinstance(dev, str) or not dev:
            raise RoutePriorityInventoryError(
                f"route[{position}].dev must be a non-empty string"
            )
        endpoint = interface_by_name.get(dev)
        if endpoint is None:
            raise RoutePriorityInventoryError(
                f"route[{position}] refers to interface {dev!r} absent from current interface inventory"
            )

        gateway = _parse_gateway(row.get("gateway"), position)
        flags = row.get("flags", [])
        if not isinstance(flags, list) or any(
            not isinstance(flag, str)
            for flag in flags
        ):
            raise RoutePriorityInventoryError(
                f"route[{position}].flags must be an array of strings"
            )
        onlink = "onlink" in flags

        matches = [
            spec
            for spec in expected.values()
            if spec.endpoint == endpoint
            and spec.gateway == gateway
            and spec.onlink == onlink
        ]
        if len(matches) != 1:
            raise RoutePriorityInventoryError(
                f"route[{position}] does not match exactly one expected logical path"
            )
        path_id = matches[0].path_id

        metric = row.get("metric")
        if type(metric) is not int or metric < 0:
            raise RoutePriorityInventoryError(
                f"route[{position}].metric must be a non-negative integer"
            )
        if metric in metrics_by_path[path_id]:
            raise RoutePriorityInventoryError(
                f"route[{position}] duplicates metric {metric} for {path_id!r}"
            )
        metrics_by_path[path_id].append(metric)

    return RoutePrioritySnapshot.build(metrics_by_path)


def _validate_domain(
    destination: IPv4Network,
    owner_protocol: int,
) -> None:
    if not isinstance(destination, IPv4Network):
        raise RoutePriorityInventoryError(
            "destination must be an IPv4Network"
        )
    if type(owner_protocol) is not int or not 0 <= owner_protocol <= 255:
        raise RoutePriorityInventoryError(
            "owner_protocol must be an integer in [0, 255]"
        )


def _index_interfaces(
    interfaces: tuple[InterfaceIdentity, ...],
) -> dict[str, InterfaceIdentity]:
    by_name: dict[str, InterfaceIdentity] = {}
    by_index: dict[int, InterfaceIdentity] = {}
    for endpoint in interfaces:
        if endpoint.ifname in by_name:
            raise RoutePriorityInventoryError(
                f"duplicate current interface name {endpoint.ifname!r}"
            )
        if endpoint.ifindex in by_index:
            raise RoutePriorityInventoryError(
                f"duplicate current ifindex {endpoint.ifindex}"
            )
        by_name[endpoint.ifname] = endpoint
        by_index[endpoint.ifindex] = endpoint
    return by_name


def _index_path_routes(
    path_routes: tuple[RoutePriorityPathRoute, ...],
    current_interfaces: dict[str, InterfaceIdentity],
) -> dict[LogicalPathId, RoutePriorityPathRoute]:
    expected: dict[LogicalPathId, RoutePriorityPathRoute] = {}
    endpoint_owners: dict[InterfaceIdentity, LogicalPathId] = {}

    for spec in path_routes:
        if spec.path_id in expected:
            raise RoutePriorityInventoryError(
                f"duplicate route identity for {spec.path_id!r}"
            )
        current = current_interfaces.get(spec.endpoint.ifname)
        if current != spec.endpoint:
            raise RoutePriorityInventoryError(
                f"expected endpoint {spec.endpoint!r} is not the current interface identity"
            )
        owner = endpoint_owners.get(spec.endpoint)
        if owner is not None:
            raise RoutePriorityInventoryError(
                f"current endpoint {spec.endpoint!r} is assigned to multiple logical paths"
            )
        endpoint_owners[spec.endpoint] = spec.path_id
        expected[spec.path_id] = spec

    return expected


def _parse_protocol(value: object, position: int) -> int:
    if type(value) is int:
        protocol = value
    elif isinstance(value, str) and value.isdecimal():
        protocol = int(value, 10)
    else:
        return -1

    if not 0 <= protocol <= 255:
        raise RoutePriorityInventoryError(
            f"route[{position}].protocol is outside [0, 255]"
        )
    return protocol


def _parse_destination(value: object, position: int) -> IPv4Network:
    if value == "default":
        return IPv4Network("0.0.0.0/0")
    if not isinstance(value, str):
        raise RoutePriorityInventoryError(
            f"route[{position}].dst must be an IPv4 prefix or 'default'"
        )
    try:
        network = ip_network(value, strict=True)
    except ValueError as exc:
        raise RoutePriorityInventoryError(
            f"route[{position}].dst is invalid: {exc}"
        ) from None
    if not isinstance(network, IPv4Network):
        raise RoutePriorityInventoryError(
            f"route[{position}].dst must be IPv4"
        )
    return network


def _parse_gateway(value: object, position: int) -> IPv4Address | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RoutePriorityInventoryError(
            f"route[{position}].gateway must be an IPv4 address"
        )
    try:
        address = ip_address(value)
    except ValueError as exc:
        raise RoutePriorityInventoryError(
            f"route[{position}].gateway is invalid: {exc}"
        ) from None
    if not isinstance(address, IPv4Address):
        raise RoutePriorityInventoryError(
            f"route[{position}].gateway must be IPv4"
        )
    return address
