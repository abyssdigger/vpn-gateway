from __future__ import annotations

import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.binding import LogicalPathId
from rou.composite_nft_policy import (
    CompositeNftDesiredState,
    CompositeNftPolicyComparison,
)
from rou.device_firewall_compare import DeviceFirewallComparison
from rou.device_firewall_desired import DeviceFirewallDesiredState
from rou.interface_identity import InterfaceIdentity
from rou.local_publication_observation import LocalPublicationComparison
from rou.local_publication_policy import LocalPublicationDesiredState
from rou.nft_namespace_inventory import NftNamespaceStatus
from rou.nft_payload_scaffold import (
    NftPayloadScaffoldComparison,
    PAYLOAD_NFT_SCAFFOLD,
)
from rou.payload_forward_compare import PayloadForwardComparison
from rou.payload_forward_desired import PayloadForwardDesiredState
from rou.payload_nat_desired import (
    PayloadMasqueradeSpec,
    PayloadNatDesiredState,
)
from rou.payload_nat_observation import PayloadNatComparison
from rou.payload_routing_compare import PayloadRoutingComparison
from rou.payload_routing_desired import (
    ManagedRouteRole,
    ManagedRouteSpec,
    ManagedRouteType,
    ManagedRuleSpec,
)
from rou.structural_policy_plan import (
    StructuralPolicyStepKind,
    select_structural_policy_step,
)
from rou.structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
)


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)
LEGACY_LANE = InterfaceIdentity("lane-nat", 30)
PATH = LogicalPathId("device", 0, 0)
PREFIX = IPv4Network("10.0.0.0/8")

GUARD = ManagedRouteSpec(
    table=0x80000000,
    destination=IPv4Network("0.0.0.0/0"),
    route_type=ManagedRouteType.BLACKHOLE,
    protocol=201,
    metric=0xFFFFFFFF,
)
PATH_ROUTE = ManagedRouteSpec(
    table=0x80000000,
    destination=PREFIX,
    route_type=ManagedRouteType.UNICAST,
    protocol=202,
    metric=1,
    path_id=PATH,
    endpoint=VPN,
)
RULE = ManagedRuleSpec(
    priority=0x4000,
    ingress=HOST,
    destination=PREFIX,
    table=0x80000000,
)

STALE_RULE = ObservedManagedRule(
    priority=0x4001,
    table=0x80000001,
    ingress=HOST,
    destination=PREFIX,
    fwmark=None,
    fwmask=None,
)
STALE_PATH = ObservedManagedRoute(
    table=0x80000000,
    destination=PREFIX,
    route_type=ManagedRouteType.UNICAST,
    protocol=202,
    metric=2,
    scope=253,
    endpoint=VPN,
    gateway=None,
    onlink=False,
)
STALE_GUARD = ObservedManagedRoute(
    table=0x80000001,
    destination=IPv4Network("0.0.0.0/0"),
    route_type=ManagedRouteType.BLACKHOLE,
    protocol=201,
    metric=0xFFFFFFFF,
    scope=0,
    endpoint=None,
    gateway=None,
    onlink=False,
)

STALE_LEGACY_LANE = ObservedManagedRoute(
    table=0x80000000,
    destination=IPv4Network("0.0.0.0/0"),
    route_type=ManagedRouteType.UNICAST,
    protocol=204,
    metric=0xFFFFFFFE,
    scope=0,
    endpoint=LEGACY_LANE,
    gateway=IPv4Address("198.18.64.5"),
    onlink=False,
    role=ManagedRouteRole.LEGACY_HOST_BOUNDARY_LANE,
)


SCAFFOLD = NftPayloadScaffoldComparison(
    namespace_status=NftNamespaceStatus.OWNED,
    confirmed_chains=PAYLOAD_NFT_SCAFFOLD,
    missing_chains=(),
    conflicts=(),
    unclassified_objects=(),
)


def routing(
    *,
    missing_routes=(),
    stale_routes=(),
    missing_rules=(),
    stale_rules=(),
):
    return PayloadRoutingComparison(
        confirmed_routes=(),
        missing_routes=missing_routes,
        stale_routes=stale_routes,
        confirmed_rules=(),
        missing_rules=missing_rules,
        stale_rules=stale_rules,
        conflicts=(),
    )


def nft(*, nat_missing=()):
    return CompositeNftPolicyComparison(
        scaffold=SCAFFOLD,
        profile_forward=PayloadForwardComparison(
            confirmed=(),
            missing=(),
            stale=(),
            conflicts=(),
        ),
        payload_nat=PayloadNatComparison(
            confirmed=(),
            missing=nat_missing,
            stale=(),
            conflicts=(),
        ),
        device_firewall=DeviceFirewallComparison(
            confirmed=(),
            missing=(),
            stale_chains=(),
            stale_jumps=(),
            conflicts=(),
        ),
        local_publication=LocalPublicationComparison(
            confirmed=(),
            missing=(),
            stale=(),
            conflicts=(),
        ),
        conflicts=(),
    )


