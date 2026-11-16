from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.payload_forward_compiler import (
    PayloadForwardCompileError,
    compile_payload_forward_policy,
)
from rou.payload_forward_desired import PayloadForwardRuleSpec
from rou.payload_forward_observation import (
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
)
from rou.payload_profile import PayloadProfileRequest
from rou.route_priority_inventory import RoutePriorityPathRoute


HOST = InterfaceIdentity("host0", 10)
EP_A = InterfaceIdentity("vpn-a", 20)
EP_B = InterfaceIdentity("vpn-b", 30)
PATH_A = LogicalPathId("a", 0, 0)
PATH_B = LogicalPathId("b", 0, 0)
ROUTE_A = RoutePriorityPathRoute(PATH_A, EP_A)
ROUTE_B = RoutePriorityPathRoute(PATH_B, EP_B)


def profile(profile_id, direction, destinations, paths):
    return PayloadProfileRequest(
        profile_id=profile_id,
        direction=direction,
        destinations=tuple(IPv4Network(value) for value in destinations),
        ordered_paths=tuple(paths),
    )


def rule(kind, ingress, egress, field, prefix):
    return PayloadForwardRuleSpec(
        kind=kind,
        ingress=ingress,
        egress=egress,
        remote_field=field,
        remote_prefix=IPv4Network(prefix),
    )


