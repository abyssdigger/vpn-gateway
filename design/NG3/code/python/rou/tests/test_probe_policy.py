from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.network_policy_layout import (
    ProbePolicyOwner,
    ProbeRoutingDemand,
    allocate_network_policy_layout,
)
from rou.probe_policy import (
    AvailabilityProbeIntent,
    AvailabilityProbeMechanism,
    ProbeLocalHook,
    ProbeLocalPlatform,
    ProbePolicyProjectionError,
    ProbeRouteType,
    build_probe_network_policy_desired_state,
)
from rou.route_priority_inventory import RoutePriorityPathRoute


A = LogicalPathId("a", 0, 0)
B = LogicalPathId("b", 0, 0)
EP_A = InterfaceIdentity("vpn0", 10)
EP_B = InterfaceIdentity("vpn1", 20)
TARGET_A = IPv4Address("10.10.10.1")
TARGET_B = IPv4Address("10.20.20.1")
LOCAL = ProbeLocalPlatform(process_uid=4242, conntrack_mark=0x20000001)


def intent(profile_id, path_id, target):
    return AvailabilityProbeIntent(
        ProbePolicyOwner(profile_id, path_id),
        IPv4Address(target),
    )


def build(intents, path_routes):
    current = tuple(intents)
    layout = allocate_network_policy_layout(
        (),
        tuple(
            ProbeRoutingDemand(item.owner)
            for item in current
        ),
        NG3_LINUX_POLICY_PLATFORM,
    )
    return build_probe_network_policy_desired_state(
        current,
        layout,
        path_routes,
        NG3_LINUX_POLICY_PLATFORM,
        LOCAL,
    )


