from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network, IPv6Network
import unittest

from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.payload_profile import PayloadProfileRequest
from rou.profile_prefix_partition import (
    ProfilePrefixPartitionError,
    build_inbound_profile_partition,
    build_outbound_profile_partition,
)


P1 = LogicalPathId("dev-a", 0, 0)
P2 = LogicalPathId("dev-b", 0, 0)


def request(
    profile_id: str,
    direction: Direction,
    *destinations: str,
    paths=(P1,),
) -> PayloadProfileRequest:
    return PayloadProfileRequest(
        profile_id=profile_id,
        direction=direction,
        destinations=tuple(IPv4Network(value) for value in destinations),
        ordered_paths=tuple(paths),
    )


def owner_of_partition(partition, address: IPv4Address) -> str | None:
    owners = [
        item.profile_id
        for item in partition
        if address in item.remote_prefix
    ]
    if len(owners) > 1:
        raise AssertionError((address, owners, partition))
    return owners[0] if owners else None


def reference_profile_owner(
    requests,
    address: IPv4Address,
    *,
    ingress_path: LogicalPathId | None = None,
) -> str | None:
    """Test-local scalar oracle for most-specific Profile ownership."""
    candidates = []
    for profile in requests:
        if ingress_path is None:
            if profile.direction not in {Direction.OUTBOUND, Direction.BIDIRECTIONAL}:
                continue
        else:
            if profile.direction not in {Direction.INBOUND, Direction.BIDIRECTIONAL}:
                continue
            if ingress_path not in profile.ordered_paths:
                continue

        matching = tuple(
            network for network in profile.destinations
            if address in network
        )
        if matching:
            candidates.append(
                (max(network.prefixlen for network in matching), profile.profile_id)
            )

    if not candidates:
        return None
    best = max(prefixlen for prefixlen, _ in candidates)
    owners = sorted(
        profile_id
        for prefixlen, profile_id in candidates
        if prefixlen == best
    )
    if len(owners) != 1:
        raise AssertionError((address, ingress_path, owners))
    return owners[0]


