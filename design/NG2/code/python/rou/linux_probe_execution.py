from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from threading import Condition, Lock, Thread, current_thread
import time
from typing import Callable, Protocol

from .availability_probe_state import ProbeObservationGeneration
from .linux_probe_driver import LinuxIcmpProbeDriver
from .probe_attempt import ProbeAttemptOutcome
from .probe_transport import (
    PhysicalProbePlane,
    ProbeExecutionPlan,
    ProbeGoodNewsInfo,
    ProbeWindowBoundaryInfo,
)


@dataclass(frozen=True)
class ProbeSendResult:
    good_news: bool
    local_error: str | None = None

    def __post_init__(self) -> None:
        if type(self.good_news) is not bool:
            raise ValueError("probe send good_news must be boolean")
        if self.local_error is not None and not self.local_error:
            raise ValueError("probe send local_error must be non-empty when present")
        if self.good_news and self.local_error is not None:
            raise ValueError("good-news send result cannot also be a local error")


class ProbeSendDriver(Protocol):
    def execute_send(
        self,
        path,
        target,
        *,
        timeout_seconds: int,
    ) -> ProbeSendResult:
        ...


class LinuxDiagnosticPingSendAdapter:
    """Hide the historical diagnostic attempt contract below production execution.

    NO_REPLY is collapsed to ordinary absence of good news. It never crosses this Adapter.
    """

    def __init__(self, driver: LinuxIcmpProbeDriver) -> None:
        if not callable(getattr(driver, "execute", None)):
            raise ValueError("ping send Adapter requires single-shot probe Driver")
        self._driver = driver

    def execute_send(
        self,
        path,
        target,
        *,
        timeout_seconds: int,
    ) -> ProbeSendResult:
        result = self._driver.execute(
            path,
            target,
            timeout_seconds=timeout_seconds,
        )
        if result.outcome is ProbeAttemptOutcome.REPLY:
            return ProbeSendResult(True)
        if result.outcome is ProbeAttemptOutcome.ERROR:
            return ProbeSendResult(
                False,
                result.diagnostic or "local probe execution error",
            )
        return ProbeSendResult(False)


class ProbeGoodNewsPublisher(Protocol):
    def publish(self, info: ProbeGoodNewsInfo) -> None:
        ...


class ProbeWindowBoundaryPublisher(Protocol):
    def publish(self, info: ProbeWindowBoundaryInfo) -> None:
        ...


class ProbeExecutionDiagnosticPublisher(Protocol):
    def publish(self, info: "ProbeExecutionDiagnosticInfo") -> None:
        ...


class ProbeExecutionHealth(str, Enum):
    READY = "ready"
    ERROR = "error"


@dataclass(frozen=True)
class ProbeExecutionDiagnosticInfo:
    generation: ProbeObservationGeneration
    plane: PhysicalProbePlane
    health: ProbeExecutionHealth
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.generation, ProbeObservationGeneration):
            raise ValueError("diagnostic requires ProbeObservationGeneration")
        if not isinstance(self.plane, PhysicalProbePlane):
            raise ValueError("diagnostic requires PhysicalProbePlane")
        if not isinstance(self.health, ProbeExecutionHealth):
            raise ValueError("diagnostic health must be ProbeExecutionHealth")
        if self.health is ProbeExecutionHealth.ERROR:
            if not self.diagnostic:
                raise ValueError("ERROR diagnostic requires detail")
        elif self.diagnostic is not None:
            raise ValueError("READY diagnostic must not carry detail")


@dataclass
class _PlaneSchedule:
    plane: PhysicalProbePlane
    next_send: float


@dataclass
class _WindowSchedule:
    probe_id: str
    interval_seconds: float
    next_boundary: float


