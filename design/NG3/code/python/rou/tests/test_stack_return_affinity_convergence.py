from __future__ import annotations

import unittest

from rou.forwarding_gate import ForwardingGateState
from rou.stack_return_affinity_convergence import (
    StackReturnAffinityConvergenceStatus,
    StackReturnAffinityObservation,
    StackReturnAffinityOwnerStatus,
    converge_stack_return_affinity_once,
)


class Gate:
    def __init__(self, state=ForwardingGateState.DISABLED):
        self.state = state

    def observe_forwarding_gate(self):
        return self.state


class Backend:
    def __init__(self, observations):
        self.observations = list(observations)
        self.replace_calls = 0

    def observe(self, desired):
        return self.observations.pop(0)

    def replace_owned(self, desired, observed):
        self.replace_calls += 1

    def cleanup_owned(self):
        raise AssertionError("not used")


class StackReturnAffinityConvergenceTests(unittest.TestCase):
    def test_exact_owner_is_noop(self):
        exact = StackReturnAffinityObservation(StackReturnAffinityOwnerStatus.EXACT)
        backend = Backend([exact])
        result = converge_stack_return_affinity_once(Gate(), backend, object())
        self.assertEqual(result.status, StackReturnAffinityConvergenceStatus.EXACT)
        self.assertTrue(result.confirmed)
        self.assertEqual(backend.replace_calls, 0)

    def test_stale_owner_is_replaced_only_behind_disabled_barrier(self):
        stale = StackReturnAffinityObservation(StackReturnAffinityOwnerStatus.STALE)
        exact = StackReturnAffinityObservation(StackReturnAffinityOwnerStatus.EXACT)
        backend = Backend([stale, exact])
        result = converge_stack_return_affinity_once(Gate(), backend, object())
        self.assertEqual(result.status, StackReturnAffinityConvergenceStatus.APPLIED)
        self.assertTrue(result.confirmed)
        self.assertEqual(backend.replace_calls, 1)

    def test_enabled_barrier_blocks_mutation(self):
        stale = StackReturnAffinityObservation(StackReturnAffinityOwnerStatus.STALE)
        backend = Backend([stale])
        result = converge_stack_return_affinity_once(
            Gate(ForwardingGateState.ENABLED), backend, object()
        )
        self.assertEqual(result.status, StackReturnAffinityConvergenceStatus.BARRIER_LOST)
        self.assertFalse(result.confirmed)
        self.assertEqual(backend.replace_calls, 0)

    def test_conflict_is_never_replaced(self):
        conflict = StackReturnAffinityObservation(
            StackReturnAffinityOwnerStatus.CONFLICT,
            diagnostic="foreign owner",
        )
        backend = Backend([conflict])
        result = converge_stack_return_affinity_once(Gate(), backend, object())
        self.assertEqual(result.status, StackReturnAffinityConvergenceStatus.CONFLICT)
        self.assertFalse(result.confirmed)
        self.assertEqual(backend.replace_calls, 0)


if __name__ == "__main__":
    unittest.main()
