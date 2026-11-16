from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Network
from typing import Protocol

from .interface_identity import InterfaceIdentity


class NetworkRulesError(ValueError):
    pass


class EndpointKind(str, Enum):
    LOCAL_NETWORK = "local-network"
    LOCAL_PROCESS = "local-process"
    INTERFACE = "interface"


@dataclass(frozen=True)
class NetworkEndpoint:
    kind: EndpointKind
    interface: InterfaceIdentity | None = None

    def __post_init__(self) -> None:
        if self.kind in {
            EndpointKind.LOCAL_NETWORK,
            EndpointKind.LOCAL_PROCESS,
        }:
            if self.interface is not None:
                raise NetworkRulesError(
                    f"{self.kind.value} endpoint must not carry interface identity"
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
    def local_process(cls) -> "NetworkEndpoint":
        return cls(EndpointKind.LOCAL_PROCESS)

    @classmethod
    def interface_path(cls, identity: InterfaceIdentity) -> "NetworkEndpoint":
        return cls(EndpointKind.INTERFACE, identity)


class TerminalDisposition(str, Enum):
    DROP = "drop"
    REJECT = "reject"


@dataclass(frozen=True)
class RoutingDomainSpec:
    name: str
    destinations: tuple[IPv4Network, ...]
    ordered_paths: tuple[InterfaceIdentity, ...]
    terminal_disposition: TerminalDisposition

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


class TrafficProtocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"


class IcmpType(int, Enum):
    ECHO_REPLY = 0
    ECHO_REQUEST = 8


@dataclass(frozen=True)
class DispatchRuleSpec:
    destination: IPv4Network
    routing_domain: str
    source: NetworkEndpoint
    bound_output: NetworkEndpoint | None = None
    protocol: TrafficProtocol | None = None

    def __post_init__(self) -> None:
        if not self.routing_domain:
            raise NetworkRulesError("dispatch routing_domain must be non-empty")

        if self.bound_output is not None:
            if self.bound_output.kind is not EndpointKind.INTERFACE:
                raise NetworkRulesError(
                    "dispatch bound_output requires a concrete interface endpoint"
                )

        if self.source.kind is EndpointKind.LOCAL_PROCESS:
            if self.bound_output is None:
                raise NetworkRulesError(
                    "local-process dispatch requires bound output interface"
                )
            if self.protocol is None:
                raise NetworkRulesError(
                    "local-process dispatch requires explicit protocol"
                )


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


@dataclass(frozen=True)
class TrafficSelector:
    source: IPv4Network | None = None
    destination: IPv4Network | None = None
    protocol: TrafficProtocol | None = None
    source_ports: tuple[PortRange, ...] = ()
    destination_ports: tuple[PortRange, ...] = ()
    icmp_types: tuple[IcmpType, ...] = ()

    def __post_init__(self) -> None:
        if (self.source_ports or self.destination_ports) and self.protocol not in {
            TrafficProtocol.TCP,
            TrafficProtocol.UDP,
        }:
            raise NetworkRulesError(
                "traffic-selector ports require tcp or udp protocol"
            )
        if self.icmp_types and self.protocol is not TrafficProtocol.ICMP:
            raise NetworkRulesError(
                "traffic-selector icmp types require icmp protocol"
            )
        if any(not isinstance(item, IcmpType) for item in self.icmp_types):
            raise NetworkRulesError(
                "traffic-selector icmp types must use IcmpType values"
            )
        if len(set(self.icmp_types)) != len(self.icmp_types):
            raise NetworkRulesError(
                "traffic-selector icmp types must not contain duplicates"
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
            and not self.icmp_types
        )


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


class SourceNatTarget(str, Enum):
    EGRESS_ADDRESS = "egress-address"


@dataclass(frozen=True)
class SourceNatSpec:
    source: NetworkEndpoint
    egress: NetworkEndpoint
    predicate: TrafficPredicate
    target: SourceNatTarget

    def __post_init__(self) -> None:
        if self.egress.kind is not EndpointKind.INTERFACE:
            raise NetworkRulesError(
                "source NAT requires a concrete egress interface endpoint"
            )


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
    source_nat: tuple[SourceNatSpec, ...] = ()

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


def routing_domains_semantically_equal(
    actual: tuple[RoutingDomainSpec, ...],
    desired: tuple[RoutingDomainSpec, ...],
) -> bool:
    """Compare routing-domain semantics while preserving ordered path priority."""

    actual_by_name = {item.name: item for item in actual}
    desired_by_name = {item.name: item for item in desired}

    if actual_by_name.keys() != desired_by_name.keys():
        return False

    for name, wanted in desired_by_name.items():
        observed = actual_by_name[name]
        if set(observed.destinations) != set(wanted.destinations):
            return False
        if observed.ordered_paths != wanted.ordered_paths:
            return False
        if observed.terminal_disposition is not wanted.terminal_disposition:
            return False

    return True


def network_rules_semantically_equal(
    actual: NetworkRulesSpec,
    desired: NetworkRulesSpec,
) -> bool:
    """Generic semantic equality used by domain-specific state calculators."""

    return (
        routing_domains_semantically_equal(
            actual.routing_domains,
            desired.routing_domains,
        )
        and actual.dispatch_rules == desired.dispatch_rules
        and set(actual.traffic_allows) == set(desired.traffic_allows)
        and set(actual.flow_initiation_allows)
        == set(desired.flow_initiation_allows)
        and actual.source_nat == desired.source_nat
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
