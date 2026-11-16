from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Network

from .interface_identity import InterfaceIdentity
from .network_rules import (
    DispatchRuleSpec,
    FlowInitiationAllowSpec,
    NetworkEndpoint,
    NetworkRulesSpec,
    PortRange,
    PredicateKind,
    RoutingDomainSpec,
    SourceNatSpec,
    SourceNatTarget,
    TerminalDisposition,
    TrafficAllowSpec,
    TrafficPredicate,
    TrafficProtocol,
    TrafficSelector,
)


LOCAL_NETWORK = NetworkEndpoint.local_network()


class PayloadDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BIDIRECTIONAL = "bidirectional"


class PayloadProtocol(str, Enum):
    ANY = "any"
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"


class PayloadNatMode(str, Enum):
    NONE = "none"
    MASQUERADE = "masquerade"


@dataclass(frozen=True, order=True)
class PayloadPortRange:
    start: int
    end: int

    def __post_init__(self) -> None:
        if not 1 <= self.start <= 65535:
            raise ValueError("payload port range start must be 1..65535")
        if not 1 <= self.end <= 65535:
            raise ValueError("payload port range end must be 1..65535")
        if self.start > self.end:
            raise ValueError("payload port range start must not exceed end")


@dataclass(frozen=True)
class PayloadTrafficSelector:
    source: IPv4Network | None = None
    destination: IPv4Network | None = None
    protocol: PayloadProtocol = PayloadProtocol.ANY
    source_ports: tuple[PayloadPortRange, ...] = ()
    destination_ports: tuple[PayloadPortRange, ...] = ()

    def __post_init__(self) -> None:
        if (
            self.source_ports or self.destination_ports
        ) and self.protocol not in {
            PayloadProtocol.TCP,
            PayloadProtocol.UDP,
        }:
            raise ValueError(
                "payload traffic-envelope ports require tcp or udp protocol"
            )
        for ranges in (self.source_ports, self.destination_ports):
            for index, left in enumerate(ranges):
                for right in ranges[index + 1 :]:
                    if left.start <= right.end and right.start <= left.end:
                        raise ValueError(
                            "payload traffic-envelope port ranges must not overlap"
                        )


class EnvelopeDirection(str, Enum):
    FROM_PATH = "from-path"
    TO_PATH = "to-path"


class EnvelopeAction(str, Enum):
    ALLOW = "allow"
    DROP = "drop"


@dataclass(frozen=True)
class TrafficEnvelopeRule:
    direction: EnvelopeDirection
    action: EnvelopeAction
    selector: PayloadTrafficSelector


@dataclass(frozen=True)
class TrafficEnvelope:
    default_action: EnvelopeAction
    rules: tuple[TrafficEnvelopeRule, ...] = ()


@dataclass(frozen=True)
class PayloadPath:
    identity: InterfaceIdentity
    traffic_envelope: TrafficEnvelope | None = None
    nat_mode: PayloadNatMode = PayloadNatMode.NONE


@dataclass(frozen=True)
class PayloadProfileRequest:
    name: str
    direction: PayloadDirection
    destinations: tuple[IPv4Network, ...]
    ordered_paths: tuple[PayloadPath, ...]
    confirmed_live_prefix_length: int | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("payload profile name must be non-empty")
        if len(set(self.destinations)) != len(self.destinations):
            raise ValueError(
                f"profile {self.name!r} contains duplicate destinations"
            )

        identities = [item.identity for item in self.ordered_paths]
        if len(set(identities)) != len(identities):
            raise ValueError(
                f"profile {self.name!r} contains duplicate concrete paths"
            )
        if self.confirmed_live_prefix_length is not None:
            if type(self.confirmed_live_prefix_length) is not int:
                raise ValueError(
                    "confirmed-live prefix length must be an integer"
                )
            if not 0 <= self.confirmed_live_prefix_length <= len(self.ordered_paths):
                raise ValueError(
                    "confirmed-live prefix length is out of range"
                )


