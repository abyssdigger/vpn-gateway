from __future__ import annotations

import unittest

from rou.forwarding_gate import (
    ForwardingGateExecutionStatus,
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from rou.linux_forwarding_gate import (
    LinuxForwardingGateBackend,
    LinuxForwardingGateError,
)


class FakeBackend:
    def __init__(self, states, *, set_error=None):
        self.states = list(states)
        self.set_error = set_error
        self.set_calls = []

    def observe_forwarding_gate(self):
        value = self.states.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def set_forwarding_gate(self, desired):
        self.set_calls.append(desired)
        if self.set_error is not None:
            raise self.set_error


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.commands = []

    def run(self, argv):
        self.commands.append(tuple(argv))
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class ForwardingGateTests(unittest.TestCase):
    def test_disable_requires_fresh_final_observation(self):
        backend = FakeBackend(
            (
                ForwardingGateState.ENABLED,
                ForwardingGateState.DISABLED,
            )
        )
        result = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.DISABLED,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(
            backend.set_calls,
            [ForwardingGateState.DISABLED],
        )
        self.assertTrue(result.mutation_attempted)

    def test_noop_still_requires_second_observation(self):
        backend = FakeBackend(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        result = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.DISABLED,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(backend.set_calls, [])
        self.assertFalse(result.mutation_attempted)

    def test_noop_drift_is_not_success(self):
        backend = FakeBackend(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.ENABLED,
            )
        )
        result = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.DISABLED,
        )
        self.assertEqual(
            result.status,
            ForwardingGateExecutionStatus.POSTCONDITION_FAILED,
        )
        self.assertFalse(result.confirmed)

    def test_initial_observation_failure_never_mutates(self):
        backend = FakeBackend((RuntimeError("read failed"),))
        result = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.DISABLED,
        )
        self.assertEqual(
            result.status,
            ForwardingGateExecutionStatus.OBSERVATION_FAILED,
        )
        self.assertEqual(backend.set_calls, [])
        self.assertIsNone(result.final)

    def test_failed_write_can_still_end_confirmed(self):
        backend = FakeBackend(
            (
                ForwardingGateState.ENABLED,
                ForwardingGateState.DISABLED,
            ),
            set_error=RuntimeError("write wrapper failed"),
        )
        result = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.DISABLED,
        )
        self.assertTrue(result.confirmed)
        self.assertIn(
            "independently confirmed",
            result.diagnostic,
        )

    def test_failed_write_with_wrong_final_state_is_apply_failed(self):
        backend = FakeBackend(
            (
                ForwardingGateState.ENABLED,
                ForwardingGateState.ENABLED,
            ),
            set_error=RuntimeError("write failed"),
        )
        result = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.DISABLED,
        )
        self.assertEqual(
            result.status,
            ForwardingGateExecutionStatus.APPLY_FAILED,
        )
        self.assertFalse(result.confirmed)

    def test_successful_write_with_wrong_final_state_is_postcondition_failure(self):
        backend = FakeBackend(
            (
                ForwardingGateState.ENABLED,
                ForwardingGateState.ENABLED,
            )
        )
        result = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.DISABLED,
        )
        self.assertEqual(
            result.status,
            ForwardingGateExecutionStatus.POSTCONDITION_FAILED,
        )

    def test_final_observation_failure_after_write_is_not_confirmed(self):
        backend = FakeBackend(
            (
                ForwardingGateState.ENABLED,
                RuntimeError("reread failed"),
            )
        )
        result = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.DISABLED,
        )
        self.assertEqual(
            result.status,
            ForwardingGateExecutionStatus.OBSERVATION_FAILED,
        )
        self.assertFalse(result.confirmed)

    def test_linux_backend_uses_managed_namespace_and_strict_values(self):
        runner = FakeRunner(("0\n", "1\n"))
        backend = LinuxForwardingGateBackend(
            runner=runner,
            namespace="managed",
        )
        self.assertEqual(
            backend.observe_forwarding_gate(),
            ForwardingGateState.DISABLED,
        )
        self.assertEqual(
            backend.observe_forwarding_gate(),
            ForwardingGateState.ENABLED,
        )
        self.assertEqual(
            runner.commands[0],
            (
                "ip",
                "netns",
                "exec",
                "managed",
                "sysctl",
                "-n",
                "net.ipv4.ip_forward",
            ),
        )

    def test_linux_backend_write_is_not_hidden_verification(self):
        runner = FakeRunner(("net.ipv4.ip_forward = 0\n",))
        backend = LinuxForwardingGateBackend(
            runner=runner,
            namespace="managed",
        )
        backend.set_forwarding_gate(ForwardingGateState.DISABLED)
        self.assertEqual(
            runner.commands,
            [
                (
                    "ip",
                    "netns",
                    "exec",
                    "managed",
                    "sysctl",
                    "-w",
                    "net.ipv4.ip_forward=0",
                )
            ],
        )

    def test_linux_backend_rejects_unexpected_observation(self):
        backend = LinuxForwardingGateBackend(
            runner=FakeRunner(("enabled\n",)),
            namespace="managed",
        )
        with self.assertRaisesRegex(
            LinuxForwardingGateError,
            "unexpected",
        ):
            backend.observe_forwarding_gate()


if __name__ == "__main__":
    unittest.main()
