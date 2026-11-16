from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.binding import LogicalPathId, PathBinding
from rou.direct_device_route import realize_direct_device_path_routes
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.network_policy_layout import allocate_network_policy_layout
from rou.payload_profile import PayloadProfileRequest
from rou.payload_routing_compare import compare_payload_routing
from rou.payload_routing_desired import build_payload_routing_desired_state
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


def desired_state():
    profile = PayloadProfileRequest(
        profile_id="corp",
        direction=Direction.OUTBOUND,
        destinations=(IPv4Network("10.0.0.0/8"),),
        ordered_paths=(A,),
    )
    layout = allocate_network_policy_layout(
        (profile,),
        (),
        NG3_LINUX_POLICY_PLATFORM,
    )
    routes = realize_direct_device_path_routes((PathBinding(A, EP_A),))
    return build_payload_routing_desired_state(
        (profile,),
        layout,
        routes,
        HOST,
    )


def exact_observation(desired):
    routes = []
    for route in desired.routes:
        routes.append(
            ObservedManagedRoute(
                table=route.table,
                destination=route.destination,
                route_type=route.route_type,
                protocol=route.protocol,
                metric=route.metric,
                scope=(
                    None
                    if route.route_type.value == "blackhole"
                    else 253
                ),
                endpoint=route.endpoint,
                gateway=route.gateway,
                onlink=route.onlink,
            )
        )
    rules = tuple(
        ObservedManagedRule(
            priority=rule.priority,
            table=rule.table,
            ingress=rule.ingress,
            destination=rule.destination,
            fwmark=None,
            fwmask=None,
        )
        for rule in desired.rules
    )
    return StructuralRoutingObservation(
        routes=tuple(routes),
        rules=rules,
        conflicts=(),
    )


class PayloadRoutingComparisonTests(unittest.TestCase):
    def test_exact_actual_state_is_confirmed(self):
        desired = desired_state()
        result = compare_payload_routing(
            desired,
            exact_observation(desired),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(len(result.confirmed_routes), 2)
        self.assertEqual(len(result.confirmed_rules), 1)

    def test_missing_and_stale_routes_are_explicit(self):
        desired = desired_state()
        actual = exact_observation(desired)
        path = next(
            route
            for route in actual.routes
            if route.endpoint is not None
        )
        stale = ObservedManagedRoute(
            table=path.table,
            destination=IPv4Network("192.0.2.0/24"),
            route_type=path.route_type,
            protocol=path.protocol,
            metric=path.metric,
            scope=path.scope,
            endpoint=path.endpoint,
            gateway=path.gateway,
            onlink=path.onlink,
        )
        observation = StructuralRoutingObservation(
            routes=(stale,) + tuple(
                route for route in actual.routes if route.endpoint is None
            ),
            rules=actual.rules,
            conflicts=(),
        )
        result = compare_payload_routing(
            desired, observation, NG3_LINUX_POLICY_PLATFORM
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(len(result.missing_routes), 1)
        self.assertEqual(len(result.stale_routes), 1)

    def test_same_name_new_ifindex_does_not_confirm_desired_path(self):
        desired = desired_state()
        actual = exact_observation(desired)
        replacement = InterfaceIdentity("patha", 11)
        changed = tuple(
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
        result = compare_payload_routing(
            desired,
            StructuralRoutingObservation(changed, actual.rules, ()),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(len(result.missing_routes), 1)
        self.assertEqual(len(result.stale_routes), 1)

    def test_unexpected_scope_does_not_confirm_route(self):
        desired = desired_state()
        actual = exact_observation(desired)
        changed = tuple(
            ObservedManagedRoute(
                table=route.table,
                destination=route.destination,
                route_type=route.route_type,
                protocol=route.protocol,
                metric=route.metric,
                scope=(
                    254 if route.endpoint is not None else route.scope
                ),
                endpoint=route.endpoint,
                gateway=route.gateway,
                onlink=route.onlink,
            )
            for route in actual.routes
        )
        result = compare_payload_routing(
            desired,
            StructuralRoutingObservation(changed, actual.rules, ()),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(len(result.missing_routes), 1)
        self.assertEqual(len(result.stale_routes), 1)

    def test_payload_conflict_blocks_confirmation(self):
        desired = desired_state()
        actual = exact_observation(desired)
        conflict = ReservedPolicyConflict(
            owner=ReservedOwnerKind.PAYLOAD,
            resource="route table=2147483648",
            reason="foreign reserved route",
        )
        result = compare_payload_routing(
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

    def test_probe_state_and_conflict_do_not_pollute_payload_comparison(self):
        desired = desired_state()
        actual = exact_observation(desired)
        probe_route = ObservedManagedRoute(
            table=0xC0000000,
            destination=IPv4Network("198.51.100.7/32"),
            route_type=actual.routes[-1].route_type,
            protocol=202,
            metric=1,
            scope=253,
            endpoint=EP_A,
            gateway=None,
            onlink=False,
        )
        probe_rule = ObservedManagedRule(
            priority=0x2000,
            table=0xC0000000,
            ingress=None,
            destination=None,
            fwmark=0x1234,
            fwmask=0xFFFF,
        )
        probe_conflict = ReservedPolicyConflict(
            owner=ReservedOwnerKind.PROBE,
            resource="rule priority=8192",
            reason="probe-only conflict",
        )
        result = compare_payload_routing(
            desired,
            StructuralRoutingObservation(
                actual.routes + (probe_route,),
                actual.rules + (probe_rule,),
                (probe_conflict,),
            ),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(result.conflicts, ())

    def test_missing_rule_is_explicit(self):
        desired = desired_state()
        actual = exact_observation(desired)
        result = compare_payload_routing(
            desired,
            StructuralRoutingObservation(
                actual.routes,
                (),
                (),
            ),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(result.missing_rules, desired.rules)


if __name__ == "__main__":
    unittest.main()
