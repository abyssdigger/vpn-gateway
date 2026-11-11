from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Network
from types import MappingProxyType
from typing import Mapping


class Direction(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BIDIRECTIONAL = "bidirectional"


class MatchKind(str, Enum):
    EXACT = "exact"
    PREFIX = "prefix"


class Availability(str, Enum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class NatMode(str, Enum):
    NONE = "none"
    MASQUERADE = "masquerade"


class TransportProtocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"


class EnvelopeDirection(str, Enum):
    FROM_DEVICE = "from-device"
    TO_DEVICE = "to-device"


class EnvelopeAction(str, Enum):
    ALLOW = "allow"
    DROP = "drop"


class EnvelopeProtocol(str, Enum):
    ANY = "any"
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"


@dataclass(frozen=True, order=True)
class PortRange:
    start: int
    end: int

    def __post_init__(self) -> None:
        if not 1 <= self.start <= 65535:
            raise ValueError("port range start must be 1..65535")
        if not 1 <= self.end <= 65535:
            raise ValueError("port range end must be 1..65535")
        if self.start > self.end:
            raise ValueError("port range start must not exceed end")

    @property
    def size(self) -> int:
        return self.end - self.start + 1

    def overlaps(self, other: "PortRange") -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass(frozen=True)
class Publication:
    protocol: TransportProtocol
    external: PortRange
    internal: PortRange

    def __post_init__(self) -> None:
        if self.external.size != self.internal.size:
            raise ValueError(
                "publication external/internal ranges must have equal cardinality"
            )


@dataclass(frozen=True)
class TrafficEnvelopeRule:
    direction: EnvelopeDirection
    action: EnvelopeAction
    source: IPv4Network | None = None
    destination: IPv4Network | None = None
    protocol: EnvelopeProtocol = EnvelopeProtocol.ANY
    source_ports: tuple[PortRange, ...] = ()
    destination_ports: tuple[PortRange, ...] = ()

    def __post_init__(self) -> None:
        if (
            self.source_ports or self.destination_ports
        ) and self.protocol not in {
            EnvelopeProtocol.TCP,
            EnvelopeProtocol.UDP,
        }:
            raise ValueError(
                "traffic-envelope ports require tcp or udp protocol"
            )


@dataclass(frozen=True)
class TrafficEnvelope:
    default_action: EnvelopeAction
    rules: tuple[TrafficEnvelopeRule, ...] = ()


@dataclass(frozen=True)
class InterfaceMatch:
    kind: MatchKind
    value: str

    def matches(self, ifname: str) -> bool:
        if self.kind is MatchKind.EXACT:
            return ifname == self.value
        return ifname.startswith(self.value)

    def overlaps(self, other: "InterfaceMatch") -> bool:
        if self.kind is MatchKind.EXACT and other.kind is MatchKind.EXACT:
            return self.value == other.value
        if self.kind is MatchKind.EXACT:
            return self.value.startswith(other.value)
        if other.kind is MatchKind.EXACT:
            return other.value.startswith(self.value)
        return self.value.startswith(other.value) or other.value.startswith(self.value)


@dataclass(frozen=True)
class ExpectedInterface:
    match: InterfaceMatch
    interface_quota: int


@dataclass(frozen=True)
class Device:
    name: str
    enabled: bool
    expected_interfaces: tuple[ExpectedInterface, ...] = ()
    nat: NatMode | None = None
    publications: tuple[Publication, ...] = ()
    traffic_envelope: TrafficEnvelope | None = None

    def __post_init__(self) -> None:
        if self.enabled and self.nat is None:
            raise ValueError("enabled Device requires explicit NatMode")

    @property
    def interface_quota(self) -> int:
        return sum(item.interface_quota for item in self.expected_interfaces)


@dataclass(frozen=True)
class Profile:
    name: str
    enabled: bool
    direction: Direction | None = None
    destinations: tuple[IPv4Network, ...] = ()
    device_order: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActiveConfig:
    devices: Mapping[str, Device]
    profiles: Mapping[str, Profile]

    def __post_init__(self) -> None:
        object.__setattr__(self, "devices", MappingProxyType(dict(self.devices)))
        object.__setattr__(self, "profiles", MappingProxyType(dict(self.profiles)))

    @property
    def active_device_names(self) -> frozenset[str]:
        names: set[str] = set()
        for profile in self.profiles.values():
            if not profile.enabled:
                continue
            for name in profile.device_order:
                device = self.devices[name]
                if device.enabled:
                    names.add(name)
        return frozenset(names)
