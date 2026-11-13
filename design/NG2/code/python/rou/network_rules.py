from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Network
from typing import Protocol


class NetworkRulesError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class InterfaceIdentity:
    ifname: str
    ifindex: int

    def __post_init__(self) -> None:
        if not self.ifname:
            raise NetworkRulesError("ifname must be non-empty")
        if len(self.ifname.encode("utf-8")) > 15:
            raise NetworkRulesError("ifname exceeds Linux IFNAMSIZ-1")
        if type(self.ifindex) is not int or self.ifindex <= 0:
            raise NetworkRulesError("ifindex must be a positive integer")


class EndpointKind(str, Enum):
    LOCAL_NETWORK = "local-network"
    INTERFACE = "interface"


@dataclass(frozen=True)
class NetworkEndpoint:
    kind: EndpointKind
    interface: InterfaceIdentity | None = None

    def __post_init__(self) -> None:
        if self.kind is EndpointKind.LOCAL_NETWORK:
            if self.interface is not None:
                raise NetworkRulesError(
                    "local-network endpoint must not carry interface identity"
                )
            return
        if self.kind is EndpointKind.INTERFACE:
            if self.interface is None:
                raise NetworkRulesError(
                    "interface endpoint requires concrete interface identity"
                )
            return
        raise NetworkRulesError(f"unsupported endpoint kind {self.kind!r}")

    @classmethod
    def local_network(cls) -> "NetworkEndpoint":
        return cls(EndpointKind.LOCAL_NETWORK)

    @classmethod
    def interface_path(cls, identity: InterfaceIdentity) -> "NetworkEndpoint":
        return cls(EndpointKind.INTERFACE, identity)


class TerminalAction(str, Enum):
    BLACKHOLE = "blackhole"
    UNREACHABLE = "unreachable"
    PROHIBIT = "prohibit"


@dataclass(frozen=True)
class RoutingDomainSpec:
    name: str
    destinations: tuple[IPv4Network, ...]
    ordered_paths: tuple[InterfaceIdentity, ...]
    terminal_action: TerminalAction

    def __post_init__(self) -> None:
        if not self.name:
            raise NetworkRulesError("routing domain name must be non-empty")
        if len(set(self.destinations)) != len(self.destinations):
            raise NetworkRulesError(
                f"routing domain {self.name!r} contains duplicate destinations"
            )
        if len(set(self.ordered_paths)) != len(self.ordered_paths):
            raise NetworkRulesError(
                f"routing domain {self.name!r} contains duplicate paths"
            )


@dataclass(frozen=True)
class DispatchRuleSpec:
    destination: IPv4Network
    routing_domain: str
    source: NetworkEndpoint

    def __post_init__(self) -> None:
        if not self.routing_domain:
            raise NetworkRulesError("dispatch routing_domain must be non-empty")


class TrafficProtocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"


@dataclass(frozen=True, order=True)
class PortRange:
    start: int
    end: int

    def __post_init__(self) -> None:
        if not 1 <= self.start <= 65535:
            raise NetworkRulesError("port range start must be 1..65535")
        if not 1 <= self.end <= 65535:
            raise NetworkRulesError("port range end must be 1..65535")
        if self.start > self.end:
            raise NetworkRulesError("port range start must not exceed end")

    def contains(self, port: int) -> bool:
        return self.start <= port <= self.end


@dataclass(frozen=True)
class PacketView:
    source: IPv4Address
    destination: IPv4Address
    protocol: TrafficProtocol
    source_port: int | None = None
    destination_port: int | None = None

    def __post_init__(self) -> None:
        ports = (self.source_port, self.destination_port)
        if self.protocol in {TrafficProtocol.TCP, TrafficProtocol.UDP}:
            for port in ports:
                if port is not None and not 1 <= port <= 65535:
                    raise NetworkRulesError("packet port must be 1..65535")
        elif any(port is not None for port in ports):
            raise NetworkRulesError("ICMP packet view must not carry ports")


