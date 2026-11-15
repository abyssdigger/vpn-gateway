from ipaddress import IPv4Address
from threading import Event
import time
import unittest

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
    LogicalProbeWindow,
    PhysicalProbePlane,
    ProbeExecutionPlan,
)


A = InterfaceIdentity("vpns00", 10)
TARGET = IPv4Address("203.0.113.24")


def plane(interval=10.0):
    return PhysicalProbePlane(
        ProbeMechanism.ICMP,
        A,
        TARGET,
        interval,
    )


def plan(sequence=1, *, plane_interval=10.0, window_interval=10.0):
    return ProbeExecutionPlan(
        ProbeObservationGeneration(sequence),
        (plane(plane_interval),),
        (LogicalProbeWindow("primary", window_interval),),
    )


class RecordingPublisher:
    def __init__(self, kind, shared=None):
        self.kind = kind
        self.events = []
        self.shared = shared

    def publish(self, info):
        self.events.append(info)
        if self.shared is not None:
            self.shared.append((self.kind, info))


class FakeDriver:
    def __init__(self):
        self.outcome = ProbeAttemptOutcome.NO_REPLY
        self.diagnostic = None
        self.calls = []
        self.entered = Event()
        self.release = Event()
        self.block = False

    def execute_send(self, path, target, *, timeout_seconds):
        self.calls.append((path, target, timeout_seconds))
        self.entered.set()
        if self.block:
            self.release.wait(timeout=2)
        if self.outcome is ProbeAttemptOutcome.ERROR:
            return ProbeSendResult(
                False,
                self.diagnostic or "local failure",
            )
        return ProbeSendResult(
            self.outcome is ProbeAttemptOutcome.REPLY,
        )


class FakeDiagnosticDriver:
    def __init__(self, result):
        self.result = result

    def execute(self, path, target, *, timeout_seconds):
        return self.result


class DiagnosticPingSendAdapterTests(unittest.TestCase):
    def test_reply_maps_to_good_news_without_attempt_type_leak(self):
        adapter = LinuxDiagnosticPingSendAdapter(
            FakeDiagnosticDriver(ProbeAttemptResult(ProbeAttemptOutcome.REPLY))
        )

        result = adapter.execute_send(A, TARGET, timeout_seconds=1)

        self.assertEqual(result, ProbeSendResult(True))

    def test_no_reply_collapses_to_plain_absence_of_good_news(self):
        adapter = LinuxDiagnosticPingSendAdapter(
            FakeDiagnosticDriver(ProbeAttemptResult(ProbeAttemptOutcome.NO_REPLY))
        )

        result = adapter.execute_send(A, TARGET, timeout_seconds=1)

        self.assertEqual(result, ProbeSendResult(False))

    def test_error_maps_only_to_local_diagnostic(self):
        adapter = LinuxDiagnosticPingSendAdapter(
            FakeDiagnosticDriver(
                ProbeAttemptResult(ProbeAttemptOutcome.ERROR, "exec failed")
            )
        )

        result = adapter.execute_send(A, TARGET, timeout_seconds=1)

        self.assertEqual(result, ProbeSendResult(False, "exec failed"))


class ProbeExecutionScheduleTests(unittest.TestCase):
    def test_activation_sends_immediately_without_closing_empty_window(self):
        schedule = ProbeExecutionSchedule()
        schedule.reconcile(plan(), 100.0)

        boundaries, sends = schedule.pop_due(100.0)

        self.assertEqual(boundaries, ())
        self.assertEqual(sends, (plane(),))

    def test_coincident_deadline_returns_boundary_before_next_send_phase(self):
        schedule = ProbeExecutionSchedule()
        schedule.reconcile(plan(), 100.0)
        schedule.pop_due(100.0)

        boundaries, sends = schedule.pop_due(110.0)

        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0].probe_id, "primary")
        self.assertEqual(sends, (plane(),))

    def test_delayed_scheduler_closes_all_elapsed_windows_but_does_not_burst_sends(self):
        schedule = ProbeExecutionSchedule()
        schedule.reconcile(plan(), 100.0)
        schedule.pop_due(100.0)

        boundaries, sends = schedule.pop_due(135.0)

        self.assertEqual(len(boundaries), 3)
        self.assertEqual(sends, (plane(),))
        self.assertEqual(schedule.next_deadline(), 140.0)

    def test_same_generation_unchanged_cadence_preserves_phase(self):
        schedule = ProbeExecutionSchedule()
        first = plan()
        schedule.reconcile(first, 100.0)
        schedule.pop_due(100.0)

        schedule.reconcile(first, 105.0)

        self.assertEqual(schedule.next_deadline(), 110.0)

    def test_same_generation_changed_cadence_restarts_only_changed_phase(self):
        schedule = ProbeExecutionSchedule()
        schedule.reconcile(plan(), 100.0)
        schedule.pop_due(100.0)

        schedule.reconcile(
            plan(plane_interval=20.0, window_interval=30.0),
            105.0,
        )

        boundaries, sends = schedule.pop_due(105.0)
        self.assertEqual(boundaries, ())
        self.assertEqual(sends, (plane(20.0),))
        self.assertEqual(schedule.next_deadline(), 125.0)

    def test_new_generation_restarts_windows_and_sends_immediately(self):
        schedule = ProbeExecutionSchedule()
        schedule.reconcile(plan(1), 100.0)
        schedule.pop_due(100.0)

        schedule.reconcile(plan(2), 105.0)
        boundaries, sends = schedule.pop_due(105.0)

        self.assertEqual(boundaries, ())
        self.assertEqual(sends, (plane(),))
        self.assertEqual(schedule.next_deadline(), 115.0)


