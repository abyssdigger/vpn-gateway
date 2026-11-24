from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from .domain import DeviceBindingIntent, ExpectedInterfaceSelector
from .interface_identity import InterfaceIdentity

LOG_TAG = "BIND"


class BindingProjectionError(ValueError):
    pass


@dataclass(frozen=True, order=True, slots=True)
class LogicalPathId:
    device_id: str
    selector_index: int
    slot_index: int


@dataclass(frozen=True, slots=True)
class SelectorBindingState:
    selector: ExpectedInterfaceSelector
    slots: tuple[InterfaceIdentity | None, ...]
    waiting: tuple[InterfaceIdentity, ...] = ()

    def __post_init__(self) -> None:
        if len(self.slots) != self.selector.quota:
            raise ValueError("slot count must equal selector quota")


@dataclass(frozen=True, slots=True)
class DeviceBindingState:
    selectors: Mapping[tuple[str, int], SelectorBindingState]

    def __post_init__(self) -> None:
        object.__setattr__(self, "selectors", MappingProxyType(dict(self.selectors)))

    @classmethod
    def empty(cls) -> "DeviceBindingState":
        return cls({})


@dataclass(frozen=True, slots=True)
class PathBinding:
    path_id: LogicalPathId
    endpoint: InterfaceIdentity


@dataclass(frozen=True, slots=True)
class WaitingCandidate:
    device_id: str
    selector_index: int
    endpoint: InterfaceIdentity


@dataclass(frozen=True, slots=True)
class DeviceBindingProjection:
    next_state: DeviceBindingState
    bindings: tuple[PathBinding, ...]
    waiting: tuple[WaitingCandidate, ...]


def project_device_bindings(
    intents: Iterable[DeviceBindingIntent],
    previous: DeviceBindingState,
    interfaces: Iterable[InterfaceIdentity],
) -> DeviceBindingProjection:
    """Project stable logical slots from one fresh ordered interface inventory.

    `previous` must be the last committed/verified projection. Slots freed by an
    endpoint disappearance in this pass are deliberately not reused until a later
    reconciliation after this proposed state has itself been committed.
    """
    ordered_intents = tuple(intents)
    observed = tuple(interfaces)
    _validate_inputs(ordered_intents, observed)

    next_states: dict[tuple[str, int], SelectorBindingState] = {}
    bindings: list[PathBinding] = []
    waiting_output: list[WaitingCandidate] = []

    for intent in ordered_intents:
        for selector_index, selector in enumerate(intent.expected_interfaces):
            key = (intent.device_id, selector_index)
            old = previous.selectors.get(key)
            if old is None or old.selector != selector:
                old_slots = (None,) * selector.quota
                old_waiting: tuple[InterfaceIdentity, ...] = ()
            else:
                old_slots = old.slots
                old_waiting = old.waiting

            matching = tuple(
                identity
                for identity in observed
                if selector.matches_name(identity.ifname)
            )
            matching_set = set(matching)

            slots: list[InterfaceIdentity | None] = []
            retained: set[InterfaceIdentity] = set()
            for endpoint in old_slots:
                if endpoint is not None and endpoint in matching_set:
                    slots.append(endpoint)
                    retained.add(endpoint)
                else:
                    slots.append(None)

            waiting: list[InterfaceIdentity] = []
            seen = set(retained)
            for endpoint in old_waiting:
                if endpoint in matching_set and endpoint not in seen:
                    waiting.append(endpoint)
                    seen.add(endpoint)
            for endpoint in matching:
                if endpoint not in seen:
                    waiting.append(endpoint)
                    seen.add(endpoint)

            committed_free_slots = [
                index
                for index, endpoint in enumerate(old_slots)
                if endpoint is None
            ]
            for slot_index in committed_free_slots:
                if not waiting:
                    break
                endpoint = waiting.pop(0)
                slots[slot_index] = endpoint
                retained.add(endpoint)

            state = SelectorBindingState(
                selector=selector,
                slots=tuple(slots),
                waiting=tuple(waiting),
            )
            next_states[key] = state

            for slot_index, endpoint in enumerate(state.slots):
                if endpoint is None:
                    continue
                bindings.append(
                    PathBinding(
                        path_id=LogicalPathId(
                            device_id=intent.device_id,
                            selector_index=selector_index,
                            slot_index=slot_index,
                        ),
                        endpoint=endpoint,
                    )
                )
            waiting_output.extend(
                WaitingCandidate(
                    device_id=intent.device_id,
                    selector_index=selector_index,
                    endpoint=endpoint,
                )
                for endpoint in state.waiting
            )

    return DeviceBindingProjection(
        next_state=DeviceBindingState(next_states),
        bindings=tuple(bindings),
        waiting=tuple(waiting_output),
    )


def _validate_inputs(
    intents: tuple[DeviceBindingIntent, ...],
    observed: tuple[InterfaceIdentity, ...],
) -> None:
    device_ids: set[str] = set()
    selectors: list[tuple[str, int, ExpectedInterfaceSelector]] = []
    for intent in intents:
        if intent.device_id in device_ids:
            raise BindingProjectionError(
                f"duplicate DeviceBindingIntent for {intent.device_id!r}"
            )
        device_ids.add(intent.device_id)
        for index, selector in enumerate(intent.expected_interfaces):
            selectors.append((intent.device_id, index, selector))

    identities: set[InterfaceIdentity] = set()
    ifnames: dict[str, int] = {}
    ifindices: dict[int, str] = {}
    for identity in observed:
        if identity in identities:
            raise BindingProjectionError(
                f"duplicate interface identity {identity!r}"
            )
        identities.add(identity)
        previous_ifindex = ifnames.get(identity.ifname)
        if previous_ifindex is not None and previous_ifindex != identity.ifindex:
            raise BindingProjectionError(
                f"interface inventory repeats ifname {identity.ifname!r}"
            )
        previous_ifname = ifindices.get(identity.ifindex)
        if previous_ifname is not None and previous_ifname != identity.ifname:
            raise BindingProjectionError(
                f"interface inventory repeats ifindex {identity.ifindex}"
            )
        ifnames[identity.ifname] = identity.ifindex
        ifindices[identity.ifindex] = identity.ifname

        matches = [
            (device_id, selector_index)
            for device_id, selector_index, selector in selectors
            if selector.matches_name(identity.ifname)
        ]
        if len(matches) > 1:
            raise BindingProjectionError(
                f"interface {identity.ifname!r} matches multiple active selectors: "
                f"{matches!r}"
            )
