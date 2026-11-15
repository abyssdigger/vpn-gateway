from ipaddress import IPv4Address
from threading import Event
import time
import unittest

from rou.availability_collector import (
    AvailabilityHysteresisPolicy,
    AvailabilityPriorityChannel,
)
from rou.availability_probe_state import ProbeObservationGeneration
from rou.interface_identity import InterfaceIdentity
from rou.linux_probe_execution import (
    LinuxDiagnosticPingSendAdapter,
    LinuxProbeExecutionAgent,
    ProbeExecutionHealth,
    ProbeExecutionSchedule,
    ProbeSendResult,
)
from rou.probe_attempt import ProbeAttemptOutcome, ProbeAttemptResult
from rou.probe_rules import ProbeMechanism
from rou.probe_transport import (
    LogicalProbeChannel,
    PhysicalProbePlane,
    ProbeExecutionPlan,
)


A = InterfaceIdentity("vpns00", 10)
TARGET = IPv4Address("203.0.113.24")
HYSTERESIS = AvailabilityHysteresisPolicy(3, 2)


def channel(
    channel_id="primary",
    *,
    interval=10,
    hysteresis=HYSTERESIS,
):
    return LogicalProbeChannel(
        AvailabilityPriorityChannel(
            channel_id,
            A,
            True,
            hysteresis,
        ),
        ProbeMechanism.ICMP,
        TARGET,
        interval,
    )


def plane(interval=10.0):
    return PhysicalProbePlane(
        ProbeMechanism.ICMP,
        A,
        TARGET,
        interval,
    )


def plan(
    sequence=1,
    *,
    interval=10,
    hysteresis=HYSTERESIS,
    plane_interval=10.0,
):
    return ProbeExecutionPlan(
        ProbeObservationGeneration(sequence),
        (plane(plane_interval),),
        (channel(interval=interval, hysteresis=hysteresis),),
    )


class RecordingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, info):
        self.events.append(info)


class RaisingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, info):
        self.events.append(info)
        raise RuntimeError("publisher boom")


class FailOncePublisher:
    def __init__(self):
        self.events = []
        self.failed = False

    def publish(self, info):
        if not self.failed:
            self.failed = True
            raise RuntimeError("publisher boom")
        self.events.append(info)


class SelectiveGoodNewsPublisher:
    def __init__(self, failing_channel):
        self.failing_channel = failing_channel
        self.events = []

    def publish(self, info):
        if info.channel.channel_id == self.failing_channel:
            raise RuntimeError("publisher boom")
        self.events.append(info)


class FakeDriver:
    def __init__(self):
        self.result = ProbeSendResult(False)
        self.calls = []
        self.entered = Event()
        self.release = Event()
        self.block = False
        self.raise_error = None

    def execute_send(self, path, target, *, timeout_seconds):
        self.calls.append((path, target, timeout_seconds))
        self.entered.set()
        if self.block:
            self.release.wait(timeout=2)
        if self.raise_error:
            raise RuntimeError(self.raise_error)
        return self.result


class FakeDiagnosticDriver:
    def __init__(self, result):
        self.result = result

    def execute(self, path, target, *, timeout_seconds):
        return self.result


class DiagnosticPingAdapterTests(unittest.TestCase):
    def test_historical_outcomes_collapse_to_good_news_or_local_error(self):
        reply = LinuxDiagnosticPingSendAdapter(
            FakeDiagnosticDriver(ProbeAttemptResult(ProbeAttemptOutcome.REPLY))
        )
        no_reply = LinuxDiagnosticPingSendAdapter(
            FakeDiagnosticDriver(ProbeAttemptResult(ProbeAttemptOutcome.NO_REPLY))
        )
        error = LinuxDiagnosticPingSendAdapter(
            FakeDiagnosticDriver(
                ProbeAttemptResult(ProbeAttemptOutcome.ERROR, "exec failed")
            )
        )

        self.assertEqual(
            reply.execute_send(A, TARGET, timeout_seconds=1),
            ProbeSendResult(True),
        )
        self.assertEqual(
            no_reply.execute_send(A, TARGET, timeout_seconds=1),
            ProbeSendResult(False),
        )
        self.assertEqual(
            error.execute_send(A, TARGET, timeout_seconds=1),
            ProbeSendResult(False, "exec failed"),
        )


