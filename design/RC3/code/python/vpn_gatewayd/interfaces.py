from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from ipaddress import IPv4Address, IPv4Network
from typing import Sequence

_EXACT_INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,14}$")
_PREFIX_INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,13}$")
_FORBIDDEN_EXACT_INTERFACES = frozenset({"lo", "any", "default", "all"})


class InterfaceSelectorKind(Enum):
    EXACT = auto()
    PREFIX = auto()
    EXACT_LIST = auto()


@dataclass(slots=True, frozen=True)
class InterfaceSelector:
    """Validated interface selector; values preserve normative selector order."""

    kind: InterfaceSelectorKind
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        values = tuple(self.values)
        object.__setattr__(self, "values", values)
        if self.kind in (InterfaceSelectorKind.EXACT, InterfaceSelectorKind.PREFIX):
            if len(values) != 1:
                raise ValueError("exact/prefix selector requires exactly one value")
        elif self.kind is InterfaceSelectorKind.EXACT_LIST:
            if not values:
                raise ValueError("explicit interface list must not be empty")
            if len(set(values)) != len(values):
                raise ValueError("explicit interface list contains duplicates")
        else:
            raise ValueError(f"unknown interface selector kind: {self.kind!r}")

        if self.kind is InterfaceSelectorKind.PREFIX:
            value = values[0]
            if not _PREFIX_INTERFACE_RE.fullmatch(value):
                raise ValueError(
                    "prefix interface selector must have a 1..14 character "
                    "prefix matching [A-Za-z][A-Za-z0-9_.-]*"
                )
            return

        for value in values:
            if not _EXACT_INTERFACE_RE.fullmatch(value):
                raise ValueError(
                    "exact interface name must match "
                    "[A-Za-z][A-Za-z0-9_.-]{0,14}"
                )
            if value.casefold() in _FORBIDDEN_EXACT_INTERFACES:
                raise ValueError(f"forbidden exact interface name: {value!r}")

    @classmethod
    def parse(cls, value: object) -> "InterfaceSelector":
        if isinstance(value, str):
            if value.endswith("+"):
                return cls(InterfaceSelectorKind.PREFIX, (value[:-1],))
            return cls(InterfaceSelectorKind.EXACT, (value,))
        if isinstance(value, list):
            if not all(isinstance(item, str) for item in value):
                raise TypeError("explicit interface list must contain strings")
            return cls(InterfaceSelectorKind.EXACT_LIST, tuple(value))
        raise TypeError("interface selector must be a string or array of strings")

    def __str__(self) -> str:
        if self.kind is InterfaceSelectorKind.PREFIX:
            return f"{self.values[0]}+"
        if self.kind is InterfaceSelectorKind.EXACT:
            return self.values[0]
        return "[" + ", ".join(repr(value) for value in self.values) + "]"

    def matches(self, interface_name: str) -> bool:
        if self.kind is InterfaceSelectorKind.EXACT:
            return interface_name == self.values[0]
        if self.kind is InterfaceSelectorKind.PREFIX:
            return interface_name.startswith(self.values[0])
        return interface_name in self.values

    def guard_interfaces(self) -> tuple[str, ...]:
        if self.kind is InterfaceSelectorKind.PREFIX:
            return (f"{self.values[0]}+",)
        return self.values

    def overlaps(self, other: "InterfaceSelector") -> bool:
        if self.kind is InterfaceSelectorKind.PREFIX:
            if other.kind is InterfaceSelectorKind.PREFIX:
                left, right = self.values[0], other.values[0]
                return left.startswith(right) or right.startswith(left)
            return any(name.startswith(self.values[0]) for name in other.values)
        if other.kind is InterfaceSelectorKind.PREFIX:
            return any(name.startswith(other.values[0]) for name in self.values)
        return bool(set(self.values) & set(other.values))


@dataclass(slots=True, frozen=True)
class InterfaceRecord:
    name: str
    ifindex: int
    ipv4: frozenset[IPv4Address]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("interface name must not be empty")
        if self.ifindex <= 0:
            raise ValueError("ifindex must be positive")
        object.__setattr__(self, "ipv4", frozenset(self.ipv4))


@dataclass(slots=True, frozen=True)
class InterfaceBinding:
    name: str
    ifindex: int

    @classmethod
    def from_record(cls, record: InterfaceRecord) -> "InterfaceBinding":
        return cls(record.name, record.ifindex)


@dataclass(slots=True, frozen=True)
class ProfileInterfaceState:
    candidates: tuple[InterfaceRecord, ...]
    active_bindings: tuple[InterfaceBinding, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "active_bindings", tuple(self.active_bindings))

def _ordered_candidates(
    selector: InterfaceSelector,
    records: Sequence[InterfaceRecord],
) -> tuple[InterfaceRecord, ...]:
    by_name: dict[str, InterfaceRecord] = {}
    for record in records:
        previous = by_name.get(record.name)
        if previous is not None and previous.ifindex != record.ifindex:
            raise ValueError(
                "duplicate interface name with conflicting ifindex: "
                f"{record.name!r} has {previous.ifindex} and {record.ifindex}"
            )
        by_name[record.name] = record

    if selector.kind is InterfaceSelectorKind.EXACT:
        record = by_name.get(selector.values[0])
        return () if record is None else (record,)
    if selector.kind is InterfaceSelectorKind.PREFIX:
        return tuple(
            sorted(
                (r for r in by_name.values() if r.name.startswith(selector.values[0])),
                key=lambda r: r.name,
            )
        )
    return tuple(by_name[name] for name in selector.values if name in by_name)


def resolve_profile_interface_state(
    selector: InterfaceSelector,
    records: Sequence[InterfaceRecord],
    network: IPv4Network,
    previous_active_bindings: Sequence[InterfaceBinding] = (),
) -> ProfileInterfaceState:
    candidates = _ordered_candidates(selector, records)
    current_active = tuple(
        InterfaceBinding.from_record(record)
        for record in candidates
        if any(address in network for address in record.ipv4)
    )

    if selector.kind is InterfaceSelectorKind.PREFIX:
        previous = tuple(previous_active_bindings)
        if len(set(previous)) != len(previous):
            raise ValueError("previous active bindings contain duplicates")

        current_set = set(current_active)
        survivors = tuple(
            binding for binding in previous if binding in current_set
        )
        survivor_set = set(survivors)
        new_bindings = tuple(
            sorted(
                (
                    binding
                    for binding in current_active
                    if binding not in survivor_set
                ),
                key=lambda binding: (binding.name, binding.ifindex),
            )
        )
        active = survivors + new_bindings
    else:
        active = current_active

    return ProfileInterfaceState(candidates=candidates, active_bindings=active)
