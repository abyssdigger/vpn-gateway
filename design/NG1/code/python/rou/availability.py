from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Mapping, Protocol

from .command_backend import CommandBackend
from .device_engine import DeviceBindingSnapshot, InterfaceIdentity
from .domain import Availability
from .environment import EnvironmentSnapshot


class AvailabilityCollector(Protocol):
    """Collect normalized availability for already-selected concrete bindings.

    DeviceEngine remains the sole owner of binding selection, historical candidate order
    and quota. A collector may perform active/protocol-specific observation, but it may
    classify only identities presented in `bindings`.

    The collector boundary is deliberately richer than a pure EnvironmentSnapshot
    function because EXP-019/020 proved that useful liveness evidence may require active
    path probes that are not present in the kernel snapshot.

    Schema-v1 production does not instantiate a collector yet. DeviceManager must define
    reviewed probe target/cadence/threshold semantics before this boundary becomes active.
    """

    def __call__(
        self,
        namespace: str,
        host_backend: CommandBackend,
        environment: EnvironmentSnapshot,
        bindings: DeviceBindingSnapshot,
    ) -> Mapping[InterfaceIdentity, Availability]:
        ...


def normalize_availability(
    bindings: DeviceBindingSnapshot,
    values: Mapping[InterfaceIdentity, Availability],
) -> Mapping[InterfaceIdentity, Availability]:
    """Validate one collector result against the concrete binding generation.

    Unknown identities are rejected rather than ignored. This prevents a stale probe result
    for a retired same-name generation from being silently applied to a fresh interface.
    """

    allowed = {
        item.identity
        for item in (*bindings.bound, *bindings.over_quota)
    }
    normalized: dict[InterfaceIdentity, Availability] = {}
    for identity, availability in values.items():
        if identity not in allowed:
            raise ValueError(
                "availability result references non-current binding identity "
                f"{identity.ifname}@{identity.ifindex}"
            )
        if not isinstance(availability, Availability):
            raise TypeError(
                "availability result must use normalized Availability enum"
            )
        normalized[identity] = availability
    return MappingProxyType(normalized)


def annotate_bindings(
    bindings: DeviceBindingSnapshot,
    values: Mapping[InterfaceIdentity, Availability],
) -> DeviceBindingSnapshot:
    """Return the same binding generations/order with normalized availability attached."""

    normalized = normalize_availability(bindings, values)

    def annotate(items):
        return tuple(
            replace(
                item,
                availability=normalized.get(
                    item.identity,
                    Availability.UNKNOWN,
                ),
            )
            for item in items
        )

    return DeviceBindingSnapshot(
        bound=annotate(bindings.bound),
        over_quota=annotate(bindings.over_quota),
    )
