from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.device_policy import DeviceNatPolicyIntent, NatIntent
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.payload_nat_desired import (
    PayloadNatProjectionError,
    build_payload_nat_desired_state,
)
from rou.payload_profile import PayloadProfileRequest
from rou.route_priority_inventory import RoutePriorityPathRoute


A0 = LogicalPathId("a", 0, 0)
A1 = LogicalPathId("a", 0, 1)
B0 = LogicalPathId("b", 0, 0)
EP_A0 = InterfaceIdentity("a0", 10)
EP_A1 = InterfaceIdentity("a1", 11)
EP_B0 = InterfaceIdentity("b0", 20)
HOST = InterfaceIdentity("host0", 5)


def profile(profile_id, paths):
    return PayloadProfileRequest(
        profile_id=profile_id,
        direction=Direction.OUTBOUND,
        destinations=(IPv4Network("10.0.0.0/8"),),
        ordered_paths=tuple(paths),
    )


def route(path_id, endpoint):
    return RoutePriorityPathRoute(path_id, endpoint)


class PayloadNatDesiredTests(unittest.TestCase):
    def test_none_emits_no_physical_nat_rule(self):
        value = build_payload_nat_desired_state(
            (profile("p", (A0,)),),
            (route(A0, EP_A0),),
            (DeviceNatPolicyIntent("a", NatIntent.NONE),),
            HOST,
        )
        self.assertEqual(value.masquerade_rules, ())

    def test_masquerade_uses_exact_boundary_and_current_endpoint(self):
        value = build_payload_nat_desired_state(
            (profile("p", (A0,)),),
            (route(A0, EP_A0),),
            (DeviceNatPolicyIntent("a", NatIntent.MASQUERADE),),
            HOST,
        )
        self.assertEqual(len(value.masquerade_rules), 1)
        rule = value.masquerade_rules[0]
        self.assertEqual(rule.path_id, A0)
        self.assertEqual(rule.ingress, HOST)
        self.assertEqual(rule.egress, EP_A0)

    def test_shared_path_across_profiles_is_deduplicated(self):
        value = build_payload_nat_desired_state(
            (
                profile("p1", (A0,)),
                profile("p2", (A0,)),
            ),
            (route(A0, EP_A0),),
            (DeviceNatPolicyIntent("a", NatIntent.MASQUERADE),),
            HOST,
        )
        self.assertEqual(len(value.masquerade_rules), 1)

    def test_multiple_current_paths_receive_independent_rules(self):
        value = build_payload_nat_desired_state(
            (profile("p", (A0, A1, B0)),),
            (
                route(B0, EP_B0),
                route(A1, EP_A1),
                route(A0, EP_A0),
            ),
            (
                DeviceNatPolicyIntent("b", NatIntent.NONE),
                DeviceNatPolicyIntent("a", NatIntent.MASQUERADE),
            ),
            HOST,
        )
        self.assertEqual(
            [(item.path_id, item.egress) for item in value.masquerade_rules],
            [(A0, EP_A0), (A1, EP_A1)],
        )

    def test_missing_nat_intent_is_not_an_implicit_default(self):
        with self.assertRaisesRegex(
            PayloadNatProjectionError,
            "no explicit normalized NAT intent",
        ):
            build_payload_nat_desired_state(
                (profile("p", (A0,)),),
                (route(A0, EP_A0),),
                (),
                HOST,
            )

    def test_duplicate_device_nat_policy_is_rejected(self):
        with self.assertRaisesRegex(
            PayloadNatProjectionError,
            "duplicate Device NAT policy",
        ):
            build_payload_nat_desired_state(
                (profile("p", (A0,)),),
                (route(A0, EP_A0),),
                (
                    DeviceNatPolicyIntent("a", NatIntent.NONE),
                    DeviceNatPolicyIntent("a", NatIntent.MASQUERADE),
                ),
                HOST,
            )

    def test_stale_or_missing_path_route_set_is_rejected(self):
        with self.assertRaisesRegex(
            PayloadNatProjectionError,
            "does not exactly match",
        ):
            build_payload_nat_desired_state(
                (profile("p", (A0,)),),
                (route(A0, EP_A0), route(B0, EP_B0)),
                (DeviceNatPolicyIntent("a", NatIntent.MASQUERADE),),
                HOST,
            )

    def test_same_endpoint_for_two_paths_is_rejected(self):
        with self.assertRaisesRegex(
            PayloadNatProjectionError,
            "multiple logical paths",
        ):
            build_payload_nat_desired_state(
                (profile("p", (A0, B0)),),
                (route(A0, EP_A0), route(B0, EP_A0)),
                (
                    DeviceNatPolicyIntent("a", NatIntent.MASQUERADE),
                    DeviceNatPolicyIntent("b", NatIntent.MASQUERADE),
                ),
                HOST,
            )

    def test_duplicate_profile_identity_is_rejected(self):
        with self.assertRaisesRegex(
            PayloadNatProjectionError,
            "duplicate payload Profile",
        ):
            build_payload_nat_desired_state(
                (
                    profile("same", (A0,)),
                    profile("same", (A0,)),
                ),
                (route(A0, EP_A0),),
                (DeviceNatPolicyIntent("a", NatIntent.MASQUERADE),),
                HOST,
            )

    def test_host_boundary_cannot_be_vpn_egress_endpoint(self):
        with self.assertRaisesRegex(
            PayloadNatProjectionError,
            "host boundary",
        ):
            build_payload_nat_desired_state(
                (profile("p", (A0,)),),
                (route(A0, HOST),),
                (DeviceNatPolicyIntent("a", NatIntent.MASQUERADE),),
                HOST,
            )

    def test_zero_path_profiles_need_no_nat_policy(self):
        value = build_payload_nat_desired_state(
            (profile("empty", ()),),
            (),
            (),
            HOST,
        )
        self.assertEqual(value.masquerade_rules, ())


if __name__ == "__main__":
    unittest.main()
