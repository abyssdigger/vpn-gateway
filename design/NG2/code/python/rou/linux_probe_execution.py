from __future__ import annotations

from dataclasses import dataclass
import logging
from enum import Enum
from math import isfinite
from threading import Condition, Lock, Thread, current_thread
import time
from typing import Callable, Protocol

from .availability_probe_state import ProbeObservationGeneration
from .linux_probe_driver import LinuxIcmpProbeDriver
from .probe_attempt import ProbeAttemptOutcome
from .availability_collector import AvailabilityGoodNews, AvailabilityTick
from .probe_transport import (
    LogicalProbeChannel,
    PhysicalProbePlane,
    ProbeExecutionPlan,
)


_LOG = logging.getLogger(__name__)

@dataclass(frozen=True)
class ProbeSendResult:
    good_news: bool
    local_error: str | None = None

    def __post_init__(self) -> None:
        if type(self.good_news) is not bool:
            raise ValueError("probe send good_news must be boolean")
        if self.local_error is not None and (
            not isinstance(self.local_error, str) or not self.local_error
        ):
            raise ValueError(
                "probe send local_error must be non-empty string when present"
            )
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
    """Hide the historical single-shot result contract below production execution."""

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
    def publish(self, info: AvailabilityGoodNews) -> None:
        ...


class ProbeTickPublisher(Protocol):
    def publish(self, info: AvailabilityTick) -> None:
        ...


class ProbeExecutionDiagnosticPublisher(Protocol):
    def publish(self, info: "ProbeExecutionDiagnosticInfo") -> None:
        ...


class ProbeExecutionHealth(str, Enum):
    READY = "ready"
    ERROR = "error"
    INACTIVE = "inactive"


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
            raise ValueError("non-ERROR diagnostic must not carry detail")


@dataclass
class _PlaneSchedule:
    plane: PhysicalProbePlane
    next_send: float


@dataclass
class _TickSchedule:
    channel: LogicalProbeChannel
    next_tick: float


