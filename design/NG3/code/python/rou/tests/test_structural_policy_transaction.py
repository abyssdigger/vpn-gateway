from __future__ import annotations

import unittest
from unittest.mock import patch

from rou.forwarding_gate import (
    ForwardingGateExecutionResult,
    ForwardingGateExecutionStatus,
    ForwardingGateState,
)
from rou.structural_policy_mutation import (
    StructuralPolicyMutationResult,
    StructuralPolicyMutationStatus,
)
from rou.structural_policy_transaction import (
    StructuralPolicyTransactionStatus,
    converge_structural_policy,
)


BARRIER = ForwardingGateExecutionResult(
    status=ForwardingGateExecutionStatus.SUCCESS,
    desired=ForwardingGateState.DISABLED,
    initial=ForwardingGateState.DISABLED,
    final=ForwardingGateState.DISABLED,
    mutation_attempted=False,
)


class Marker:
    pass


def mutation(status, initial=None, final=None, *, diagnostic=None):
    return StructuralPolicyMutationResult(
        status=status,
        barrier=BARRIER,
        initial=initial,
        final=final,
        mutation_attempted=(
            status is StructuralPolicyMutationStatus.STEP_APPLIED
        ),
        diagnostic=diagnostic,
    )


class StructuralPolicyTransactionTests(unittest.TestCase):
    def run_script(self, scripted, distances):
        calls = []

        def fake_step(*args):
            calls.append(args)
            if not scripted:
                raise AssertionError("unexpected extra convergence attempt")
            return scripted.pop(0)

        def fake_distance(value):
            return distances[value]

        with (
            patch(
                "rou.structural_policy_transaction."
                "converge_structural_policy_step_once",
                side_effect=fake_step,
            ),
            patch(
                "rou.structural_policy_transaction.structural_policy_distance",
                side_effect=fake_distance,
            ),
        ):
            result = converge_structural_policy(
                object(),
                object(),
                object(),
                object(),
                object(),
            )
        return result, calls

    def test_strictly_decreasing_steps_end_confirmed_without_retry_budget(self):
        a0, a1, b0, b1, c0, c1 = (Marker() for _ in range(6))
        scripted = [
            mutation(StructuralPolicyMutationStatus.STEP_APPLIED, a0, a1),
            mutation(StructuralPolicyMutationStatus.STEP_APPLIED, b0, b1),
            mutation(StructuralPolicyMutationStatus.CONFIRMED, c0, c1),
        ]
        distances = {
            a0: 5,
            a1: 4,
            b0: 4,
            b1: 2,
            c0: 2,
            c1: 0,
        }

        result, calls = self.run_script(scripted, distances)

        self.assertEqual(
            result.status,
            StructuralPolicyTransactionStatus.CONFIRMED,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(len(calls), 3)
        self.assertEqual(result.initial_distance, 5)
        self.assertEqual(result.final_distance, 0)

    def test_terminal_one_step_failure_is_not_retried(self):
        a0 = Marker()
        scripted = [
            mutation(
                StructuralPolicyMutationStatus.CONFLICT,
                a0,
                a0,
                diagnostic="synthetic conflict",
            ),
            mutation(StructuralPolicyMutationStatus.CONFIRMED, a0, a0),
        ]
        distances = {a0: 3}

        result, calls = self.run_script(scripted, distances)

        self.assertEqual(
            result.status,
            StructuralPolicyTransactionStatus.FAILED,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(len(calls), 1)
        self.assertIn("conflict", result.diagnostic)
        self.assertEqual(len(scripted), 1)

    def test_fresh_inter_attempt_regression_stops_transaction(self):
        a0, a1, b0, b1 = (Marker() for _ in range(4))
        scripted = [
            mutation(StructuralPolicyMutationStatus.STEP_APPLIED, a0, a1),
            mutation(StructuralPolicyMutationStatus.STEP_APPLIED, b0, b1),
            mutation(StructuralPolicyMutationStatus.CONFIRMED, b1, b1),
        ]
        distances = {
            a0: 5,
            a1: 4,
            b0: 6,
            b1: 5,
        }

        result, calls = self.run_script(scripted, distances)

        self.assertEqual(
            result.status,
            StructuralPolicyTransactionStatus.REGRESSED,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.final_distance, 6)
        self.assertIn("regressed between", result.diagnostic)
        self.assertEqual(len(scripted), 1)

    def test_invalid_step_applied_distance_is_rejected(self):
        a0, a1 = Marker(), Marker()
        scripted = [
            mutation(StructuralPolicyMutationStatus.STEP_APPLIED, a0, a1),
        ]
        distances = {a0: 2, a1: 2}

        result, calls = self.run_script(scripted, distances)

        self.assertEqual(
            result.status,
            StructuralPolicyTransactionStatus.REGRESSED,
        )
        self.assertEqual(len(calls), 1)
        self.assertIn("strict structural distance", result.diagnostic)

    def test_fresh_confirmed_attempt_wins_over_prior_distance_regression(self):
        a0, a1, b0, b1 = (Marker() for _ in range(4))
        scripted = [
            mutation(StructuralPolicyMutationStatus.STEP_APPLIED, a0, a1),
            mutation(StructuralPolicyMutationStatus.CONFIRMED, b0, b1),
        ]
        distances = {
            a0: 5,
            a1: 4,
            b0: 6,
            b1: 0,
        }

        result, calls = self.run_script(scripted, distances)

        self.assertEqual(
            result.status,
            StructuralPolicyTransactionStatus.CONFIRMED,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.final_distance, 0)

    def test_external_progress_between_attempts_is_allowed(self):
        a0, a1, b0, b1 = (Marker() for _ in range(4))
        scripted = [
            mutation(StructuralPolicyMutationStatus.STEP_APPLIED, a0, a1),
            mutation(StructuralPolicyMutationStatus.CONFIRMED, b0, b1),
        ]
        distances = {
            a0: 7,
            a1: 6,
            b0: 3,
            b1: 0,
        }

        result, calls = self.run_script(scripted, distances)

        self.assertEqual(
            result.status,
            StructuralPolicyTransactionStatus.CONFIRMED,
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.initial_distance, 7)
        self.assertEqual(result.final_distance, 0)


if __name__ == "__main__":
    unittest.main()
