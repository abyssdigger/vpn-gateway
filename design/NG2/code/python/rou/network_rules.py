from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Network
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


@dataclass(frozen=True, order=True)
class InterfaceRef:
    """Reference to an interface in the network-rules domain.

    ifindex=None denotes a name-stable infrastructure reference.
    ifindex!=None denotes one concrete generation-aware interface identity.
    """

    ifname: str
    ifindex: int | None = None

    def __post_init__(self) -> None:
        if not self.ifname:
            raise NetworkRulesError("interface reference name must be non-empty")
        if len(self.ifname.encode("utf-8")) > 15:
            raise NetworkRulesError("interface reference exceeds Linux IFNAMSIZ-1")
        if self.ifindex is not None and (
            type(self.ifindex) is not int or self.ifindex <= 0
        ):
            raise NetworkRulesError("interface reference ifindex must be positive")

    @classmethod
    def stable(cls, ifname: str) -> "InterfaceRef":
        return cls(ifname)

    @classmethod
    def concrete(cls, identity: InterfaceIdentity) -> "InterfaceRef":
        return cls(identity.ifname, identity.ifindex)


class TerminalAction(str, Enum):
    BLACKHOLE = "blackhole"
    UNREACHABLE = "unreachable"
    PROHIBIT = "prohibit"


@dataclass(frozen=True)
class RoutingDomainSpec:
    name: str
    destinations: tuple[IPv4Network, ...]
    ordered_paths: tuple[InterfaceRef, ...]
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
    ingress: InterfaceRef | None = None
    egress: InterfaceRef | None = None

    def __post_init__(self) -> None:
        if not self.routing_domain:
            raise NetworkRulesError("dispatch routing_domain must be non-empty")
        if self.ingress is None and self.egress is None:
            raise NetworkRulesError(
                "dispatch rule requires ingress and/or egress selector"
            )


@dataclass(frozen=True)
class NetworkRulesSpec:
    routing_domains: tuple[RoutingDomainSpec, ...] = ()
    dispatch_rules: tuple[DispatchRuleSpec, ...] = ()

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


@dataclass(frozen=True, order=True)
class NetworkRulesScope:
    """Ownership/context selector for one Adapter caller.

    Scope is deliberately not part of NetworkRulesSpec.
    """

    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise NetworkRulesError("network rules scope must be non-empty")


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
    def apply(
        self,
        scope: NetworkRulesScope,
        spec: NetworkRulesSpec,
    ) -> ActionResult:
        ...

    def renew_state(self, scope: NetworkRulesScope) -> ActionResult:
        ...

    def get_last_state(self, scope: NetworkRulesScope) -> NetworkRulesState:
        ...
