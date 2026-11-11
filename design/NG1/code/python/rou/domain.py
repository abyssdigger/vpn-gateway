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
