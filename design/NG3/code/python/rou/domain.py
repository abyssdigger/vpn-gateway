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


class SelectorKind(str, Enum):
    EXACT = "exact"
    PREFIX = "prefix"


@dataclass(frozen=True, slots=True)
class ExpectedInterfaceSelector:
    kind: SelectorKind
    value: str
    quota: int

    def matches_name(self, ifname: str) -> bool:
        if self.kind is SelectorKind.EXACT:
            return ifname == self.value
        return ifname.startswith(self.value)

    def overlaps(self, other: "ExpectedInterfaceSelector") -> bool:
        if self.kind is SelectorKind.EXACT and other.kind is SelectorKind.EXACT:
            return self.value == other.value
        if self.kind is SelectorKind.EXACT:
            return self.value.startswith(other.value)
        if other.kind is SelectorKind.EXACT:
            return other.value.startswith(self.value)
        return self.value.startswith(other.value) or other.value.startswith(self.value)


@dataclass(frozen=True, slots=True)
class DeviceStructuralIntent:
    device_id: str
    enabled: bool
    expected_interfaces: tuple[ExpectedInterfaceSelector, ...] = ()

    @property
    def path_capacity(self) -> int:
        return sum(selector.quota for selector in self.expected_interfaces)


@dataclass(frozen=True, slots=True)
class ProfileStructuralIntent:
    profile_id: str
    enabled: bool
    direction: Direction | None = None
    destinations: tuple[IPv4Network, ...] = ()
    device_order: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DeviceBindingIntent:
    device_id: str
    expected_interfaces: tuple[ExpectedInterfaceSelector, ...]


@dataclass(frozen=True, slots=True)
class StructuralConfig:
    devices: Mapping[str, DeviceStructuralIntent]
    profiles: Mapping[str, ProfileStructuralIntent]
    active_device_ids: frozenset[str]
    device_binding_intents: tuple[DeviceBindingIntent, ...]

    @classmethod
    def build(
        cls,
        *,
        devices: dict[str, DeviceStructuralIntent],
        profiles: dict[str, ProfileStructuralIntent],
        active_device_ids: frozenset[str],
    ) -> "StructuralConfig":
        bindings = tuple(
            DeviceBindingIntent(
                device_id=device_id,
                expected_interfaces=devices[device_id].expected_interfaces,
            )
            for device_id in sorted(active_device_ids)
        )
        return cls(
            devices=MappingProxyType(dict(devices)),
            profiles=MappingProxyType(dict(profiles)),
            active_device_ids=active_device_ids,
            device_binding_intents=bindings,
        )
