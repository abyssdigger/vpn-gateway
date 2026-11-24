from __future__ import annotations

import unittest

from rou.protective_mode_manager import (
    ProtectiveModeActionStatus,
    ProtectiveModeManager,
    ProtectiveModeStatus,
)
from rou.protective_payload_gate import (
    ProtectivePayloadGateObservation,
    ProtectivePayloadGateObservationStatus,
)


class FakeDriver:
    def __init__(self, observations, *, apply_errors=()):
        self.observations = list(observations)
        self.apply_errors = list(apply_errors)
        self.apply_calls = []

    def observe_protective_payload_gate(self, desired):
        value = self.observations.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def apply_protective_payload_gate(self, desired, initial):
        self.apply_calls.append((desired, initial))
        if self.apply_errors:
            value = self.apply_errors.pop(0)
            if value is not None:
                raise value


def exact():
    return ProtectivePayloadGateObservation(
        ProtectivePayloadGateObservationStatus.EXACT
    )


def absent():
    return ProtectivePayloadGateObservation(
        ProtectivePayloadGateObservationStatus.ABSENT
    )


def drift():
    return ProtectivePayloadGateObservation(
        ProtectivePayloadGateObservationStatus.OWNED_DRIFT
    )


def conflict():
    return ProtectivePayloadGateObservation(
        ProtectivePayloadGateObservationStatus.CONFLICT,
        "conflict",
    )


class ProtectiveModeManagerTests(unittest.TestCase):
    def test_sources_cannot_clear_each_other(self):
        manager = ProtectiveModeManager()
        driver = FakeDriver((exact(), exact(), exact(), exact(), exact(), exact()))

        first = manager.request_active("operator", "stack0", driver)
        second = manager.request_active("aggressive", "stack0", driver)
        remaining = manager.request_inactive(
            "operator",
            "stack0",
            normal_release_confirmed=True,
            driver=driver,
        )

        self.assertTrue(first.confirmed_active)
        self.assertTrue(second.confirmed_active)
        self.assertTrue(remaining.confirmed_active)
        self.assertEqual(
            remaining.projection.request_sources,
            frozenset({"aggressive"}),
        )

    def test_final_source_cannot_release_without_normal_precondition(self):
        manager = ProtectiveModeManager()
        driver = FakeDriver((exact(), exact(), exact(), exact()))
        manager.request_active("operator", "stack0", driver)

        result = manager.request_inactive(
            "operator",
            "stack0",
            normal_release_confirmed=False,
            driver=driver,
        )
        self.assertEqual(
            result.action_status,
            ProtectiveModeActionStatus.LEAVE_BLOCKED,
        )
        self.assertEqual(result.projection.status, ProtectiveModeStatus.ACTIVE)
        self.assertEqual(result.projection.request_sources, frozenset())

    def test_confirmed_final_release_disables_gate(self):
        manager = ProtectiveModeManager()
        driver = FakeDriver((exact(), exact(), drift(), absent()))
        manager.request_active("operator", "stack0", driver)
        result = manager.request_inactive(
            "operator",
            "stack0",
            normal_release_confirmed=True,
            driver=driver,
        )
        self.assertEqual(
            result.action_status,
            ProtectiveModeActionStatus.INACTIVE_CONFIRMED,
        )
        self.assertTrue(result.confirmed_inactive)

    def test_failed_release_recloses_before_returning_problem(self):
        manager = ProtectiveModeManager()
        driver = FakeDriver(
            (
                exact(),
                exact(),
                drift(),
                drift(),
                exact(),
                exact(),
            ),
            apply_errors=(RuntimeError("delete failed"),),
        )
        manager.request_active("operator", "stack0", driver)
        result = manager.request_inactive(
            "operator",
            "stack0",
            normal_release_confirmed=True,
            driver=driver,
        )
        self.assertEqual(
            result.action_status,
            ProtectiveModeActionStatus.LEAVE_FAILED_RECONTAINED,
        )
        self.assertEqual(result.projection.status, ProtectiveModeStatus.ACTIVE)

    def test_unconfirmed_recontainment_is_explicit_safety_failure(self):
        manager = ProtectiveModeManager()
        driver = FakeDriver(
            (
                exact(),
                exact(),
                drift(),
                drift(),
                conflict(),
            ),
            apply_errors=(RuntimeError("delete failed"),),
        )
        manager.request_active("operator", "stack0", driver)
        result = manager.request_inactive(
            "operator",
            "stack0",
            normal_release_confirmed=True,
            driver=driver,
        )
        self.assertEqual(
            result.action_status,
            ProtectiveModeActionStatus.SAFETY_RECLOSE_FAILED,
        )
        self.assertEqual(result.projection.status, ProtectiveModeStatus.PROBLEM)


if __name__ == "__main__":
    unittest.main()
