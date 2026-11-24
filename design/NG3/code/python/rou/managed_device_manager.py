"""A.012 orchestration core for explicitly managed Device base realizations.

Architecture: A.012 ManagedDeviceManager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from .managed_wireguard_adapter import (
    ManagedWireGuardObservation,
    ManagedWireGuardState,
)
from .release1_config import CurrentConfig, ManagedWireGuardConfig


class ManagedDeviceDesiredState(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"


@dataclass(frozen=True, slots=True)
class ManagedDeviceRealization:
    device_id: str
    desired_state: ManagedDeviceDesiredState
    desired_generation: str | None
    confirmed_state: ManagedWireGuardState | None
    confirmed_generation: str | None
    waiting_for_dependencies: bool = False
    problem: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id:
            raise ValueError("device_id must be non-empty text")
        if self.desired_state is ManagedDeviceDesiredState.PRESENT:
            if self.desired_generation is None and self.problem is None:
                raise ValueError(
                    "present desired state requires a generation or problem"
                )
        elif self.desired_generation is not None:
            raise ValueError("absent desired state cannot carry a generation")
        if self.waiting_for_dependencies:
            if self.desired_state is not ManagedDeviceDesiredState.ABSENT:
                raise ValueError(
                    "dependency wait is valid only for desired absence"
                )
            if self.problem is not None:
                raise ValueError(
                    "dependency wait and lifecycle problem are distinct states"
                )


class ManagedDeviceLifecycleAdapter(Protocol):
    def desired_generation(
        self,
        device_id: str,
        desired: ManagedWireGuardConfig,
    ) -> str:
        """Return validated desired base-generation token without mutation."""

    def observe(self, device_id: str) -> ManagedWireGuardObservation:
        """Fresh-observe current owned base realization."""

    def converge_present(
        self,
        device_id: str,
        desired: ManagedWireGuardConfig,
    ) -> ManagedWireGuardObservation:
        """Converge and freshly confirm desired base realization."""

    def converge_absent(self, device_id: str) -> ManagedWireGuardObservation:
        """Remove owned base realization and freshly confirm absence."""


@dataclass(slots=True)
class ManagedDeviceManager:
    """Current-only owner of managed Device base-presence demand."""

    lifecycle: ManagedDeviceLifecycleAdapter
    _known_managed_ids: set[str] = field(default_factory=set, init=False)

    def reconcile(
        self,
        config: CurrentConfig,
        *,
        dependency_free_device_ids: frozenset[str] = frozenset(),
    ) -> tuple[ManagedDeviceRealization, ...]:
        if not isinstance(config, CurrentConfig):
            raise ValueError("config must be CurrentConfig")
        if not isinstance(dependency_free_device_ids, frozenset):
            raise ValueError("dependency_free_device_ids must be a frozenset")
        if any(
            not isinstance(device_id, str) or not device_id
            for device_id in dependency_free_device_ids
        ):
            raise ValueError(
                "dependency_free_device_ids must contain non-empty strings"
            )

        configured = set(config.managed_vpns)
        active = config.structural.active_device_ids
        subjects = sorted(configured | self._known_managed_ids)
        next_known = set(configured)
        result: list[ManagedDeviceRealization] = []

        for device_id in subjects:
            desired = config.managed_vpns.get(device_id)
            if desired is not None and device_id in active:
                projection = self._reconcile_present(device_id, desired)
                result.append(projection)
                next_known.add(device_id)
                continue

            projection = self._reconcile_absent(
                device_id,
                may_remove=device_id in dependency_free_device_ids,
            )
            result.append(projection)
            if (
                device_id not in configured
                and (
                    projection.confirmed_state is not ManagedWireGuardState.ABSENT
                    or projection.problem is not None
                )
            ):
                next_known.add(device_id)

        self._known_managed_ids = next_known
        return tuple(result)

    def _reconcile_present(
        self,
        device_id: str,
        desired: ManagedWireGuardConfig,
    ) -> ManagedDeviceRealization:
        try:
            desired_generation = self.lifecycle.desired_generation(
                device_id,
                desired,
            )
            observation = self.lifecycle.converge_present(
                device_id,
                desired,
            )
            if observation.state is not ManagedWireGuardState.PRESENT:
                raise RuntimeError(
                    "D.001 returned non-present state for desired presence"
                )
            if observation.confirmed_generation != desired_generation:
                raise RuntimeError(
                    "D.001 confirmed generation differs from desired generation"
                )
            return ManagedDeviceRealization(
                device_id=device_id,
                desired_state=ManagedDeviceDesiredState.PRESENT,
                desired_generation=desired_generation,
                confirmed_state=observation.state,
                confirmed_generation=observation.confirmed_generation,
            )
        except Exception as exc:
            return ManagedDeviceRealization(
                device_id=device_id,
                desired_state=ManagedDeviceDesiredState.PRESENT,
                desired_generation=(
                    desired_generation
                    if "desired_generation" in locals()
                    else None
                ),
                confirmed_state=None,
                confirmed_generation=None,
                problem=f"{type(exc).__name__}: {exc}",
            )

    def _reconcile_absent(
        self,
        device_id: str,
        *,
        may_remove: bool,
    ) -> ManagedDeviceRealization:
        try:
            observation = (
                self.lifecycle.converge_absent(device_id)
                if may_remove
                else self.lifecycle.observe(device_id)
            )
            if observation.state is ManagedWireGuardState.ABSENT:
                return ManagedDeviceRealization(
                    device_id=device_id,
                    desired_state=ManagedDeviceDesiredState.ABSENT,
                    desired_generation=None,
                    confirmed_state=ManagedWireGuardState.ABSENT,
                    confirmed_generation=None,
                )
            if may_remove:
                raise RuntimeError(
                    "D.001 returned present state after requested absence"
                )
            return ManagedDeviceRealization(
                device_id=device_id,
                desired_state=ManagedDeviceDesiredState.ABSENT,
                desired_generation=None,
                confirmed_state=observation.state,
                confirmed_generation=observation.confirmed_generation,
                waiting_for_dependencies=True,
            )
        except Exception as exc:
            return ManagedDeviceRealization(
                device_id=device_id,
                desired_state=ManagedDeviceDesiredState.ABSENT,
                desired_generation=None,
                confirmed_state=None,
                confirmed_generation=None,
                problem=f"{type(exc).__name__}: {exc}",
            )