class LinuxProbeExecutionAgentTests(unittest.TestCase):
    def setUp(self):
        self.driver = FakeDriver()
        self.order = []
        self.good = RecordingPublisher("good", self.order)
        self.boundary = RecordingPublisher("boundary", self.order)
        self.diagnostic = RecordingPublisher("diagnostic", self.order)
        self.agent = LinuxProbeExecutionAgent(
            self.driver,
            self.good,
            self.boundary,
            self.diagnostic,
            timeout_seconds=2,
            clock=lambda: 100.0,
        )

    def wait_for_calls(self, count):
        deadline = time.monotonic() + 2
        while len(self.driver.calls) < count and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertGreaterEqual(len(self.driver.calls), count)

    def wait_for_events(self, publisher, count):
        deadline = time.monotonic() + 2
        while len(publisher.events) < count and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertGreaterEqual(len(publisher.events), count)

    def test_reply_publishes_good_news_and_local_ready_diagnostic(self):
        self.driver.outcome = ProbeAttemptOutcome.REPLY
        self.agent.update_plan(plan())
        self.agent.process_due(100.0)

        self.wait_for_events(self.good, 1)
        self.wait_for_events(self.diagnostic, 1)

        self.assertEqual(self.good.events[0].generation.sequence, 1)
        self.assertIs(
            self.diagnostic.events[0].health,
            ProbeExecutionHealth.READY,
        )

    def test_no_reply_never_becomes_production_good_news_or_negative_event(self):
        self.driver.outcome = ProbeAttemptOutcome.NO_REPLY
        self.agent.update_plan(plan())
        self.agent.process_due(100.0)

        self.wait_for_calls(1)
        self.wait_for_events(self.diagnostic, 1)

        self.assertEqual(self.good.events, [])
        self.assertEqual(self.boundary.events, [])
        self.assertIs(
            self.diagnostic.events[0].health,
            ProbeExecutionHealth.READY,
        )

    def test_local_error_is_diagnostic_only_and_deduplicated(self):
        self.driver.outcome = ProbeAttemptOutcome.ERROR
        self.driver.diagnostic = "exec failed"
        self.agent.update_plan(plan())

        self.agent.process_due(100.0)
        self.wait_for_events(self.diagnostic, 1)
        self.agent.process_due(110.0)
        self.wait_for_calls(2)
        time.sleep(0.02)

        self.assertEqual(self.good.events, [])
        self.assertEqual(len(self.diagnostic.events), 1)
        self.assertIs(
            self.diagnostic.events[0].health,
            ProbeExecutionHealth.ERROR,
        )

    def test_successful_local_execution_clears_previous_error(self):
        self.driver.outcome = ProbeAttemptOutcome.ERROR
        self.agent.update_plan(plan())
        self.agent.process_due(100.0)
        self.wait_for_events(self.diagnostic, 1)

        self.driver.outcome = ProbeAttemptOutcome.NO_REPLY
        self.agent.process_due(110.0)
        self.wait_for_events(self.diagnostic, 2)

        self.assertIs(
            self.diagnostic.events[-1].health,
            ProbeExecutionHealth.READY,
        )

    def test_boundary_is_published_before_send_is_launched_at_same_deadline(self):
        self.driver.outcome = ProbeAttemptOutcome.REPLY
        self.agent.update_plan(plan())
        self.agent.process_due(100.0)
        self.wait_for_events(self.good, 1)
        self.order.clear()

        self.agent.process_due(110.0)
        self.wait_for_events(self.good, 2)

        self.assertEqual(self.order[0][0], "boundary")

    def test_old_generation_worker_result_is_dropped_after_plan_change(self):
        self.driver.outcome = ProbeAttemptOutcome.REPLY
        self.driver.block = True
        self.agent.update_plan(plan(1))
        self.agent.process_due(100.0)
        self.assertTrue(self.driver.entered.wait(timeout=2))

        self.agent.update_plan(plan(2))
        self.driver.release.set()
        time.sleep(0.02)

        self.assertEqual(self.good.events, [])
        self.assertEqual(self.diagnostic.events, [])

    def test_stop_quiesces_schedule_and_is_idempotent(self):
        self.agent.update_plan(plan())
        self.agent.stop()
        self.agent.stop()

        self.agent.process_due(100.0)

        self.assertEqual(self.driver.calls, [])


if __name__ == "__main__":
    unittest.main()
