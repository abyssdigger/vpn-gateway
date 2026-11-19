from ipaddress import IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import (
    NetworkPolicyLayout,
    NumericResourcePool,
    PayloadDispatchRule,
    PayloadPolicyAllocation,
)
from rou.payload_profile import PayloadProfileRequest
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.stack_return_affinity import (
    StackReturnAffinityAllocation,
    StackReturnAffinityError,
    StackReturnAffinityPlatformSpace,
    allocate_stack_return_affinity,
    build_stack_return_affinity_desired,
)


HOST = InterfaceIdentity("host0", 10)
A = InterfaceIdentity("vpn-a", 20)
B = InterfaceIdentity("vpn-b", 30)
PA = LogicalPathId("a", 0, 0)
PB = LogicalPathId("b", 0, 0)
RA = RoutePriorityPathRoute(PA, A)
RB = RoutePriorityPathRoute(PB, B)


def profile(profile_id, direction, prefix, path):
    return PayloadProfileRequest(
        profile_id=profile_id,
        direction=direction,
        destinations=(IPv4Network(prefix),),
        ordered_paths=(path,),
    )


def layout():
    return NetworkPolicyLayout(
        payload=(
            PayloadPolicyAllocation(
                profile_id="broad",
                table=1001,
                metric_space=None,
                terminal_guard_metric=100,
                path_route_protocol=202,
                guard_route_protocol=203,
                host_boundary_lane_route_protocol=204,
            ),
            PayloadPolicyAllocation(
                profile_id="specific",
                table=1002,
                metric_space=None,
                terminal_guard_metric=100,
                path_route_protocol=202,
                guard_route_protocol=203,
                host_boundary_lane_route_protocol=204,
            ),
        ),
        probe=(),
        dispatch_rules=(
            PayloadDispatchRule(
                profile_id="specific",
                destination=IPv4Network("10.0.0.0/24"),
                priority=1000,
                table=1002,
            ),
            PayloadDispatchRule(
                profile_id="broad",
                destination=IPv4Network("10.0.0.0/16"),
                priority=1001,
                table=1001,
            ),
        ),
        nft_family="ip",
        nft_table="vpn_gate",
    )


class StackReturnAffinityAllocationTests(unittest.TestCase):
    def test_allocation_is_profile_sorted_and_precedes_dispatch(self):
        p1 = profile("specific", Direction.INBOUND, "10.0.0.0/24", PB)
        p2 = profile("broad", Direction.INBOUND, "10.0.0.0/16", PA)
        l = layout()
        desired = allocate_stack_return_affinity(
            (p1, p2),
            l,
            StackReturnAffinityPlatformSpace(
                marks=NumericResourcePool(0x1000, 0x1010),
                rule_priorities=NumericResourcePool(900, 1000),
            ),
        )
        self.assertEqual(
            [(item.profile_id, item.mark, item.rule_priority) for item in desired],
            [
                ("broad", 0x1000, 900),
                ("specific", 0x1001, 901),
            ],
        )

    def test_allocation_rejects_priority_not_before_dispatch(self):
        p1 = profile("broad", Direction.INBOUND, "10.0.0.0/16", PA)
        p2 = profile("specific", Direction.INBOUND, "10.0.0.0/24", PB)
        with self.assertRaisesRegex(StackReturnAffinityError, "before ordinary payload dispatch"):
            allocate_stack_return_affinity(
                (p1, p2),
                layout(),
                StackReturnAffinityPlatformSpace(
                    marks=NumericResourcePool(0x1000, 0x1010),
                    rule_priorities=NumericResourcePool(1000, 1010),
                ),
            )


class StackReturnAffinityTests(unittest.TestCase):
    def test_overlapping_remote_prefixes_keep_distinct_ingress_affinity(self):
        desired = build_stack_return_affinity_desired(
            (
                profile("broad", Direction.INBOUND, "10.0.0.0/16", PA),
                profile("specific", Direction.INBOUND, "10.0.0.0/24", PB),
            ),
            (RA, RB),
            HOST,
            layout(),
            (
                StackReturnAffinityAllocation("broad", 0xA1, 1101),
                StackReturnAffinityAllocation("specific", 0xA2, 1102),
            ),
        )

        by_ingress = {item.ingress: item for item in desired.classifiers}
        self.assertEqual(by_ingress[A].remote_prefix, IPv4Network("10.0.0.0/16"))
        self.assertEqual(by_ingress[A].mark, 0xA1)
        self.assertEqual(by_ingress[B].remote_prefix, IPv4Network("10.0.0.0/24"))
        self.assertEqual(by_ingress[B].mark, 0xA2)

        rules = {item.profile_id: item for item in desired.rules}
        self.assertEqual(rules["broad"].table, 1001)
        self.assertEqual(rules["specific"].table, 1002)

    def test_outbound_only_profile_needs_no_affinity_allocation(self):
        p = PayloadProfileRequest(
            profile_id="out",
            direction=Direction.OUTBOUND,
            destinations=(IPv4Network("10.0.0.0/8"),),
            ordered_paths=(PA,),
        )
        l = NetworkPolicyLayout(
            payload=(
                PayloadPolicyAllocation(
                    profile_id="out",
                    table=1001,
                    metric_space=None,
                    terminal_guard_metric=100,
                    path_route_protocol=202,
                    guard_route_protocol=203,
                ),
            ),
            probe=(),
            dispatch_rules=(),
            nft_family="ip",
            nft_table="vpn_gate",
        )
        desired = build_stack_return_affinity_desired(
            (p,), (RA,), HOST, l, ()
        )
        self.assertEqual(desired.classifiers, ())
        self.assertEqual(desired.rules, ())

    def test_release1_rejects_multiple_inbound_paths(self):
        p = PayloadProfileRequest(
            profile_id="broad",
            direction=Direction.INBOUND,
            destinations=(IPv4Network("10.0.0.0/16"),),
            ordered_paths=(PA, PB),
        )
        with self.assertRaisesRegex(StackReturnAffinityError, "more than one current path"):
            build_stack_return_affinity_desired(
                (p,), (RA, RB), HOST, layout(), ()
            )


if __name__ == "__main__":
    unittest.main()
