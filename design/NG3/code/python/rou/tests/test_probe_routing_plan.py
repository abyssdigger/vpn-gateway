from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import ProbePolicyOwner
from rou.payload_routing_desired import ManagedRouteSpec, ManagedRouteType
from rou.probe_policy import ProbeRuleSpec
from rou.probe_routing_compare import ProbeRoutingComparison
from rou.probe_routing_plan import (
    ProbeRoutingStepKind,
    probe_routing_rank,
    select_probe_routing_step,
)
from rou.structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
)


PATH = LogicalPathId("device", 0, 0)
EP = InterfaceIdentity("vpn0", 20)
OLD_EP = InterfaceIdentity("vpn0", 19)
TABLE = 0xC0000000
TARGET = IPv4Address("198.51.100.7")

GUARD = ManagedRouteSpec(
    table=TABLE,
    destination=IPv4Network("0.0.0.0/0"),
    route_type=ManagedRouteType.BLACKHOLE,
    protocol=201,
    metric=0xFFFFFFFF,
)
PATH_ROUTE = ManagedRouteSpec(
    table=TABLE,
    destination=IPv4Network(f"{TARGET}/32"),
    route_type=ManagedRouteType.UNICAST,
    protocol=202,
    metric=1,
    path_id=PATH,
    endpoint=EP,
)
RULE = ProbeRuleSpec(
    owner=ProbePolicyOwner("corp", PATH),
    priority=0x2000,
    process_uid=4242,
    endpoint=EP,
    target=TARGET,
    table=TABLE,
)

OBS_GUARD = ObservedManagedRoute(
    table=TABLE,
    destination=IPv4Network("0.0.0.0/0"),
    route_type=ManagedRouteType.BLACKHOLE,
    protocol=201,
    metric=0xFFFFFFFF,
    scope=None,
    endpoint=None,
    gateway=None,
    onlink=False,
)
OBS_PATH = ObservedManagedRoute(
    table=TABLE,
    destination=IPv4Network(f"{TARGET}/32"),
    route_type=ManagedRouteType.UNICAST,
    protocol=202,
    metric=1,
    scope=253,
    endpoint=EP,
    gateway=None,
    onlink=False,
)
OBS_OLD_PATH = ObservedManagedRoute(
    table=TABLE,
    destination=IPv4Network(f"{TARGET}/32"),
    route_type=ManagedRouteType.UNICAST,
    protocol=202,
    metric=1,
    scope=253,
    endpoint=OLD_EP,
    gateway=None,
    onlink=False,
)
OBS_RULE = ObservedManagedRule(
    priority=0x2000,
    table=TABLE,
    ingress=None,
    destination=IPv4Network(f"{TARGET}/32"),
    uid_start=4242,
    uid_end=4242,
    ipproto=1,
    egress=EP,
)


def comparison(
    *,
    confirmed_routes=(),
    missing_routes=(),
    stale_routes=(),
    confirmed_rules=(),
    missing_rules=(),
    stale_rules=(),
    observed_rules=(),
):
    return ProbeRoutingComparison(
        confirmed_routes=confirmed_routes,
        missing_routes=missing_routes,
        stale_routes=stale_routes,
        confirmed_rules=confirmed_rules,
        missing_rules=missing_rules,
        stale_rules=stale_rules,
        observed_rules=observed_rules,
        conflicts=(),
    )


class ProbeRoutingPlanTests(unittest.TestCase):
    def test_empty_table_adds_guard_before_path_and_rule(self):
        value = comparison(
            missing_routes=(GUARD, PATH_ROUTE),
            missing_rules=(RULE,),
        )
        step = select_probe_routing_step(value)
        self.assertEqual(
            step.kind,
            ProbeRoutingStepKind.ADD_GUARD_ROUTE,
        )
        self.assertEqual(step.desired_route, GUARD)

    def test_active_confirmed_rule_is_withdrawn_before_route_repair(self):
        value = comparison(
            confirmed_routes=(GUARD,),
            missing_routes=(PATH_ROUTE,),
            stale_routes=(OBS_OLD_PATH,),
            confirmed_rules=(RULE,),
            observed_rules=(OBS_RULE,),
        )
        self.assertEqual(probe_routing_rank(value), (1, 2, 0, 0))
        step = select_probe_routing_step(value)
        self.assertEqual(
            step.kind,
            ProbeRoutingStepKind.WITHDRAW_RULE,
        )
        self.assertEqual(step.observed_rule, OBS_RULE)

    def test_withdrawal_can_improve_rank_while_creating_missing_rule(self):
        before = comparison(
            confirmed_routes=(GUARD,),
            missing_routes=(PATH_ROUTE,),
            stale_routes=(OBS_OLD_PATH,),
            confirmed_rules=(RULE,),
            observed_rules=(OBS_RULE,),
        )
        after = comparison(
            confirmed_routes=(GUARD,),
            missing_routes=(PATH_ROUTE,),
            stale_routes=(OBS_OLD_PATH,),
            missing_rules=(RULE,),
            observed_rules=(),
        )
        self.assertLess(
            probe_routing_rank(after),
            probe_routing_rank(before),
        )

    def test_stale_selector_is_removed_before_table_mutation(self):
        stale_rule = ObservedManagedRule(
            priority=0x2000,
            table=TABLE,
            ingress=None,
            destination=IPv4Network("203.0.113.9/32"),
            uid_start=4242,
            uid_end=4242,
            ipproto=1,
            egress=EP,
        )
        value = comparison(
            missing_routes=(GUARD, PATH_ROUTE),
            missing_rules=(RULE,),
            stale_rules=(stale_rule,),
            observed_rules=(stale_rule,),
        )
        step = select_probe_routing_step(value)
        self.assertEqual(
            step.kind,
            ProbeRoutingStepKind.WITHDRAW_RULE,
        )
        self.assertEqual(step.observed_rule, stale_rule)

    def test_stale_path_is_deleted_before_stale_guard(self):
        stale_guard = ObservedManagedRoute(
            table=TABLE,
            destination=IPv4Network("0.0.0.0/0"),
            route_type=ManagedRouteType.BLACKHOLE,
            protocol=201,
            metric=0xFFFFFFFE,
            scope=None,
            endpoint=None,
            gateway=None,
            onlink=False,
        )
        value = comparison(
            stale_routes=(stale_guard, OBS_OLD_PATH),
        )
        step = select_probe_routing_step(value)
        self.assertEqual(
            step.kind,
            ProbeRoutingStepKind.DELETE_PATH_ROUTE,
        )
        self.assertEqual(step.observed_route, OBS_OLD_PATH)

    def test_rule_is_added_only_after_routes_are_exact(self):
        value = comparison(
            confirmed_routes=(GUARD, PATH_ROUTE),
            missing_rules=(RULE,),
        )
        step = select_probe_routing_step(value)
        self.assertEqual(step.kind, ProbeRoutingStepKind.ADD_RULE)
        self.assertEqual(step.desired_rule, RULE)

    def test_exact_state_has_no_step(self):
        value = comparison(
            confirmed_routes=(GUARD, PATH_ROUTE),
            confirmed_rules=(RULE,),
            observed_rules=(OBS_RULE,),
        )
        self.assertTrue(value.confirmed)
        self.assertIsNone(select_probe_routing_step(value))


if __name__ == "__main__":
    unittest.main()