@dataclass(frozen=True)
class TrafficSelector:
    source: IPv4Network | None = None
    destination: IPv4Network | None = None
    protocol: TrafficProtocol | None = None
    source_ports: tuple[PortRange, ...] = ()
    destination_ports: tuple[PortRange, ...] = ()

    def __post_init__(self) -> None:
        if (self.source_ports or self.destination_ports) and self.protocol not in {
            TrafficProtocol.TCP,
            TrafficProtocol.UDP,
        }:
            raise NetworkRulesError(
                "traffic-selector ports require tcp or udp protocol"
            )
        for ranges in (self.source_ports, self.destination_ports):
            for index, left in enumerate(ranges):
                for right in ranges[index + 1 :]:
                    if left.start <= right.end and right.start <= left.end:
                        raise NetworkRulesError(
                            "traffic-selector port ranges must not overlap"
                        )

    @property
    def universal(self) -> bool:
        return (
            self.source is None
            and self.destination is None
            and self.protocol is None
            and not self.source_ports
            and not self.destination_ports
        )

    def matches(self, packet: PacketView) -> bool:
        if self.source is not None and packet.source not in self.source:
            return False
        if self.destination is not None and packet.destination not in self.destination:
            return False
        if self.protocol is not None and packet.protocol is not self.protocol:
            return False
        if self.source_ports:
            if packet.source_port is None:
                return False
            if not any(item.contains(packet.source_port) for item in self.source_ports):
                return False
        if self.destination_ports:
            if packet.destination_port is None:
                return False
            if not any(
                item.contains(packet.destination_port)
                for item in self.destination_ports
            ):
                return False
        return True


class PredicateKind(str, Enum):
    ALWAYS = "always"
    NEVER = "never"
    MATCH = "match"
    ALL = "all"
    ANY = "any"
    NOT = "not"


@dataclass(frozen=True)
class TrafficPredicate:
    kind: PredicateKind
    selector: TrafficSelector | None = None
    children: tuple["TrafficPredicate", ...] = ()

    def __post_init__(self) -> None:
        if self.kind is PredicateKind.MATCH:
            if self.selector is None or self.children:
                raise NetworkRulesError(
                    "match predicate requires selector and no children"
                )
            return
        if self.selector is not None:
            raise NetworkRulesError(
                f"{self.kind.value} predicate must not carry selector"
            )
        if self.kind in {PredicateKind.ALWAYS, PredicateKind.NEVER}:
            if self.children:
                raise NetworkRulesError(
                    f"{self.kind.value} predicate must not carry children"
                )
            return
        if self.kind is PredicateKind.NOT:
            if len(self.children) != 1:
                raise NetworkRulesError("not predicate requires one child")
            return
        if self.kind in {PredicateKind.ALL, PredicateKind.ANY}:
            if len(self.children) < 2:
                raise NetworkRulesError(
                    f"{self.kind.value} predicate requires at least two children"
                )
            return
        raise NetworkRulesError(f"unsupported predicate kind {self.kind!r}")

    @classmethod
    def always(cls) -> "TrafficPredicate":
        return cls(PredicateKind.ALWAYS)

    @classmethod
    def never(cls) -> "TrafficPredicate":
        return cls(PredicateKind.NEVER)

    @classmethod
    def match(cls, selector: TrafficSelector) -> "TrafficPredicate":
        if selector.universal:
            return cls.always()
        return cls(PredicateKind.MATCH, selector=selector)

    @classmethod
    def all_of(cls, *items: "TrafficPredicate") -> "TrafficPredicate":
        flattened: list[TrafficPredicate] = []
        for item in items:
            if item.kind is PredicateKind.NEVER:
                return cls.never()
            if item.kind is PredicateKind.ALWAYS:
                continue
            if item.kind is PredicateKind.ALL:
                flattened.extend(item.children)
            else:
                flattened.append(item)
        if not flattened:
            return cls.always()
        unique = tuple(dict.fromkeys(flattened))
        if len(unique) == 1:
            return unique[0]
        return cls(PredicateKind.ALL, children=unique)

    @classmethod
    def any_of(cls, *items: "TrafficPredicate") -> "TrafficPredicate":
        flattened: list[TrafficPredicate] = []
        for item in items:
            if item.kind is PredicateKind.ALWAYS:
                return cls.always()
            if item.kind is PredicateKind.NEVER:
                continue
            if item.kind is PredicateKind.ANY:
                flattened.extend(item.children)
            else:
                flattened.append(item)
        if not flattened:
            return cls.never()
        unique = tuple(dict.fromkeys(flattened))
        if len(unique) == 1:
            return unique[0]
        return cls(PredicateKind.ANY, children=unique)

    @classmethod
    def negate(cls, item: "TrafficPredicate") -> "TrafficPredicate":
        if item.kind is PredicateKind.ALWAYS:
            return cls.never()
        if item.kind is PredicateKind.NEVER:
            return cls.always()
        if item.kind is PredicateKind.NOT:
            return item.children[0]
        return cls(PredicateKind.NOT, children=(item,))

    def matches(self, packet: PacketView) -> bool:
        if self.kind is PredicateKind.ALWAYS:
            return True
        if self.kind is PredicateKind.NEVER:
            return False
        if self.kind is PredicateKind.MATCH:
            assert self.selector is not None
            return self.selector.matches(packet)
        if self.kind is PredicateKind.ALL:
            return all(item.matches(packet) for item in self.children)
        if self.kind is PredicateKind.ANY:
            return any(item.matches(packet) for item in self.children)
        if self.kind is PredicateKind.NOT:
            return not self.children[0].matches(packet)
        raise AssertionError(f"unreachable predicate kind {self.kind!r}")


