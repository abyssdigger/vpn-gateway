from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.availability_routing import AvailabilityWindowPolicy
from rou.interface_identity import InterfaceIdentity
from rou.linux_local_process import LinuxLocalProcessConfig
from rou.linux_network import (
    LinuxNetworkDesiredError,
    compile_linux_network_desired,
    linux_network_route_priority_only_change,
    project_network_rules_to_interfaces,
)
from rou.linux_routing import LinuxRoutingAllocationState
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
    ProbeRulesCalculator,
)
from rou.network_rules import (
    DispatchRuleSpec,
    FlowInitiationAllowSpec,
    NetworkEndpoint,
    NetworkRulesSpec,
    RoutingDomainSpec,
    TerminalDisposition,
    TrafficAllowSpec,
    IcmpType,
    TrafficPredicate,
    TrafficProtocol,
    TrafficSelector,
)
from rou.network_rules_composition import (
    OwnedNetworkRules,
    OwnerToken,
    compose_network_rules,
)


LOCAL = NetworkEndpoint.local_network()


class LinuxNetworkDesiredTests(unittest.TestCase):
    def test_route_priority_only_change_accepts_pure_path_permutation(self):
        first = InterfaceIdentity("vpns00", 10)
        second = InterfaceIdentity("vpns01", 11)
        network = IPv4Network("10.0.0.0/8")
        local = NetworkEndpoint.local_network()

        def desired(order):
            rules = NetworkRulesSpec(
                routing_domains=(
                    RoutingDomainSpec(
                        "corp",
                        (network,),
                        order,
                        TerminalDisposition.DROP,
                    ),
                ),
                dispatch_rules=(
                    DispatchRuleSpec(network, "corp", source=local),
                ),
                traffic_allows=tuple(
                    TrafficAllowSpec(
                        local,
                        NetworkEndpoint.interface_path(identity),
                        TrafficPredicate.always(),
                    )
                    for identity in (first, second)
                ),
                flow_initiation_allows=tuple(
                    FlowInitiationAllowSpec(
                        local,
                        NetworkEndpoint.interface_path(identity),
                        TrafficPredicate.always(),
                    )
                    for identity in (first, second)
                ),
            )
            return compile_linux_network_desired(
                compose_network_rules(
                    (OwnedNetworkRules(OwnerToken(1), rules),)
                ),
                LinuxRoutingAllocationState(),
                local_interface="host0",
            )

        current = desired((first, second))
        reordered = desired((second, first))

        self.assertTrue(
            linux_network_route_priority_only_change(
                current,
                reordered,
            )
        )

        changed_rules = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "corp",
                    (IPv4Network("192.0.2.0/24"),),
                    (second, first),
                    TerminalDisposition.DROP,
                ),
            ),
        )
        broader = compile_linux_network_desired(
            compose_network_rules(
                (OwnedNetworkRules(OwnerToken(1), changed_rules),)
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )
        self.assertFalse(
            linux_network_route_priority_only_change(
                current,
                broader,
            )
        )

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

    def test_absent_generation_projects_to_zero_path_and_no_permissions(self):
        old = InterfaceIdentity("vpns00", 10)
        network = IPv4Network("10.0.0.0/8")
        local = NetworkEndpoint.local_network()
        path = NetworkEndpoint.interface_path(old)
        rules = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "corp",
                    (network,),
                    (old,),
                    TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(network, "corp", source=local),
            ),
            traffic_allows=(
                TrafficAllowSpec(local, path, TrafficPredicate.always()),
            ),
            flow_initiation_allows=(
                FlowInitiationAllowSpec(
                    local,
                    path,
                    TrafficPredicate.always(),
                ),
            ),
        )
        composed = compose_network_rules(
            (OwnedNetworkRules(OwnerToken(1), rules),)
        )

        projected = project_network_rules_to_interfaces(
            composed,
            (InterfaceIdentity("vpns00", 11),),
        )
        actual = projected.owners[0].rules

        self.assertEqual(
            actual.routing_domains[0].ordered_paths,
            (),
        )
        self.assertEqual(actual.traffic_allows, ())
        self.assertEqual(actual.flow_initiation_allows, ())
        self.assertEqual(len(actual.dispatch_rules), 1)

    def test_fresh_generation_owner_can_coexist_with_stale_other_owner_after_projection(self):
        old = InterfaceIdentity("vpns00", 10)
        new = InterfaceIdentity("vpns00", 11)
        local = NetworkEndpoint.local_network()

        def owner(token, destination, identity):
            network = IPv4Network(destination)
            path = NetworkEndpoint.interface_path(identity)
            return OwnedNetworkRules(
                OwnerToken(token),
                NetworkRulesSpec(
                    routing_domains=(
                        RoutingDomainSpec(
                            "shared-name",
                            (network,),
                            (identity,),
                            TerminalDisposition.DROP,
                        ),
                    ),
                    dispatch_rules=(
                        DispatchRuleSpec(
                            network,
                            "shared-name",
                            source=local,
                        ),
                    ),
                    traffic_allows=(
                        TrafficAllowSpec(
                            local,
                            path,
                            TrafficPredicate.always(),
                        ),
                    ),
                ),
            )

        composed = compose_network_rules(
            (
                owner(1, "10.0.0.0/8", new),
                owner(2, "192.168.0.0/16", old),
            )
        )

        projected = project_network_rules_to_interfaces(
            composed,
            (new,),
        )

        first = projected.owners[0].rules
        second = projected.owners[1].rules
        self.assertEqual(
            first.routing_domains[0].ordered_paths,
            (new,),
        )
        self.assertEqual(
            second.routing_domains[0].ordered_paths,
            (),
        )
        self.assertEqual(second.traffic_allows, ())

        # The Linux compiler now sees only one live generation of the name.
        compile_linux_network_desired(
            projected,
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )


    def test_local_process_projection_tracks_bound_output_generation(self):
        old = InterfaceIdentity("vpns00", 10)
        new = InterfaceIdentity("vpns00", 11)
        target = IPv4Network("203.0.113.24/32")
        local_process = NetworkEndpoint.local_process()
        old_path = NetworkEndpoint.interface_path(old)
        rules = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "probe",
                    (target,),
                    (old,),
                    TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    target,
                    "probe",
                    source=local_process,
                    bound_output=old_path,
                    protocol=TrafficProtocol.ICMP,
                ),
            ),
            traffic_allows=(
                TrafficAllowSpec(
                    local_process,
                    old_path,
                    TrafficPredicate.always(),
                ),
                TrafficAllowSpec(
                    old_path,
                    local_process,
                    TrafficPredicate.always(),
                ),
            ),
        )
        projected = project_network_rules_to_interfaces(
            compose_network_rules(
                (OwnedNetworkRules(OwnerToken(1), rules),)
            ),
            (new,),
        )
        actual = projected.owners[0].rules

        self.assertEqual(actual.routing_domains[0].ordered_paths, ())
        self.assertEqual(actual.dispatch_rules, ())
        self.assertEqual(actual.traffic_allows, ())


    def test_probe_rules_compile_with_explicit_linux_local_process_config(self):
        identity = InterfaceIdentity("vpns00", 10)
        rules = ProbeRulesCalculator().calculate(
            AvailabilityProbeSetRequest(
                (
                    AvailabilityProbeRequest(
                        "probe",
                        identity,
                        IPv4Address("203.0.113.24"),
                        policy=AvailabilityWindowPolicy(10, 3),
                    ),
                )
            )
        )

        desired = compile_linux_network_desired(
            compose_network_rules(
                (OwnedNetworkRules(OwnerToken(1), rules),)
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
            local_process=LinuxLocalProcessConfig(
                uid=65534,
                ct_mark=0x24,
            ),
        )

        self.assertEqual(len(desired.routing.dispatch_rules), 1)
        self.assertIsNotNone(desired.filter)
        self.assertFalse(desired.ip_forward_required)

    def test_local_process_allow_without_matching_dispatch_is_rejected(self):
        identity = InterfaceIdentity("vpns00", 10)
        path = NetworkEndpoint.interface_path(identity)
        target = IPv4Network("203.0.113.24/32")
        rules = NetworkRulesSpec(
            traffic_allows=(
                TrafficAllowSpec(
                    NetworkEndpoint.local_process(),
                    path,
                    TrafficPredicate.match(
                        TrafficSelector(
                            destination=target,
                            protocol=TrafficProtocol.ICMP,
                            icmp_types=(IcmpType.ECHO_REQUEST,),
                        )
                    ),
                ),
            ),
        )

        with self.assertRaisesRegex(
            LinuxNetworkDesiredError,
            "lacks matching owner-scoped isolated dispatch",
        ):
            compile_linux_network_desired(
                compose_network_rules(
                    (OwnedNetworkRules(OwnerToken(1), rules),)
                ),
                LinuxRoutingAllocationState(),
                local_interface="host0",
                local_process=LinuxLocalProcessConfig(
                    uid=65534,
                    ct_mark=0x24,
                ),
            )

    def test_local_process_broad_predicate_is_rejected(self):
        identity = InterfaceIdentity("vpns00", 10)
        path = NetworkEndpoint.interface_path(identity)
        target = IPv4Network("203.0.113.24/32")
        rules = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "probe",
                    (target,),
                    (identity,),
                    TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    target,
                    "probe",
                    source=NetworkEndpoint.local_process(),
                    bound_output=path,
                    protocol=TrafficProtocol.ICMP,
                ),
            ),
            traffic_allows=(
                TrafficAllowSpec(
                    NetworkEndpoint.local_process(),
                    path,
                    TrafficPredicate.always(),
                ),
            ),
        )

        with self.assertRaisesRegex(
            LinuxNetworkDesiredError,
            "exact probe MATCH predicates",
        ):
            compile_linux_network_desired(
                compose_network_rules(
                    (OwnedNetworkRules(OwnerToken(1), rules),)
                ),
                LinuxRoutingAllocationState(),
                local_interface="host0",
                local_process=LinuxLocalProcessConfig(
                    uid=65534,
                    ct_mark=0x24,
                ),
            )

    def test_local_process_dispatch_only_remains_fail_closed(self):
        identity = InterfaceIdentity("vpns00", 10)
        path = NetworkEndpoint.interface_path(identity)
        target = IPv4Network("203.0.113.24/32")
        rules = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "probe",
                    (target,),
                    (identity,),
                    TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    target,
                    "probe",
                    source=NetworkEndpoint.local_process(),
                    bound_output=path,
                    protocol=TrafficProtocol.ICMP,
                ),
            ),
        )

        desired = compile_linux_network_desired(
            compose_network_rules(
                (OwnedNetworkRules(OwnerToken(1), rules),)
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
            local_process=LinuxLocalProcessConfig(
                uid=65534,
                ct_mark=0x24,
            ),
        )

        self.assertIn("meta skuid 65534 drop", desired.filter.definition)
        self.assertNotIn("ct mark set 0x24 accept", desired.filter.definition)

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
