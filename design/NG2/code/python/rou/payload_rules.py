from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Network

from .network_rules import (
    DispatchRuleSpec,
    FlowInitiationAllowSpec,
    InterfaceIdentity,
    NetworkEndpoint,
    NetworkRulesError,
    NetworkRulesSpec,
    RoutingDomainSpec,
    TerminalAction,
    TrafficAllowSpec,
    TrafficPredicate,
    TrafficSelector,
)


LOCAL_NETWORK = NetworkEndpoint.local_network()


class PayloadDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BIDIRECTIONAL = "bidirectional"


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
    selector: TrafficSelector


@dataclass(frozen=True)
class TrafficEnvelope:
    default_action: EnvelopeAction
    rules: tuple[TrafficEnvelopeRule, ...] = ()


@dataclass(frozen=True)
class PayloadPath:
    identity: InterfaceIdentity
    traffic_envelope: TrafficEnvelope | None = None


@dataclass(frozen=True)
class PayloadProfileRequest:
    name: str
    direction: PayloadDirection
    destinations: tuple[IPv4Network, ...]
    ordered_paths: tuple[PayloadPath, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise NetworkRulesError("payload profile name must be non-empty")
        if len(set(self.destinations)) != len(self.destinations):
            raise NetworkRulesError(
                f"profile {self.name!r} contains duplicate destinations"
            )

        identities = [item.identity for item in self.ordered_paths]
        if len(set(identities)) != len(identities):
            raise NetworkRulesError(
                f"profile {self.name!r} contains duplicate concrete paths"
            )


@dataclass(frozen=True)
class PayloadTrafficStateRequest:
    profiles: tuple[PayloadProfileRequest, ...]

    def __post_init__(self) -> None:
        names = [item.name for item in self.profiles]
        if len(set(names)) != len(names):
            raise NetworkRulesError("duplicate payload profile name")


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
        matched = TrafficPredicate.match(rule.selector)
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
                    raise NetworkRulesError(
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

        for profile in request.profiles:
            routing_domains.append(
                RoutingDomainSpec(
                    name=profile.name,
                    destinations=profile.destinations,
                    ordered_paths=tuple(
                        path.identity for path in profile.ordered_paths
                    ),
                    terminal_action=TerminalAction.BLACKHOLE,
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

            for path in profile.ordered_paths:
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

                    if to_path.kind.value != "never":
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

                    if from_path.kind.value != "never":
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
        )