class ProbeExecutionSchedule:
    """Generation-bound deterministic cadence state.

    The schedule owns only time placement. It never derives availability verdicts.
    """

    def __init__(self) -> None:
        self._plan: ProbeExecutionPlan | None = None
        self._planes: dict[tuple[object, object, object], _PlaneSchedule] = {}
        self._windows: dict[str, _WindowSchedule] = {}

    @property
    def plan(self) -> ProbeExecutionPlan | None:
        return self._plan

    def reconcile(
        self,
        plan: ProbeExecutionPlan | None,
        now: float,
    ) -> None:
        if (
            isinstance(now, bool)
            or not isinstance(now, (int, float))
            or not isfinite(float(now))
        ):
            raise ValueError("schedule time must be finite numeric")
        now = float(now)

        previous = self._plan
        generation_changed = (
            previous is None
            or plan is None
            or previous.generation != plan.generation
        )

        if plan is None:
            self._plan = None
            self._planes.clear()
            self._windows.clear()
            return

        old_planes = self._planes
        old_windows = self._windows
        new_planes: dict[tuple[object, object, object], _PlaneSchedule] = {}
        new_windows: dict[str, _WindowSchedule] = {}

        for plane in plan.planes:
            key = (plane.mechanism, plane.path, plane.target)
            old = old_planes.get(key)
            if (
                not generation_changed
                and old is not None
                and old.plane.interval_seconds == plane.interval_seconds
            ):
                next_send = old.next_send
            else:
                # Activation or cadence change gets one immediate send.
                next_send = now
            new_planes[key] = _PlaneSchedule(plane, next_send)

        for window in plan.windows:
            old = old_windows.get(window.probe_id)
            if (
                not generation_changed
                and old is not None
                and old.interval_seconds == window.interval_seconds
            ):
                next_boundary = old.next_boundary
            else:
                # New/changed logical evidence window starts now.
                next_boundary = now + window.interval_seconds
            new_windows[window.probe_id] = _WindowSchedule(
                window.probe_id,
                window.interval_seconds,
                next_boundary,
            )

        self._plan = plan
        self._planes = new_planes
        self._windows = new_windows

    def next_deadline(self) -> float | None:
        deadlines = [
            item.next_send
            for item in self._planes.values()
        ] + [
            item.next_boundary
            for item in self._windows.values()
        ]
        return min(deadlines) if deadlines else None

    def pop_due(
        self,
        now: float,
    ) -> tuple[tuple[ProbeWindowBoundaryInfo, ...], tuple[PhysicalProbePlane, ...]]:
        plan = self._plan
        if plan is None:
            return (), ()
        if (
            isinstance(now, bool)
            or not isinstance(now, (int, float))
            or not isfinite(float(now))
        ):
            raise ValueError("schedule time must be finite numeric")
        now = float(now)

        boundaries: list[ProbeWindowBoundaryInfo] = []
        for probe_id in sorted(self._windows):
            item = self._windows[probe_id]
            if item.next_boundary > now:
                continue
            elapsed = int(
                (now - item.next_boundary) // item.interval_seconds
            ) + 1
            boundaries.append(
                ProbeWindowBoundaryInfo(
                    probe_id,
                    plan.generation,
                    elapsed_intervals=elapsed,
                )
            )
            item.next_boundary += elapsed * item.interval_seconds

        sends: list[PhysicalProbePlane] = []
        for key in sorted(
            self._planes,
            key=lambda item: (
                item[0].value,
                item[1].ifname,
                item[1].ifindex,
                int(item[2]),
            ),
        ):
            item = self._planes[key]
            if item.next_send > now:
                continue
            sends.append(item.plane)
            # Do not burst stale sends after a scheduler delay. One current send is
            # useful; historical sends are not.
            while item.next_send <= now:
                item.next_send += item.plane.interval_seconds

        # Caller must publish boundaries before starting sends. This realizes the
        # normative boundary-before-next-send rule for coincident deadlines.
        return tuple(boundaries), tuple(sends)


