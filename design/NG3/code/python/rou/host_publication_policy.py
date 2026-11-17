"""Pure desired-state projection for Device host-side server publication."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address
from typing import Iterable

from .local_publication_policy import PublicationProtocol


class HostPublicationSelectorKind(str, Enum):
    ANY = "any"
    IPV4 = "ipv4"
    INTERFACE = "interface"


@dataclass(frozen=True, slots=True)
class HostPublicationMappingIntent:
    """One normalized external->managed publication pair."""

    device_id: str
    protocol: PublicationProtocol
    selector_kind: HostPublicationSelectorKind
    selector_value: IPv4Address | str | None
    host_port: int
    internal_address: IPv4Address
    internal_port: int

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id:
            raise ValueError("device_id must be non-empty text")
        if not isinstance(self.protocol, PublicationProtocol):
            raise ValueError("protocol must be PublicationProtocol")
        if not isinstance(self.selector_kind, HostPublicationSelectorKind):
            raise ValueError("selector_kind must be HostPublicationSelectorKind")
        if self.selector_kind is HostPublicationSelectorKind.ANY:
            if self.selector_value is not None:
                raise ValueError("any selector must not carry a value")
        elif self.selector_kind is HostPublicationSelectorKind.IPV4:
            if not isinstance(self.selector_value, IPv4Address):
                raise ValueError("ipv4 selector must carry IPv4Address")
        elif self.selector_kind is HostPublicationSelectorKind.INTERFACE:
            if (
                not isinstance(self.selector_value, str)
                or not self.selector_value
                or len(self.selector_value.encode("utf-8")) > 15
            ):
                raise ValueError("interface selector must carry Linux interface name")
        else:
            raise ValueError("unsupported selector kind")
        for name, value in (
            ("host_port", self.host_port),
            ("internal_port", self.internal_port),
        ):
            if type(value) is not int or not 1 <= value <= 65535:
                raise ValueError(f"{name} must be an integer in [1, 65535]")
        if not isinstance(self.internal_address, IPv4Address):
            raise ValueError("internal_address must be IPv4Address")


@dataclass(frozen=True, slots=True)
class HostPublicationRuleSpec:
    protocol: PublicationProtocol
    selector_kind: HostPublicationSelectorKind
    selector_value: IPv4Address | str | None
    host_port: int
    internal_address: IPv4Address
    internal_port: int

    def __post_init__(self) -> None:
        # Reuse intent validation without making Device identity part of physical state.
        HostPublicationMappingIntent(
            device_id="_",
            protocol=self.protocol,
            selector_kind=self.selector_kind,
            selector_value=self.selector_value,
            host_port=self.host_port,
            internal_address=self.internal_address,
            internal_port=self.internal_port,
        )


class HostPublicationProjectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HostPublicationDesiredState:
    rules: tuple[HostPublicationRuleSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rules, tuple):
            raise ValueError("rules must be a tuple")
        if not all(isinstance(rule, HostPublicationRuleSpec) for rule in self.rules):
            raise ValueError("rules must contain HostPublicationRuleSpec")
        if len(set(self.rules)) != len(self.rules):
            raise ValueError("duplicate host publication rule")
        object.__setattr__(
            self,
            "rules",
            tuple(sorted(self.rules, key=_rule_sort_key)),
        )


def build_host_publication_desired(
    intents: Iterable[HostPublicationMappingIntent],
) -> HostPublicationDesiredState:
    """Set-union normalized contributions and reject ambiguous overlap.

    Selector precedence is intentionally absent. If two potentially overlapping
    external selectors for one protocol/host-port request different targets,
    declaration order must not decide the result.
    """
    rules: set[HostPublicationRuleSpec] = set()
    for intent in intents:
        if not isinstance(intent, HostPublicationMappingIntent):
            raise HostPublicationProjectionError(
                "intents must contain HostPublicationMappingIntent"
            )
        candidate = HostPublicationRuleSpec(
            protocol=intent.protocol,
            selector_kind=intent.selector_kind,
            selector_value=intent.selector_value,
            host_port=intent.host_port,
            internal_address=intent.internal_address,
            internal_port=intent.internal_port,
        )
        for existing in rules:
            if (
                existing.protocol is candidate.protocol
                and existing.host_port == candidate.host_port
                and _selectors_may_overlap(existing, candidate)
                and _target(existing) != _target(candidate)
            ):
                raise HostPublicationProjectionError(
                    "ambiguous host publication: overlapping external selector "
                    f"for {candidate.protocol.value}/{candidate.host_port} "
                    "requires different internal target"
                )
        rules.add(candidate)
    return HostPublicationDesiredState(tuple(rules))


def _target(rule: HostPublicationRuleSpec) -> tuple[IPv4Address, int]:
    return rule.internal_address, rule.internal_port


def _selectors_may_overlap(
    left: HostPublicationRuleSpec,
    right: HostPublicationRuleSpec,
) -> bool:
    if (
        left.selector_kind is HostPublicationSelectorKind.ANY
        or right.selector_kind is HostPublicationSelectorKind.ANY
    ):
        return True
    if left.selector_kind is right.selector_kind:
        return left.selector_value == right.selector_value
    # One exact host IPv4 and one ingress-interface selector can both match a
    # packet to that local IPv4 arriving through the selected interface.
    return True


def _rule_sort_key(rule: HostPublicationRuleSpec) -> tuple[object, ...]:
    value = (
        ""
        if rule.selector_value is None
        else str(rule.selector_value)
    )
    return (
        rule.protocol.value,
        rule.host_port,
        rule.selector_kind.value,
        value,
        int(rule.internal_address),
        rule.internal_port,
    )
