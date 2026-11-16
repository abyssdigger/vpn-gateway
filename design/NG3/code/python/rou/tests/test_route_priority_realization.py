from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.route_priority_profile import RoutePriorityDomainId
from rou.route_priority_realization import (
    RoutePriorityDomainRealization,
    RoutePriorityMetricSpace,
    RoutePriorityRealizationError,
)


A = LogicalPathId("a", 0, 0)
B = LogicalPathId("b", 0, 0)
EP_A = InterfaceIdentity("patha", 10)
EP_B = InterfaceIdentity("pathb", 20)
DOMAIN = RoutePriorityDomainId("profile-a", IPv4Network("10.0.0.0/8"))


def realization(metric_space=None, paths=None):
    return RoutePriorityDomainRealization(
        domain_id=DOMAIN,
        table=100,
        owner_protocol=202,
        path_routes=(
            RoutePriorityPathRoute(A, EP_A),
            RoutePriorityPathRoute(B, EP_B),
        ) if paths is None else paths,
        metric_space=metric_space
        or RoutePriorityMetricSpace(
            preference_slots=(10, 20),
            scratch_metrics=(30,),
        ),
    )


class RoutePriorityRealizationTests(unittest.TestCase):
    def test_semantic_order_maps_to_internal_preference_slots(self):
        value = realization()
        self.assertEqual(dict(value.desired_metrics((A, B))), {A: 10, B: 20})
        self.assertEqual(dict(value.desired_metrics((B, A))), {B: 10, A: 20})
        self.assertEqual(value.metric_space.working_metrics, (10, 20, 30))

    def test_membership_mismatch_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityRealizationError,
            "membership does not match",
        ):
            realization().desired_metrics((A,))

    def test_duplicate_semantic_path_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityRealizationError,
            "membership does not match",
        ):
            realization().desired_metrics((A, A))

    def test_multi_path_requires_scratch_metric(self):
        with self.assertRaisesRegex(
            RoutePriorityRealizationError,
            "scratch",
        ):
            realization(
                RoutePriorityMetricSpace(preference_slots=(10, 20))
            )

    def test_single_path_does_not_require_scratch_metric(self):
        value = realization(
            RoutePriorityMetricSpace(preference_slots=(10,)),
            paths=(RoutePriorityPathRoute(A, EP_A),),
        )
        self.assertEqual(dict(value.desired_metrics((A,))), {A: 10})

    def test_preference_slots_must_follow_linux_metric_preference(self):
        with self.assertRaisesRegex(
            RoutePriorityRealizationError,
            "strictly increasing",
        ):
            RoutePriorityMetricSpace(
                preference_slots=(20, 10),
                scratch_metrics=(30,),
            )

    def test_metric_space_rejects_duplicate_or_invalid_metrics(self):
        with self.assertRaisesRegex(
            RoutePriorityRealizationError,
            "duplicate metrics",
        ):
            RoutePriorityMetricSpace(
                preference_slots=(10, 20),
                scratch_metrics=(20,),
            )
        with self.assertRaisesRegex(
            RoutePriorityRealizationError,
            "integers in",
        ):
            RoutePriorityMetricSpace(preference_slots=(True,))
        with self.assertRaisesRegex(
            RoutePriorityRealizationError,
            "integers in",
        ):
            RoutePriorityMetricSpace(preference_slots=(0x1_0000_0000,))

    def test_one_endpoint_cannot_realize_two_logical_paths(self):
        with self.assertRaisesRegex(
            RoutePriorityRealizationError,
            "one endpoint",
        ):
            realization(
                paths=(
                    RoutePriorityPathRoute(A, EP_A),
                    RoutePriorityPathRoute(B, EP_A),
                )
            )

    def test_table_and_protocol_are_strict_internal_identifiers(self):
        with self.assertRaisesRegex(RoutePriorityRealizationError, "table"):
            RoutePriorityDomainRealization(
                DOMAIN,
                True,
                202,
                (RoutePriorityPathRoute(A, EP_A),),
                RoutePriorityMetricSpace((10,)),
            )
        with self.assertRaisesRegex(
            RoutePriorityRealizationError,
            "owner_protocol",
        ):
            RoutePriorityDomainRealization(
                DOMAIN,
                100,
                True,
                (RoutePriorityPathRoute(A, EP_A),),
                RoutePriorityMetricSpace((10,)),
            )


if __name__ == "__main__":
    unittest.main()
