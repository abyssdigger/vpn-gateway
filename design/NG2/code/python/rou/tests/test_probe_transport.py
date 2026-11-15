from ipaddress import IPv4Address
import unittest

from rou.availability_collector import (
    AvailabilityHysteresisPolicy,
    AvailabilityPriorityChannel,
)
from rou.availability_probe_state import ProbeObservationGeneration
from rou.interface_identity import InterfaceIdentity
from rou.probe_rules import AvailabilityProbeRequest, AvailabilityProbeSetRequest
from rou.probe_transport import (
    LogicalProbeChannel,
    PhysicalProbePlane,
    ProbeExecutionPlan,
    ProbeExecutionPlanCalculator,
)


A = InterfaceIdentity("a0", 10)
B = InterfaceIdentity("b0", 11)


def probe(
    probe_id,
    path,
    target,
    interval,
    *,
    enabled=True,
    failure=3,
    recovery=2,
):
    return AvailabilityProbeRequest(
        probe_id,
        path,
        IPv4Address(target),
        enabled=enabled,
        interval_seconds=interval,
        hysteresis=AvailabilityHysteresisPolicy(failure, recovery),
    )


class ProbeExecutionPlanTests(unittest.TestCase):
    def setUp(self):
        self.generation = ProbeObservationGeneration(7)
        self.calculator = ProbeExecutionPlanCalculator()

    def test_shared_plane_uses_fastest_send_cadence_and_keeps_logical_channels(self):
        request = AvailabilityProbeSetRequest(
            (
                probe("slow", A, "203.0.113.10", 30),
                probe("fast", A, "203.0.113.10", 10),
            )
        )

        plan = self.calculator.calculate(request, self.generation)

        self.assertEqual(len(plan.planes), 1)
        self.assertEqual(plan.planes[0].interval_seconds, 10.0)
        self.assertEqual(
            [
                (item.priority.channel_id, item.interval_seconds)
                for item in plan.channels
            ],
            [("fast", 10), ("slow", 30)],
        )

    def test_disabled_probe_creates_no_execution_demand(self):
        plan = self.calculator.calculate(
            AvailabilityProbeSetRequest(
                (probe("off", A, "203.0.113.10", 10, enabled=False),)
            ),
            self.generation,
        )

        self.assertEqual(plan.planes, ())
        self.assertEqual(plan.channels, ())

    def test_distinct_paths_keep_distinct_physical_planes(self):
        plan = self.calculator.calculate(
            AvailabilityProbeSetRequest(
                (
                    probe("a", A, "203.0.113.10", 10),
                    probe("b", B, "203.0.113.10", 20),
                )
            ),
            self.generation,
        )

        self.assertEqual(
            [(item.path, item.interval_seconds) for item in plan.planes],
            [(A, 10.0), (B, 20.0)],
        )

    def test_plan_rejects_duplicate_physical_plane_and_channel(self):
        request = probe("a", A, "203.0.113.10", 10)
        mechanism = request.mechanism
        channel = LogicalProbeChannel(
            AvailabilityPriorityChannel(
                "a",
                A,
                True,
                AvailabilityHysteresisPolicy(3, 2),
            ),
            mechanism,
            IPv4Address("203.0.113.10"),
            10,
        )

        with self.assertRaisesRegex(ValueError, "duplicate physical planes"):
            ProbeExecutionPlan(
                self.generation,
                (
                    PhysicalProbePlane(
                        mechanism, A, IPv4Address("203.0.113.10"), 10
                    ),
                    PhysicalProbePlane(
                        mechanism, A, IPv4Address("203.0.113.10"), 20
                    ),
                ),
                (channel,),
            )

        with self.assertRaisesRegex(ValueError, "duplicate logical channels"):
            ProbeExecutionPlan(
                self.generation,
                (
                    PhysicalProbePlane(
                        mechanism, A, IPv4Address("203.0.113.10"), 10
                    ),
                ),
                (channel, channel),
            )

    def test_logical_channel_projects_only_payload_relevant_priority_descriptor(self):
        request = AvailabilityProbeSetRequest(
            (probe("a", A, "203.0.113.10", 10),)
        )

        channel = self.calculator.calculate(
            request,
            self.generation,
        ).channels[0]

        self.assertEqual(channel.priority.channel_id, "a")
        self.assertEqual(channel.priority.path, A)
        self.assertEqual(
            channel.priority.policy,
            AvailabilityHysteresisPolicy(3, 2),
        )
        self.assertFalse(hasattr(channel.priority, "target"))
        self.assertFalse(hasattr(channel.priority, "mechanism"))
        self.assertFalse(hasattr(channel.priority, "interval_seconds"))


if __name__ == "__main__":
    unittest.main()
