from ipaddress import IPv4Address, IPv4Network
import unittest

from predicate_eval import PacketView, predicate_matches

from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    DispatchRuleSpec,
    EndpointKind,
    NetworkEndpoint,
    NetworkRulesAdapter,
    NetworkRulesError,
    NetworkRulesSpec,
    NetworkRulesState,
    PortRange,
    PredicateKind,
    RoutingDomainSpec,
    SourceNatSpec,
    SourceNatTarget,
    StateKnowledge,
    TerminalDisposition,
    TrafficPredicate,
    TrafficProtocol,
    TrafficSelector,
)


class NetworkRulesContractTests(unittest.TestCase):
    def test_interface_identity_preserves_generation(self):
        old = InterfaceIdentity("vpns00", 10)
        new = InterfaceIdentity("vpns00", 11)
        self.assertNotEqual(old, new)

    def test_local_network_endpoint_has_no_linux_interface_name(self):
        endpoint = NetworkEndpoint.local_network()
        self.assertIs(endpoint.kind, EndpointKind.LOCAL_NETWORK)
        self.assertIsNone(endpoint.interface)

    def test_local_process_endpoint_is_semantic_not_linux_identity(self):
        endpoint = NetworkEndpoint.local_process()
        self.assertIs(endpoint.kind, EndpointKind.LOCAL_PROCESS)
        self.assertIsNone(endpoint.interface)

    def test_local_process_dispatch_requires_bound_output_and_protocol(self):
        target = IPv4Network("203.0.113.24/32")
        with self.assertRaisesRegex(
            NetworkRulesError,
            "bound output interface",
        ):
            DispatchRuleSpec(
                target,
                "probe",
                source=NetworkEndpoint.local_process(),
                protocol=TrafficProtocol.ICMP,
            )

        path = NetworkEndpoint.interface_path(
            InterfaceIdentity("vpns00", 10)
        )
        with self.assertRaisesRegex(
            NetworkRulesError,
            "explicit protocol",
        ):
            DispatchRuleSpec(
                target,
                "probe",
                source=NetworkEndpoint.local_process(),
                bound_output=path,
            )

        rule = DispatchRuleSpec(
            target,
            "probe",
            source=NetworkEndpoint.local_process(),
            bound_output=path,
            protocol=TrafficProtocol.ICMP,
        )
        self.assertEqual(rule.bound_output, path)

    def test_dispatch_must_reference_known_domain(self):
        with self.assertRaises(NetworkRulesError):
            NetworkRulesSpec(
                dispatch_rules=(
                    DispatchRuleSpec(
                        IPv4Network("10.0.0.0/8"),
                        "missing",
                        source=NetworkEndpoint.local_network(),
                    ),
                ),
            )

    def test_zero_path_domain_is_valid_fail_closed_intent(self):
        spec = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "profile-a",
                    (IPv4Network("10.0.0.0/8"),),
                    (),
                    TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    IPv4Network("10.0.0.0/8"),
                    "profile-a",
                    source=NetworkEndpoint.local_network(),
                ),
            ),
        )

        self.assertEqual(spec.routing_domains[0].ordered_paths, ())

    def test_predicate_supports_allow_all_except_match(self):
        blocked = TrafficPredicate.match(
            TrafficSelector(
                source=IPv4Network("10.20.0.0/16"),
                protocol=TrafficProtocol.TCP,
                destination_ports=(PortRange(8007, 8007),),
            )
        )
        allowed = TrafficPredicate.negate(blocked)

        blocked_packet = PacketView(
            IPv4Address("10.20.1.2"),
            IPv4Address("192.168.1.10"),
            TrafficProtocol.TCP,
            source_port=50000,
            destination_port=8007,
        )
        other_packet = PacketView(
            IPv4Address("10.20.1.2"),
            IPv4Address("192.168.1.10"),
            TrafficProtocol.TCP,
            source_port=50000,
            destination_port=443,
        )

        self.assertFalse(predicate_matches(allowed, blocked_packet))
        self.assertTrue(predicate_matches(allowed, other_packet))

    def test_predicate_constructors_simplify_constants(self):
        match = TrafficPredicate.match(
            TrafficSelector(destination=IPv4Network("10.0.0.0/8"))
        )
        self.assertEqual(
            TrafficPredicate.all_of(TrafficPredicate.always(), match),
            match,
        )
        self.assertIs(
            TrafficPredicate.any_of(
                TrafficPredicate.never(),
                TrafficPredicate.always(),
            ).kind,
            PredicateKind.ALWAYS,
        )

    def test_source_nat_requires_concrete_egress_path(self):
        with self.assertRaises(NetworkRulesError):
            SourceNatSpec(
                source=NetworkEndpoint.local_network(),
                egress=NetworkEndpoint.local_network(),
                predicate=TrafficPredicate.always(),
                target=SourceNatTarget.EGRESS_ADDRESS,
            )

    def test_unknown_state_cannot_claim_rules(self):
        with self.assertRaises(NetworkRulesError):
            NetworkRulesState(
                StateKnowledge.UNKNOWN,
                NetworkRulesSpec(),
                fresh=False,
            )

    def test_known_state_requires_rules(self):
        with self.assertRaises(NetworkRulesError):
            NetworkRulesState(
                StateKnowledge.KNOWN,
                None,
                fresh=True,
            )

    def test_adapter_contract_has_explicit_cleanup(self):
        self.assertTrue(hasattr(NetworkRulesAdapter, "cleanup"))


if __name__ == "__main__":
    unittest.main()