@dataclass(frozen=True)
class PayloadTrafficStateRequest:
    profiles: tuple[PayloadProfileRequest, ...]

    def __post_init__(self) -> None:
        names = [item.name for item in self.profiles]
        if len(set(names)) != len(names):
            raise ValueError("duplicate payload profile name")


def _to_network_selector(
    selector: PayloadTrafficSelector,
) -> TrafficSelector:
    protocol = (
        None
        if selector.protocol is PayloadProtocol.ANY
        else TrafficProtocol(selector.protocol.value)
    )
    return TrafficSelector(
        source=selector.source,
        destination=selector.destination,
        protocol=protocol,
        source_ports=tuple(
            PortRange(item.start, item.end)
            for item in selector.source_ports
        ),
        destination_ports=tuple(
            PortRange(item.start, item.end)
            for item in selector.destination_ports
        ),
    )


def _envelope_allowed_predicate(
    envelope: TrafficEnvelope | None,
    direction: EnvelopeDirection,
) -> TrafficPredicate:
    if envelope is None:
        return TrafficPredicate.always()

    remaining = TrafficPredicate.always()
    allowed: list[TrafficPredicate] = []

    for rule in envelope.rules:
        if rule.direction is not direction:
            continue
        matched = TrafficPredicate.match(
            _to_network_selector(rule.selector)
        )
        selected = TrafficPredicate.all_of(remaining, matched)
        if rule.action is EnvelopeAction.ALLOW:
            allowed.append(selected)
        remaining = TrafficPredicate.all_of(
            remaining,
            TrafficPredicate.negate(matched),
        )

    if envelope.default_action is EnvelopeAction.ALLOW:
        allowed.append(remaining)

    return TrafficPredicate.any_of(*allowed)


def _more_specific_destinations(
    destination: IPv4Network,
    all_destinations: tuple[IPv4Network, ...],
) -> tuple[IPv4Network, ...]:
    return tuple(
        item
        for item in all_destinations
        if item != destination
        and item.prefixlen > destination.prefixlen
        and item.subnet_of(destination)
    )


def _destination_predicate(
    destination: IPv4Network,
    all_destinations: tuple[IPv4Network, ...],
    direction: EnvelopeDirection,
) -> TrafficPredicate:
    if direction is EnvelopeDirection.TO_PATH:
        base = TrafficPredicate.match(
            TrafficSelector(destination=destination)
        )
        exclusions = tuple(
            TrafficPredicate.match(TrafficSelector(destination=item))
            for item in _more_specific_destinations(
                destination,
                all_destinations,
            )
        )
    else:
        base = TrafficPredicate.match(TrafficSelector(source=destination))
        exclusions = tuple(
            TrafficPredicate.match(TrafficSelector(source=item))
            for item in _more_specific_destinations(
                destination,
                all_destinations,
            )
        )

    if not exclusions:
        return base

    return TrafficPredicate.all_of(
        base,
        TrafficPredicate.negate(TrafficPredicate.any_of(*exclusions)),
    )


