from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.network_policy_layout import (
    NetworkPolicyLayoutError,
    NetworkPolicyPlatformSpace,
    NumericResourcePool,
    ProbePolicyOwner,
    ProbeRoutingDemand,
    RouteMetricPlatformSpace,
    allocate_network_policy_layout,
)
from rou.payload_profile import PayloadProfileRequest


A = LogicalPathId("a", 0, 0)
B = LogicalPathId("b", 0, 0)


def platform(
    *,
    payload_tables=(1000, 1010),
    probe_tables=(2000, 2010),
    probe_priorities=(100, 200),
    payload_priorities=(1000, 2000),
    ambient=32766,
    first_metric=10,
    guard_metric=1000,
):
    return NetworkPolicyPlatformSpace(
        payload_tables=NumericResourcePool(*payload_tables),
        probe_tables=NumericResourcePool(*probe_tables),
        probe_rule_priorities=NumericResourcePool(*probe_priorities),
        payload_rule_priorities=NumericResourcePool(*payload_priorities),
        ambient_main_rule_priority=ambient,
        path_route_protocol=202,
        guard_route_protocol=201,
        legacy_host_boundary_lane_route_protocol=204,
        route_metrics=RouteMetricPlatformSpace(
            first_preference_metric=first_metric,
            terminal_guard_metric=guard_metric,
        ),
        nft_family="inet",
        nft_table="vpn_gate",
    )


def profile(profile_id, destinations, paths=()):
    return PayloadProfileRequest(
        profile_id=profile_id,
        direction=Direction.OUTBOUND,
        destinations=tuple(IPv4Network(value) for value in destinations),
        ordered_paths=tuple(paths),
    )


