from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.device_policy import (
    DeviceFirewallAction,
    DeviceFirewallDirection,
    DeviceFirewallPolicyIntent,
    DeviceFirewallRuleIntent,
    DeviceNatPolicyIntent,
    NatIntent,
)
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import (
    NG3_LINUX_POLICY_PLATFORM,
    NG3_STACK_RETURN_AFFINITY_PLATFORM,
)
from rou.local_publication_policy import (
    PublicationLocalEndpointIntent,
    PublicationProtocol,
)
from rou.network_policy_layout import allocate_network_policy_layout
from rou.payload_network_policy_desired import (
    PayloadNetworkPolicyProjectionError,
    build_payload_network_policy_desired_state,
)
from rou.payload_profile import PayloadProfileRequest
from rou.payload_routing_desired import ManagedRouteType
from rou.route_priority_inventory import RoutePriorityPathRoute


HOST = InterfaceIdentity("host0", 10)
OTHER_HOST = InterfaceIdentity("host0", 11)
VPN_A = InterfaceIdentity("vpn-a", 20)
VPN_B = InterfaceIdentity("vpn-b", 30)
PATH_A = LogicalPathId("a", 0, 0)
PATH_B = LogicalPathId("b", 0, 0)


def profile(profile_id, prefix, path):
    return PayloadProfileRequest(
        profile_id=profile_id,
        direction=Direction.OUTBOUND,
        destinations=(IPv4Network(prefix),),
        ordered_paths=(() if path is None else (path,)),
    )


def layout_for(*profiles):
    return allocate_network_policy_layout(
        profiles,
        (),
        NG3_LINUX_POLICY_PLATFORM,
    )


def firewall(device_id, explicit=False):
    return DeviceFirewallPolicyIntent(
        device_id=device_id,
        rules=(
            (
                DeviceFirewallRuleIntent(
                    direction=DeviceFirewallDirection.OUT,
                    action=DeviceFirewallAction.ALLOW,
                    protocol="tcp",
                    destination_ports=443,
                ),
            )
            if explicit
            else None
        ),
    )


