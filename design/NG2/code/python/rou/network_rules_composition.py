from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .network_rules import (
    DispatchRuleSpec,
    EndpointKind,
    NetworkEndpoint,
    NetworkRulesSpec,
)


class NetworkRulesCompositionError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class OwnerToken:
    value: int

    def __post_init__(self) -> None:
        if type(self.value) is not int or self.value <= 0:
            raise NetworkRulesCompositionError(
                "owner token must be a positive integer"
            )


@dataclass(frozen=True, order=True)
class OwnedRoutingDomainRef:
    owner: OwnerToken
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise NetworkRulesCompositionError(
                "owned routing-domain name must be non-empty"
            )


@dataclass(frozen=True)
class OwnedNetworkRules:
    owner: OwnerToken
    rules: NetworkRulesSpec


@dataclass(frozen=True)
class OwnedDispatchRule:
    owner: OwnerToken
    source: NetworkEndpoint
    destination: IPv4Network
    routing_domain: OwnedRoutingDomainRef


@dataclass(frozen=True)
class ComposedNetworkRules:
    owners: tuple[OwnedNetworkRules, ...]
    dispatch_rules: tuple[OwnedDispatchRule, ...]


@dataclass
class _OwnerEntry:
    identity: object
    token: OwnerToken
    rules: NetworkRulesSpec


class OwnerRulesRegistry:
    """Adapter-internal current desired rules keyed strictly by object identity."""

    def __init__(self) -> None:
        self._entries: list[_OwnerEntry] = []
        self._next_token = 1

    def replace(
        self,
        owner: object,
        rules: NetworkRulesSpec,
    ) -> OwnerToken:
        entry = self._find(owner)
        if entry is not None:
            entry.rules = rules
            return entry.token

        token = OwnerToken(self._next_token)
        self._next_token += 1
        self._entries.append(_OwnerEntry(owner, token, rules))
        return token

    def get(self, owner: object) -> OwnedNetworkRules | None:
        entry = self._find(owner)
        if entry is None:
            return None
        return OwnedNetworkRules(entry.token, entry.rules)

    def remove(self, owner: object) -> bool:
        for index, entry in enumerate(self._entries):
            if entry.identity is owner:
                del self._entries[index]
                return True
        return False

    def snapshot(self) -> tuple[OwnedNetworkRules, ...]:
        return tuple(
            OwnedNetworkRules(entry.token, entry.rules)
            for entry in self._entries
        )

    def _find(self, owner: object) -> _OwnerEntry | None:
        for entry in self._entries:
            if entry.identity is owner:
                return entry
        return None


def _endpoint_key(endpoint: NetworkEndpoint) -> tuple:
    if endpoint.kind is EndpointKind.LOCAL_NETWORK:
        return (0, "", 0)

    assert endpoint.interface is not None
    return (
        1,
        endpoint.interface.ifname,
        endpoint.interface.ifindex,
    )


def _dispatch_selector_key(
    rule: DispatchRuleSpec,
) -> tuple[NetworkEndpoint, IPv4Network]:
    return (rule.source, rule.destination)


def _dispatch_sort_key(rule: OwnedDispatchRule) -> tuple:
    return (
        -rule.destination.prefixlen,
        int(rule.destination.network_address),
        _endpoint_key(rule.source),
        rule.owner.value,
        rule.routing_domain.name,
    )


def compose_network_rules(
    owners: tuple[OwnedNetworkRules, ...],
) -> ComposedNetworkRules:
    """Compose live owner desired sets without inventing inter-owner priority."""

    tokens = [item.owner for item in owners]
    if len(set(tokens)) != len(tokens):
        raise NetworkRulesCompositionError(
            "duplicate owner token in composition input"
        )

    ordered_owners = tuple(
        sorted(owners, key=lambda item: item.owner.value)
    )

    dispatch: list[OwnedDispatchRule] = []
    selectors: dict[tuple[NetworkEndpoint, IPv4Network], OwnerToken] = {}

    for owned in ordered_owners:
        for rule in owned.rules.dispatch_rules:
            selector = _dispatch_selector_key(rule)
            previous = selectors.get(selector)
            if previous is not None:
                raise NetworkRulesCompositionError(
                    "duplicate dispatch selector "
                    f"{rule.source!r} -> {rule.destination}: "
                    f"owners {previous.value} and {owned.owner.value}"
                )
            selectors[selector] = owned.owner

            dispatch.append(
                OwnedDispatchRule(
                    owner=owned.owner,
                    source=rule.source,
                    destination=rule.destination,
                    routing_domain=OwnedRoutingDomainRef(
                        owned.owner,
                        rule.routing_domain,
                    ),
                )
            )

    dispatch.sort(key=_dispatch_sort_key)

    return ComposedNetworkRules(
        owners=ordered_owners,
        dispatch_rules=tuple(dispatch),
    )
