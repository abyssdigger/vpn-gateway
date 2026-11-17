"""Normalized supported-integration local transport intent and desired nft rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address
from typing import Iterable

from .interface_identity import InterfaceIdentity


class IntegrationTransportProtocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"


class IntegrationLocalHook(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


@dataclass(frozen=True, slots=True)
class IntegrationLocalTransportIntent:
    """One normalized VPN integration transport allowance.

    local_port is optional. When known, both directions are exact on both
    transport ports. When absent, reverse INPUT is limited to conntrack
    established/related traffic from the exact remote endpoint/port.
    """

    integration_id: str
    protocol: IntegrationTransportProtocol
    host_boundary: InterfaceIdentity
    local_address: IPv4Address
    remote_address: IPv4Address
    remote_port: int
    local_port: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.integration_id, str) or not self.integration_id:
            raise ValueError("integration_id must be non-empty text")
        if not isinstance(self.protocol, IntegrationTransportProtocol):
            raise ValueError("protocol must be IntegrationTransportProtocol")
        if not isinstance(self.host_boundary, InterfaceIdentity):
            raise ValueError("host_boundary must be InterfaceIdentity")
        if not isinstance(self.local_address, IPv4Address):
            raise ValueError("local_address must be IPv4Address")
        if not isinstance(self.remote_address, IPv4Address):
            raise ValueError("remote_address must be IPv4Address")
        if type(self.remote_port) is not int or not 1 <= self.remote_port <= 65535:
            raise ValueError("remote_port must be an integer in [1, 65535]")
        if self.local_port is not None and (
            type(self.local_port) is not int or not 1 <= self.local_port <= 65535
        ):
            raise ValueError("local_port must be None or an integer in [1, 65535]")


@dataclass(frozen=True, order=True, slots=True)
class IntegrationLocalRuleSpec:
    hook: IntegrationLocalHook
    protocol: IntegrationTransportProtocol
    host_boundary: InterfaceIdentity
    local_address: IPv4Address
    remote_address: IPv4Address
    remote_port: int
    local_port: int | None


@dataclass(frozen=True, slots=True)
class IntegrationLocalDesiredState:
    rules: tuple[IntegrationLocalRuleSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rules, tuple):
            raise ValueError("rules must be a tuple")
        if not all(isinstance(rule, IntegrationLocalRuleSpec) for rule in self.rules):
            raise ValueError("rules must contain IntegrationLocalRuleSpec")
        if len(set(self.rules)) != len(self.rules):
            raise ValueError("duplicate desired integration-local rule")
        object.__setattr__(
            self,
            "rules",
            tuple(
                sorted(
                    self.rules,
                    key=lambda rule: (
                        rule.hook.value,
                        rule.protocol.value,
                        rule.host_boundary.ifindex,
                        int(rule.local_address),
                        int(rule.remote_address),
                        rule.remote_port,
                        -1 if rule.local_port is None else rule.local_port,
                    ),
                )
            ),
        )


def build_integration_local_desired(
    intents: Iterable[IntegrationLocalTransportIntent],
) -> IntegrationLocalDesiredState:
    """Set-union exact supported-integration local/system contributions."""
    rules: set[IntegrationLocalRuleSpec] = set()
    for intent in intents:
        if not isinstance(intent, IntegrationLocalTransportIntent):
            raise ValueError("intents must contain IntegrationLocalTransportIntent")
        for hook in (IntegrationLocalHook.INPUT, IntegrationLocalHook.OUTPUT):
            rules.add(
                IntegrationLocalRuleSpec(
                    hook=hook,
                    protocol=intent.protocol,
                    host_boundary=intent.host_boundary,
                    local_address=intent.local_address,
                    remote_address=intent.remote_address,
                    remote_port=intent.remote_port,
                    local_port=intent.local_port,
                )
            )
    return IntegrationLocalDesiredState(tuple(rules))
