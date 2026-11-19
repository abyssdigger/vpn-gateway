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
from rou.payload_routing_desired import ManagedRouteType
from rou.probe_policy import (
    AvailabilityProbeIntent,
    ProbeLocalPlatform,
    build_probe_network_policy_desired_state,
)
from rou.probe_routing_compare import compare_probe_routing
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
    ReservedOwnerKind,
    ReservedPolicyConflict,
    StructuralRoutingObservation,
)


A = LogicalPathId("a", 0, 0)
EP_A = InterfaceIdentity("patha", 10)
HOST = InterfaceIdentity("host0", 5)
TARGET = IPv4Address("198.51.100.7")
LOCAL = ProbeLocalPlatform(4242, 0x20000001)


def desired_state():
    owner = ProbePolicyOwner("corp", A)
    layout = allocate_network_policy_layout(
        (),
        (ProbeRoutingDemand(owner),),
        NG3_LINUX_POLICY_PLATFORM,
    )
    return build_probe_network_policy_desired_state(
        (AvailabilityProbeIntent(owner, TARGET),),
        layout,
        (RoutePriorityPathRoute(A, EP_A),),
        NG3_LINUX_POLICY_PLATFORM,
        LOCAL,
    )


def exact_observation(desired):
    routes = tuple(
        ObservedManagedRoute(
            table=route.table,
            destination=route.destination,
            route_type=route.route_type,
            protocol=route.protocol,
            metric=route.metric,
            scope=(
                None
                if route.route_type is ManagedRouteType.BLACKHOLE
                else 253
            ),
            endpoint=route.endpoint,
            gateway=route.gateway,
            onlink=route.onlink,
        )
        for route in desired.routes
    )
    rules = tuple(
        ObservedManagedRule(
            priority=rule.priority,
            table=rule.table,
            ingress=None,
            destination=IPv4Network(f"{rule.target}/32"),
            uid_start=rule.process_uid,
            uid_end=rule.process_uid,
            ipproto=1,
        )
        for rule in desired.rules
    )
    return StructuralRoutingObservation(routes, rules, ())


class ProbeRoutingComparisonTests(unittest.TestCase):
    def test_exact_actual_probe_routing_is_confirmed(self):
        desired = desired_state()
        result = compare_probe_routing(
            desired,
            exact_observation(desired),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(len(result.confirmed_routes), 2)
        self.assertEqual(len(result.confirmed_rules), 1)

    def test_uid_drift_is_missing_plus_stale(self):
        desired = desired_state()
        actual = exact_observation(desired)
        rule = actual.rules[0]
        changed = ObservedManagedRule(
            priority=rule.priority,
            table=rule.table,
            ingress=None,
            destination=rule.destination,
            uid_start=rule.uid_start + 1,
            uid_end=rule.uid_end + 1,
            ipproto=rule.ipproto,
        )
        result = compare_probe_routing(
            desired,
            StructuralRoutingObservation(
                actual.routes,
                (changed,),
                (),
            ),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(result.missing_rules, desired.rules)
        self.assertEqual(result.stale_rules, (changed,))

    def test_target_drift_is_missing_plus_stale(self):
        desired = desired_state()
        actual = exact_observation(desired)
        rule = actual.rules[0]
        changed = ObservedManagedRule(
            priority=rule.priority,
            table=rule.table,
            ingress=None,
            destination=IPv4Network("203.0.113.9/32"),
            uid_start=rule.uid_start,
            uid_end=rule.uid_end,
            ipproto=rule.ipproto,
        )
        result = compare_probe_routing(
            desired,
            StructuralRoutingObservation(
                actual.routes,
                (changed,),
                (),
            ),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(len(result.missing_rules), 1)
        self.assertEqual(result.stale_rules, (changed,))

    def test_same_name_new_ifindex_does_not_confirm_probe_path(self):
        desired = desired_state()
        actual = exact_observation(desired)
        replacement = InterfaceIdentity("patha", 11)
        changed_routes = tuple(
            ObservedManagedRoute(
                table=route.table,
                destination=route.destination,
                route_type=route.route_type,
                protocol=route.protocol,
                metric=route.metric,
                scope=route.scope,
                endpoint=(
                    replacement if route.endpoint is not None else None
                ),
                gateway=route.gateway,
                onlink=route.onlink,
            )
            for route in actual.routes
        )
        result = compare_probe_routing(
            desired,
            StructuralRoutingObservation(
                changed_routes,
                actual.rules,
                (),
            ),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(len(result.missing_routes), 1)
        self.assertEqual(len(result.stale_routes), 1)

    def test_probe_conflict_blocks_confirmation(self):
        desired = desired_state()
        actual = exact_observation(desired)
        conflict = ReservedPolicyConflict(
            owner=ReservedOwnerKind.PROBE,
            resource="rule priority=8192",
            reason="unsupported reserved probe selector",
        )
        result = compare_probe_routing(
            desired,
            StructuralRoutingObservation(
                actual.routes,
                actual.rules,
                (conflict,),
            ),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(result.conflicts, (conflict,))

    def test_payload_state_and_conflict_do_not_pollute_probe_comparison(self):
        desired = desired_state()
        actual = exact_observation(desired)
        payload_route = ObservedManagedRoute(
            table=0x80000000,
            destination=IPv4Network("10.0.0.0/8"),
            route_type=ManagedRouteType.UNICAST,
            protocol=202,
            metric=1,
            scope=253,
            endpoint=EP_A,
            gateway=None,
            onlink=False,
        )
        payload_rule = ObservedManagedRule(
            priority=0x4000,
            table=0x80000000,
            ingress=HOST,
            destination=IPv4Network("10.0.0.0/8"),
        )
        conflict = ReservedPolicyConflict(
            owner=ReservedOwnerKind.PAYLOAD,
            resource="route table=2147483648",
            reason="payload-only conflict",
        )
        result = compare_probe_routing(
            desired,
            StructuralRoutingObservation(
                actual.routes + (payload_route,),
                actual.rules + (payload_rule,),
                (conflict,),
            ),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(result.conflicts, ())

    def test_missing_probe_state_is_explicit(self):
        desired = desired_state()
        result = compare_probe_routing(
            desired,
            StructuralRoutingObservation((), (), ()),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(result.missing_routes, desired.routes)
        self.assertEqual(result.missing_rules, desired.rules)


if __name__ == "__main__":
    unittest.main()
