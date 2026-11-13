from ipaddress import IPv4Network
import unittest

from rou.network_rules import (
    DispatchRuleSpec,
    InterfaceIdentity,
    InterfaceRef,
    NetworkRulesError,
    NetworkRulesScope,
    NetworkRulesSpec,
    NetworkRulesState,
    RoutingDomainSpec,
    StateKnowledge,
    TerminalAction,
)


class NetworkRulesContractTests(unittest.TestCase):
    def test_concrete_interface_ref_preserves_generation(self):
        old = InterfaceRef.concrete(InterfaceIdentity("vpns00", 10))
        new = InterfaceRef.concrete(InterfaceIdentity("vpns00", 11))
        self.assertNotEqual(old, new)

    def test_scope_is_not_part_of_rules_spec(self):
        spec = NetworkRulesSpec()
        payload = NetworkRulesScope("payload")
        availability = NetworkRulesScope("availability")

        self.assertEqual(spec, NetworkRulesSpec())
        self.assertNotEqual(payload, availability)

    def test_dispatch_must_reference_known_domain(self):
        with self.assertRaises(NetworkRulesError):
            NetworkRulesSpec(
                dispatch_rules=(
                    DispatchRuleSpec(
                        IPv4Network("10.0.0.0/8"),
                        "missing",
                        ingress=InterfaceRef.stable("host0"),
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
                    TerminalAction.BLACKHOLE,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    IPv4Network("10.0.0.0/8"),
                    "profile-a",
                    ingress=InterfaceRef.stable("host0"),
                ),
            ),
        )

        self.assertEqual(spec.routing_domains[0].ordered_paths, ())

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


if __name__ == "__main__":
    unittest.main()