class NetworkPolicyLayoutTests(unittest.TestCase):
    def test_allocation_is_deterministic_across_input_order(self):
        p_a = profile("a", ("10.0.0.0/8",), (A, B))
        p_b = profile("b", ("192.0.2.0/24",), (B,))
        q_a = ProbeRoutingDemand(ProbePolicyOwner("a", A))
        q_b = ProbeRoutingDemand(ProbePolicyOwner("b", B))

        one = allocate_network_policy_layout(
            (p_b, p_a),
            (q_b, q_a),
            platform(),
        )
        two = allocate_network_policy_layout(
            (p_a, p_b),
            (q_a, q_b),
            platform(),
        )
        self.assertEqual(one, two)

    def test_payload_tables_are_ranked_by_profile_id_and_zero_path_is_kept(self):
        layout = allocate_network_policy_layout(
            (
                profile("z", ("203.0.113.0/24",), ()),
                profile("a", ("10.0.0.0/8",), (A,)),
            ),
            (),
            platform(),
        )
        by_id = {item.profile_id: item for item in layout.payload}
        self.assertEqual(by_id["a"].table, 1000)
        self.assertEqual(by_id["z"].table, 1001)
        self.assertIsNone(by_id["z"].metric_space)
        self.assertEqual(by_id["z"].terminal_guard_metric, 1000)

    def test_overlapping_dispatch_is_most_specific_first(self):
        layout = allocate_network_policy_layout(
            (
                profile("corp", ("10.0.0.0/8",), (A,)),
                profile("host", ("10.1.2.3/32",), (B,)),
                profile("subnet", ("10.1.0.0/16",), (A,)),
            ),
            (),
            platform(),
        )
        self.assertEqual(
            [
                (str(rule.destination), rule.priority)
                for rule in layout.dispatch_rules
            ],
            [
                ("10.1.2.3/32", 1000),
                ("10.1.0.0/16", 1001),
                ("10.0.0.0/8", 1002),
            ],
        )

    def test_metric_space_uses_same_internal_slots_per_profile_table(self):
        layout = allocate_network_policy_layout(
            (
                profile("a", ("10.0.0.0/8",), (A, B)),
                profile("b", ("192.0.2.0/24",), (B, A)),
            ),
            (),
            platform(first_metric=10, guard_metric=100),
        )
        for item in layout.payload:
            self.assertEqual(
                item.metric_space.preference_slots,
                (10, 11),
            )
            self.assertEqual(item.metric_space.scratch_metrics, (12,))
            self.assertEqual(item.terminal_guard_metric, 100)

    def test_probe_resources_are_disjoint_and_owner_sorted(self):
        layout = allocate_network_policy_layout(
            (profile("a", ("10.0.0.0/8",), (A,)),),
            (
                ProbeRoutingDemand(ProbePolicyOwner("b", B)),
                ProbeRoutingDemand(ProbePolicyOwner("a", A)),
            ),
            platform(),
        )
        self.assertEqual(
            [
                (item.owner.profile_id, item.table, item.rule_priority)
                for item in layout.probe
            ],
            [
                ("a", 2000, 100),
                ("b", 2001, 101),
            ],
        )
        self.assertTrue(
            all(item.table >= 2000 for item in layout.probe)
        )
        self.assertTrue(
            all(item.table < 2000 for item in layout.payload)
        )

    def test_payload_capacity_failure_happens_before_partial_result(self):
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "capacity",
        ):
            allocate_network_policy_layout(
                (
                    profile("a", ("10.0.0.0/8",), (A,)),
                    profile("b", ("192.0.2.0/24",), (B,)),
                ),
                (),
                platform(payload_tables=(1000, 1001)),
            )

    def test_dispatch_priority_capacity_is_checked(self):
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "capacity",
        ):
            allocate_network_policy_layout(
                (
                    profile(
                        "a",
                        ("10.0.0.0/8", "192.0.2.0/24"),
                        (A,),
                    ),
                ),
                (),
                platform(payload_priorities=(1000, 1001)),
            )

    def test_probe_capacity_is_checked(self):
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "capacity",
        ):
            allocate_network_policy_layout(
                (),
                (
                    ProbeRoutingDemand(ProbePolicyOwner("a", A)),
                    ProbeRoutingDemand(ProbePolicyOwner("b", B)),
                ),
                platform(probe_tables=(2000, 2001)),
            )

    def test_exact_duplicate_destination_ownership_is_rejected(self):
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "duplicate exact destination",
        ):
            allocate_network_policy_layout(
                (
                    profile("a", ("10.0.0.0/8",), (A,)),
                    profile("b", ("10.0.0.0/8",), (B,)),
                ),
                (),
                platform(),
            )

    def test_duplicate_logical_path_in_profile_is_rejected(self):
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "repeats a logical path",
        ):
            allocate_network_policy_layout(
                (profile("a", ("10.0.0.0/8",), (A, A)),),
                (),
                platform(),
            )

    def test_table_pools_must_be_disjoint_and_avoid_linux_reserved_ids(self):
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "must be disjoint",
        ):
            platform(
                payload_tables=(1000, 1010),
                probe_tables=(1005, 1020),
            )
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "reserved table IDs",
        ):
            platform(payload_tables=(250, 260))

    def test_rule_pools_encode_probe_before_payload_before_main(self):
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "higher precedence",
        ):
            platform(
                probe_priorities=(2000, 2100),
                payload_priorities=(1000, 1500),
            )
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "before ambient/main",
        ):
            platform(
                payload_priorities=(32000, 33000),
                ambient=32766,
            )

    def test_rule_pools_must_not_claim_linux_local_priority_zero(self):
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "priority 0",
        ):
            platform(probe_priorities=(0, 100))

    def test_payload_profile_id_must_be_non_empty(self):
        invalid = PayloadProfileRequest(
            profile_id="",
            direction=Direction.OUTBOUND,
            destinations=(IPv4Network("10.0.0.0/8"),),
            ordered_paths=(A,),
        )
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "non-empty string",
        ):
            allocate_network_policy_layout(
                (invalid,),
                (),
                platform(),
            )

    def test_route_protocol_markers_are_distinct_internal_roles(self):
        value = platform()
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "must be distinct",
        ):
            NetworkPolicyPlatformSpace(
                payload_tables=value.payload_tables,
                probe_tables=value.probe_tables,
                probe_rule_priorities=value.probe_rule_priorities,
                payload_rule_priorities=value.payload_rule_priorities,
                ambient_main_rule_priority=value.ambient_main_rule_priority,
                path_route_protocol=202,
                guard_route_protocol=202,
                legacy_host_boundary_lane_route_protocol=204,
                route_metrics=value.route_metrics,
                nft_family="inet",
                nft_table="vpn_gate",
            )

    def test_metric_space_rejects_unrepresentable_path_count(self):
        with self.assertRaisesRegex(
            NetworkPolicyLayoutError,
            "cannot fit",
        ):
            allocate_network_policy_layout(
                (
                    profile(
                        "a",
                        ("10.0.0.0/8",),
                        (A, B),
                    ),
                ),
                (),
                platform(first_metric=10, guard_metric=12),
            )

    def test_reserved_ranges_remain_classifiable_after_owner_set_changes(self):
        space = platform()
        first = allocate_network_policy_layout(
            (
                profile("a", ("10.0.0.0/8",), (A,)),
                profile("b", ("192.0.2.0/24",), (B,)),
            ),
            (),
            space,
        )
        old_b_table = next(
            item.table
            for item in first.payload
            if item.profile_id == "b"
        )

        second = allocate_network_policy_layout(
            (profile("b", ("192.0.2.0/24",), (B,)),),
            (),
            space,
        )
        new_b_table = second.payload[0].table

        self.assertNotEqual(old_b_table, new_b_table)
        self.assertTrue(space.payload_tables.contains(old_b_table))
        self.assertTrue(space.payload_tables.contains(new_b_table))

    def test_nft_namespace_is_platform_owned_not_derived_from_profile(self):
        layout = allocate_network_policy_layout(
            (
                profile(
                    "user_supplied_profile_name",
                    ("10.0.0.0/8",),
                    (A,),
                ),
            ),
            (),
            platform(),
        )
        self.assertEqual(layout.nft_family, "inet")
        self.assertEqual(layout.nft_table, "vpn_gate")
        self.assertNotIn(
            "user_supplied_profile_name",
            layout.nft_table,
        )


if __name__ == "__main__":
    unittest.main()