class PayloadRulesCalculator:
    """Translate payload policy into network-rules semantics.

    Profile direction and Device traffic envelopes are resolved here. The Adapter
    receives only effective allow policy and does not know those payload-domain concepts.
    """

    def calculate(
        self,
        request: PayloadTrafficStateRequest,
    ) -> NetworkRulesSpec:
        seen_destinations: dict[IPv4Network, str] = {}
        all_destinations: list[IPv4Network] = []

        for profile in request.profiles:
            for destination in profile.destinations:
                previous = seen_destinations.get(destination)
                if previous is not None:
                    raise ValueError(
                        f"payload destination {destination} is claimed by both "
                        f"{previous!r} and {profile.name!r}"
                    )
                seen_destinations[destination] = profile.name
                all_destinations.append(destination)

        destination_space = tuple(all_destinations)
        routing_domains: list[RoutingDomainSpec] = []
        dispatch_rules: list[DispatchRuleSpec] = []
        traffic_allows: list[TrafficAllowSpec] = []
        flow_allows: list[FlowInitiationAllowSpec] = []
        source_nat: list[SourceNatSpec] = []

        for profile in request.profiles:
            routing_domains.append(
                RoutingDomainSpec(
                    name=profile.name,
                    destinations=profile.destinations,
                    ordered_paths=tuple(
                        path.identity for path in profile.ordered_paths
                    ),
                    terminal_disposition=TerminalDisposition.DROP,
                    confirmed_live_prefix_length=(
                        profile.confirmed_live_prefix_length
                    ),
                )
            )

            dispatch_rules.extend(
                DispatchRuleSpec(
                    destination=destination,
                    routing_domain=profile.name,
                    source=LOCAL_NETWORK,
                )
                for destination in profile.destinations
            )

            policy_paths = sorted(
                profile.ordered_paths,
                key=lambda path: (
                    path.identity.ifname,
                    path.identity.ifindex,
                ),
            )
            for path in policy_paths:
                path_endpoint = NetworkEndpoint.interface_path(path.identity)
                envelope_to = _envelope_allowed_predicate(
                    path.traffic_envelope,
                    EnvelopeDirection.TO_PATH,
                )
                envelope_from = _envelope_allowed_predicate(
                    path.traffic_envelope,
                    EnvelopeDirection.FROM_PATH,
                )

                for destination in profile.destinations:
                    to_path = TrafficPredicate.all_of(
                        _destination_predicate(
                            destination,
                            destination_space,
                            EnvelopeDirection.TO_PATH,
                        ),
                        envelope_to,
                    )
                    from_path = TrafficPredicate.all_of(
                        _destination_predicate(
                            destination,
                            destination_space,
                            EnvelopeDirection.FROM_PATH,
                        ),
                        envelope_from,
                    )

                    if to_path.kind is not PredicateKind.NEVER:
                        traffic_allows.append(
                            TrafficAllowSpec(
                                LOCAL_NETWORK,
                                path_endpoint,
                                to_path,
                            )
                        )
                        if profile.direction in {
                            PayloadDirection.OUTBOUND,
                            PayloadDirection.BIDIRECTIONAL,
                        }:
                            flow_allows.append(
                                FlowInitiationAllowSpec(
                                    LOCAL_NETWORK,
                                    path_endpoint,
                                    to_path,
                                )
                            )

                    if from_path.kind is not PredicateKind.NEVER:
                        traffic_allows.append(
                            TrafficAllowSpec(
                                path_endpoint,
                                LOCAL_NETWORK,
                                from_path,
                            )
                        )
                        if profile.direction in {
                            PayloadDirection.INBOUND,
                            PayloadDirection.BIDIRECTIONAL,
                        }:
                            flow_allows.append(
                                FlowInitiationAllowSpec(
                                    path_endpoint,
                                    LOCAL_NETWORK,
                                    from_path,
                                )
                            )

                    if path.nat_mode is PayloadNatMode.MASQUERADE:
                        source_nat.append(
                            SourceNatSpec(
                                source=LOCAL_NETWORK,
                                egress=path_endpoint,
                                predicate=_destination_predicate(
                                    destination,
                                    destination_space,
                                    EnvelopeDirection.TO_PATH,
                                ),
                                target=SourceNatTarget.EGRESS_ADDRESS,
                            )
                        )

        dispatch_rules.sort(
            key=lambda rule: (
                -rule.destination.prefixlen,
                int(rule.destination.network_address),
                rule.routing_domain,
            )
        )

        return NetworkRulesSpec(
            routing_domains=tuple(routing_domains),
            dispatch_rules=tuple(dispatch_rules),
            traffic_allows=tuple(traffic_allows),
            flow_initiation_allows=tuple(flow_allows),
            source_nat=tuple(source_nat),
        )
