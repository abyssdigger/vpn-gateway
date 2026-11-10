from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from ipaddress import IPv4Address, IPv4Network
from types import MappingProxyType
from typing import Mapping, Sequence

_EXACT_INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,14}$")
_PREFIX_INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,13}$")
_FORBIDDEN_EXACT_INTERFACES = frozenset({"lo", "any", "default", "all"})


class InterfaceSelectorKind(Enum):
    EXACT = auto()
    PREFIX = auto()


@dataclass(slots=True, frozen=True)
class InterfaceSelector:
    """Validated exact or textual-prefix interface selector."""

    kind: InterfaceSelectorKind
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        values = tuple(self.values)
        object.__setattr__(self, "values", values)
        if len(values) != 1:
            raise ValueError("interface selector requires exactly one value")

        value = values[0]
        if self.kind is InterfaceSelectorKind.PREFIX:
            if not _PREFIX_INTERFACE_RE.fullmatch(value):
                raise ValueError(
                    "prefix interface selector must have a 1..14 character "
                    "prefix matching [A-Za-z][A-Za-z0-9_.-]*"
                )
            return
        if self.kind is not InterfaceSelectorKind.EXACT:
            raise ValueError(f"unknown interface selector kind: {self.kind!r}")
        if not _EXACT_INTERFACE_RE.fullmatch(value):
            raise ValueError(
                "exact interface name must match "
                "[A-Za-z][A-Za-z0-9_.-]{0,14}"
            )
        if value.casefold() in _FORBIDDEN_EXACT_INTERFACES:
            raise ValueError(f"forbidden exact interface name: {value!r}")

    @classmethod
    def parse(cls, value: object) -> "InterfaceSelector":
        if not isinstance(value, str):
            raise TypeError("interface selector must be a string")
        if value.endswith("+"):
            return cls(InterfaceSelectorKind.PREFIX, (value[:-1],))
        return cls(InterfaceSelectorKind.EXACT, (value,))

    @property
    def value(self) -> str:
        return self.values[0]

    def __str__(self) -> str:
        if self.kind is InterfaceSelectorKind.PREFIX:
            return f"{self.value}+"
        return self.value

    def matches(self, interface_name: str) -> bool:
        if self.kind is InterfaceSelectorKind.PREFIX:
            return interface_name.startswith(self.value)
        return interface_name == self.value

    def guard_interface(self) -> str:
        if self.kind is InterfaceSelectorKind.PREFIX:
            return f"{self.value}+"
        return self.value

    def guard_interfaces(self) -> tuple[str, ...]:
        return (self.guard_interface(),)

    def overlaps(self, other: "InterfaceSelector") -> bool:
        if self.kind is InterfaceSelectorKind.PREFIX:
            if other.kind is InterfaceSelectorKind.PREFIX:
                return (
                    self.value.startswith(other.value)
                    or other.value.startswith(self.value)
                )
            return other.value.startswith(self.value)
        if other.kind is InterfaceSelectorKind.PREFIX:
            return self.value.startswith(other.value)
        return self.value == other.value


@dataclass(slots=True, frozen=True)
class BindingSpec:
    interface: InterfaceSelector
    network: IPv4Network
    config_index: int
    exact_rank: int | None

    def __post_init__(self) -> None:
        if self.config_index < 0:
            raise ValueError("binding config_index must be non-negative")
        if self.interface.kind is InterfaceSelectorKind.EXACT:
            if self.exact_rank is None or self.exact_rank < 0:
                raise ValueError("exact BindingSpec requires non-negative exact_rank")
        elif self.exact_rank is not None:
            raise ValueError("prefix BindingSpec must not have exact_rank")


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
    exact_bindings: tuple[InterfaceBinding, ...] = ()
    prefix_bindings: tuple[InterfaceBinding, ...] = ()
    owner_index_by_binding: Mapping[InterfaceBinding, int] = MappingProxyType({})

    def __post_init__(self) -> None:
        candidates = tuple(self.candidates)
        active = tuple(self.active_bindings)
        exact = tuple(self.exact_bindings)
        prefix = tuple(self.prefix_bindings)
        owners = dict(self.owner_index_by_binding)
        if active != exact + prefix:
            raise ValueError("active_bindings must equal exact_bindings + prefix_bindings")
        if len(set(active)) != len(active):
            raise ValueError("active bindings contain duplicates")
        if set(owners) != set(active):
            raise ValueError("owner mapping must match active bindings exactly")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "active_bindings", active)
        object.__setattr__(self, "exact_bindings", exact)
        object.__setattr__(self, "prefix_bindings", prefix)
        object.__setattr__(self, "owner_index_by_binding", MappingProxyType(owners))


