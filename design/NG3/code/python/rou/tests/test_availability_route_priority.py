from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.availability_route_priority import (
    AvailabilityRoutePriorityError,
    build_availability_route_priority_plans,
    converge_availability_route_priority_once,
)
from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.network_policy_layout import allocate_network_policy_layout
from rou.payload_profile import PayloadProfileRequest
from rou.route_priority_inventory import RoutePriorityPathRoute


A = LogicalPathId("wg", 0, 0)
B = LogicalPathId("oc", 0, 0)
EA = InterfaceIdentity("wg0", 10)
EB = InterfaceIdentity("oc0", 20)


class NoIoRunner:
    def __init__(self):
        self.commands = []

    def run(self, argv):
        self.commands.append(tuple(argv))
        raise AssertionError("unexpected physical I/O")


def profile(paths=(A, B), destinations=("10.0.0.0/8",)):
    return PayloadProfileRequest(
        "corp",
        Direction.OUTBOUND,
        tuple(IPv4Network(value) for value in destinations),
        tuple(paths),
    )


def layout_for(p):
    return allocate_network_policy_layout(
        (p,),
        (),
        NG3_LINUX_POLICY_PLATFORM,
    )


class AvailabilityRoutePriorityTests(unittest.TestCase):
    def test_effective_order_maps_directly_to_metric_preference_slots(self):
        effective = profile((B, A))
        plans = build_availability_route_priority_plans(
            (effective,),
            layout_for(effective),
            (
                RoutePriorityPathRoute(A, EA),
                RoutePriorityPathRoute(B, EB),
            ),
            runner=NoIoRunner(),
            namespace="vpng-test",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(len(plans[0].requests), 1)
        request = plans[0].requests[0]
        self.assertEqual(request.desired[B], 1)
        self.assertEqual(request.desired[A], 2)
        self.assertEqual(request.working_metrics, (1, 2, 3))

    def test_all_profile_destinations_receive_same_effective_order(self):
        effective = profile(
            (B, A),
            ("10.0.0.0/8", "192.0.2.0/24"),
        )
        plans = build_availability_route_priority_plans(
            (effective,),
            layout_for(effective),
            (
                RoutePriorityPathRoute(A, EA),
                RoutePriorityPathRoute(B, EB),
            ),
            runner=NoIoRunner(),
            namespace="vpng-test",
        )
        self.assertEqual(len(plans[0].requests), 2)
        for request in plans[0].requests:
            self.assertEqual(request.desired[B], 1)
            self.assertEqual(request.desired[A], 2)

    def test_zero_path_profile_needs_no_priority_io_and_is_confirmed(self):
        effective = profile(())
        runner = NoIoRunner()
        result = converge_availability_route_priority_once(
            (effective,),
            layout_for(effective),
            (),
            runner=runner,
            namespace="vpng-test",
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(len(result.profiles), 1)
        self.assertTrue(result.profiles[0].confirmed)
        self.assertIsNone(result.profiles[0].result)
        self.assertEqual(runner.commands, [])

    def test_path_realization_membership_mismatch_is_rejected(self):
        effective = profile((A, B))
        with self.assertRaisesRegex(
            AvailabilityRoutePriorityError,
            "does not match effective Profile membership",
        ):
            build_availability_route_priority_plans(
                (effective,),
                layout_for(effective),
                (RoutePriorityPathRoute(A, EA),),
                runner=NoIoRunner(),
                namespace="vpng-test",
            )

    def test_layout_profile_mismatch_is_rejected(self):
        baseline = profile((A, B))
        effective = PayloadProfileRequest(
            "guest",
            Direction.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (A, B),
        )
        with self.assertRaisesRegex(
            AvailabilityRoutePriorityError,
            "does not match payload layout",
        ):
            build_availability_route_priority_plans(
                (effective,),
                layout_for(baseline),
                (
                    RoutePriorityPathRoute(A, EA),
                    RoutePriorityPathRoute(B, EB),
                ),
                runner=NoIoRunner(),
                namespace="vpng-test",
            )


if __name__ == "__main__":
    unittest.main()
