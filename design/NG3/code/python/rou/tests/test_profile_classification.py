from __future__ import annotations

import ipaddress
import unittest

from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.payload_profile import PayloadProfileRequest
from rou.profile_classification import (
    ProfileClassificationError,
    classify_inbound_profile,
    classify_outbound_profile,
)


def req(
    profile_id: str,
    direction: Direction,
    prefixes: tuple[str, ...],
    paths: tuple[LogicalPathId, ...] = (),
) -> PayloadProfileRequest:
    return PayloadProfileRequest(
        profile_id=profile_id,
        direction=direction,
        destinations=tuple(ipaddress.IPv4Network(value) for value in prefixes),
        ordered_paths=paths,
    )


class ProfileClassificationTests(unittest.TestCase):
    def test_outbound_direction_and_most_specific(self):
        requests = (
            req("broad", Direction.OUTBOUND, ("10.0.0.0/8",)),
            req("specific", Direction.BIDIRECTIONAL, ("10.1.0.0/16",)),
            req("inbound-only", Direction.INBOUND, ("10.1.2.0/24",)),
        )
        self.assertEqual(
            classify_outbound_profile(requests, ipaddress.IPv4Address("10.1.2.3")).profile_id,
            "specific",
        )

    def test_outbound_no_match_is_none(self):
        requests = (req("corp", Direction.OUTBOUND, ("10.0.0.0/8",)),)
        self.assertIsNone(
            classify_outbound_profile(requests, ipaddress.IPv4Address("192.0.2.1"))
        )

    def test_inbound_filters_by_direction_and_ingress_before_prefix(self):
        path_a = LogicalPathId("a", 0, 0)
        path_b = LogicalPathId("b", 0, 0)
        requests = (
            req("valid-a", Direction.INBOUND, ("10.0.0.0/8",), (path_a,)),
            req("wrong-path-specific", Direction.INBOUND, ("10.1.0.0/16",), (path_b,)),
            req("outbound-only", Direction.OUTBOUND, ("10.1.2.0/24",), (path_a,)),
        )
        self.assertEqual(
            classify_inbound_profile(
                requests, path_a, ipaddress.IPv4Address("10.1.2.3")
            ).profile_id,
            "valid-a",
        )

    def test_same_remote_source_classifies_by_actual_ingress(self):
        path_a = LogicalPathId("a", 0, 0)
        path_b = LogicalPathId("b", 0, 0)
        requests = (
            req("via-a", Direction.INBOUND, ("10.0.0.0/8",), (path_a,)),
            req("via-b", Direction.INBOUND, ("10.0.0.0/8",), (path_b,)),
        )
        source = ipaddress.IPv4Address("10.2.3.4")
        self.assertEqual(classify_inbound_profile(requests, path_a, source).profile_id, "via-a")
        self.assertEqual(classify_inbound_profile(requests, path_b, source).profile_id, "via-b")

    def test_zero_path_profile_cannot_accept_inbound_new_flow(self):
        path = LogicalPathId("a", 0, 0)
        requests = (req("zero", Direction.INBOUND, ("10.0.0.0/8",), ()),)
        self.assertIsNone(
            classify_inbound_profile(requests, path, ipaddress.IPv4Address("10.1.2.3"))
        )

    def test_specificity_uses_only_prefixes_matching_the_remote_address(self):
        requests = (
            req("mixed", Direction.OUTBOUND, ("10.0.0.0/8", "192.0.2.1/32")),
            req("actual-specific", Direction.OUTBOUND, ("10.1.0.0/16",)),
        )
        self.assertEqual(
            classify_outbound_profile(
                requests, ipaddress.IPv4Address("10.1.2.3")
            ).profile_id,
            "actual-specific",
        )

    def test_ambiguous_equal_specificity_fails_instead_of_using_input_order(self):
        requests = (
            req("a", Direction.OUTBOUND, ("10.0.0.0/8",)),
            req("b", Direction.OUTBOUND, ("10.0.0.0/8",)),
        )
        with self.assertRaises(ProfileClassificationError):
            classify_outbound_profile(requests, ipaddress.IPv4Address("10.1.2.3"))


if __name__ == "__main__":
    unittest.main()