def _index_records(
    records: Sequence[InterfaceRecord],
) -> tuple[dict[str, InterfaceRecord], tuple[InterfaceRecord, ...]]:
    by_name: dict[str, InterfaceRecord] = {}
    ordered: list[InterfaceRecord] = []
    for record in records:
        previous = by_name.get(record.name)
        if previous is not None:
            if previous.ifindex != record.ifindex:
                raise ValueError(
                    "duplicate interface name with conflicting ifindex: "
                    f"{record.name!r} has {previous.ifindex} and {record.ifindex}"
                )
            continue
        by_name[record.name] = record
        ordered.append(record)
    return by_name, tuple(ordered)


def resolve_profile_interface_state(
    specs: Sequence[BindingSpec],
    records: Sequence[InterfaceRecord],
    previous_prefix_active_bindings: Sequence[InterfaceBinding] = (),
) -> ProfileInterfaceState:
    specs = tuple(specs)
    by_name, inventory = _index_records(records)

    matched_owner: dict[str, int] = {}
    candidates_by_name: dict[str, InterfaceRecord] = {}
    exact_active: list[InterfaceBinding] = []
    owner_by_binding: dict[InterfaceBinding, int] = {}

    for spec in specs:
        if spec.interface.kind is not InterfaceSelectorKind.EXACT:
            continue
        record = by_name.get(spec.interface.value)
        if record is None:
            continue
        matched_owner[record.name] = spec.config_index
        candidates_by_name[record.name] = record
        if any(address in spec.network for address in record.ipv4):
            binding = InterfaceBinding.from_record(record)
            exact_active.append(binding)
            owner_by_binding[binding] = spec.config_index

    current_prefix: list[InterfaceBinding] = []
    current_prefix_owner: dict[InterfaceBinding, int] = {}
    for record in inventory:
        owner: BindingSpec | None = None
        for spec in specs:
            if (
                spec.interface.kind is InterfaceSelectorKind.PREFIX
                and spec.interface.matches(record.name)
            ):
                if owner is not None:
                    raise ValueError(
                        f"interface {record.name!r} matches multiple BindingSpec selectors"
                    )
                owner = spec
        if owner is None:
            continue
        if record.name in matched_owner:
            raise ValueError(
                f"interface {record.name!r} matches multiple BindingSpec selectors"
            )
        matched_owner[record.name] = owner.config_index
        candidates_by_name[record.name] = record
        if any(address in owner.network for address in record.ipv4):
            binding = InterfaceBinding.from_record(record)
            current_prefix.append(binding)
            current_prefix_owner[binding] = owner.config_index

    previous = tuple(previous_prefix_active_bindings)
    if len(set(previous)) != len(previous):
        raise ValueError("previous prefix active bindings contain duplicates")
    current_set = set(current_prefix)
    survivors = tuple(binding for binding in previous if binding in current_set)
    survivor_set = set(survivors)
    new_bindings = tuple(
        binding for binding in current_prefix if binding not in survivor_set
    )
    prefix_active = survivors + new_bindings

    for binding in prefix_active:
        owner_by_binding[binding] = current_prefix_owner[binding]

    exact_candidates = [
        candidates_by_name[spec.interface.value]
        for spec in specs
        if (
            spec.interface.kind is InterfaceSelectorKind.EXACT
            and spec.interface.value in candidates_by_name
        )
    ]
    exact_candidate_names = {record.name for record in exact_candidates}
    prefix_candidates = [
        record for record in inventory
        if record.name in candidates_by_name
        and record.name not in exact_candidate_names
    ]

    return ProfileInterfaceState(
        candidates=tuple(exact_candidates + prefix_candidates),
        active_bindings=tuple(exact_active) + prefix_active,
        exact_bindings=tuple(exact_active),
        prefix_bindings=prefix_active,
        owner_index_by_binding=owner_by_binding,
    )
