from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.alpha_probe_projection import (
    build_alpha_explicit_probe_desired,
)
from rou.availability_routing_state import AvailabilityRoutingState
from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.payload_profile import PayloadProfileRequest
from rou.probe_attempt_runtime import (
    ProbeAttemptPreconditions,
    ProbeSubjectRuntimeState,
    run_probe_attempt_once,
)
from rou.probe_policy import ProbeLocalPlatform
from rou.probe_route_feedback import project_probe_route_feedback
from rou.probe_runtime import (
    AvailabilityProbeAgent,
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)
from rou.release1_config import (
    AvailabilityCheckConfig,
    ProfileRelease1Config,
)
from rou.route_priority_inventory import RoutePriorityPathRoute


A = LogicalPathId("primary", 0, 0)
B = LogicalPathId("reserve", 0, 0)
EP_A = InterfaceIdentity("wg0", 10)
EP_B = InterfaceIdentity("tun0", 11)
TARGET = IPv4Address("198.51.100.7")
READY = ProbeAttemptPreconditions(True, True)


class StaticDriver:
    def __init__(self, outcome):
        self.outcome = outcome

    def check(self, _context):
        return ProbeTechnicalObservation(self.outcome)


class ProbeRuntimePipelineTests(unittest.TestCase):
    def test_explicit_target_problem_confirmation_drives_effective_order(self):
        profile = PayloadProfileRequest(
            profile_id="corp",
            direction=Direction.OUTBOUND,
            destinations=(IPv4Network("10.0.0.0/8"),),
            ordered_paths=(A, B),
        )
        release1 = {
            "corp": ProfileRelease1Config(
                ordinary_gateway_nat=False,
                route_return=False,
                availability_check=AvailabilityCheckConfig(
                    "icmp",
                    TARGET,
                ),
                reserve_device_ids=frozenset({"reserve"}),
            )
        }
        desired = build_alpha_explicit_probe_desired(
            (profile,),
            release1,
            (
                RoutePriorityPathRoute(A, EP_A),
                RoutePriorityPathRoute(B, EP_B),
            ),
            NG3_LINUX_POLICY_PLATFORM,
            ProbeLocalPlatform(4242, 0x20000001),
        )
        self.assertEqual(len(desired.semantic.intents), 2)

        by_path = {
            intent.owner.path_id: intent
            for intent in desired.semantic.intents
        }
        agents = {
            A: AvailabilityProbeAgent(),
            B: AvailabilityProbeAgent(),
        }
        states = {
            A: ProbeSubjectRuntimeState(),
            B: ProbeSubjectRuntimeState(),
        }

        for _ in range(2):
            result = run_probe_attempt_once(
                agents[A],
                StaticDriver(ProbeTechnicalOutcome.NO_REPLY),
                by_path[A],
                EP_A,
                states[A],
                READY,
                degradation_threshold=2,
                recovery_threshold=2,
            )
            states[A] = result.next_state

            result = run_probe_attempt_once(
                agents[B],
                StaticDriver(ProbeTechnicalOutcome.REPLY),
                by_path[B],
                EP_B,
                states[B],
                READY,
                degradation_threshold=2,
                recovery_threshold=2,
            )
            states[B] = result.next_state

        feedback = project_probe_route_feedback(
            profile,
            {
                by_path[A].owner: states[A],
                by_path[B].owner: states[B],
            },
            AvailabilityRoutingState(),
            reserve_device_ids=frozenset({"reserve"}),
        )
        self.assertEqual(feedback.problem_paths, (A,))
        self.assertEqual(feedback.routing.effective_order, (B, A))
        self.assertEqual(
            feedback.routing.next_state.active_path,
            B,
        )

        for _ in range(2):
            result = run_probe_attempt_once(
                agents[A],
                StaticDriver(ProbeTechnicalOutcome.REPLY),
                by_path[A],
                EP_A,
                states[A],
                READY,
                degradation_threshold=2,
                recovery_threshold=2,
            )
            states[A] = result.next_state

        recovered = project_probe_route_feedback(
            profile,
            {
                by_path[A].owner: states[A],
                by_path[B].owner: states[B],
            },
            feedback.routing.next_state,
            reserve_device_ids=frozenset({"reserve"}),
        )
        self.assertEqual(recovered.problem_paths, ())
        self.assertEqual(recovered.routing.effective_order, (A, B))
        self.assertEqual(
            recovered.routing.next_state.active_path,
            A,
        )


if __name__ == "__main__":
    unittest.main()
