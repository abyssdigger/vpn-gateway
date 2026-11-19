from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.availability_confirmation import (
    AvailabilityConfirmationState,
)
from rou.availability_routing_state import AvailabilityRoutingState
from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.network_policy_layout import ProbePolicyOwner
from rou.payload_profile import PayloadProfileRequest
from rou.probe_attempt_runtime import ProbeSubjectRuntimeState
from rou.probe_route_feedback import project_probe_route_feedback


A = LogicalPathId("primary", 0, 0)
B = LogicalPathId("backup", 0, 0)
OLD = LogicalPathId("old", 0, 0)


def profile(paths=(A, B)):
    return PayloadProfileRequest(
        profile_id="corp",
        direction=Direction.OUTBOUND,
        destinations=(IPv4Network("10.0.0.0/8"),),
        ordered_paths=tuple(paths),
    )


def subject(path, *, problem=False):
    return (
        ProbePolicyOwner("corp", path),
        ProbeSubjectRuntimeState(
            AvailabilityConfirmationState(
                availability_problem=problem
            )
        ),
    )


class ProbeRouteFeedbackTests(unittest.TestCase):
    def test_confirmed_problem_moves_path_below_healthy_path(self):
        owner, state = subject(A, problem=True)
        value = project_probe_route_feedback(
            profile(),
            {owner: state},
            AvailabilityRoutingState(),
        )
        self.assertEqual(value.problem_paths, (A,))
        self.assertEqual(value.routing.effective_order, (B, A))
        self.assertEqual(value.routing.next_state.active_path, B)

    def test_missing_subject_state_is_unknown_not_problem(self):
        value = project_probe_route_feedback(
            profile(),
            {},
            AvailabilityRoutingState(),
        )
        self.assertEqual(value.problem_paths, ())
        self.assertEqual(value.routing.effective_order, (A, B))
        self.assertEqual(value.routing.next_state.active_path, A)

    def test_stale_disappeared_subject_state_cannot_degrade_current_paths(self):
        old_owner, old_state = subject(OLD, problem=True)
        value = project_probe_route_feedback(
            profile(),
            {old_owner: old_state},
            AvailabilityRoutingState(),
        )
        self.assertEqual(value.problem_paths, ())
        self.assertEqual(value.routing.effective_order, (A, B))

    def test_normal_active_path_remains_sticky_after_better_path_recovers(self):
        a_owner, a_state = subject(A, problem=False)
        b_owner, b_state = subject(B, problem=False)
        value = project_probe_route_feedback(
            profile(),
            {
                a_owner: a_state,
                b_owner: b_state,
            },
            AvailabilityRoutingState(active_path=B),
        )
        self.assertEqual(value.routing.effective_order, (B, A))

    def test_reserve_active_path_relinquishes_to_nominal_better_path(self):
        a_owner, a_state = subject(A, problem=False)
        b_owner, b_state = subject(B, problem=False)
        value = project_probe_route_feedback(
            profile(),
            {
                a_owner: a_state,
                b_owner: b_state,
            },
            AvailabilityRoutingState(active_path=B),
            reserve_device_ids=frozenset({"backup"}),
        )
        self.assertEqual(value.routing.effective_order, (A, B))
        self.assertEqual(value.routing.next_state.active_path, A)


if __name__ == "__main__":
    unittest.main()
