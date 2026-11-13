from __future__ import annotations

from dataclasses import dataclass

from .network_rules import NetworkRulesSpec


class OwnerRegistryError(RuntimeError):
    pass


@dataclass
class _OwnerEntry:
    owner: object
    desired: NetworkRulesSpec


class DesiredRulesByOwner:
    """Adapter-internal desired rules indexed strictly by caller identity.

    A strong reference is intentional: while an owner is registered its Python id cannot
    be reused for another object. Explicit Adapter cleanup releases the registration.
    """

    def __init__(self) -> None:
        self._entries: dict[int, _OwnerEntry] = {}

    def replace(self, owner: object, desired: NetworkRulesSpec) -> None:
        key = id(owner)
        current = self._entries.get(key)
        if current is not None and current.owner is not owner:
            raise OwnerRegistryError(
                "owner identity collision while previous owner is still registered"
            )
        self._entries[key] = _OwnerEntry(owner, desired)

    def get(self, owner: object) -> NetworkRulesSpec | None:
        current = self._entries.get(id(owner))
        if current is None:
            return None
        if current.owner is not owner:
            raise OwnerRegistryError("owner identity collision")
        return current.desired

    def remove(self, owner: object) -> bool:
        key = id(owner)
        current = self._entries.get(key)
        if current is None:
            return False
        if current.owner is not owner:
            raise OwnerRegistryError("owner identity collision")
        del self._entries[key]
        return True

    def desired_sets(self) -> tuple[NetworkRulesSpec, ...]:
        """Return independently owned desired sets for lower-domain composition."""

        return tuple(
            entry.desired
            for entry in self._entries.values()
        )

    def __len__(self) -> int:
        return len(self._entries)