class ProbeExecutionScheduleTests(unittest.TestCase):
    def test_activation_sends_immediately_and_ticks_after_interval(self):
        schedule = ProbeExecutionSchedule()
        schedule.reconcile(plan(), 100.0)

        ticks, sends = schedule.pop_due(100.0)
        self.assertEqual(ticks, ())
        self.assertEqual(sends, (plane(),))

        ticks, sends = schedule.pop_due(110.0)
        self.assertEqual(
            [item.channel.channel_id for item in ticks],
            ["primary"],
        )
        self.assertEqual(sends, (plane(),))

    def test_delayed_scheduler_emits_one_tick_not_elapsed_count(self):
        schedule = ProbeExecutionSchedule()
        schedule.reconcile(plan(), 100.0)
        schedule.pop_due(100.0)

        ticks, sends = schedule.pop_due(135.0)

        self.assertEqual(len(ticks), 1)
        self.assertEqual(sends, (plane(),))
        self.assertEqual(schedule.next_deadline(), 140.0)

    def test_cadence_change_restarts_only_logical_tick_phase(self):
        schedule = ProbeExecutionSchedule()
        schedule.reconcile(plan(), 100.0)
        schedule.pop_due(100.0)

        schedule.reconcile(plan(interval=30), 105.0)

        ticks, sends = schedule.pop_due(110.0)
        self.assertEqual(ticks, ())
        self.assertEqual(sends, (plane(),))
        self.assertEqual(schedule.next_deadline(), 120.0)

    def test_hysteresis_change_does_not_change_tick_cadence(self):
        schedule = ProbeExecutionSchedule()
        schedule.reconcile(plan(), 100.0)
        schedule.pop_due(100.0)

        schedule.reconcile(
            plan(hysteresis=AvailabilityHysteresisPolicy(7, 4)),
            105.0,
        )

        ticks, sends = schedule.pop_due(110.0)

        self.assertEqual(len(ticks), 1)
        self.assertEqual(sends, (plane(),))

    def test_generation_change_restarts_send_immediately(self):
        schedule = ProbeExecutionSchedule()
        schedule.reconcile(plan(1), 100.0)
        schedule.pop_due(100.0)

        schedule.reconcile(plan(2), 105.0)
        ticks, sends = schedule.pop_due(105.0)

        self.assertEqual(ticks, ())
        self.assertEqual(sends, (plane(),))


