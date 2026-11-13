from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .network_rules import (
    DispatchRuleSpec,
    InterfaceIdentity,
    InterfaceRef,
    NetworkRulesError,
    NetworkRulesSpec,
    RoutingDomainSpec,
    TerminalAction,
)


HOST_INTERFACE = InterfaceRef.stable("host0")


@dataclass(frozen=True)
class PayloadPath:
    device_name: str
    identity: InterfaceIdentity

    def __post_init__(self) -> None:
        if not self.device_name:
            raise NetworkRulesError("payload path device_name must be non-empty")


@dataclass(frozen=True)
class PayloadProfileRequest:
    name: str
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


class PayloadRulesCalculator:
    """Compile the routing/dispatch slice of payload intent.

    Filter and NAT policy intentionally remain out of this first executable slice.
    """

    def calculate(
        self,
        request: PayloadTrafficStateRequest,
    ) -> NetworkRulesSpec:
        seen_destinations: dict[IPv4Network, str] = {}
        routing_domains: list[RoutingDomainSpec] = []
        dispatch_rules: list[DispatchRuleSpec] = []

        for profile in request.profiles:
            for destination in profile.destinations:
                previous = seen_destinations.get(destination)
                if previous is not None:
                    raise NetworkRulesError(
                        f"payload destination {destination} is claimed by both "
                        f"{previous!r} and {profile.name!r}"
                    )
                seen_destinations[destination] = profile.name

            routing_domains.append(
                RoutingDomainSpec(
                    name=profile.name,
                    destinations=profile.destinations,
                    ordered_paths=tuple(
                        InterfaceRef.concrete(path.identity)
                        for path in profile.ordered_paths
                    ),
                    terminal_action=TerminalAction.BLACKHOLE,
                )
            )

            dispatch_rules.extend(
                DispatchRuleSpec(
                    destination=destination,
                    routing_domain=profile.name,
                    ingress=HOST_INTERFACE,
                )
                for destination in profile.destinations
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
        )
