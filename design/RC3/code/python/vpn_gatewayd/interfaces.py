from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from ipaddress import IPv4Address


_EXACT_INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,14}$")
_PREFIX_INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,13}$")
_FORBIDDEN_EXACT_INTERFACES = frozenset({"lo", "any", "default", "all"})


class InterfaceSelectorKind(Enum):
    EXACT = auto()
    PREFIX_FAMILY = auto()


@dataclass(slots=True, frozen=True)
class InterfaceSelector:
    """Validated interface selector from configuration."""

    kind: InterfaceSelectorKind
    value: str

    def __post_init__(self) -> None:
        if self.kind is InterfaceSelectorKind.EXACT:
            if not _EXACT_INTERFACE_RE.fullmatch(self.value):
                raise ValueError(
                    "exact interface selector must match "
                    "[A-Za-z][A-Za-z0-9_.-]{0,14}"
                )
            if self.value.casefold() in _FORBIDDEN_EXACT_INTERFACES:
                raise ValueError(
                    f"forbidden exact interface selector: {self.value!r}"
                )
            return

        if self.kind is InterfaceSelectorKind.PREFIX_FAMILY:
            if not _PREFIX_INTERFACE_RE.fullmatch(self.value):
                raise ValueError(
                    "prefix interface selector must have a 1..14 character "
                    "prefix matching [A-Za-z][A-Za-z0-9_.-]*"
                )
            return

        raise ValueError(f"unknown interface selector kind: {self.kind!r}")

    @classmethod
    def parse(cls, text: str) -> InterfaceSelector:
        if not isinstance(text, str):
            raise TypeError("interface selector must be a string")
        if text.endswith("+"):
            return cls(InterfaceSelectorKind.PREFIX_FAMILY, text[:-1])
        return cls(InterfaceSelectorKind.EXACT, text)

    def __str__(self) -> str:
        if self.kind is InterfaceSelectorKind.PREFIX_FAMILY:
            return f"{self.value}+"
        return self.value

    def matches(self, interface_name: str) -> bool:
        if self.kind is InterfaceSelectorKind.EXACT:
            return interface_name == self.value
        return interface_name.startswith(self.value)

    def overlaps(self, other: InterfaceSelector) -> bool:
        """Return whether both selectors can match at least one same ifname."""
        if self.kind is InterfaceSelectorKind.EXACT:
            return other.matches(self.value)
        if other.kind is InterfaceSelectorKind.EXACT:
            return self.matches(other.value)
        return self.value.startswith(other.value) or other.value.startswith(
            self.value
        )


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
    def from_record(cls, record: InterfaceRecord) -> InterfaceBinding:
        return cls(record.name, record.ifindex)


class InterfaceResolutionState(Enum):
    ABSENT = auto()
    BOUND = auto()
    AMBIGUOUS = auto()


@dataclass(slots=True, frozen=True)
class InterfaceResolution:
    state: InterfaceResolutionState
    matches: tuple[InterfaceRecord, ...]

    def __post_init__(self) -> None:
        count = len(self.matches)
        if self.state is InterfaceResolutionState.ABSENT and count != 0:
            raise ValueError("ABSENT resolution must have no matches")
        if self.state is InterfaceResolutionState.BOUND and count != 1:
            raise ValueError("BOUND resolution must have exactly one match")
        if self.state is InterfaceResolutionState.AMBIGUOUS and count < 2:
            raise ValueError("AMBIGUOUS resolution must have at least two matches")

    @classmethod
    def absent(cls) -> InterfaceResolution:
        return cls(InterfaceResolutionState.ABSENT, ())

    @classmethod
    def bound(cls, record: InterfaceRecord) -> InterfaceResolution:
        return cls(InterfaceResolutionState.BOUND, (record,))

    @classmethod
    def ambiguous(
        cls,
        matches: tuple[InterfaceRecord, ...],
    ) -> InterfaceResolution:
        return cls(InterfaceResolutionState.AMBIGUOUS, matches)

    @property
    def binding(self) -> InterfaceBinding | None:
        if self.state is not InterfaceResolutionState.BOUND:
            return None
        return InterfaceBinding.from_record(self.matches[0])

    @property
    def bound_record(self) -> InterfaceRecord | None:
        if self.state is not InterfaceResolutionState.BOUND:
            return None
        return self.matches[0]


def resolve_interface_selector(
    selector: InterfaceSelector,
    records: tuple[InterfaceRecord, ...] | list[InterfaceRecord],
) -> InterfaceResolution:
    """Resolve one selector against one immutable interface inventory."""
    matches = tuple(
        sorted(
            (record for record in records if selector.matches(record.name)),
            key=lambda record: (record.name, record.ifindex),
        )
    )
    if not matches:
        return InterfaceResolution.absent()
    if len(matches) == 1:
        return InterfaceResolution.bound(matches[0])
    return InterfaceResolution.ambiguous(matches)


def interface_resolution_ready(
    resolution: InterfaceResolution,
    expected_local_address: IPv4Address,
) -> bool:
    """Readiness is unique binding plus expected local IPv4 presence."""
    record = resolution.bound_record
    return record is not None and expected_local_address in record.ipv4


@dataclass(slots=True, frozen=True)
class ProfileInterfaceState:
    resolution: InterfaceResolution
    ready: bool

    def __post_init__(self) -> None:
        if (
            self.ready
            and self.resolution.state is not InterfaceResolutionState.BOUND
        ):
            raise ValueError(
                "ready profile interface state requires BOUND resolution"
            )

    @property
    def binding(self) -> InterfaceBinding | None:
        return self.resolution.binding


def resolve_profile_interface_state(
    selector: InterfaceSelector,
    records: tuple[InterfaceRecord, ...] | list[InterfaceRecord],
    expected_local_address: IPv4Address,
) -> ProfileInterfaceState:
    resolution = resolve_interface_selector(selector, records)
    return ProfileInterfaceState(
        resolution=resolution,
        ready=interface_resolution_ready(
            resolution,
            expected_local_address,
        ),
    )