class ProbePolicyTests(unittest.TestCase):
    def test_one_probe_projects_exact_route_rule_and_local_admission(self):
        desired = build(
            (intent("corp", A, str(TARGET_A)),),
            (RoutePriorityPathRoute(A, EP_A),),
        )

        self.assertEqual(len(desired.routes), 2)
        unicast = next(
            route
            for route in desired.routes
            if route.route_type is ProbeRouteType.UNICAST
        )
        guard = next(
            route
            for route in desired.routes
            if route.route_type is ProbeRouteType.BLACKHOLE
        )
        self.assertEqual(
            unicast.destination,
            IPv4Network(f"{TARGET_A}/32"),
        )
        self.assertEqual(unicast.endpoint, EP_A)
        self.assertEqual(unicast.path_id, A)
        self.assertEqual(
            unicast.protocol,
            NG3_LINUX_POLICY_PLATFORM.path_route_protocol,
        )
        self.assertEqual(
            unicast.metric,
            NG3_LINUX_POLICY_PLATFORM.route_metrics.first_preference_metric,
        )
        self.assertEqual(guard.destination, IPv4Network("0.0.0.0/0"))
        self.assertEqual(
            guard.protocol,
            NG3_LINUX_POLICY_PLATFORM.guard_route_protocol,
        )
        self.assertEqual(
            guard.metric,
            NG3_LINUX_POLICY_PLATFORM.route_metrics.terminal_guard_metric,
        )

        self.assertEqual(len(desired.rules), 1)
        rule = desired.rules[0]
        self.assertEqual(rule.owner, ProbePolicyOwner("corp", A))
        self.assertIs(rule.mechanism, AvailabilityProbeMechanism.ICMP)
        self.assertEqual(rule.process_uid, 4242)
        self.assertEqual(rule.target, TARGET_A)
        self.assertTrue(
            NG3_LINUX_POLICY_PLATFORM.probe_tables.contains(rule.table)
        )
        self.assertTrue(
            NG3_LINUX_POLICY_PLATFORM.probe_rule_priorities.contains(
                rule.priority
            )
        )

        self.assertEqual(len(desired.local_rules), 2)
        output = next(
            item
            for item in desired.local_rules
            if item.hook is ProbeLocalHook.OUTPUT
        )
        input_rule = next(
            item
            for item in desired.local_rules
            if item.hook is ProbeLocalHook.INPUT
        )
        self.assertEqual(output.endpoint, EP_A)
        self.assertEqual(output.target, TARGET_A)
        self.assertEqual(output.process_uid, 4242)
        self.assertEqual(output.conntrack_mark, 0x20000001)
        self.assertEqual(input_rule.endpoint, EP_A)
        self.assertEqual(input_rule.target, TARGET_A)
        self.assertIsNone(input_rule.process_uid)
        self.assertEqual(input_rule.conntrack_mark, 0x20000001)

    def test_path_realization_gateway_and_onlink_are_preserved(self):
        route = RoutePriorityPathRoute(
            A,
            EP_A,
            gateway=IPv4Address("192.0.2.1"),
            onlink=True,
        )
        desired = build(
            (intent("corp", A, str(TARGET_A)),),
            (route,),
        )
        unicast = next(
            item
            for item in desired.routes
            if item.route_type is ProbeRouteType.UNICAST
        )
        self.assertEqual(unicast.gateway, IPv4Address("192.0.2.1"))
        self.assertTrue(unicast.onlink)

    def test_projection_is_deterministic_across_input_order(self):
        intents_a = (
            intent("z", B, str(TARGET_B)),
            intent("a", A, str(TARGET_A)),
        )
        routes_a = (
            RoutePriorityPathRoute(B, EP_B),
            RoutePriorityPathRoute(A, EP_A),
        )
        one = build(intents_a, routes_a)
        two = build(tuple(reversed(intents_a)), tuple(reversed(routes_a)))
        self.assertEqual(one, two)

    def test_probe_allocation_owner_set_must_match_intents(self):
        current = (intent("corp", A, str(TARGET_A)),)
        stale_layout = allocate_network_policy_layout(
            (),
            (ProbeRoutingDemand(ProbePolicyOwner("other", A)),),
            NG3_LINUX_POLICY_PLATFORM,
        )
        with self.assertRaisesRegex(
            ProbePolicyProjectionError,
            "owner set",
        ):
            build_probe_network_policy_desired_state(
                current,
                stale_layout,
                (RoutePriorityPathRoute(A, EP_A),),
                NG3_LINUX_POLICY_PLATFORM,
                LOCAL,
            )

    def test_missing_current_path_realization_is_rejected(self):
        with self.assertRaisesRegex(
            ProbePolicyProjectionError,
            "no current path realization",
        ):
            build(
                (intent("corp", A, str(TARGET_A)),),
                (),
            )

    def test_duplicate_probe_owner_is_rejected(self):
        item = intent("corp", A, str(TARGET_A))
        layout = allocate_network_policy_layout(
            (),
            (ProbeRoutingDemand(item.owner),),
            NG3_LINUX_POLICY_PLATFORM,
        )
        with self.assertRaisesRegex(
            ProbePolicyProjectionError,
            "duplicate availability probe owner",
        ):
            build_probe_network_policy_desired_state(
                (item, item),
                layout,
                (RoutePriorityPathRoute(A, EP_A),),
                NG3_LINUX_POLICY_PLATFORM,
                LOCAL,
            )

    def test_one_endpoint_cannot_realize_multiple_probe_paths(self):
        with self.assertRaisesRegex(
            ProbePolicyProjectionError,
            "multiple logical paths",
        ):
            build(
                (
                    intent("a", A, str(TARGET_A)),
                    intent("b", B, str(TARGET_B)),
                ),
                (
                    RoutePriorityPathRoute(A, EP_A),
                    RoutePriorityPathRoute(B, EP_A),
                ),
            )

    def test_non_typed_probe_mechanism_is_rejected(self):
        with self.assertRaisesRegex(
            ProbePolicyProjectionError,
            "mechanism",
        ):
            AvailabilityProbeIntent(
                ProbePolicyOwner("corp", A),
                TARGET_A,
                "icmp",
            )

    def test_invalid_local_platform_is_rejected(self):
        for uid in (-1, 0):
            with self.subTest(uid=uid):
                with self.assertRaisesRegex(
                    ProbePolicyProjectionError,
                    "process_uid",
                ):
                    ProbeLocalPlatform(uid, 1)
        with self.assertRaisesRegex(
            ProbePolicyProjectionError,
            "conntrack_mark",
        ):
            ProbeLocalPlatform(1, 0)


if __name__ == "__main__":
    unittest.main()