class PayloadNetworkPolicyDesiredTests(unittest.TestCase):
    def test_zero_path_preserves_guard_and_dispatch_but_no_positive_nft_rules(self):
        p = profile("future", "10.0.0.0/8", None)
        desired = build_payload_network_policy_desired_state(
            (p,),
            layout_for(p),
            (),
            HOST,
            (),
            (),
            (),
        )

        self.assertEqual(len(desired.routing.routes), 1)
        self.assertEqual(
            desired.routing.routes[0].route_type,
            ManagedRouteType.BLACKHOLE,
        )
        self.assertEqual(len(desired.routing.rules), 1)
        self.assertEqual(desired.nft.profile_forward.rules, ())
        self.assertEqual(desired.nft.payload_nat.masquerade_rules, ())
        self.assertEqual(desired.nft.device_firewall.chains, ())
        self.assertEqual(desired.nft.local_publication.rules, ())

    def test_current_path_composes_all_materialized_owner_classes(self):
        p = profile("corp", "10.0.0.0/8", PATH_A)
        route = RoutePriorityPathRoute(
            PATH_A,
            VPN_A,
            gateway=IPv4Address("192.0.2.1"),
            onlink=True,
        )
        publication = PublicationLocalEndpointIntent(
            device_id="a",
            protocol=PublicationProtocol.TCP,
            local_address=IPv4Address("198.51.100.10"),
            internal_port=443,
            host_boundary=HOST,
        )
        desired = build_payload_network_policy_desired_state(
            (p,),
            layout_for(p),
            (route,),
            HOST,
            (DeviceNatPolicyIntent("a", NatIntent.MASQUERADE),),
            (firewall("a", explicit=True),),
            (publication,),
        )

        self.assertEqual(len(desired.routing.routes), 2)
        self.assertEqual(
            {item.route_type for item in desired.routing.routes},
            {ManagedRouteType.BLACKHOLE, ManagedRouteType.UNICAST},
        )
        self.assertEqual(len(desired.routing.rules), 1)
        self.assertEqual(len(desired.nft.profile_forward.rules), 2)
        self.assertEqual(len(desired.nft.payload_nat.masquerade_rules), 1)
        self.assertEqual(len(desired.nft.device_firewall.chains), 2)
        self.assertEqual(
            tuple(
                chain.child_chain_name
                for chain in desired.nft.device_firewall.chains
            ),
            ("df_out_00000000", "df_in_00000000"),
        )
        self.assertEqual(len(desired.nft.local_publication.rules), 2)


    def test_inbound_affinity_no_longer_depends_on_host_behavior_lane(self):
        p = PayloadProfileRequest(
            profile_id="corp",
            direction=Direction.INBOUND,
            destinations=(IPv4Network("10.0.0.0/8"),),
            ordered_paths=(PATH_A,),
        )
        desired = build_payload_network_policy_desired_state(
            (p,),
            layout_for(p),
            (RoutePriorityPathRoute(PATH_A, VPN_A),),
            HOST,
            (DeviceNatPolicyIntent("a", NatIntent.NONE),),
            (firewall("a"),),
            (),
            stack_return_affinity_platform=NG3_STACK_RETURN_AFFINITY_PLATFORM,
        )
        self.assertIsNotNone(desired.stack_return_affinity)
        self.assertEqual(len(desired.stack_return_affinity.classifiers), 1)
        self.assertEqual(desired.stack_return_affinity.outbound_classifiers, ())
        self.assertFalse(
            any(route.role.value == "host_boundary_lane" for route in desired.routing.routes)
        )

    def test_missing_nat_semantics_for_current_device_is_rejected(self):
        p = profile("corp", "10.0.0.0/8", PATH_A)
        with self.assertRaisesRegex(
            PayloadNetworkPolicyProjectionError,
            "payload NAT projection failed.*no explicit normalized NAT intent",
        ):
            build_payload_network_policy_desired_state(
                (p,),
                layout_for(p),
                (RoutePriorityPathRoute(PATH_A, VPN_A),),
                HOST,
                (),
                (firewall("a"),),
                (),
            )

    def test_missing_firewall_semantics_for_current_device_is_rejected(self):
        p = profile("corp", "10.0.0.0/8", PATH_A)
        with self.assertRaisesRegex(
            PayloadNetworkPolicyProjectionError,
            "Device firewall projection failed.*no normalized Device firewall policy",
        ):
            build_payload_network_policy_desired_state(
                (p,),
                layout_for(p),
                (RoutePriorityPathRoute(PATH_A, VPN_A),),
                HOST,
                (DeviceNatPolicyIntent("a", NatIntent.NONE),),
                (),
                (),
            )

    def test_publication_must_use_same_current_host_boundary_generation(self):
        p = profile("future", "10.0.0.0/8", None)
        publication = PublicationLocalEndpointIntent(
            device_id="future",
            protocol=PublicationProtocol.UDP,
            local_address=IPv4Address("198.51.100.11"),
            internal_port=44443,
            host_boundary=OTHER_HOST,
        )

        with self.assertRaisesRegex(
            PayloadNetworkPolicyProjectionError,
            "publication intent host boundary does not match",
        ):
            build_payload_network_policy_desired_state(
                (p,),
                layout_for(p),
                (),
                HOST,
                (),
                (),
                (publication,),
            )

    def test_input_iteration_order_does_not_change_complete_desired_state(self):
        p_a = profile("a-profile", "10.0.0.0/8", PATH_A)
        p_b = profile("b-profile", "192.0.2.0/24", PATH_B)
        profiles = (p_a, p_b)
        layout = layout_for(*profiles)
        routes = (
            RoutePriorityPathRoute(PATH_A, VPN_A),
            RoutePriorityPathRoute(PATH_B, VPN_B),
        )
        nat = (
            DeviceNatPolicyIntent("a", NatIntent.NONE),
            DeviceNatPolicyIntent("b", NatIntent.NONE),
        )
        fw = (
            firewall("a"),
            firewall("b"),
        )

        left = build_payload_network_policy_desired_state(
            profiles,
            layout,
            routes,
            HOST,
            nat,
            fw,
            (),
        )
        right = build_payload_network_policy_desired_state(
            tuple(reversed(profiles)),
            layout,
            tuple(reversed(routes)),
            HOST,
            tuple(reversed(nat)),
            tuple(reversed(fw)),
            (),
        )

        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
