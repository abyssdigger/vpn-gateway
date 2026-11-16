from ipaddress import IPv4Address
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import CommandResult
from rou.device_engine import DeviceBindingState
from rou.domain import ActiveConfig
from rou.nat_state import ExplicitNoNatProvider
from rou.planner import PlannerProjection, PlannerResult, PlannerRuntimeState
from rou.runtime import RuntimeLoopConfig, run_runtime_loop
from rou.state_store import StateLoadResult


class FakeHostBackend:
    def __init__(self):
        self.calls = []

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append(argv)
        return CommandResult(argv, 0, "", "")


class FakeStore:
    def __init__(self):
        self.state = PlannerRuntimeState.empty()
        self.saved = []

    def load(self, config):
        return StateLoadResult(self.state, 0)

    def save(self, state):
        self.saved.append(state)
        self.state = state


class FakeWakeups:
    def __init__(self, result=False, fail=None):
        self.result = result
        self.fail = fail
        self.calls = 0

    def wait(self, timeout):
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return self.result


def dummy_projection():
    return PlannerProjection(
        device_state=DeviceBindingState.empty(),
        bindings=None,
        metrics=None,
        allocation=None,
        kernel=None,
        firewall=None,
        nat=None,
    )


class RuntimeLoopTests(unittest.TestCase):
    def test_initial_reconcile_and_metric_promotion_do_not_wait(self):
        backend = FakeHostBackend()
        store = FakeStore()
        wakeups = FakeWakeups()
        reconciles = 0
        results = [
            PlannerResult(
                PlannerRuntimeState.empty(),
                dummy_projection(),
                False,
                True,
            ),
            PlannerResult(
                PlannerRuntimeState.empty(),
                dummy_projection(),
                False,
                False,
            ),
        ]

        def fake_reconcile(*args, **kwargs):
            nonlocal reconciles
            result = results[reconciles]
            reconciles += 1
            return result

        with patch("rou.runtime.reconcile_once", side_effect=fake_reconcile):
            result = run_runtime_loop(
                ActiveConfig({}, {}),
                "rou0",
                backend,
                ExplicitNoNatProvider(),
                store,
                wakeups,
                loop_config=RuntimeLoopConfig(
                    retry_delay_seconds=0,
                    audit_interval_seconds=10,
                ),
                should_stop=lambda: reconciles >= 2,
            )

        self.assertEqual(result.reconciliations, 2)
        self.assertEqual(wakeups.calls, 0)

    def test_wakeup_exception_propagates_and_finally_closes_forwarding(self):
        backend = FakeHostBackend()
        store = FakeStore()
        wakeups = FakeWakeups(fail=RuntimeError("monitor died"))
        reconciles = 0

        def fake_reconcile(*args, **kwargs):
            nonlocal reconciles
            reconciles += 1
            return PlannerResult(
                PlannerRuntimeState.empty(),
                dummy_projection(),
                False,
                False,
            )

        with patch("rou.runtime.reconcile_once", side_effect=fake_reconcile):
            with self.assertRaisesRegex(RuntimeError, "monitor died"):
                run_runtime_loop(
                    ActiveConfig({}, {}),
                    "rou0",
                    backend,
                    ExplicitNoNatProvider(),
                    store,
                    wakeups,
                    loop_config=RuntimeLoopConfig(
                        retry_delay_seconds=0,
                        audit_interval_seconds=10,
                    ),
                )

        close_commands = [
            argv
            for argv in backend.calls
            if "net.ipv4.ip_forward=0" in argv
        ]
        self.assertGreaterEqual(len(close_commands), 2)

    def test_service_health_failure_escapes_and_closes_forwarding(self):
        backend = FakeHostBackend()
        store = FakeStore()
        wakeups = FakeWakeups()

        def fail_health():
            raise RuntimeError("publication worker died")

        with self.assertRaisesRegex(RuntimeError, "publication worker died"):
            run_runtime_loop(
                ActiveConfig({}, {}),
                "rou0",
                backend,
                ExplicitNoNatProvider(),
                store,
                wakeups,
                loop_config=RuntimeLoopConfig(
                    retry_delay_seconds=0,
                    audit_interval_seconds=10,
                ),
                health_check=fail_health,
            )

        close_commands = [
            argv
            for argv in backend.calls
            if "net.ipv4.ip_forward=0" in argv
        ]
        self.assertGreaterEqual(len(close_commands), 2)


    def test_local_publication_address_is_forwarded_to_planner(self):
        backend = FakeHostBackend()
        store = FakeStore()
        wakeups = FakeWakeups()
        reconciles = 0
        seen = []

        def fake_reconcile(*args, **kwargs):
            nonlocal reconciles
            reconciles += 1
            seen.append(kwargs.get("local_publication_address"))
            return PlannerResult(
                PlannerRuntimeState.empty(),
                dummy_projection(),
                False,
                False,
            )

        address = IPv4Address("192.0.2.2")
        with patch("rou.runtime.reconcile_once", side_effect=fake_reconcile):
            run_runtime_loop(
                ActiveConfig({}, {}),
                "rou0",
                backend,
                ExplicitNoNatProvider(),
                store,
                wakeups,
                loop_config=RuntimeLoopConfig(
                    retry_delay_seconds=0,
                    audit_interval_seconds=10,
                ),
                should_stop=lambda: reconciles >= 1,
                local_publication_address=address,
            )

        self.assertEqual(seen, [address])

    def test_normal_stop_closes_forwarding(self):
        backend = FakeHostBackend()
        store = FakeStore()
        wakeups = FakeWakeups()
        reconciles = 0

        def fake_reconcile(*args, **kwargs):
            nonlocal reconciles
            reconciles += 1
            return PlannerResult(
                PlannerRuntimeState.empty(),
                dummy_projection(),
                False,
                False,
            )

        with patch("rou.runtime.reconcile_once", side_effect=fake_reconcile):
            result = run_runtime_loop(
                ActiveConfig({}, {}),
                "rou0",
                backend,
                ExplicitNoNatProvider(),
                store,
                wakeups,
                loop_config=RuntimeLoopConfig(
                    retry_delay_seconds=0,
                    audit_interval_seconds=10,
                ),
                should_stop=lambda: reconciles >= 1,
            )

        self.assertEqual(result.reconciliations, 1)
        self.assertTrue(
            "net.ipv4.ip_forward=0" in backend.calls[-1]
        )


if __name__ == "__main__":
    unittest.main()
