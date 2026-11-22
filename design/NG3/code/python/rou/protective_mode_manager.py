"""Source-scoped protective-mode Manager core.

Architecture: A.011 ProtectiveModeManager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock

from .protective_payload_gate import (
    ProtectivePayloadGateDesired,
    ProtectivePayloadGateDriver,
    ProtectivePayloadGateState,
    converge_protective_payload_gate_once,
)


class ProtectiveModeStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    PROBLEM = "problem"


class ProtectiveModeActionStatus(str, Enum):
    ACTIVE_CONFIRMED = "active_confirmed"
    INACTIVE_CONFIRMED = "inactive_confirmed"
    LEAVE_BLOCKED = "leave_blocked"
    GATE_FAILED = "gate_failed"
    LEAVE_FAILED_RECONTAINED = "leave_failed_recontained"
    SAFETY_RECLOSE_FAILED = "safety_reclose_failed"


@dataclass(frozen=True, slots=True)
class ProtectiveModeProjection:
    request_sources: frozenset[str]
    status: ProtectiveModeStatus
    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class ProtectiveModeActionResult:
    action_status: ProtectiveModeActionStatus
    projection: ProtectiveModeProjection

    @property
    def confirmed_active(self) -> bool:
        return self.projection.status is ProtectiveModeStatus.ACTIVE

    @property
    def confirmed_inactive(self) -> bool:
        return self.projection.status is ProtectiveModeStatus.INACTIVE


@dataclass(slots=True)
class ProtectiveModeManager:
    _sources: set[str] = field(default_factory=set, init=False, repr=False)
    _release_pending: bool = field(default=False, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _projection: ProtectiveModeProjection = field(
        default_factory=lambda: ProtectiveModeProjection(
            frozenset(),
            ProtectiveModeStatus.INACTIVE,
        ),
        init=False,
        repr=False,
    )

    def current_state(self) -> ProtectiveModeProjection:
        with self._lock:
            return self._projection

    def request_active(
        self,
        source: str,
        boundary_interface: str,
        driver: ProtectivePayloadGateDriver,
    ) -> ProtectiveModeActionResult:
        with self._lock:
            self._validate_source(source)
            self._validate_boundary(boundary_interface)
            self._sources.add(source)
            self._release_pending = False
            return self._ensure_active(boundary_interface, driver)

    def request_inactive(
        self,
        source: str,
        boundary_interface: str,
        *,
        normal_release_confirmed: bool,
        driver: ProtectivePayloadGateDriver,
    ) -> ProtectiveModeActionResult:
        with self._lock:
            self._validate_source(source)
            self._validate_boundary(boundary_interface)
            if type(normal_release_confirmed) is not bool:
                raise ValueError("normal_release_confirmed must be bool")
            self._sources.discard(source)
            if self._sources:
                self._release_pending = False
                return self._ensure_active(boundary_interface, driver)
            self._release_pending = True
            return self.reconcile_once(
                boundary_interface,
                normal_release_confirmed=normal_release_confirmed,
                driver=driver,
            )

    def reconcile_once(
        self,
        boundary_interface: str,
        *,
        normal_release_confirmed: bool,
        driver: ProtectivePayloadGateDriver,
    ) -> ProtectiveModeActionResult:
        with self._lock:
            self._validate_boundary(boundary_interface)
            if type(normal_release_confirmed) is not bool:
                raise ValueError("normal_release_confirmed must be bool")

            if self._sources:
                self._release_pending = False
                return self._ensure_active(boundary_interface, driver)

            if not self._release_pending:
                self._projection = ProtectiveModeProjection(
                    frozenset(),
                    ProtectiveModeStatus.INACTIVE,
                )
                return ProtectiveModeActionResult(
                    ProtectiveModeActionStatus.INACTIVE_CONFIRMED,
                    self._projection,
                )

            if not normal_release_confirmed:
                active = self._ensure_active(boundary_interface, driver)
                if active.confirmed_active:
                    self._projection = ProtectiveModeProjection(
                        frozenset(),
                        ProtectiveModeStatus.ACTIVE,
                        "leave blocked: normal release precondition is not confirmed",
                    )
                    return ProtectiveModeActionResult(
                        ProtectiveModeActionStatus.LEAVE_BLOCKED,
                        self._projection,
                    )
                return active

            disabled = converge_protective_payload_gate_once(
                driver,
                ProtectivePayloadGateDesired(
                    ProtectivePayloadGateState.DISABLED
                ),
            )
            if disabled.confirmed:
                self._release_pending = False
                self._projection = ProtectiveModeProjection(
                    frozenset(),
                    ProtectiveModeStatus.INACTIVE,
                )
                return ProtectiveModeActionResult(
                    ProtectiveModeActionStatus.INACTIVE_CONFIRMED,
                    self._projection,
                )

            reclosed = converge_protective_payload_gate_once(
                driver,
                ProtectivePayloadGateDesired(
                    ProtectivePayloadGateState.ENABLED,
                    boundary_interface,
                ),
            )
            if reclosed.confirmed:
                diagnostic = (
                    "protective leave was not confirmed; protective gate "
                    "was independently re-confirmed active"
                )
                if disabled.diagnostic:
                    diagnostic += f": {disabled.diagnostic}"
                self._projection = ProtectiveModeProjection(
                    frozenset(),
                    ProtectiveModeStatus.ACTIVE,
                    diagnostic,
                )
                return ProtectiveModeActionResult(
                    ProtectiveModeActionStatus.LEAVE_FAILED_RECONTAINED,
                    self._projection,
                )

            diagnostic = (
                "protective leave was not confirmed and fail-closed "
                "re-containment could not be confirmed"
            )
            if reclosed.diagnostic:
                diagnostic += f": {reclosed.diagnostic}"
            self._projection = ProtectiveModeProjection(
                frozenset(),
                ProtectiveModeStatus.PROBLEM,
                diagnostic,
            )
            return ProtectiveModeActionResult(
                ProtectiveModeActionStatus.SAFETY_RECLOSE_FAILED,
                self._projection,
            )

    def _ensure_active(
        self,
        boundary_interface: str,
        driver: ProtectivePayloadGateDriver,
    ) -> ProtectiveModeActionResult:
        result = converge_protective_payload_gate_once(
            driver,
            ProtectivePayloadGateDesired(
                ProtectivePayloadGateState.ENABLED,
                boundary_interface,
            ),
        )
        if result.confirmed:
            self._projection = ProtectiveModeProjection(
                frozenset(self._sources),
                ProtectiveModeStatus.ACTIVE,
            )
            return ProtectiveModeActionResult(
                ProtectiveModeActionStatus.ACTIVE_CONFIRMED,
                self._projection,
            )

        self._projection = ProtectiveModeProjection(
            frozenset(self._sources),
            ProtectiveModeStatus.PROBLEM,
            result.diagnostic or f"protective gate failed: {result.status.value}",
        )
        return ProtectiveModeActionResult(
            ProtectiveModeActionStatus.GATE_FAILED,
            self._projection,
        )

    @staticmethod
    def _validate_source(source: str) -> None:
        if not isinstance(source, str) or not source:
            raise ValueError("source must be non-empty text")

    @staticmethod
    def _validate_boundary(boundary_interface: str) -> None:
        if not isinstance(boundary_interface, str) or not boundary_interface:
            raise ValueError("boundary_interface must be non-empty text")
