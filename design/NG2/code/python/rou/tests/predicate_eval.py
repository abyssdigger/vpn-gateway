from dataclasses import dataclass
from ipaddress import IPv4Address

from rou.network_rules import (
    PredicateKind,
    TrafficPredicate,
    TrafficProtocol,
    TrafficSelector,
)


@dataclass(frozen=True)
class PacketView:
    source: IPv4Address
    destination: IPv4Address
    protocol: TrafficProtocol
    source_port: int | None = None
    destination_port: int | None = None


def _port_matches(port: int | None, ranges) -> bool:
    if not ranges:
        return True
    if port is None:
        return False
    return any(item.start <= port <= item.end for item in ranges)


def _selector_matches(selector: TrafficSelector, packet: PacketView) -> bool:
    return (
        (selector.source is None or packet.source in selector.source)
        and (
            selector.destination is None
            or packet.destination in selector.destination
        )
        and (
            selector.protocol is None
            or packet.protocol is selector.protocol
        )
        and _port_matches(packet.source_port, selector.source_ports)
        and _port_matches(
            packet.destination_port,
            selector.destination_ports,
        )
    )


def predicate_matches(
    predicate: TrafficPredicate,
    packet: PacketView,
) -> bool:
    if predicate.kind is PredicateKind.ALWAYS:
        return True
    if predicate.kind is PredicateKind.NEVER:
        return False
    if predicate.kind is PredicateKind.MATCH:
        assert predicate.selector is not None
        return _selector_matches(predicate.selector, packet)
    if predicate.kind is PredicateKind.ALL:
        return all(
            predicate_matches(item, packet)
            for item in predicate.children
        )
    if predicate.kind is PredicateKind.ANY:
        return any(
            predicate_matches(item, packet)
            for item in predicate.children
        )
    if predicate.kind is PredicateKind.NOT:
        return not predicate_matches(predicate.children[0], packet)
    raise AssertionError(f"unreachable predicate kind {predicate.kind!r}")