class LinuxProbeExecutionAgent:
    """Long-lived Linux active-probe execution Agent.

    It owns cadence and process-launch lifecycle, but no availability policy. Physical
    sends use a ProbeSendDriver asynchronously. The compatibility Adapter may reuse the
    already-proven LinuxIcmpProbeDriver without exposing its attempt result contract.
    Only successful replies become good-news; local failures are diagnostics only.
    """

    def __init__(
        self,
        driver: ProbeSendDriver,
        good_news_publisher: ProbeGoodNewsPublisher,
        boundary_publisher: ProbeWindowBoundaryPublisher,
        diagnostic_publisher: ProbeExecutionDiagnosticPublisher,
        *,
        timeout_seconds: int = 1,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not callable(getattr(driver, "execute_send", None)):
            raise ValueError("Linux probe execution Agent requires ProbeSendDriver")
        if type(timeout_seconds) is not int or timeout_seconds <= 0:
            raise ValueError("technical timeout_seconds must be a positive integer")

        self._driver = driver
        self._good_news_publisher = good_news_publisher
        self._boundary_publisher = boundary_publisher
        self._diagnostic_publisher = diagnostic_publisher
        self._timeout_seconds = timeout_seconds
        self._clock = clock

        self._condition = Condition()
        self._schedule = ProbeExecutionSchedule()
        self._running = False
        self._thread: Thread | None = None
        # Good-news and window-boundary facts share one publication order per Agent.
        # EventEnvelope revisions can later preserve this order across async delivery.
        self._event_publication_lock = Lock()
        self._diagnostic_lock = Lock()
        self._latest_diagnostic: dict[
            tuple[ProbeObservationGeneration, PhysicalProbePlane],
            ProbeExecutionDiagnosticInfo,
        ] = {}

    def start(self) -> None:
        with self._condition:
            if self._running:
                return
            self._running = True
            self._thread = Thread(
                target=self._run,
                name="vpn-gate-probe-execution",
                daemon=True,
            )
            self._thread.start()

    def update_plan(self, plan: ProbeExecutionPlan | None) -> None:
        with self._condition:
            self._schedule.reconcile(plan, self._clock())
            self._discard_stale_diagnostics_locked(plan)
            self._condition.notify_all()

    def stop(self) -> None:
        thread: Thread | None
        with self._condition:
            if not self._running:
                self._schedule.reconcile(None, self._clock())
                self._discard_stale_diagnostics_locked(None)
                return
            self._running = False
            self._schedule.reconcile(None, self._clock())
            self._discard_stale_diagnostics_locked(None)
            thread = self._thread
            self._condition.notify_all()
        if thread is not None and thread is not current_thread():
            thread.join()
        with self._condition:
            self._thread = None

    def process_due(self, now: float | None = None) -> None:
        """Process due work once.

        Public for deterministic integration/testing and used by the internal loop.
        Publication occurs outside the schedule lock.
        """

        if now is None:
            now = self._clock()
        with self._condition:
            boundaries, sends = self._schedule.pop_due(now)
            plan = self._schedule.plan

        if plan is None:
            return

        for event in boundaries:
            with self._event_publication_lock:
                self._boundary_publisher.publish(event)
        for plane in sends:
            self._launch_send(plan, plane)

    def _run(self) -> None:
        while True:
            with self._condition:
                if not self._running:
                    return
                deadline = self._schedule.next_deadline()
                if deadline is None:
                    self._condition.wait()
                    continue
                delay = deadline - self._clock()
                if delay > 0:
                    self._condition.wait(timeout=delay)
                    continue
            self.process_due()

    def _launch_send(
        self,
        plan: ProbeExecutionPlan,
        plane: PhysicalProbePlane,
    ) -> None:
        Thread(
            target=self._execute_send,
            args=(plan, plane),
            name=(
                "vpn-gate-probe-send-"
                f"{plane.path.ifname}-{plane.path.ifindex}-{plane.target}"
            ),
            daemon=True,
        ).start()

    def _execute_send(
        self,
        plan: ProbeExecutionPlan,
        plane: PhysicalProbePlane,
    ) -> None:
        result = self._driver.execute_send(
            plane.path,
            plane.target,
            timeout_seconds=self._timeout_seconds,
        )

        with self._condition:
            current = self._schedule.plan
            if current is None or current.generation != plan.generation:
                return
            if plane not in current.planes:
                return

        if result.local_error is not None:
            self._publish_diagnostic_error(
                plan,
                plane,
                result.local_error,
            )
            return

        self._publish_diagnostic_ready(plan, plane)
        if result.good_news:
            with self._event_publication_lock:
                self._good_news_publisher.publish(
                    ProbeGoodNewsInfo(
                        plane.mechanism,
                        plane.path,
                        plane.target,
                        plan.generation,
                    )
                )

    def _publish_diagnostic_ready(
        self,
        plan: ProbeExecutionPlan,
        plane: PhysicalProbePlane,
    ) -> None:
        self._publish_diagnostic(
            ProbeExecutionDiagnosticInfo(
                plan.generation,
                plane,
                ProbeExecutionHealth.READY,
            )
        )

    def _publish_diagnostic_error(
        self,
        plan: ProbeExecutionPlan,
        plane: PhysicalProbePlane,
        diagnostic: str,
    ) -> None:
        self._publish_diagnostic(
            ProbeExecutionDiagnosticInfo(
                plan.generation,
                plane,
                ProbeExecutionHealth.ERROR,
                diagnostic,
            )
        )

    def _publish_diagnostic(
        self,
        info: ProbeExecutionDiagnosticInfo,
    ) -> None:
        key = (info.generation, info.plane)
        with self._diagnostic_lock:
            if self._latest_diagnostic.get(key) == info:
                return
            self._latest_diagnostic[key] = info
        self._diagnostic_publisher.publish(info)

    def _discard_stale_diagnostics_locked(
        self,
        plan: ProbeExecutionPlan | None,
    ) -> None:
        # Called while schedule condition is held; diagnostic map has its own lock.
        with self._diagnostic_lock:
            if plan is None:
                self._latest_diagnostic.clear()
                return
            live = {
                (plan.generation, plane)
                for plane in plan.planes
            }
            for key in tuple(self._latest_diagnostic):
                if key not in live:
                    self._latest_diagnostic.pop(key, None)
