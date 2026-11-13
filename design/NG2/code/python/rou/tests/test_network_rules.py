from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    DispatchRuleSpec,
    EndpointKind,
    NetworkEndpoint,
    NetworkRulesAdapter,
    NetworkRulesError,
    NetworkRulesSpec,
    NetworkRulesState,
    PacketView,
    PortRange,
    PredicateKind,
    RoutingDomainSpec,
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

        self.assertFalse(allowed.matches(blocked_packet))
        self.assertTrue(allowed.matches(other_packet))

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
