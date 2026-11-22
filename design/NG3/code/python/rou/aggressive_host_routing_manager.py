"""Continuous aggressive host-routing semantic owner.

Architecture: E.003 AggressiveHostRoutingManager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Event, Lock, RLock, Thread
from typing import Callable

from .aggressive_host_routing_enforcer import (
    AggressiveHostRoutingDesired,
    AggressiveHostRoutingEnforcementResult,
    converge_aggressive_host_routing_active_once,
    converge_aggressive_host_routing_inactive_once,
)
from .linux_aggressive_escape_guard import LinuxAggressiveEscapeGuardDriver
from .linux_host_managed_routing_backend import LinuxHostManagedRoutingDriver
from .protective_mode_manager import ProtectiveModeManager
from .protective_payload_gate import ProtectivePayloadGateDriver


AGGRESSIVE_PROTECTIVE_SOURCE = "aggressive"


class AggressiveHostRoutingManagerStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    DEGRADED = "degraded"
    PROBLEM = "problem"


@dataclass(frozen=True, slots=True)
class AggressiveHostRoutingManagerProjection:
    status: AggressiveHostRoutingManagerStatus
    protective_requested: bool
    diagnostic: str | None = None


@dataclass(slots=True)
class AggressiveHostRoutingManager:
    routing_driver: LinuxHostManagedRoutingDriver
    guard_driver: LinuxAggressiveEscapeGuardDriver
    protective_manager: ProtectiveModeManager
    protective_driver: ProtectivePayloadGateDriver
    protective_boundary_interface: str
    normal_release_confirmed: Callable[[], bool]
    audit_interval_seconds: float = 1.0
    _desired: AggressiveHostRoutingDesired | None = field(
        default=None, init=False, repr=False
    )
    _projection: AggressiveHostRoutingManagerProjection = field(
        default_factory=lambda: AggressiveHostRoutingManagerProjection(
            AggressiveHostRoutingManagerStatus.INACTIVE,
            False,
        ),
        init=False,
        repr=False,
    )
    _stop: Event = field(default_factory=Event, init=False, repr=False)
    _thread: Thread | None = field(default=None, init=False, repr=False)
    _state_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _operation_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.routing_driver, LinuxHostManagedRoutingDriver):
            raise ValueError("routing_driver must be LinuxHostManagedRoutingDriver")
        if not isinstance(self.guard_driver, LinuxAggressiveEscapeGuardDriver):
            raise ValueError("guard_driver must be LinuxAggressiveEscapeGuardDriver")
        if not isinstance(self.protective_manager, ProtectiveModeManager):
            raise ValueError("protective_manager must be ProtectiveModeManager")
        if (
            not isinstance(self.protective_boundary_interface, str)
            or not self.protective_boundary_interface
        ):
            raise ValueError("protective_boundary_interface must be non-empty text")
        if not callable(self.normal_release_confirmed):
            raise ValueError("normal_release_confirmed must be callable")
        if (
            not isinstance(self.audit_interval_seconds, (int, float))
            or isinstance(self.audit_interval_seconds, bool)
            or self.audit_interval_seconds <= 0
        ):
            raise ValueError("audit_interval_seconds must be positive")

    def current_state(self) -> AggressiveHostRoutingManagerProjection:
        with self._state_lock:
            return self._projection

    def activate(
        self,
        desired: AggressiveHostRoutingDesired,
    ) -> AggressiveHostRoutingManagerProjection:
        if not isinstance(desired, AggressiveHostRoutingDesired):
            raise ValueError("desired must be AggressiveHostRoutingDesired")
        with self._operation_lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("aggressive host-routing Manager is already active")
            result = converge_aggressive_host_routing_active_once(
                self.routing_driver,
                self.guard_driver,
                desired,
            )
            if not result.confirmed_active:
                self._desired = desired
                self._publish_failure(result)
                return self.current_state()

            self._desired = desired
            release_ok = self._clear_own_protective_request()
            self._set_projection(
                (
                    AggressiveHostRoutingManagerStatus.ACTIVE
                    if release_ok
                    else AggressiveHostRoutingManagerStatus.DEGRADED
                ),
                diagnostic=(
                    None
                    if release_ok
                    else "aggressive routing recovered but protective release is pending"
                ),
            )
            self._stop.clear()
            self._thread = Thread(
                target=self._audit_loop,
                name="vpn-gate-aggressive-routing",
                daemon=True,
            )
            self._thread.start()
            return self.current_state()

    def audit_once(self) -> AggressiveHostRoutingManagerProjection:
        with self._operation_lock:
            desired = self._desired
            if desired is None:
                return self.current_state()
            result = converge_aggressive_host_routing_active_once(
                self.routing_driver,
                self.guard_driver,
                desired,
            )
            if result.confirmed_active:
                release_ok = self._clear_own_protective_request()
                self._set_projection(
                    (
                        AggressiveHostRoutingManagerStatus.ACTIVE
                        if release_ok
                        else AggressiveHostRoutingManagerStatus.DEGRADED
                    ),
                    diagnostic=(
                        None
                        if release_ok
                        else "aggressive routing is exact but protective release is pending"
                    ),
                )
            else:
                self._publish_failure(result)
            return self.current_state()

    def deactivate(self) -> AggressiveHostRoutingManagerProjection:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(1.0, self.audit_interval_seconds * 2.0))
        with self._operation_lock:
            desired = self._desired
            if desired is None:
                self._set_projection(AggressiveHostRoutingManagerStatus.INACTIVE)
                self._thread = None
                return self.current_state()

            result = converge_aggressive_host_routing_inactive_once(
                self.routing_driver,
                self.guard_driver,
                desired,
            )
            if not result.confirmed_inactive:
                self._set_projection(
                    AggressiveHostRoutingManagerStatus.PROBLEM,
                    diagnostic=result.diagnostic or result.status.value,
                )
                self._thread = None
                return self.current_state()

            release_ok = self._clear_own_protective_request()
            self._desired = None
            self._thread = None
            self._set_projection(
                (
                    AggressiveHostRoutingManagerStatus.INACTIVE
                    if release_ok
                    else AggressiveHostRoutingManagerStatus.DEGRADED
                ),
                diagnostic=(
                    None
                    if release_ok
                    else "aggressive routing is inactive but protective release is pending"
                ),
            )
            return self.current_state()

    def _audit_loop(self) -> None:
        while not self._stop.wait(self.audit_interval_seconds):
            try:
                self.audit_once()
            except Exception as exc:
                self._set_projection(
                    AggressiveHostRoutingManagerStatus.PROBLEM,
                    diagnostic=(
                        "aggressive audit raised unexpectedly: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                )

    def _publish_failure(
        self,
        result: AggressiveHostRoutingEnforcementResult,
    ) -> None:
        protective = self.protective_manager.request_active(
            AGGRESSIVE_PROTECTIVE_SOURCE,
            self.protective_boundary_interface,
            self.protective_driver,
        )
        source_registered = (
            AGGRESSIVE_PROTECTIVE_SOURCE
            in protective.projection.request_sources
        )
        status = (
            AggressiveHostRoutingManagerStatus.DEGRADED
            if result.local_containment_confirmed
            and protective.confirmed_active
            else AggressiveHostRoutingManagerStatus.PROBLEM
        )
        detail = result.diagnostic or result.status.value
        if not result.local_containment_confirmed:
            detail += "; local aggressive containment is not confirmed"
        if not protective.confirmed_active:
            detail += "; global protective containment is not confirmed"
        self._set_projection(
            status,
            protective_requested=source_registered,
            diagnostic=detail,
        )

    def _clear_own_protective_request(self) -> bool:
        current = self.protective_manager.current_state()
        if AGGRESSIVE_PROTECTIVE_SOURCE not in current.request_sources:
            return not (
                not current.request_sources
                and current.status.value == "active"
            )
        try:
            normal_ready = bool(self.normal_release_confirmed())
        except Exception:
            return False
        result = self.protective_manager.request_inactive(
            AGGRESSIVE_PROTECTIVE_SOURCE,
            self.protective_boundary_interface,
            normal_release_confirmed=normal_ready,
            driver=self.protective_driver,
        )
        if AGGRESSIVE_PROTECTIVE_SOURCE in result.projection.request_sources:
            return False
        if result.projection.request_sources:
            return True
        return result.confirmed_inactive

    def _set_projection(
        self,
        status: AggressiveHostRoutingManagerStatus,
        *,
        protective_requested: bool | None = None,
        diagnostic: str | None = None,
    ) -> None:
        with self._state_lock:
            if protective_requested is None:
                protective_requested = (
                    AGGRESSIVE_PROTECTIVE_SOURCE
                    in self.protective_manager.current_state().request_sources
                )
            self._projection = AggressiveHostRoutingManagerProjection(
                status,
                protective_requested,
                diagnostic,
            )
