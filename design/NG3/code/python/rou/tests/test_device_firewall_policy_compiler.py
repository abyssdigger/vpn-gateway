from __future__ import annotations

import unittest

from rou.binding import LogicalPathId
from rou.device_firewall_policy_compiler import (
    DeviceFirewallPolicyCompileError,
    compile_device_firewall_policies,
)
from rou.device_policy import (
    DeviceFirewallAction,
    DeviceFirewallDirection,
    DeviceFirewallPolicyIntent,
    DeviceFirewallRuleIntent,
)
from rou.interface_identity import InterfaceIdentity
from rou.route_priority_inventory import RoutePriorityPathRoute


HOST = InterfaceIdentity("host0", 10)
EP_A0 = InterfaceIdentity("vpn-a0", 20)
EP_A1 = InterfaceIdentity("vpn-a1", 21)
EP_B = InterfaceIdentity("vpn-b", 30)
PATH_A0 = LogicalPathId("a", 0, 0)
PATH_A1 = LogicalPathId("a", 0, 1)
PATH_B = LogicalPathId("b", 0, 0)


def explicit(device_id):
    return DeviceFirewallPolicyIntent(
        device_id=device_id,
        rules=(
            DeviceFirewallRuleIntent(
                direction=DeviceFirewallDirection.OUT,
                action=DeviceFirewallAction.ALLOW,
                protocol="tcp",
            ),
        ),
    )


def omitted(device_id):
    return DeviceFirewallPolicyIntent(
        device_id=device_id,
        rules=None,
    )


class DeviceFirewallPolicyCompilerTests(unittest.TestCase):
    def test_one_explicit_path_gets_canonical_out_and_in_names(self):
        desired = compile_device_firewall_policies(
            (explicit("a"),),
            (RoutePriorityPathRoute(PATH_A0, EP_A0),),
            HOST,
        )

        self.assertEqual(
            tuple(chain.child_chain_name for chain in desired.chains),
            ("df_out_00000000", "df_in_00000000"),
        )
        self.assertEqual(desired.chains[0].ingress, HOST)
        self.assertEqual(desired.chains[0].egress, EP_A0)
        self.assertEqual(desired.chains[1].ingress, EP_A0)
        self.assertEqual(desired.chains[1].egress, HOST)

    def test_omitted_policy_adds_no_device_layer_chains(self):
        desired = compile_device_firewall_policies(
            (omitted("a"),),
            (RoutePriorityPathRoute(PATH_A0, EP_A0),),
            HOST,
        )
        self.assertEqual(desired.chains, ())

    def test_names_are_independent_of_input_route_order(self):
        routes_forward = (
            RoutePriorityPathRoute(PATH_A0, EP_A0),
            RoutePriorityPathRoute(PATH_B, EP_B),
        )
        routes_reverse = tuple(reversed(routes_forward))
        policies = (explicit("a"), explicit("b"))

        left = compile_device_firewall_policies(
            policies,
            routes_forward,
            HOST,
        )
        right = compile_device_firewall_policies(
            tuple(reversed(policies)),
            routes_reverse,
            HOST,
        )

        self.assertEqual(left, right)
        self.assertEqual(
            tuple(chain.child_chain_name for chain in left.chains),
            (
                "df_out_00000000",
                "df_in_00000000",
                "df_out_00000001",
                "df_in_00000001",
            ),
        )

    def test_same_device_multipath_gets_distinct_chain_pairs(self):
        desired = compile_device_firewall_policies(
            (explicit("a"),),
            (
                RoutePriorityPathRoute(PATH_A1, EP_A1),
                RoutePriorityPathRoute(PATH_A0, EP_A0),
            ),
            HOST,
        )

        self.assertEqual(
            tuple(chain.child_chain_name for chain in desired.chains),
            (
                "df_out_00000000",
                "df_in_00000000",
                "df_out_00000001",
                "df_in_00000001",
            ),
        )
        self.assertEqual(
            {
                (chain.ingress, chain.egress)
                for chain in desired.chains
            },
            {
                (HOST, EP_A0),
                (EP_A0, HOST),
                (HOST, EP_A1),
                (EP_A1, HOST),
            },
        )

    def test_missing_policy_for_current_path_is_not_implicit_allow(self):
        with self.assertRaisesRegex(
            DeviceFirewallPolicyCompileError,
            "no normalized Device firewall policy",
        ):
            compile_device_firewall_policies(
                (),
                (RoutePriorityPathRoute(PATH_A0, EP_A0),),
                HOST,
            )

    def test_extra_policy_without_current_path_is_harmless_input(self):
        desired = compile_device_firewall_policies(
            (omitted("a"), explicit("unused")),
            (RoutePriorityPathRoute(PATH_A0, EP_A0),),
            HOST,
        )
        self.assertEqual(desired.chains, ())

    def test_duplicate_policy_device_id_is_rejected(self):
        with self.assertRaisesRegex(
            DeviceFirewallPolicyCompileError,
            "duplicate Device firewall policy",
        ):
            compile_device_firewall_policies(
                (omitted("a"), explicit("a")),
                (RoutePriorityPathRoute(PATH_A0, EP_A0),),
                HOST,
            )

    def test_duplicate_path_realization_is_rejected(self):
        with self.assertRaisesRegex(
            DeviceFirewallPolicyCompileError,
            "duplicate current path realization",
        ):
            compile_device_firewall_policies(
                (explicit("a"),),
                (
                    RoutePriorityPathRoute(PATH_A0, EP_A0),
                    RoutePriorityPathRoute(PATH_A0, EP_A1),
                ),
                HOST,
            )

    def test_one_endpoint_cannot_back_two_paths(self):
        with self.assertRaisesRegex(
            DeviceFirewallPolicyCompileError,
            "cannot realize multiple logical paths",
        ):
            compile_device_firewall_policies(
                (explicit("a"),),
                (
                    RoutePriorityPathRoute(PATH_A0, EP_A0),
                    RoutePriorityPathRoute(PATH_A1, EP_A0),
                ),
                HOST,
            )

    def test_host_boundary_cannot_be_device_path_endpoint(self):
        with self.assertRaisesRegex(
            DeviceFirewallPolicyCompileError,
            "host boundary cannot also be",
        ):
            compile_device_firewall_policies(
                (explicit("a"),),
                (RoutePriorityPathRoute(PATH_A0, HOST),),
                HOST,
            )


if __name__ == "__main__":
    unittest.main()