class ProbeExecutionSchedule:
    """Generation-bound physical-send and logical-tick cadence."""

    def __init__(self) -> None:
        self._plan: ProbeExecutionPlan | None = None
        self._planes: dict[tuple[object, object, object], _PlaneSchedule] = {}
        self._ticks: dict[str, _TickSchedule] = {}

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

        if plan is not None and not isinstance(plan, ProbeExecutionPlan):
            raise ValueError("schedule plan must be ProbeExecutionPlan or None")

        previous = self._plan
        generation_changed = (
            previous is None
            or plan is None
            or previous.generation != plan.generation
        )

        if plan is None:
            self._plan = None
            self._planes.clear()
            self._ticks.clear()
            return

        old_planes = self._planes
        old_ticks = self._ticks
        new_planes: dict[tuple[object, object, object], _PlaneSchedule] = {}
        new_ticks: dict[str, _TickSchedule] = {}

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
                next_send = now
            new_planes[key] = _PlaneSchedule(plane, next_send)

        for channel in plan.channels:
            old = old_ticks.get(channel.priority.channel_id)
            if (
                not generation_changed
                and old is not None
                and old.channel.interval_seconds == channel.interval_seconds
            ):
                next_tick = old.next_tick
            else:
                next_tick = now + float(channel.interval_seconds)
            new_ticks[channel.priority.channel_id] = _TickSchedule(channel, next_tick)

        self._plan = plan
        self._planes = new_planes
        self._ticks = new_ticks

    def next_deadline(self) -> float | None:
        deadlines = [
            item.next_send
            for item in self._planes.values()
        ] + [
            item.next_tick
            for item in self._ticks.values()
        ]
        return min(deadlines) if deadlines else None

    def pop_due(
        self,
        now: float,
    ) -> tuple[tuple[AvailabilityTick, ...], tuple[PhysicalProbePlane, ...]]:
        if self._plan is None:
            return (), ()
        if (
            isinstance(now, bool)
            or not isinstance(now, (int, float))
            or not isfinite(float(now))
        ):
            raise ValueError("schedule time must be finite numeric")
        now = float(now)

        ticks: list[AvailabilityTick] = []
        for probe_id in sorted(self._ticks):
            item = self._ticks[probe_id]
            if item.next_tick > now:
                continue
            ticks.append(AvailabilityTick(item.channel.priority))
            interval = float(item.channel.interval_seconds)
            elapsed = int((now - item.next_tick) // interval) + 1
            item.next_tick += elapsed * interval

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
            interval = float(item.plane.interval_seconds)
            elapsed = int((now - item.next_send) // interval) + 1
            item.next_send += elapsed * interval

        return tuple(ticks), tuple(sends)


class LinuxProbeExecutionAgent:
    """Long-lived Linux probe Agent with no availability hysteresis policy."""

    def __init__(
        self,
        driver: ProbeSendDriver,
        good_news_publisher: ProbeGoodNewsPublisher,
        tick_publisher: ProbeTickPublisher,
        diagnostic_publisher: ProbeExecutionDiagnosticPublisher,
        *,
        timeout_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not callable(getattr(driver, "execute_send", None)):
            raise ValueError("Linux probe execution Agent requires ProbeSendDriver")
        if type(timeout_seconds) is not int or timeout_seconds <= 0:
            raise ValueError("technical timeout_seconds must be a positive integer")
        if not callable(clock):
            raise ValueError("probe execution clock must be callable")

        self._driver = driver
        self._good_news_publisher = good_news_publisher
        self._tick_publisher = tick_publisher
        self._diagnostic_publisher = diagnostic_publisher
        self._timeout_seconds = timeout_seconds
        self._clock = clock

        self._condition = Condition()
        self._schedule = ProbeExecutionSchedule()
        self._running = False
        self._thread: Thread | None = None

        self._diagnostic_publication_lock = Lock()
        self._diagnostic_lock = Lock()
        self._in_flight: set[
            tuple[
                ProbeObservationGeneration,
                object,
                object,
                object,
            ]
        ] = set()
        self._latest_diagnostic: dict[
            tuple[ProbeObservationGeneration, PhysicalProbePlane],
            ProbeExecutionDiagnosticInfo,
        ] = {}

    def start(self) -> None:
        with self._condition:
            if self._running:
                return
            self._running = True
            thread = Thread(
                target=self._run,
                name="vpn-gate-probe-execution",
                daemon=True,
            )
            self._thread = thread
            try:
                thread.start()
            except Exception:
                self._running = False
                self._thread = None
                self._condition.notify_all()
                raise

    def update_plan(self, plan: ProbeExecutionPlan | None) -> None:
        with self._condition:
            self._schedule.reconcile(plan, self._clock())
            inactive = self._take_stale_diagnostics_locked(plan)
            self._condition.notify_all()
        self._publish_inactive_diagnostics(inactive)

    def stop(self) -> None:
        thread: Thread | None
        with self._condition:
            was_running = self._running
            self._running = False
            self._schedule.reconcile(None, self._clock())
            inactive = self._take_stale_diagnostics_locked(None)
            thread = self._thread if was_running else None
            self._condition.notify_all()

        self._publish_inactive_diagnostics(inactive)

        if thread is not None and thread is not current_thread():
            thread.join()
        with self._condition:
            self._thread = None

    def process_due(self, now: float | None = None) -> None:
        if now is None:
            now = self._clock()
        with self._condition:
            ticks, sends = self._schedule.pop_due(now)
            plan = self._schedule.plan

        if plan is None:
            return

        for info in ticks:
            try:
                self._tick_publisher.publish(info)
            except Exception:
                _LOG.exception(
                    "availability tick publisher raised for channel %s",
                    info.channel.channel_id,
                )
        for plane in sends:
            self._launch_send(plan, plane)

    def _run(self) -> None:
        try:
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
        finally:
            with self._condition:
                if self._thread is current_thread():
                    self._running = False
                    self._thread = None
                self._condition.notify_all()

    def _launch_send(
        self,
        plan: ProbeExecutionPlan,
        plane: PhysicalProbePlane,
    ) -> None:
        key = self._in_flight_key(plan, plane)
        with self._condition:
            current = self._schedule.plan
            if current is None or current.generation != plan.generation:
                return
            if plane not in current.planes:
                return
            if key in self._in_flight:
                overrun = True
            else:
                self._in_flight.add(key)
                overrun = False

        if overrun:
            self._publish_diagnostic_error(
                plan,
                plane,
                "previous physical probe send is still in flight",
            )
            return

        worker = Thread(
            target=self._execute_send,
            args=(plan, plane, key),
            name=(
                "vpn-gate-probe-send-"
                f"{plane.path.ifname}-{plane.path.ifindex}-{plane.target}"
            ),
            daemon=True,
        )
        try:
            worker.start()
        except Exception as exc:
            with self._condition:
                self._in_flight.discard(key)
            self._publish_diagnostic_error(
                plan,
                plane,
                f"cannot start probe send worker: {exc}",
            )

    def _execute_send(
        self,
        plan: ProbeExecutionPlan,
        plane: PhysicalProbePlane,
        key: tuple[ProbeObservationGeneration, object, object, object],
    ) -> None:
        try:
            try:
                result = self._driver.execute_send(
                    plane.path,
                    plane.target,
                    timeout_seconds=self._timeout_seconds,
                )
            except Exception as exc:
                result = ProbeSendResult(
                    False,
                    f"probe send Driver raised: {exc}",
                )

            with self._condition:
                current = self._schedule.plan
                if current is None or current.generation != plan.generation:
                    return
                if plane not in current.planes:
                    return
                consumers = tuple(
                    channel
                    for channel in current.channels
                    if (
                        channel.mechanism is plane.mechanism
                        and channel.priority.path == plane.path
                        and channel.target == plane.target
                    )
                )

            if result.local_error is not None:
                self._publish_diagnostic_error(plan, plane, result.local_error)
                return

            self._publish_diagnostic_ready(plan, plane)
            if result.good_news:
                for channel in consumers:
                    try:
                        self._good_news_publisher.publish(
                            AvailabilityGoodNews(channel.priority)
                        )
                    except Exception:
                        _LOG.exception(
                            "availability good-news publisher raised "
                            "for channel %s",
                            channel.priority.channel_id,
                        )
        finally:
            with self._condition:
                self._in_flight.discard(key)

    @staticmethod
    def _in_flight_key(
        plan: ProbeExecutionPlan,
        plane: PhysicalProbePlane,
    ) -> tuple[ProbeObservationGeneration, object, object, object]:
        return (
            plan.generation,
            plane.mechanism,
            plane.path,
            plane.target,
        )

    def _publish_diagnostic_ready(
        self,
        plan: ProbeExecutionPlan,
        plane: PhysicalProbePlane,
    ) -> None:
        self._publish_diagnostic(
            plan,
            ProbeExecutionDiagnosticInfo(
                plan.generation,
                plane,
                ProbeExecutionHealth.READY,
            ),
        )

    def _publish_diagnostic_error(
        self,
        plan: ProbeExecutionPlan,
        plane: PhysicalProbePlane,
        diagnostic: str,
    ) -> None:
        self._publish_diagnostic(
            plan,
            ProbeExecutionDiagnosticInfo(
                plan.generation,
                plane,
                ProbeExecutionHealth.ERROR,
                diagnostic,
            ),
        )

    def _publish_diagnostic(
        self,
        plan: ProbeExecutionPlan,
        info: ProbeExecutionDiagnosticInfo,
    ) -> None:
        with self._diagnostic_publication_lock:
            with self._condition:
                current = self._schedule.plan
                if current is None or current.generation != plan.generation:
                    return
                if info.plane not in current.planes:
                    return

                key = (info.generation, info.plane)
                with self._diagnostic_lock:
                    if self._latest_diagnostic.get(key) == info:
                        return
                    self._latest_diagnostic[key] = info

            try:
                self._diagnostic_publisher.publish(info)
            except Exception:
                with self._diagnostic_lock:
                    if self._latest_diagnostic.get(key) == info:
                        self._latest_diagnostic.pop(key, None)
                _LOG.exception(
                    "probe execution diagnostic publisher raised "
                    "for %s/%s",
                    info.plane.path.ifname,
                    info.plane.target,
                )

    def _take_stale_diagnostics_locked(
        self,
        plan: ProbeExecutionPlan | None,
    ) -> tuple[ProbeExecutionDiagnosticInfo, ...]:
        with self._diagnostic_lock:
            if plan is None:
                stale = tuple(self._latest_diagnostic.values())
                self._latest_diagnostic.clear()
            else:
                live = {
                    (plan.generation, plane)
                    for plane in plan.planes
                }
                stale = tuple(
                    info
                    for key, info in self._latest_diagnostic.items()
                    if key not in live
                )
                for key in tuple(self._latest_diagnostic):
                    if key not in live:
                        self._latest_diagnostic.pop(key, None)

        return tuple(
            ProbeExecutionDiagnosticInfo(
                info.generation,
                info.plane,
                ProbeExecutionHealth.INACTIVE,
            )
            for info in stale
        )

    def _publish_inactive_diagnostics(
        self,
        items: tuple[ProbeExecutionDiagnosticInfo, ...],
    ) -> None:
        if not items:
            return
        with self._diagnostic_publication_lock:
            for info in items:
                try:
                    self._diagnostic_publisher.publish(info)
                except Exception:
                    _LOG.exception(
                        "inactive probe diagnostic publisher raised "
                        "for %s/%s",
                        info.plane.path.ifname,
                        info.plane.target,
                    )
