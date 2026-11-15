import unittest

from rou.availability_collector import (
    AvailabilityHysteresisPolicy,
    AvailabilityChannelState,
    AvailabilityPendingInput,
    calculate_availability_path_order,
)
from rou.interface_identity import InterfaceIdentity


A = InterfaceIdentity("a0", 10)
B = InterfaceIdentity("b0", 11)
C = InterfaceIdentity("c0", 12)
D = InterfaceIdentity("d0", 13)


class AvailabilityPendingInputTests(unittest.TestCase):
    def test_good_news_counter_saturates_at_recovery_requirement(self):
        policy = AvailabilityHysteresisPolicy(3, 3)
        pending = AvailabilityPendingInput()

        for _ in range(20):
            pending.note_good_news(policy)

        self.assertEqual(pending.pending_good_news, 3)

    def test_ticks_are_one_pending_fact_not_a_count(self):
        pending = AvailabilityPendingInput()

        pending.note_tick()
        pending.note_tick()
        pending.note_tick()

        self.assertEqual(pending.take(), (0, True))
        self.assertEqual(pending.take(), (0, False))


class AvailabilityChannelStateTests(unittest.TestCase):
    def setUp(self):
        self.policy = AvailabilityHysteresisPolicy(failure_ticks=3, recovery_good_news=3)

    def test_initial_state_has_no_availability_problems(self):
        state = AvailabilityChannelState()

        self.assertFalse(state.availability_problems)

    def test_no_problem_state_requires_failure_ticks_without_good_news(self):
        state = AvailabilityChannelState()

        self.assertFalse(
            state.process(self.policy, pending_good_news=0, tick_pending=True)
        )
        self.assertFalse(
            state.process(self.policy, pending_good_news=0, tick_pending=True)
        )
        self.assertTrue(
            state.process(self.policy, pending_good_news=0, tick_pending=True)
        )
        self.assertTrue(state.availability_problems)

    def test_any_good_news_before_tick_resets_failure_progress(self):
        state = AvailabilityChannelState()

        state.process(self.policy, pending_good_news=0, tick_pending=True)
        state.process(self.policy, pending_good_news=0, tick_pending=True)
        state.process(self.policy, pending_good_news=1, tick_pending=False)
        state.process(self.policy, pending_good_news=0, tick_pending=True)

        self.assertFalse(state.availability_problems)
        self.assertEqual(state.failure_misses, 0)

    def test_problem_state_counts_multiple_delayed_replies_in_one_pass(self):
        state = AvailabilityChannelState(availability_problems=True)

        changed = state.process(
            self.policy,
            pending_good_news=3,
            tick_pending=True,
        )

        self.assertTrue(changed)
        self.assertFalse(state.availability_problems)

    def test_problem_recovery_progress_survives_tick_with_good_news(self):
        state = AvailabilityChannelState(availability_problems=True)

        state.process(self.policy, pending_good_news=1, tick_pending=True)
        self.assertEqual(state.recovery_progress, 1)

        state.process(self.policy, pending_good_news=1, tick_pending=True)
        self.assertEqual(state.recovery_progress, 2)

        state.process(self.policy, pending_good_news=1, tick_pending=True)
        self.assertFalse(state.availability_problems)

    def test_problem_recovery_progress_resets_on_tick_without_good_news(self):
        state = AvailabilityChannelState(availability_problems=True)

        state.process(self.policy, pending_good_news=2, tick_pending=True)
        self.assertEqual(state.recovery_progress, 2)

        state.process(self.policy, pending_good_news=0, tick_pending=True)

        self.assertTrue(state.availability_problems)
        self.assertEqual(state.recovery_progress, 0)

    def test_simultaneous_recovery_and_tick_cannot_redegrade_channel(self):
        policy = AvailabilityHysteresisPolicy(1, 2)
        state = AvailabilityChannelState(availability_problems=True)

        changed = state.process(
            policy,
            pending_good_news=2,
            tick_pending=True,
        )

        self.assertTrue(changed)
        self.assertFalse(state.availability_problems)
        self.assertEqual(state.failure_misses, 0)

    def test_policy_progress_reset_preserves_problem_flag(self):
        state = AvailabilityChannelState(
            availability_problems=True,
            recovery_progress=2,
            good_news_since_tick=True,
        )

        state.reset_policy_progress()

        self.assertTrue(state.availability_problems)
        self.assertEqual(state.recovery_progress, 0)
        self.assertFalse(state.good_news_since_tick)

    def test_disabled_probing_clears_problem_by_definition(self):
        state = AvailabilityChannelState(
            availability_problems=True,
            recovery_progress=2,
        )

        changed = state.disable()

        self.assertTrue(changed)
        self.assertFalse(state.availability_problems)
        self.assertEqual(state.recovery_progress, 0)


class AvailabilityPathOrderTests(unittest.TestCase):
    def test_initial_no_problem_state_is_configured_order(self):
        configured = (A, B, C, D)

        self.assertEqual(
            calculate_availability_path_order(
                configured,
                configured,
                frozenset(),
            ),
            configured,
        )

    def test_problem_path_is_passed_by_no_problem_paths(self):
        configured = (A, B, C, D)

        self.assertEqual(
            calculate_availability_path_order(
                configured,
                configured,
                frozenset((B,)),
            ),
            (A, C, D, B),
        )

    def test_problem_paths_preserve_current_relative_order(self):
        configured = (A, B, C, D)
        current = (C, B, A, D)

        self.assertEqual(
            calculate_availability_path_order(
                configured,
                current,
                frozenset((A, B)),
            ),
            (C, D, B, A),
        )

    def test_all_problem_paths_preserve_current_order(self):
        configured = (A, B, C, D)
        current = (C, B, A, D)

        self.assertEqual(
            calculate_availability_path_order(
                configured,
                current,
                frozenset(configured),
            ),
            current,
        )

    def test_cleared_problem_rejoins_configured_priority_prefix(self):
        configured = (A, B, C, D)
        current = (A, C, D, B)

        self.assertEqual(
            calculate_availability_path_order(
                configured,
                current,
                frozenset(),
            ),
            configured,
        )


if __name__ == "__main__":
    unittest.main()
