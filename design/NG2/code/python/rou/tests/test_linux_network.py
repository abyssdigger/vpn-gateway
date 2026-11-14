from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_network import (
    LinuxNetworkDesiredError,
    compile_linux_network_desired,
)
from rou.linux_routing import LinuxRoutingAllocationState
from rou.network_rules import (
    DispatchRuleSpec,
    FlowInitiationAllowSpec,
    NetworkEndpoint,
    NetworkRulesSpec,
    RoutingDomainSpec,
    TerminalDisposition,
    TrafficAllowSpec,
    TrafficPredicate,
)
from rou.network_rules_composition import (
    OwnedNetworkRules,
    OwnerToken,
    compose_network_rules,
)


LOCAL = NetworkEndpoint.local_network()


class LinuxNetworkDesiredTests(unittest.TestCase):
    def test_no_owners_means_no_nft_tables_and_forwarding_off(self):
        desired = compile_linux_network_desired(
            compose_network_rules(()),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        self.assertIsNone(desired.filter)
        self.assertIsNone(desired.nat)
        self.assertFalse(desired.ip_forward_required)

    def test_empty_live_owner_keeps_default_deny_table_without_forwarding(self):
        desired = compile_linux_network_desired(
            compose_network_rules(
                (
                    OwnedNetworkRules(
                        OwnerToken(1),
                        NetworkRulesSpec(),
                    ),
                )
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        self.assertIsNotNone(desired.filter)
        self.assertIsNotNone(desired.nat)
        self.assertFalse(desired.ip_forward_required)
        self.assertIn("policy drop", desired.filter.definition)

    def test_effective_forwarded_traffic_requires_ip_forward(self):
        path = NetworkEndpoint.interface_path(
            InterfaceIdentity("vpns00", 10)
        )
        traffic = TrafficAllowSpec(
            LOCAL,
            path,
            TrafficPredicate.always(),
        )
        flow = FlowInitiationAllowSpec(
            LOCAL,
            path,
            TrafficPredicate.always(),
        )
        desired = compile_linux_network_desired(
            compose_network_rules(
                (
                    OwnedNetworkRules(
                        OwnerToken(1),
                        NetworkRulesSpec(
                            traffic_allows=(traffic,),
                            flow_initiation_allows=(flow,),
                        ),
                    ),
                )
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        self.assertTrue(desired.ip_forward_required)

    def test_traffic_allow_without_new_flow_still_keeps_forwarding_for_existing_state(self):
        path = NetworkEndpoint.interface_path(
            InterfaceIdentity("vpns00", 10)
        )
        traffic = TrafficAllowSpec(
            LOCAL,
            path,
            TrafficPredicate.always(),
        )
        desired = compile_linux_network_desired(
            compose_network_rules(
                (
                    OwnedNetworkRules(
                        OwnerToken(1),
                        NetworkRulesSpec(
                            traffic_allows=(traffic,),
                        ),
                    ),
                )
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        self.assertTrue(desired.ip_forward_required)

    def test_two_generations_same_name_cannot_coexist_in_linux_desired(self):
        old = InterfaceIdentity("vpns00", 10)
        new = InterfaceIdentity("vpns00", 11)
        network = IPv4Network("10.0.0.0/8")
        rules = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "corp",
                    (network,),
                    (old, new),
                    TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    network,
                    "corp",
                    source=LOCAL,
                ),
            ),
        )

        with self.assertRaises(LinuxNetworkDesiredError):
            compile_linux_network_desired(
                compose_network_rules(
                    (OwnedNetworkRules(OwnerToken(1), rules),)
                ),
                LinuxRoutingAllocationState(),
                local_interface="host0",
            )


if __name__ == "__main__":
    unittest.main()