class LinuxProbeExecutionAgentTests(unittest.TestCase):
    def setUp(self):
        self.driver = FakeDriver()
        self.good = RecordingPublisher()
        self.tick = RecordingPublisher()
        self.diag = RecordingPublisher()
        self.agent = LinuxProbeExecutionAgent(
            self.driver,
            self.good,
            self.tick,
            self.diag,
            timeout_seconds=2,
            clock=lambda: 100.0,
        )

    def wait_for(self, seq, count):
        deadline = time.monotonic() + 2
        while len(seq) < count and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertGreaterEqual(len(seq), count)

    def test_reply_fans_out_to_current_logical_consumers(self):
        second = channel(
            "second",
            interval=20,
            hysteresis=AvailabilityHysteresisPolicy(2, 3),
        )
        current = ProbeExecutionPlan(
            ProbeObservationGeneration(1),
            (plane(),),
            (channel(), second),
        )
        self.driver.result = ProbeSendResult(True)

        self.agent.update_plan(current)
        self.agent.process_due(100.0)
        self.wait_for(self.good.events, 2)

        self.assertEqual(
            {item.channel.channel_id for item in self.good.events},
            {"primary", "second"},
        )
        for item in self.good.events:
            self.assertFalse(hasattr(item.channel, "target"))
            self.assertFalse(hasattr(item.channel, "mechanism"))
            self.assertFalse(hasattr(item.channel, "interval_seconds"))

    def test_no_reply_is_not_an_availability_event(self):
        self.agent.update_plan(plan())
        self.agent.process_due(100.0)
        self.wait_for(self.diag.events, 1)

        self.assertEqual(self.good.events, [])
        self.assertIs(self.diag.events[-1].health, ProbeExecutionHealth.READY)

    def test_tick_is_published_as_one_logical_fact(self):
        self.agent.update_plan(plan())
        self.agent.process_due(100.0)

        self.agent.process_due(135.0)

        self.assertEqual(len(self.tick.events), 1)
        self.assertEqual(
            self.tick.events[0].channel.channel_id,
            "primary",
        )

    def test_slow_send_does_not_overlap_same_plane(self):
        self.driver.block = True
        self.agent.update_plan(plan())
        self.agent.process_due(100.0)
        self.assertTrue(self.driver.entered.wait(timeout=2))

        self.agent.process_due(110.0)
        self.wait_for(self.diag.events, 1)

        self.assertEqual(len(self.driver.calls), 1)
        self.assertIs(self.diag.events[-1].health, ProbeExecutionHealth.ERROR)
        self.assertIn("still in flight", self.diag.events[-1].diagnostic)
        self.driver.release.set()

    def test_old_generation_worker_result_is_dropped(self):
        self.driver.result = ProbeSendResult(True)
        self.driver.block = True
        self.agent.update_plan(plan(1))
        self.agent.process_due(100.0)
        self.assertTrue(self.driver.entered.wait(timeout=2))

        self.agent.update_plan(plan(2))
        self.driver.release.set()
        time.sleep(0.02)

        self.assertEqual(self.good.events, [])

    def test_plan_removal_invalidates_diagnostic_state(self):
        self.agent.update_plan(plan())
        self.agent.process_due(100.0)
        self.wait_for(self.diag.events, 1)

        self.agent.update_plan(None)

        self.assertIs(self.diag.events[-1].health, ProbeExecutionHealth.INACTIVE)

    def test_driver_exception_is_diagnostic_only(self):
        self.driver.raise_error = "boom"
        self.agent.update_plan(plan())
        self.agent.process_due(100.0)
        self.wait_for(self.diag.events, 1)

        self.assertEqual(self.good.events, [])
        self.assertIs(self.diag.events[-1].health, ProbeExecutionHealth.ERROR)

    def test_tick_publisher_exception_does_not_abort_due_processing(self):
        tick = RaisingPublisher()
        agent = LinuxProbeExecutionAgent(
            self.driver,
            self.good,
            tick,
            self.diag,
            timeout_seconds=2,
            clock=lambda: 100.0,
        )
        agent.update_plan(plan())
        agent.process_due(100.0)
        self.wait_for(self.driver.calls, 1)

        agent.process_due(110.0)
        self.wait_for(self.driver.calls, 2)

        self.assertEqual(len(tick.events), 1)

    def test_one_good_news_subscriber_failure_does_not_block_other_consumers(self):
        good = SelectiveGoodNewsPublisher("primary")
        agent = LinuxProbeExecutionAgent(
            self.driver,
            good,
            self.tick,
            self.diag,
            timeout_seconds=2,
            clock=lambda: 100.0,
        )
        second = channel(
            "second",
            interval=20,
            hysteresis=AvailabilityHysteresisPolicy(2, 3),
        )
        current = ProbeExecutionPlan(
            ProbeObservationGeneration(1),
            (plane(),),
            (channel(), second),
        )
        self.driver.result = ProbeSendResult(True)

        agent.update_plan(current)
        agent.process_due(100.0)
        self.wait_for(good.events, 1)

        self.assertEqual(
            [item.channel.channel_id for item in good.events],
            ["second"],
        )

    def test_diagnostic_publisher_failure_does_not_suppress_good_news(self):
        diag = RaisingPublisher()
        agent = LinuxProbeExecutionAgent(
            self.driver,
            self.good,
            self.tick,
            diag,
            timeout_seconds=2,
            clock=lambda: 100.0,
        )
        self.driver.result = ProbeSendResult(True)

        agent.update_plan(plan())
        agent.process_due(100.0)
        self.wait_for(self.good.events, 1)

        self.assertEqual(
            self.good.events[0].channel.channel_id,
            "primary",
        )

    def test_failed_diagnostic_publication_is_retryable(self):
        diag = FailOncePublisher()
        agent = LinuxProbeExecutionAgent(
            self.driver,
            self.good,
            self.tick,
            diag,
            timeout_seconds=2,
            clock=lambda: 100.0,
        )
        self.driver.result = ProbeSendResult(True)

        agent.update_plan(plan())
        agent.process_due(100.0)

        # Good news is emitted after the failed READY diagnostic publication,
        # so observing it proves the first worker advanced past that callback.
        self.wait_for(self.good.events, 1)

        # Allow the worker's finally block to release the in-flight slot before
        # scheduling the next physical send.
        deadline = time.monotonic() + 2
        while len(self.driver.calls) < 2 and time.monotonic() < deadline:
            agent.process_due(110.0)
            time.sleep(0.005)

        self.assertGreaterEqual(len(self.driver.calls), 2)
        self.wait_for(diag.events, 1)
        self.assertIs(diag.events[0].health, ProbeExecutionHealth.READY)

    def test_stop_is_idempotent_and_quiesces_schedule(self):
        self.agent.update_plan(plan())
        self.agent.stop()
        self.agent.stop()
        self.agent.process_due(100.0)

        self.assertEqual(self.driver.calls, [])


if __name__ == "__main__":
    unittest.main()
