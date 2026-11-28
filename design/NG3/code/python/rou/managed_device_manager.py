"""A.012 orchestration core for explicitly managed Device base realizations.

Architecture: A.012 ManagedDeviceManager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable, Protocol

from .binding import PathBinding
from .interface_identity import InterfaceIdentity
from .managed_device_demand import (
    ManagedDeviceDemandProjection,
    project_final,
    project_regular,
)

from .managed_wireguard_adapter import (
    ManagedWireGuardObservation,
    ManagedWireGuardState,
)
from .release1_config import CurrentConfig, ManagedWireGuardConfig
from .managed_reclaim_projection import ReclaimDecision, ReclaimReason


class ManagedDeviceDesiredState(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"


class ManagedDeviceIntentBasis(str, Enum):
    STRUCTURAL = "structural"
    RECLAIM_RETENTION = "reclaim_retention"
    RECLAIM_DEFERRED_HOLD = "reclaim_deferred_hold"
    RECLAIM_RETIREMENT = "reclaim_retirement"


@dataclass(frozen=True, slots=True)
class ManagedDeviceRealization:
    device_id: str
    desired_state: ManagedDeviceDesiredState
    desired_generation: str | None
    confirmed_state: ManagedWireGuardState | None
    confirmed_generation: str | None
    waiting_for_dependencies: bool = False
    problem: str | None = None
    confirmed_interface: InterfaceIdentity | None = None
    intent_basis: ManagedDeviceIntentBasis | None = None
    payload_eligible: bool | None = None

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

    def confirm_present(
        self,
        device_id: str,
        desired_base: ManagedWireGuardConfig,
    ) -> ManagedWireGuardObservation:
        """Confirm an existing exact base without mutation."""

    def converge_present(
        self,
        device_id: str,
        desired: ManagedWireGuardConfig,
    ) -> ManagedWireGuardObservation:
        """Converge and freshly confirm desired base realization."""

    def converge_absent(self, device_id: str) -> ManagedWireGuardObservation:
        """Remove owned base realization and freshly confirm absence."""

    def retire_exact(
        self, device_id: str, expected_identity: InterfaceIdentity,
        expected_generation: str, desired_base: ManagedWireGuardConfig,
    ) -> ManagedWireGuardObservation:
        """Retire the exact already-confirmed managed base realization."""


@dataclass(slots=True)
class ManagedDeviceManager:
    """Current-only owner of managed Device base-presence demand."""

    lifecycle: ManagedDeviceLifecycleAdapter
    _known_managed_ids: set[str] = field(default_factory=set, init=False)

    @staticmethod
    def _validate_desired(
        config: CurrentConfig, desired_device_ids: frozenset[str]
    ) -> None:
        if not isinstance(config, CurrentConfig):
            raise ValueError("config must be CurrentConfig")
        if not isinstance(desired_device_ids, frozenset):
            raise ValueError("desired_device_ids must be a frozenset")
        eligible = set(config.managed_vpns) & config.structural.active_device_ids
        if not desired_device_ids <= eligible:
            raise ValueError("desired_device_ids must contain only active managed Devices")

    def reconcile(
        self,
        config: CurrentConfig,
        *,
        desired_device_ids: frozenset[str],
        dependency_free_device_ids: frozenset[str] = frozenset(),
    ) -> tuple[ManagedDeviceRealization, ...]:
        """Converge an explicit demand; never derive it from structural activity."""
        self._validate_desired(config, desired_device_ids)
        self._validate_dependency_release(dependency_free_device_ids)
        present = tuple(
            self.converge_present(config, device_id)
            for device_id in sorted(desired_device_ids)
        )
        absent = self.reconcile_undemanded(
            config,
            desired_device_ids=desired_device_ids,
            dependency_free_device_ids=dependency_free_device_ids,
        )
        return tuple(sorted(present + absent, key=lambda item: item.device_id))

    def observe_exact_base(
        self, config: CurrentConfig, device_id: str
    ) -> tuple[str | None, ManagedWireGuardObservation]:
        """Read-only present confirmation; no demand or ownership-state change."""
        self._validate_desired(config, frozenset({device_id}))
        observed = self.lifecycle.observe(device_id)
        if observed.device_id != device_id:
            raise RuntimeError("D.001 returned another Device")
        if observed.state is ManagedWireGuardState.ABSENT:
            return None, observed
        if observed.state is not ManagedWireGuardState.PRESENT or observed.interface is None:
            raise RuntimeError("D.001 presence is unconfirmed")
        desired = config.managed_vpns[device_id]
        expected = self.lifecycle.desired_generation(device_id, desired)
        confirmed = self.lifecycle.confirm_present(device_id, desired)
        if (not expected or confirmed.device_id != device_id
                or confirmed.state is not ManagedWireGuardState.PRESENT
                or confirmed.interface != observed.interface
                or confirmed.confirmed_generation != expected):
            raise RuntimeError("D.001 exact base confirmation changed or mismatched")
        return expected, confirmed

    def retire_reclaim_candidate(
        self, config: CurrentConfig, candidate: ReclaimDecision,
    ) -> ManagedWireGuardObservation:
        """Execute exact D.001 retirement after caller-confirmed dependency guards."""
        if (not isinstance(candidate, ReclaimDecision)
                or candidate.reason is not ReclaimReason.SURPLUS
                or not isinstance(candidate.interface, InterfaceIdentity)
                or not candidate.generation):
            raise ValueError("exact surplus retirement decision required")
        self._validate_desired(config, frozenset({candidate.device_id}))
        result = self.lifecycle.retire_exact(
            candidate.device_id, candidate.interface, candidate.generation,
            config.managed_vpns[candidate.device_id],
        )
        if (result.device_id != candidate.device_id
                or result.state is not ManagedWireGuardState.ABSENT
                or result.interface is not None
                or result.confirmed_generation is not None):
            raise RuntimeError("D.001 exact retirement did not confirm absence")
        return result

    def converge_present(
        self, config: CurrentConfig, device_id: str
    ) -> ManagedDeviceRealization:
        self._validate_desired(config, frozenset({device_id}))
        self._known_managed_ids.add(device_id)
        return self._reconcile_present(device_id, config.managed_vpns[device_id])

    @staticmethod
    def _validate_dependency_release(dependency_free_device_ids: frozenset[str]) -> None:
        if not isinstance(dependency_free_device_ids, frozenset) or any(
            not isinstance(device_id, str) or not device_id
            for device_id in dependency_free_device_ids
        ):
            raise ValueError(
                "dependency_free_device_ids must be a frozenset of non-empty strings"
            )

    def reconcile_undemanded(
        self,
        config: CurrentConfig,
        *,
        desired_device_ids: frozenset[str],
        dependency_free_device_ids: frozenset[str] = frozenset(),
    ) -> tuple[ManagedDeviceRealization, ...]:
        """Observe or safely release only subjects outside the final desired set."""
        self._validate_desired(config, desired_device_ids)
        self._validate_dependency_release(dependency_free_device_ids)
        configured = set(config.managed_vpns)
        subjects = sorted((configured | self._known_managed_ids) - desired_device_ids)
        next_known = set(configured)
        result: list[ManagedDeviceRealization] = []
        for device_id in subjects:
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
                confirmed_interface=observation.interface,
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
                confirmed_interface=observation.interface,
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


@dataclass(frozen=True, slots=True)
class ManagedDeviceConvergence:
    """One bounded presence attempt, before dependency release."""

    projection: ManagedDeviceDemandProjection
    realizations: tuple[ManagedDeviceRealization, ...]
    attempt_problems: tuple[ManagedDeviceRealization, ...]

    @property
    def confirmed_interfaces(self) -> frozenset[InterfaceIdentity]:
        return frozenset(
            item.confirmed_interface
            for item in self.realizations
            if item.desired_state is ManagedDeviceDesiredState.PRESENT
            and item.confirmed_state is ManagedWireGuardState.PRESENT
            and item.confirmed_interface is not None
            and item.problem is None
        )


def _next_candidate(
    projection: ManagedDeviceDemandProjection,
    attempted: dict[str, ManagedDeviceRealization],
    *,
    reserve: bool,
) -> str | None:
    # First converge the actual calculated demand. Only if its candidates
    # have already had a chance and observed capacity remains insufficient,
    # consider another absent candidate in the same baseline hierarchy.
    for profile in projection.profiles:
        selected = profile.reserve_device_ids if reserve else profile.ordinary_device_ids
        for device_id in selected:
            if device_id not in attempted:
                return device_id

    for profile in projection.profiles:
        deficit = profile.regular_deficit
        if reserve:
            deficit = max(0, deficit - profile.reserve_present)
        if not deficit:
            continue
        candidates = profile.reserve_candidates if reserve else profile.ordinary_candidates
        for device_id in candidates:
            if device_id not in attempted:
                return device_id
    return None


def converge_managed_device_presence(
    config: CurrentConfig,
    manager: ManagedDeviceManager,
    observe: Callable[[], Iterable[PathBinding]],
) -> ManagedDeviceConvergence:
    """Try each necessary managed Device at most once per fresh trigger.

    No dependency release occurs in either phase. A failed D.001 action is
    not path capacity, and its same-name endpoint must not be admitted as a
    successfully managed realization. Fresh observations drive every next
    selection. The next trigger retries any still-demanded failed ordinary.
    """
    attempted: dict[str, ManagedDeviceRealization] = {}

    def fresh() -> tuple[PathBinding, ...]:
        return tuple(
            path for path in observe()
            if path.path_id.device_id not in attempted
            or (
                attempted[path.path_id.device_id].problem is None
                and attempted[path.path_id.device_id].confirmed_interface == path.endpoint
            )
        )

    presence = fresh()
    while True:
        regular = project_regular(config, presence)
        candidate = _next_candidate(regular, attempted, reserve=False)
        if candidate is None:
            final = project_final(config, presence)
            candidate = _next_candidate(final, attempted, reserve=True)
            if candidate is None:
                break
        attempted[candidate] = manager.converge_present(config, candidate)
        presence = fresh()

    desired = final.desired_device_ids
    # Every final demanded candidate has received its own D.001 attempt.
    present = tuple(attempted[d] for d in sorted(desired))
    absent = manager.reconcile_undemanded(config, desired_device_ids=desired)
    return ManagedDeviceConvergence(
        final,
        tuple(sorted(present + absent, key=lambda item: item.device_id)),
        tuple(item for item in attempted.values() if item.problem is not None),
    )
