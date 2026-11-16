from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.network_policy_layout import allocate_network_policy_layout
from rou.payload_profile import PayloadProfileRequest
from rou.route_priority_domain_builder import (
    RoutePriorityDomainBuildError,
    build_route_priority_domain_realizations,
)
from rou.route_priority_inventory import RoutePriorityPathRoute


A = LogicalPathId("a", 0, 0)
B = LogicalPathId("b", 0, 0)
EP_A = InterfaceIdentity("patha", 10)
EP_B = InterfaceIdentity("pathb", 20)


def profile(paths=(A, B)):
    return PayloadProfileRequest(
        profile_id="corp",
        direction=Direction.OUTBOUND,
        destinations=(
            IPv4Network("192.0.2.0/24"),
            IPv4Network("10.0.0.0/8"),
        ),
        ordered_paths=tuple(paths),
    )


def allocation(value):
    return allocate_network_policy_layout(
        (value,),
        (),
        NG3_LINUX_POLICY_PLATFORM,
    ).payload[0]


class RoutePriorityDomainBuilderTests(unittest.TestCase):
    def test_builds_one_domain_per_destination_with_shared_profile_table(self):
        value = profile()
        domains = build_route_priority_domain_realizations(
            value,
            allocation(value),
            (
                RoutePriorityPathRoute(B, EP_B),
                RoutePriorityPathRoute(A, EP_A),
            ),
        )

        self.assertEqual(
            [str(item.domain_id.destination) for item in domains],
            ["10.0.0.0/8", "192.0.2.0/24"],
        )
        self.assertEqual(
            {item.table for item in domains},
            {0x80000000},
        )
        self.assertEqual(
            {item.owner_protocol for item in domains},
            {202},
        )
        self.assertEqual(
            [spec.path_id for spec in domains[0].path_routes],
            [A, B],
        )
        self.assertEqual(
            dict(domains[0].desired_metrics(value.ordered_paths)),
            {A: 1, B: 2},
        )
        self.assertEqual(
            domains[0].metric_space.scratch_metrics,
            (3,),
        )

    def test_zero_path_profile_has_no_priority_domain(self):
        value = profile(paths=())
        self.assertEqual(
            build_route_priority_domain_realizations(
                value,
                allocation(value),
                (),
            ),
            (),
        )

    def test_missing_or_extra_physical_path_is_rejected(self):
        value = profile()
        alloc = allocation(value)

        with self.assertRaisesRegex(
            RoutePriorityDomainBuildError,
            "membership does not match",
        ):
            build_route_priority_domain_realizations(
                value,
                alloc,
                (RoutePriorityPathRoute(A, EP_A),),
            )

        extra = LogicalPathId("c", 0, 0)
        with self.assertRaisesRegex(
            RoutePriorityDomainBuildError,
            "membership does not match",
        ):
            build_route_priority_domain_realizations(
                value,
                alloc,
                (
                    RoutePriorityPathRoute(A, EP_A),
                    RoutePriorityPathRoute(B, EP_B),
                    RoutePriorityPathRoute(
                        extra,
                        InterfaceIdentity("pathc", 30),
                    ),
                ),
            )

    def test_profile_allocation_identity_mismatch_is_rejected(self):
        value = profile()
        other = PayloadProfileRequest(
            profile_id="other",
            direction=value.direction,
            destinations=value.destinations,
            ordered_paths=value.ordered_paths,
        )
        with self.assertRaisesRegex(
            RoutePriorityDomainBuildError,
            "identity does not match",
        ):
            build_route_priority_domain_realizations(
                other,
                allocation(value),
                (
                    RoutePriorityPathRoute(A, EP_A),
                    RoutePriorityPathRoute(B, EP_B),
                ),
            )

    def test_duplicate_physical_path_realization_is_rejected(self):
        value = profile()
        with self.assertRaisesRegex(
            RoutePriorityDomainBuildError,
            "duplicate physical route realization",
        ):
            build_route_priority_domain_realizations(
                value,
                allocation(value),
                (
                    RoutePriorityPathRoute(A, EP_A),
                    RoutePriorityPathRoute(A, EP_A),
                ),
            )

    def test_gateway_onlink_semantics_are_preserved_not_inferred(self):
        value = profile(paths=(A,))
        routed = RoutePriorityPathRoute(
            A,
            EP_A,
            gateway=None,
            onlink=False,
        )
        domains = build_route_priority_domain_realizations(
            value,
            allocation(value),
            (routed,),
        )
        self.assertEqual(domains[0].path_routes, (routed,))


if __name__ == "__main__":
    unittest.main()
