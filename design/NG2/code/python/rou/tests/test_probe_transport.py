from ipaddress import IPv4Address
import unittest

from rou.availability_collector import AvailabilityChannelPolicy
from rou.availability_probe_state import ProbeObservationGeneration
from rou.interface_identity import InterfaceIdentity
from rou.probe_rules import AvailabilityProbeRequest, AvailabilityProbeSetRequest
from rou.probe_transport import (
    LogicalProbeChannel,
    PhysicalProbePlane,
    ProbeExecutionPlan,
    ProbeExecutionPlanCalculator,
    ProbeGoodNewsInfo,
    ProbeTickInfo,
)


A = InterfaceIdentity("a0", 10)
B = InterfaceIdentity("b0", 11)


def probe(probe_id, path, target, interval, *, enabled=True, failure=3, recovery=2):
    return AvailabilityProbeRequest(
        probe_id,
        path,
        IPv4Address(target),
        enabled=enabled,
        policy=AvailabilityChannelPolicy(interval, failure, recovery),
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
            [(item.probe_id, item.policy.interval_seconds) for item in plan.channels],
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
        mechanism = probe("a", A, "203.0.113.10", 10).mechanism
        channel = LogicalProbeChannel(
            "a",
            mechanism,
            A,
            IPv4Address("203.0.113.10"),
            AvailabilityChannelPolicy(10, 3, 2),
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

    def test_good_news_and_tick_only_carry_channel_identity(self):
        channel = self.calculator.calculate(
            AvailabilityProbeSetRequest(
                (probe("a", A, "203.0.113.10", 10),)
            ),
            self.generation,
        ).channels[0]

        self.assertEqual(ProbeGoodNewsInfo(channel).channel, channel)
        self.assertEqual(ProbeTickInfo(channel).channel, channel)


if __name__ == "__main__":
    unittest.main()
