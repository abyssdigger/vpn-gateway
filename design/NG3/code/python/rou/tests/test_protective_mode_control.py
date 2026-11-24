from __future__ import annotations

from pathlib import Path
import tempfile
from threading import RLock
from time import monotonic, sleep
import unittest

from rou.protective_mode_control import (
    ProtectiveModeControlService,
    request_protective_control,
)
from rou.protective_mode_manager import (
    ProtectiveModeManager,
    ProtectiveModeStatus,
)
from rou.protective_payload_gate import (
    ProtectivePayloadGateObservation,
    ProtectivePayloadGateObservationStatus,
    ProtectivePayloadGateState,
)


class FakeDriver:
    def __init__(self):
        self.enabled = False
        self.boundary = None
        self.apply_calls = 0
        self.lock = RLock()

    def observe_protective_payload_gate(self, desired):
        with self.lock:
            if not self.enabled:
                return ProtectivePayloadGateObservation(
                    ProtectivePayloadGateObservationStatus.ABSENT
                )
            if (
                desired.state is ProtectivePayloadGateState.ENABLED
                and desired.boundary_interface == self.boundary
            ):
                return ProtectivePayloadGateObservation(
                    ProtectivePayloadGateObservationStatus.EXACT
                )
            return ProtectivePayloadGateObservation(
                ProtectivePayloadGateObservationStatus.OWNED_DRIFT
            )

    def apply_protective_payload_gate(self, desired, initial):
        with self.lock:
            self.apply_calls += 1
            self.enabled = (
                desired.state is ProtectivePayloadGateState.ENABLED
            )
            self.boundary = (
                desired.boundary_interface if self.enabled else None
            )

    def force_absent(self):
        with self.lock:
            self.enabled = False
            self.boundary = None


def wait_until(predicate, timeout=1.0):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


class ProtectiveModeControlServiceTests(unittest.TestCase):
    def test_control_periodic_repair_and_safe_leave(self):
        with tempfile.TemporaryDirectory() as root:
            socket_path = Path(root) / "control.sock"
            driver = FakeDriver()
            manager = ProtectiveModeManager()
            normal = {"ready": True}
            service = ProtectiveModeControlService(
                manager,
                driver,
                "stack0",
                lambda: normal["ready"],
                RLock(),
                socket_path=socket_path,
                audit_interval_seconds=0.05,
            )
            service.start()
            try:
                state = request_protective_control(socket_path, "status")
                self.assertTrue(state["ok"])
                self.assertEqual(
                    state["protective"]["status"],
                    ProtectiveModeStatus.INACTIVE.value,
                )

                entered = request_protective_control(
                    socket_path,
                    "active",
                    source="operator",
                )
                self.assertTrue(entered["ok"])
                self.assertTrue(driver.enabled)

                driver.force_absent()
                wait_until(lambda: driver.enabled)
                self.assertGreaterEqual(driver.apply_calls, 2)

                normal["ready"] = False
                blocked = request_protective_control(
                    socket_path,
                    "inactive",
                    source="operator",
                )
                self.assertFalse(blocked["ok"])
                self.assertEqual(
                    blocked["protective"]["status"],
                    ProtectiveModeStatus.ACTIVE.value,
                )
                self.assertEqual(
                    blocked["protective"]["request_sources"],
                    [],
                )
                self.assertTrue(driver.enabled)

                normal["ready"] = True
                wait_until(
                    lambda: (
                        request_protective_control(
                            socket_path, "status"
                        )["protective"]["status"]
                        == ProtectiveModeStatus.INACTIVE.value
                    )
                )
                self.assertFalse(driver.enabled)
            finally:
                service.stop()

            self.assertFalse(socket_path.exists())

    def test_source_scoping_survives_control_surface(self):
        with tempfile.TemporaryDirectory() as root:
            socket_path = Path(root) / "control.sock"
            driver = FakeDriver()
            manager = ProtectiveModeManager()
            service = ProtectiveModeControlService(
                manager,
                driver,
                "stack0",
                lambda: True,
                RLock(),
                socket_path=socket_path,
                audit_interval_seconds=0.05,
            )
            service.start()
            try:
                self.assertTrue(
                    request_protective_control(
                        socket_path, "active", source="operator"
                    )["ok"]
                )
                self.assertTrue(
                    request_protective_control(
                        socket_path, "active", source="automation:qa"
                    )["ok"]
                )
                remaining = request_protective_control(
                    socket_path,
                    "inactive",
                    source="operator",
                )
                self.assertFalse(remaining["ok"])
                self.assertEqual(
                    remaining["protective"]["request_sources"],
                    ["automation:qa"],
                )
                self.assertTrue(driver.enabled)
                final = request_protective_control(
                    socket_path,
                    "inactive",
                    source="automation:qa",
                )
                self.assertTrue(final["ok"])
                self.assertFalse(driver.enabled)
            finally:
                service.stop()


if __name__ == "__main__":
    unittest.main()
