from __future__ import annotations

from dataclasses import dataclass
import logging
from types import MappingProxyType
from typing import Iterable, Mapping

from .domain import ActiveConfig, Availability


LOG = logging.getLogger(__name__)


@dataclass(frozen=True, order=True)
class InterfaceIdentity:
    ifname: str
    ifindex: int


@dataclass(frozen=True)
class EnvironmentInterface:
    identity: InterfaceIdentity


@dataclass(frozen=True)
class BoundInterface:
    device_name: str
    expected_index: int
    identity: InterfaceIdentity
    availability: Availability = Availability.UNKNOWN


@dataclass(frozen=True)
class ExpectedBindingState:
    device_name: str
    expected_index: int
    candidate_order: tuple[InterfaceIdentity, ...]


@dataclass(frozen=True)
class DeviceBindingState:
    expectations: Mapping[tuple[str, int], ExpectedBindingState]

    def __post_init__(self) -> None:
        object.__setattr__(self, "expectations", MappingProxyType(dict(self.expectations)))

    @classmethod
    def empty(cls) -> "DeviceBindingState":
        return cls({})


@dataclass(frozen=True)
class DeviceBindingSnapshot:
    bound: tuple[BoundInterface, ...]
    over_quota: tuple[BoundInterface, ...]

    @property
    def by_device(self) -> Mapping[str, tuple[BoundInterface, ...]]:
        grouped: dict[str, list[BoundInterface]] = {}
        for item in self.bound:
            grouped.setdefault(item.device_name, []).append(item)
        return MappingProxyType({name: tuple(items) for name, items in grouped.items()})


@dataclass(frozen=True)
class DeviceReconcileResult:
    next_state: DeviceBindingState
    snapshot: DeviceBindingSnapshot



def binding_snapshot_from_state(
    config: ActiveConfig,
    state: DeviceBindingState,
    availability: Mapping[InterfaceIdentity, Availability] | None = None,
) -> DeviceBindingSnapshot:
    """Reconstruct the previously committed binding snapshot.

    Candidate history is committed only after complete verification. Reconstructing the
    previous bound/over-quota split lets Planner prove whether observed policy is the old
    verified generation during an ordinary interface lifecycle transition.

    Availability is not persisted in schema version 1 because the production trigger is
    deliberately deferred; callers may inject explicit historical availability later when
    DeviceManager owns that state.
    """

    availability = availability or {}
    active_devices = config.active_device_names
    bound: list[BoundInterface] = []
    over_quota: list[BoundInterface] = []

    for device_name, device in config.devices.items():
        if device_name not in active_devices:
            continue
        for expected_index, expected in enumerate(device.expected_interfaces):
            previous = state.expectations.get((device_name, expected_index))
            if previous is None:
                continue

            candidates = [
                identity
                for identity in previous.candidate_order
                if expected.match.matches(identity.ifname)
            ]
            for position, identity in enumerate(candidates):
                item = BoundInterface(
                    device_name=device_name,
                    expected_index=expected_index,
                    identity=identity,
                    availability=availability.get(
                        identity,
                        Availability.UNKNOWN,
                    ),
                )
                if position < expected.interface_quota:
                    bound.append(item)
                else:
                    over_quota.append(item)

    return DeviceBindingSnapshot(tuple(bound), tuple(over_quota))


def reconcile_devices(
    config: ActiveConfig,
    previous: DeviceBindingState,
    interfaces: Iterable[EnvironmentInterface],
    availability: Mapping[InterfaceIdentity, Availability] | None = None,
) -> DeviceReconcileResult:
    """Project DeviceEngine binding state from one fresh ordered environment snapshot.

    Existing candidates that are still present keep their historical order. Newly
    observed candidates append in the supplied kernel-snapshot order. Bound members are
    the first N candidates for an ExpectedInterface; excess candidates remain observable
    but do not become TrafficEngine inputs.

    This function is deliberately mutation-free. The caller owns the
    observe/apply/fresh-observe/verify/commit boundary.
    """

    availability = availability or {}
    observed = tuple(interfaces)
    LOG.debug(
        "device-reconcile-start observed=%s previous_expectations=%d active_devices=%s",
        [(item.identity.ifname, item.identity.ifindex) for item in observed],
        len(previous.expectations),
        sorted(config.active_device_names),
    )
    present = {item.identity for item in observed}
    active_devices = config.active_device_names

    next_expectations: dict[tuple[str, int], ExpectedBindingState] = {}
    bound: list[BoundInterface] = []
    over_quota: list[BoundInterface] = []

    for device_name, device in config.devices.items():
        if device_name not in active_devices:
            continue

        for expected_index, expected in enumerate(device.expected_interfaces):
            key = (device_name, expected_index)
            old = previous.expectations.get(key)
            candidates: list[InterfaceIdentity] = []
            seen: set[InterfaceIdentity] = set()

            if old is not None:
                for identity in old.candidate_order:
                    if identity in present and expected.match.matches(identity.ifname):
                        candidates.append(identity)
                        seen.add(identity)

            for item in observed:
                identity = item.identity
                if identity not in seen and expected.match.matches(identity.ifname):
                    candidates.append(identity)
                    seen.add(identity)

            state = ExpectedBindingState(device_name, expected_index, tuple(candidates))
            next_expectations[key] = state
            LOG.debug(
                "device-selector-projection device=%s expected_index=%d quota=%d candidates=%s",
                device_name,
                expected_index,
                expected.interface_quota,
                [(item.ifname, item.ifindex) for item in candidates],
            )

            for position, identity in enumerate(candidates):
                item = BoundInterface(
                    device_name=device_name,
                    expected_index=expected_index,
                    identity=identity,
                    availability=availability.get(identity, Availability.UNKNOWN),
                )
                if position < expected.interface_quota:
                    bound.append(item)
                else:
                    over_quota.append(item)

    result = DeviceReconcileResult(
        next_state=DeviceBindingState(next_expectations),
        snapshot=DeviceBindingSnapshot(tuple(bound), tuple(over_quota)),
    )
    LOG.debug(
        "device-reconcile-result bound=%s over_quota=%s",
        [
            (
                item.device_name,
                item.expected_index,
                item.identity.ifname,
                item.identity.ifindex,
                item.availability.value,
            )
            for item in result.snapshot.bound
        ],
        [
            (
                item.device_name,
                item.expected_index,
                item.identity.ifname,
                item.identity.ifindex,
            )
            for item in result.snapshot.over_quota
        ],
    )
    return result