class PayloadForwardCompilerTests(unittest.TestCase):
    def test_outbound_compiles_new_and_stateful_return(self):
        desired = compile_payload_forward_policy(
            (
                profile(
                    "corp",
                    Direction.OUTBOUND,
                    ("10.0.0.0/8",),
                    (PATH_A,),
                ),
            ),
            (ROUTE_A,),
            HOST,
        )
        self.assertEqual(
            set(desired.rules),
            {
                rule(
                    PayloadForwardRuleKind.NEW,
                    HOST,
                    EP_A,
                    PayloadForwardRemoteField.DESTINATION,
                    "10.0.0.0/8",
                ),
                rule(
                    PayloadForwardRuleKind.RETURN,
                    EP_A,
                    HOST,
                    PayloadForwardRemoteField.SOURCE,
                    "10.0.0.0/8",
                ),
            },
        )

    def test_inbound_compiles_ingress_new_and_reverse_return(self):
        desired = compile_payload_forward_policy(
            (
                profile(
                    "support",
                    Direction.INBOUND,
                    ("192.0.2.0/24",),
                    (PATH_A,),
                ),
            ),
            (ROUTE_A,),
            HOST,
        )
        self.assertEqual(
            set(desired.rules),
            {
                rule(
                    PayloadForwardRuleKind.NEW,
                    EP_A,
                    HOST,
                    PayloadForwardRemoteField.SOURCE,
                    "192.0.2.0/24",
                ),
                rule(
                    PayloadForwardRuleKind.RETURN,
                    HOST,
                    EP_A,
                    PayloadForwardRemoteField.DESTINATION,
                    "192.0.2.0/24",
                ),
            },
        )

    def test_bidirectional_compiles_both_new_directions_and_returns(self):
        desired = compile_payload_forward_policy(
            (
                profile(
                    "bi",
                    Direction.BIDIRECTIONAL,
                    ("198.51.100.7/32",),
                    (PATH_A,),
                ),
            ),
            (ROUTE_A,),
            HOST,
        )
        self.assertEqual(len(desired.rules), 4)
        self.assertEqual(
            {
                (item.kind, item.ingress, item.egress, item.remote_field)
                for item in desired.rules
            },
            {
                (
                    PayloadForwardRuleKind.NEW,
                    HOST,
                    EP_A,
                    PayloadForwardRemoteField.DESTINATION,
                ),
                (
                    PayloadForwardRuleKind.RETURN,
                    EP_A,
                    HOST,
                    PayloadForwardRemoteField.SOURCE,
                ),
                (
                    PayloadForwardRuleKind.NEW,
                    EP_A,
                    HOST,
                    PayloadForwardRemoteField.SOURCE,
                ),
                (
                    PayloadForwardRuleKind.RETURN,
                    HOST,
                    EP_A,
                    PayloadForwardRemoteField.DESTINATION,
                ),
            },
        )

    def test_zero_path_profile_generates_no_positive_permission(self):
        desired = compile_payload_forward_policy(
            (
                profile(
                    "future",
                    Direction.OUTBOUND,
                    ("10.0.0.0/8",),
                    (),
                ),
            ),
            (),
            HOST,
        )
        self.assertEqual(desired.rules, ())

    def test_outbound_most_specific_partition_prevents_broad_path_widening(self):
        specific = IPv4Network("10.20.0.0/16")
        desired = compile_payload_forward_policy(
            (
                profile(
                    "broad",
                    Direction.OUTBOUND,
                    ("10.0.0.0/8",),
                    (PATH_B,),
                ),
                profile(
                    "specific",
                    Direction.OUTBOUND,
                    ("10.20.0.0/16",),
                    (PATH_A,),
                ),
            ),
            (ROUTE_A, ROUTE_B),
            HOST,
        )

        a_new = [
            item
            for item in desired.rules
            if item.kind is PayloadForwardRuleKind.NEW
            and item.ingress == HOST
            and item.egress == EP_A
        ]
        b_new = [
            item
            for item in desired.rules
            if item.kind is PayloadForwardRuleKind.NEW
            and item.ingress == HOST
            and item.egress == EP_B
        ]

        self.assertEqual(
            [item.remote_prefix for item in a_new],
            [specific],
        )
        self.assertTrue(b_new)
        self.assertTrue(
            all(
                not item.remote_prefix.overlaps(specific)
                for item in b_new
            )
        )

    def test_inbound_partition_is_restricted_by_actual_ingress_path_first(self):
        desired = compile_payload_forward_policy(
            (
                profile(
                    "broad-b",
                    Direction.INBOUND,
                    ("10.0.0.0/8",),
                    (PATH_B,),
                ),
                profile(
                    "specific-a",
                    Direction.INBOUND,
                    ("10.20.0.0/16",),
                    (PATH_A,),
                ),
            ),
            (ROUTE_A, ROUTE_B),
            HOST,
        )

        b_new = [
            item
            for item in desired.rules
            if item.kind is PayloadForwardRuleKind.NEW
            and item.ingress == EP_B
            and item.egress == HOST
        ]
        a_new = [
            item
            for item in desired.rules
            if item.kind is PayloadForwardRuleKind.NEW
            and item.ingress == EP_A
            and item.egress == HOST
        ]

        self.assertEqual(
            [item.remote_prefix for item in b_new],
            [IPv4Network("10.0.0.0/8")],
        )
        self.assertEqual(
            [item.remote_prefix for item in a_new],
            [IPv4Network("10.20.0.0/16")],
        )

    def test_physical_path_set_must_exactly_match_semantic_membership(self):
        with self.assertRaisesRegex(
            PayloadForwardCompileError,
            "exactly match current semantic payload paths",
        ):
            compile_payload_forward_policy(
                (
                    profile(
                        "corp",
                        Direction.OUTBOUND,
                        ("10.0.0.0/8",),
                        (PATH_A,),
                    ),
                ),
                (ROUTE_A, ROUTE_B),
                HOST,
            )

    def test_one_endpoint_cannot_realize_two_logical_paths(self):
        duplicate_endpoint = RoutePriorityPathRoute(PATH_B, EP_A)
        with self.assertRaisesRegex(
            PayloadForwardCompileError,
            "cannot realize multiple logical paths",
        ):
            compile_payload_forward_policy(
                (
                    profile(
                        "corp",
                        Direction.OUTBOUND,
                        ("10.0.0.0/8",),
                        (PATH_A, PATH_B),
                    ),
                ),
                (ROUTE_A, duplicate_endpoint),
                HOST,
            )

    def test_host_boundary_cannot_be_payload_path_endpoint(self):
        host_route = RoutePriorityPathRoute(PATH_A, HOST)
        with self.assertRaisesRegex(
            PayloadForwardCompileError,
            "host boundary cannot also be",
        ):
            compile_payload_forward_policy(
                (
                    profile(
                        "corp",
                        Direction.OUTBOUND,
                        ("10.0.0.0/8",),
                        (PATH_A,),
                    ),
                ),
                (host_route,),
                HOST,
            )

    def test_duplicate_profile_identity_is_rejected(self):
        p = profile(
            "corp",
            Direction.OUTBOUND,
            ("10.0.0.0/8",),
            (PATH_A,),
        )
        with self.assertRaisesRegex(
            PayloadForwardCompileError,
            "duplicate Profile request",
        ):
            compile_payload_forward_policy(
                (p, p),
                (ROUTE_A,),
                HOST,
            )


if __name__ == "__main__":
    unittest.main()
