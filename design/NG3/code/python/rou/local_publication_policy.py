"""Normalized publication-local intent and exact lower desired rule projection."""

from __future__ import annotations

from dataclasses import dataclass
from .ip_port import IP_PORT_MAX, IP_PORT_MIN, is_ip_port
from enum import Enum
from ipaddress import IPv4Address
from typing import Iterable

from .interface_identity import InterfaceIdentity


class PublicationProtocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"


class LocalPublicationHook(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


@dataclass(frozen=True, slots=True)
class PublicationLocalEndpointIntent:
    """One normalized internal publication endpoint, not external config spelling."""

    device_id: str
    protocol: PublicationProtocol
    local_address: IPv4Address
    internal_port: int
    host_boundary: InterfaceIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id:
            raise ValueError("device_id must be non-empty text")
        if not isinstance(self.protocol, PublicationProtocol):
            raise ValueError("protocol must be PublicationProtocol")
        if not isinstance(self.local_address, IPv4Address):
            raise ValueError("local_address must be IPv4Address")
        if not is_ip_port(self.internal_port):
            raise ValueError(f"internal_port must be an integer in [{IP_PORT_MIN}, {IP_PORT_MAX}]")
        if not isinstance(self.host_boundary, InterfaceIdentity):
            raise ValueError("host_boundary must be InterfaceIdentity")


@dataclass(frozen=True, order=True, slots=True)
class LocalPublicationRuleSpec:
    hook: LocalPublicationHook
    protocol: PublicationProtocol
    host_boundary: InterfaceIdentity
    local_address: IPv4Address
    local_port: int


@dataclass(frozen=True, slots=True)
class LocalPublicationDesiredState:
    rules: tuple[LocalPublicationRuleSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rules, tuple):
            raise ValueError("rules must be a tuple")
        if not all(isinstance(rule, LocalPublicationRuleSpec) for rule in self.rules):
            raise ValueError("rules must contain LocalPublicationRuleSpec")
        if len(set(self.rules)) != len(self.rules):
            raise ValueError("duplicate desired local publication rule")

        endpoint_hooks: dict[tuple[object, ...], set[LocalPublicationHook]] = {}
        for rule in self.rules:
            key = (
                rule.protocol,
                rule.host_boundary,
                rule.local_address,
                rule.local_port,
            )
            endpoint_hooks.setdefault(key, set()).add(rule.hook)
        required_hooks = {
            LocalPublicationHook.INPUT,
            LocalPublicationHook.OUTPUT,
        }
        if any(hooks != required_hooks for hooks in endpoint_hooks.values()):
            raise ValueError(
                "each desired local publication endpoint must contain INPUT and OUTPUT"
            )

        object.__setattr__(self, "rules", tuple(sorted(self.rules)))


def build_local_publication_desired(
    intents: Iterable[PublicationLocalEndpointIntent],
) -> LocalPublicationDesiredState:
    """Set-union normalized publication contributions with canonical deduplication."""
    rules: set[LocalPublicationRuleSpec] = set()
    for intent in intents:
        if not isinstance(intent, PublicationLocalEndpointIntent):
            raise ValueError("intents must contain PublicationLocalEndpointIntent")
        rules.add(
            LocalPublicationRuleSpec(
                hook=LocalPublicationHook.INPUT,
                protocol=intent.protocol,
                host_boundary=intent.host_boundary,
                local_address=intent.local_address,
                local_port=intent.internal_port,
            )
        )
        rules.add(
            LocalPublicationRuleSpec(
                hook=LocalPublicationHook.OUTPUT,
                protocol=intent.protocol,
                host_boundary=intent.host_boundary,
                local_address=intent.local_address,
                local_port=intent.internal_port,
            )
        )
    return LocalPublicationDesiredState(tuple(rules))
