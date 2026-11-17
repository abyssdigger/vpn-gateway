from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rou.controller_restart import (
    ControllerRestartStatus,
    restart_controller_once,
)


class ControllerRestartTests(unittest.TestCase):
    def call_restart(self, stop_result, start_result):
        with (
            patch(
                "rou.controller_restart.stop_controller_once",
                return_value=stop_result,
            ) as stop_mock,
            patch(
                "rou.controller_restart.start_controller_once",
                return_value=start_result,
            ) as start_mock,
        ):
            result = restart_controller_once(
                object(),
                object(),
                object(),
                object(),
                object(),
                lambda: object(),
            )
        return result, stop_mock, start_mock

    def test_stop_failure_blocks_start(self):
        stop = SimpleNamespace(stopped=False)
        start = SimpleNamespace(ready=True, session=object())

        result, stop_mock, start_mock = self.call_restart(stop, start)

        self.assertEqual(
            result.status,
            ControllerRestartStatus.STOP_FAILED,
        )
        self.assertIs(result.stop, stop)
        self.assertIsNone(result.start)
        self.assertFalse(result.ready)
        self.assertIsNone(result.session)
        stop_mock.assert_called_once()
        start_mock.assert_not_called()

    def test_successful_stop_then_ready_start_returns_new_session(self):
        new_session = object()
        stop = SimpleNamespace(stopped=True)
        start = SimpleNamespace(ready=True, session=new_session)

        result, stop_mock, start_mock = self.call_restart(stop, start)

        self.assertEqual(result.status, ControllerRestartStatus.READY)
        self.assertTrue(result.ready)
        self.assertIs(result.start, start)
        self.assertIs(result.session, new_session)
        stop_mock.assert_called_once()
        start_mock.assert_called_once()

    def test_start_failure_is_preserved_without_restart_retry(self):
        stop = SimpleNamespace(stopped=True)
        start = SimpleNamespace(ready=False, session=None)

        result, stop_mock, start_mock = self.call_restart(stop, start)

        self.assertEqual(
            result.status,
            ControllerRestartStatus.START_FAILED,
        )
        self.assertIs(result.stop, stop)
        self.assertIs(result.start, start)
        self.assertFalse(result.ready)
        self.assertIsNone(result.session)
        stop_mock.assert_called_once()
        start_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
