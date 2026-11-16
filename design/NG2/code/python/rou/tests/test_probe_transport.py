from ipaddress import IPv4Address
import unittest

from rou.availability_probe_state import ProbeObservationGeneration
from rou.availability_routing import AvailabilityWindowPolicy
from rou.interface_identity import InterfaceIdentity
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
)
from rou.probe_transport import (
    LogicalProbeWindow,
    PhysicalProbePlane,
    ProbeExecutionPlan,
    ProbeExecutionPlanCalculator,
    ProbeGoodNewsInfo,
    ProbeWindowBoundaryInfo,
)


A = InterfaceIdentity("a0", 10)
B = InterfaceIdentity("b0", 11)


def probe(probe_id, path, target, interval, *, enabled=True):
    return AvailabilityProbeRequest(
        probe_id,
        path,
        IPv4Address(target),
        enabled=enabled,
        policy=AvailabilityWindowPolicy(interval, 3),
    )


class ProbeExecutionPlanTests(unittest.TestCase):
    def setUp(self):
        self.generation = ProbeObservationGeneration(7)
        self.calculator = ProbeExecutionPlanCalculator()

    def test_shared_plane_uses_fastest_physical_send_cadence(self):
        request = AvailabilityProbeSetRequest(
            (
                probe("slow", A, "203.0.113.10", 30),
                probe("fast", A, "203.0.113.10", 10),
            )
        )

        plan = self.calculator.calculate(request, self.generation)

        self.assertEqual(plan.generation, self.generation)
        self.assertEqual(len(plan.planes), 1)
        self.assertEqual(plan.planes[0].interval_seconds, 10.0)
        self.assertEqual(
            [(item.probe_id, item.interval_seconds) for item in plan.windows],
            [("fast", 10.0), ("slow", 30.0)],
        )

    def test_distinct_generation_or_path_keeps_distinct_physical_planes(self):
        request = AvailabilityProbeSetRequest(
            (
                probe("a", A, "203.0.113.10", 10),
                probe("b", B, "203.0.113.10", 20),
            )
        )

        plan = self.calculator.calculate(request, self.generation)

        self.assertEqual(len(plan.planes), 2)
        self.assertEqual(
            [(item.path, item.interval_seconds) for item in plan.planes],
            [(A, 10.0), (B, 20.0)],
        )

    def test_disabled_probe_creates_no_execution_demand(self):
        request = AvailabilityProbeSetRequest(
            (probe("off", A, "203.0.113.10", 10, enabled=False),)
        )

        plan = self.calculator.calculate(request, self.generation)

        self.assertEqual(plan.planes, ())
        self.assertEqual(plan.windows, ())

    def test_plan_rejects_duplicate_physical_identity_with_different_interval(self):
        mechanism = AvailabilityProbeSetRequest(
            (probe("a", A, "203.0.113.10", 10),)
        ).probes[0].mechanism
        with self.assertRaisesRegex(ValueError, "duplicate physical planes"):
            ProbeExecutionPlan(
                self.generation,
                (
                    PhysicalProbePlane(
                        mechanism,
                        A,
                        IPv4Address("203.0.113.10"),
                        10,
                    ),
                    PhysicalProbePlane(
                        mechanism,
                        A,
                        IPv4Address("203.0.113.10"),
                        20,
                    ),
                ),
                (LogicalProbeWindow("a", 10),),
            )

    def test_events_require_generation_bound_typed_subjects(self):
        good = ProbeGoodNewsInfo(
            request_mechanism := AvailabilityProbeSetRequest(
                (probe("a", A, "203.0.113.10", 10),)
            ).probes[0].mechanism,
            A,
            IPv4Address("203.0.113.10"),
            self.generation,
        )
        boundary = ProbeWindowBoundaryInfo("a", self.generation)

        self.assertEqual(good.generation, self.generation)
        self.assertEqual(boundary.probe_id, "a")
        self.assertEqual(good.mechanism, request_mechanism)


if __name__ == "__main__":
    unittest.main()