EMPTY_NFT_DESIRED = CompositeNftDesiredState(
    PayloadForwardDesiredState(()),
    PayloadNatDesiredState(()),
    DeviceFirewallDesiredState(()),
    LocalPublicationDesiredState(()),
)


class StructuralPolicyPlanTests(unittest.TestCase):
    def test_missing_guard_precedes_stale_dispatch(self):
        step = select_structural_policy_step(
            routing(
                missing_routes=(GUARD,),
                stale_rules=(STALE_RULE,),
            ),
            nft(),
            EMPTY_NFT_DESIRED,
        )
        self.assertEqual(step.kind, StructuralPolicyStepKind.ADD_GUARD_ROUTE)
        self.assertEqual(step.desired_route, GUARD)

    def test_stale_dispatch_precedes_stale_route_cleanup(self):
        step = select_structural_policy_step(
            routing(
                stale_routes=(STALE_PATH,),
                stale_rules=(STALE_RULE,),
            ),
            nft(),
            EMPTY_NFT_DESIRED,
        )
        self.assertEqual(
            step.kind,
            StructuralPolicyStepKind.DELETE_ROUTING_RULE,
        )
        self.assertEqual(step.observed_rule, STALE_RULE)

    def test_stale_unicast_is_removed_before_stale_guard(self):
        step = select_structural_policy_step(
            routing(stale_routes=(STALE_GUARD, STALE_PATH)),
            nft(),
            EMPTY_NFT_DESIRED,
        )
        self.assertEqual(
            step.kind,
            StructuralPolicyStepKind.DELETE_ROUTING_ROUTE,
        )
        self.assertEqual(step.observed_route, STALE_PATH)

    def test_stale_legacy_lane_is_selected_for_route_cleanup(self):
        step = select_structural_policy_step(
            routing(stale_routes=(STALE_LEGACY_LANE,)),
            nft(),
            EMPTY_NFT_DESIRED,
        )
        self.assertEqual(
            step.kind,
            StructuralPolicyStepKind.DELETE_ROUTING_ROUTE,
        )
        self.assertEqual(step.observed_route, STALE_LEGACY_LANE)

    def test_missing_path_route_precedes_nft_convergence(self):
        nat_spec = PayloadMasqueradeSpec(PATH, HOST, VPN)
        desired = CompositeNftDesiredState(
            PayloadForwardDesiredState(()),
            PayloadNatDesiredState((nat_spec,)),
            DeviceFirewallDesiredState(()),
            LocalPublicationDesiredState(()),
        )
        step = select_structural_policy_step(
            routing(missing_routes=(PATH_ROUTE,)),
            nft(nat_missing=(nat_spec,)),
            desired,
        )
        self.assertEqual(step.kind, StructuralPolicyStepKind.ADD_PATH_ROUTE)

    def test_nft_converges_before_missing_rpdb_activation(self):
        nat_spec = PayloadMasqueradeSpec(PATH, HOST, VPN)
        desired = CompositeNftDesiredState(
            PayloadForwardDesiredState(()),
            PayloadNatDesiredState((nat_spec,)),
            DeviceFirewallDesiredState(()),
            LocalPublicationDesiredState(()),
        )
        step = select_structural_policy_step(
            routing(missing_rules=(RULE,)),
            nft(nat_missing=(nat_spec,)),
            desired,
        )
        self.assertEqual(step.kind, StructuralPolicyStepKind.APPLY_NFT_STEP)
        self.assertIsNotNone(step.nft_step)

    def test_missing_rpdb_rule_is_last_structural_mutation(self):
        step = select_structural_policy_step(
            routing(missing_rules=(RULE,)),
            nft(),
            EMPTY_NFT_DESIRED,
        )
        self.assertEqual(step.kind, StructuralPolicyStepKind.ADD_ROUTING_RULE)
        self.assertEqual(step.desired_rule, RULE)

    def test_exact_state_has_no_step(self):
        exact_routing = PayloadRoutingComparison(
            confirmed_routes=(GUARD, PATH_ROUTE),
            missing_routes=(),
            stale_routes=(),
            confirmed_rules=(RULE,),
            missing_rules=(),
            stale_rules=(),
            conflicts=(),
        )
        self.assertIsNone(
            select_structural_policy_step(
                exact_routing,
                nft(),
                EMPTY_NFT_DESIRED,
            )
        )


if __name__ == "__main__":
    unittest.main()