class ProfilePrefixPartitionTests(unittest.TestCase):
    def assert_disjoint(self, partition):
        for index, left in enumerate(partition):
            for right in partition[index + 1 :]:
                self.assertFalse(
                    left.remote_prefix.overlaps(right.remote_prefix),
                    (left, right),
                )

    def assert_outbound_equivalent(self, requests, domain: str):
        partition = build_outbound_profile_partition(requests)
        network = IPv4Network(domain)
        for integer in range(
            int(network.network_address),
            int(network.broadcast_address) + 1,
        ):
            address = IPv4Address(integer)
            self.assertEqual(
                owner_of_partition(partition, address),
                reference_profile_owner(requests, address),
                address,
            )
        self.assert_disjoint(partition)

    def assert_inbound_equivalent(self, requests, ingress_path, domain: str):
        partition = build_inbound_profile_partition(requests, ingress_path)
        network = IPv4Network(domain)
        for integer in range(
            int(network.network_address),
            int(network.broadcast_address) + 1,
        ):
            address = IPv4Address(integer)
            self.assertEqual(
                owner_of_partition(partition, address),
                reference_profile_owner(
                    requests,
                    address,
                    ingress_path=ingress_path,
                ),
                address,
            )
        self.assert_disjoint(partition)

    def test_non_overlapping_outbound_profiles_remain_direct_fragments(self):
        requests = (
            request("a", Direction.OUTBOUND, "10.0.0.0/25"),
            request("b", Direction.BIDIRECTIONAL, "10.0.0.128/25"),
        )
        partition = build_outbound_profile_partition(requests)
        self.assertEqual(
            [(x.profile_id, str(x.remote_prefix)) for x in partition],
            [("a", "10.0.0.0/25"), ("b", "10.0.0.128/25")],
        )

    def test_more_specific_profile_carves_broad_profile(self):
        requests = (
            request("broad", Direction.OUTBOUND, "10.0.0.0/24"),
            request("specific", Direction.OUTBOUND, "10.0.0.64/26"),
        )
        partition = build_outbound_profile_partition(requests)
        self.assert_outbound_equivalent(requests, "10.0.0.0/24")
        self.assertIn(
            ("specific", "10.0.0.64/26"),
            [(x.profile_id, str(x.remote_prefix)) for x in partition],
        )
        self.assertFalse(
            any(
                x.profile_id == "broad"
                and IPv4Address("10.0.0.65") in x.remote_prefix
                for x in partition
            )
        )

    def test_alternating_nested_owners_restore_more_specific_outer_owner(self):
        requests = (
            request("a", Direction.OUTBOUND, "0.0.0.0/0", "64.0.0.0/3"),
            request("b", Direction.OUTBOUND, "0.0.0.0/1"),
        )
        partition = build_outbound_profile_partition(requests)
        for address, expected in (
            ("1.1.1.1", "b"),
            ("70.0.0.1", "a"),
            ("130.0.0.1", "a"),
        ):
            self.assertEqual(
                owner_of_partition(partition, IPv4Address(address)),
                expected,
            )
        self.assert_disjoint(partition)

    def test_default_profile_is_partitioned_by_specific_profile(self):
        requests = (
            request("default", Direction.OUTBOUND, "0.0.0.0/0"),
            request("specific", Direction.OUTBOUND, "192.0.2.0/24"),
        )
        partition = build_outbound_profile_partition(requests)
        self.assertEqual(
            owner_of_partition(partition, IPv4Address("192.0.2.5")),
            "specific",
        )
        self.assertEqual(
            owner_of_partition(partition, IPv4Address("203.0.113.5")),
            "default",
        )
        self.assert_disjoint(partition)

    def test_same_profile_nested_destinations_collapse_without_semantic_change(self):
        requests = (
            request(
                "a",
                Direction.OUTBOUND,
                "10.0.0.0/24",
                "10.0.0.64/26",
            ),
        )
        partition = build_outbound_profile_partition(requests)
        self.assertEqual(
            [(x.profile_id, str(x.remote_prefix)) for x in partition],
            [("a", "10.0.0.0/24")],
        )

    def test_exact_duplicate_destination_across_outbound_candidates_is_error(self):
        requests = (
            request("a", Direction.OUTBOUND, "10.0.0.0/24"),
            request("b", Direction.BIDIRECTIONAL, "10.0.0.0/24"),
        )
        with self.assertRaisesRegex(
            ProfilePrefixPartitionError,
            "belongs to multiple candidate Profiles",
        ):
            build_outbound_profile_partition(requests)

    def test_outbound_excludes_inbound_only_profile(self):
        requests = (
            request("out", Direction.OUTBOUND, "10.0.0.0/24"),
            request("in", Direction.INBOUND, "10.0.0.64/26"),
        )
        partition = build_outbound_profile_partition(requests)
        self.assertEqual(
            [(x.profile_id, str(x.remote_prefix)) for x in partition],
            [("out", "10.0.0.0/24")],
        )

    def test_inbound_specific_profile_on_other_path_does_not_shadow(self):
        requests = (
            request(
                "broad",
                Direction.INBOUND,
                "10.0.0.0/24",
                paths=(P1,),
            ),
            request(
                "specific-other",
                Direction.INBOUND,
                "10.0.0.64/26",
                paths=(P2,),
            ),
        )
        partition = build_inbound_profile_partition(requests, P1)
        self.assertEqual(
            [(x.profile_id, str(x.remote_prefix)) for x in partition],
            [("broad", "10.0.0.0/24")],
        )
        self.assert_inbound_equivalent(
            requests,
            P1,
            "10.0.0.0/24",
        )

    def test_inbound_specific_profile_shadows_when_ingress_path_is_allowed(self):
        requests = (
            request(
                "broad",
                Direction.BIDIRECTIONAL,
                "10.0.0.0/24",
                paths=(P1,),
            ),
            request(
                "specific",
                Direction.INBOUND,
                "10.0.0.64/26",
                paths=(P1, P2),
            ),
        )
        self.assert_inbound_equivalent(
            requests,
            P1,
            "10.0.0.0/24",
        )
        partition = build_inbound_profile_partition(requests, P1)
        self.assertEqual(
            owner_of_partition(
                partition,
                IPv4Address("10.0.0.70"),
            ),
            "specific",
        )

    def test_inbound_excludes_outbound_only_profile(self):
        requests = (
            request(
                "out",
                Direction.OUTBOUND,
                "10.0.0.0/24",
                paths=(P1,),
            ),
        )
        self.assertEqual(
            build_inbound_profile_partition(requests, P1),
            (),
        )

    def test_no_candidates_returns_empty_partition(self):
        requests = (
            request("in", Direction.INBOUND, "10.0.0.0/24"),
        )
        self.assertEqual(build_outbound_profile_partition(requests), ())

    def test_partition_is_independent_of_request_input_order(self):
        requests = (
            request("a", Direction.OUTBOUND, "10.0.0.0/24"),
            request("b", Direction.OUTBOUND, "10.0.0.64/26"),
            request("c", Direction.OUTBOUND, "10.0.0.80/28"),
        )
        self.assertEqual(
            build_outbound_profile_partition(requests),
            build_outbound_profile_partition(tuple(reversed(requests))),
        )

    def test_exhaustive_outbound_equivalence_for_nested_profiles(self):
        requests = (
            request("a", Direction.OUTBOUND, "10.0.0.0/24"),
            request("b", Direction.OUTBOUND, "10.0.0.64/26"),
            request("c", Direction.BIDIRECTIONAL, "10.0.0.80/28"),
            request("a2", Direction.INBOUND, "10.0.0.88/29"),
        )
        self.assert_outbound_equivalent(
            requests,
            "10.0.0.0/24",
        )

    def test_exhaustive_inbound_equivalence_is_path_relative(self):
        requests = (
            request(
                "a",
                Direction.INBOUND,
                "10.0.0.0/24",
                paths=(P1,),
            ),
            request(
                "b",
                Direction.BIDIRECTIONAL,
                "10.0.0.64/26",
                paths=(P2,),
            ),
            request(
                "c",
                Direction.INBOUND,
                "10.0.0.80/28",
                paths=(P1, P2),
            ),
        )
        self.assert_inbound_equivalent(
            requests,
            P1,
            "10.0.0.0/24",
        )
        self.assert_inbound_equivalent(
            requests,
            P2,
            "10.0.0.0/24",
        )

    def test_invalid_ingress_path_is_rejected(self):
        requests = (
            request("a", Direction.INBOUND, "10.0.0.0/24"),
        )
        with self.assertRaisesRegex(
            ProfilePrefixPartitionError,
            "LogicalPathId",
        ):
            build_inbound_profile_partition(requests, "not-a-path")

    def test_duplicate_profile_id_is_rejected(self):
        requests = (
            request("a", Direction.OUTBOUND, "10.0.0.0/25"),
            request("a", Direction.OUTBOUND, "10.0.0.128/25"),
        )
        with self.assertRaisesRegex(
            ProfilePrefixPartitionError,
            "duplicate Profile request",
        ):
            build_outbound_profile_partition(requests)

    def test_duplicate_destination_inside_profile_is_rejected(self):
        network = IPv4Network("10.0.0.0/24")
        profile = PayloadProfileRequest(
            profile_id="a",
            direction=Direction.OUTBOUND,
            destinations=(network, network),
            ordered_paths=(P1,),
        )
        with self.assertRaisesRegex(
            ProfilePrefixPartitionError,
            "repeats destination",
        ):
            build_outbound_profile_partition((profile,))

    def test_non_ipv4_destination_is_rejected(self):
        profile = PayloadProfileRequest(
            profile_id="a",
            direction=Direction.OUTBOUND,
            destinations=(IPv6Network("2001:db8::/32"),),
            ordered_paths=(P1,),
        )
        with self.assertRaisesRegex(
            ProfilePrefixPartitionError,
            "non-IPv4 destination",
        ):
            build_outbound_profile_partition((profile,))

    def test_invalid_direction_is_rejected(self):
        profile = PayloadProfileRequest(
            profile_id="a",
            direction=None,
            destinations=(IPv4Network("10.0.0.0/24"),),
            ordered_paths=(P1,),
        )
        with self.assertRaisesRegex(
            ProfilePrefixPartitionError,
            "invalid direction",
        ):
            build_outbound_profile_partition((profile,))


if __name__ == "__main__":
    unittest.main()
