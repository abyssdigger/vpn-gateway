from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rou.controller_stop import (
    ControllerStopStatus,
    stop_controller_once,
)
from rou.forwarding_gate import (
    ForwardingGateExecutionResult,
    ForwardingGateExecutionStatus,
    ForwardingGateState,
)


CONTAINED = ForwardingGateExecutionResult(
    status=ForwardingGateExecutionStatus.SUCCESS,
    desired=ForwardingGateState.DISABLED,
    initial=ForwardingGateState.ENABLED,
    final=ForwardingGateState.DISABLED,
    mutation_attempted=True,
)

UNCONTAINED = ForwardingGateExecutionResult(
    status=ForwardingGateExecutionStatus.POSTCONDITION_FAILED,
    desired=ForwardingGateState.DISABLED,
    initial=ForwardingGateState.ENABLED,
    final=ForwardingGateState.ENABLED,
    mutation_attempted=True,
    diagnostic="still enabled",
)


class FakeLock:
    def __init__(self, *, acquired=True, release_error=None):
        self._acquired = acquired
        self.release_error = release_error
        self.release_count = 0

    @property
    def acquired(self):
        return self._acquired

    def release(self):
        self.release_count += 1
        self._acquired = False
        if self.release_error is not None:
            raise self.release_error


class ControllerStopTests(unittest.TestCase):
    def session(self, lock=None):
        return SimpleNamespace(lock=lock or FakeLock())

    def run_stop(self, *, containment=CONTAINED, cleanup_error=None, lock=None):
        session = self.session(lock)
        events = []

        def converge(*args, **kwargs):
            events.append("contain")
            return containment

        def destroy(*args, **kwargs):
            events.append("destroy")
            if cleanup_error is not None:
                raise cleanup_error

        original_release = session.lock.release

        def release():
            events.append("release")
            return original_release()

        session.lock.release = release

        with (
            patch(
                "rou.controller_stop.converge_forwarding_gate_once",
                side_effect=converge,
            ),
            patch(
                "rou.controller_stop.destroy_managed_network_domain",
                side_effect=destroy,
            ),
        ):
            result = stop_controller_once(
                session,
                SimpleNamespace(namespace="vg-test"),
                object(),
            )

        return result, session.lock, events

    def test_success_contains_then_destroys_then_releases_lock(self):
        result, lock, events = self.run_stop()

        self.assertEqual(result.status, ControllerStopStatus.STOPPED)
        self.assertTrue(result.stopped)
        self.assertEqual(events, ["contain", "destroy", "release"])
        self.assertFalse(lock.acquired)
        self.assertEqual(lock.release_count, 1)

    def test_failed_containment_does_not_suppress_stronger_cleanup(self):
        result, lock, events = self.run_stop(containment=UNCONTAINED)

        self.assertEqual(result.status, ControllerStopStatus.STOPPED)
        self.assertEqual(events, ["contain", "destroy", "release"])
        self.assertFalse(lock.acquired)
        self.assertFalse(result.containment.confirmed)

    def test_cleanup_failure_with_confirmed_containment_retains_lock(self):
        result, lock, events = self.run_stop(
            cleanup_error=RuntimeError("namespace remains"),
        )

        self.assertEqual(
            result.status,
            ControllerStopStatus.CLEANUP_FAILED_CONTAINED,
        )
        self.assertEqual(events, ["contain", "destroy"])
        self.assertTrue(lock.acquired)
        self.assertEqual(lock.release_count, 0)
        self.assertIn("namespace remains", result.cleanup_error)

    def test_cleanup_failure_without_containment_retains_lock_and_is_distinct(self):
        result, lock, events = self.run_stop(
            containment=UNCONTAINED,
            cleanup_error=RuntimeError("delete failed"),
        )

        self.assertEqual(
            result.status,
            ControllerStopStatus.CLEANUP_FAILED_UNCONTAINED,
        )
        self.assertEqual(events, ["contain", "destroy"])
        self.assertTrue(lock.acquired)
        self.assertFalse(result.containment.confirmed)

    def test_released_session_is_rejected_before_cleanup(self):
        session = self.session(FakeLock(acquired=False))
        with (
            patch("rou.controller_stop.converge_forwarding_gate_once") as converge,
            patch("rou.controller_stop.destroy_managed_network_domain") as destroy,
        ):
            with self.assertRaisesRegex(ValueError, "still-acquired"):
                stop_controller_once(
                    session,
                    SimpleNamespace(namespace="vg-test"),
                    object(),
                )

        converge.assert_not_called()
        destroy.assert_not_called()

    def test_lock_release_failure_is_observable_after_cleanup(self):
        result, lock, events = self.run_stop(
            lock=FakeLock(release_error=OSError("unlock failed")),
        )

        self.assertEqual(
            result.status,
            ControllerStopStatus.LOCK_RELEASE_FAILED,
        )
        self.assertEqual(events, ["contain", "destroy", "release"])
        self.assertFalse(lock.acquired)
        self.assertIn("unlock failed", result.lock_error)


if __name__ == "__main__":
    unittest.main()