@dataclass(frozen=True)
class TrafficAllowSpec:
    source: NetworkEndpoint
    destination: NetworkEndpoint
    predicate: TrafficPredicate


@dataclass(frozen=True)
class FlowInitiationAllowSpec:
    source: NetworkEndpoint
    destination: NetworkEndpoint
    predicate: TrafficPredicate


@dataclass(frozen=True)
class NetworkRulesSpec:
    """Semantic desired network rules.

    Filtering is allow-only. Anything not represented by traffic_allows is denied.
    A new flow must match both traffic_allows and flow_initiation_allows. Stateful
    realization of those semantics belongs to the Adapter.
    """

    routing_domains: tuple[RoutingDomainSpec, ...] = ()
    dispatch_rules: tuple[DispatchRuleSpec, ...] = ()
    traffic_allows: tuple[TrafficAllowSpec, ...] = ()
    flow_initiation_allows: tuple[FlowInitiationAllowSpec, ...] = ()

    def __post_init__(self) -> None:
        domain_names = [item.name for item in self.routing_domains]
        if len(set(domain_names)) != len(domain_names):
            raise NetworkRulesError("duplicate routing domain name")

        known = set(domain_names)
        for rule in self.dispatch_rules:
            if rule.routing_domain not in known:
                raise NetworkRulesError(
                    f"dispatch references unknown routing domain "
                    f"{rule.routing_domain!r}"
                )


class StateKnowledge(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NetworkRulesState:
    knowledge: StateKnowledge
    rules: NetworkRulesSpec | None
    fresh: bool
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if self.knowledge is StateKnowledge.KNOWN and self.rules is None:
            raise NetworkRulesError("known state requires rules")
        if self.knowledge is StateKnowledge.UNKNOWN and self.rules is not None:
            raise NetworkRulesError("unknown state must not claim rules")
        if self.knowledge is StateKnowledge.UNKNOWN and self.fresh:
            raise NetworkRulesError("unknown state cannot be authoritative fresh state")


@dataclass(frozen=True)
class ActionResult:
    success: bool
    diagnostic: str | None = None


class NetworkRulesAdapter(Protocol):
    """Direct Adapter.

    owner is opaque caller-instance identity. The Adapter must compare ownership by
    identity, not by caller-provided semantic names or equality.
    """

    def apply(
        self,
        owner: object,
        spec: NetworkRulesSpec,
    ) -> ActionResult:
        ...

    def renew_state(self, owner: object) -> ActionResult:
        ...

    def get_last_state(self, owner: object) -> NetworkRulesState:
        ...

    def cleanup(self, owner: object) -> ActionResult:
        ...
