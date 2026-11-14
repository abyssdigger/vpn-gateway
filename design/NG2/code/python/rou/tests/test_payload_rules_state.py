from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    NetworkEndpoint,
    NetworkRulesSpec,
    NetworkRulesState,
    RoutingDomainSpec,
    StateKnowledge,
    TerminalDisposition,
    TrafficAllowSpec,
    TrafficPredicate,
)
from rou.payload_rules_state import (
    Convergence,
    Knowledge,
    PayloadRulesStateCalculator,
    Safety,
    Service,
)


def _domain(name: str, *paths: InterfaceIdentity) -> RoutingDomainSpec:
    return RoutingDomainSpec(
        name=name,
        destinations=(IPv4Network("10.0.0.0/8"),),
        ordered_paths=paths,
        terminal_disposition=TerminalDisposition.DROP,
    )


def _allow(path: InterfaceIdentity) -> TrafficAllowSpec:
    return TrafficAllowSpec(
        source=NetworkEndpoint.local_network(),
        destination=NetworkEndpoint.interface_path(path),
        predicate=TrafficPredicate.always(),
    )


class PayloadRulesStateCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.calc = PayloadRulesStateCalculator()
        self.path = InterfaceIdentity("vpns00", 10)

    def test_stale_known_observation_is_not_authoritative(self):
        desired = NetworkRulesSpec(
            routing_domains=(_domain("a", self.path),),
            traffic_allows=(_allow(self.path),),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            desired,
            fresh=False,
        )

        state = self.calc.calculate(desired, observed)

        self.assertIs(state.knowledge, Knowledge.UNKNOWN)
        self.assertIs(state.convergence, Convergence.UNKNOWN)
        self.assertIs(state.safety, Safety.UNKNOWN)
        self.assertIs(state.service, Service.UNKNOWN)

    def test_unknown_observation_produces_unknown_axes(self):
        observed = NetworkRulesState(
            StateKnowledge.UNKNOWN,
            None,
            fresh=False,
        )

        state = self.calc.calculate(NetworkRulesSpec(), observed)

        self.assertEqual(
            state,
            state.__class__(
                Knowledge.UNKNOWN,
                Convergence.UNKNOWN,
                Safety.UNKNOWN,
                Service.UNKNOWN,
            ),
        )

    def test_exact_active_rules_are_matched_safe_ready(self):
        desired = NetworkRulesSpec(
            routing_domains=(_domain("a", self.path),),
            traffic_allows=(_allow(self.path),),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            desired,
            fresh=True,
        )

        state = self.calc.calculate(desired, observed)

        self.assertEqual(
            state,
            state.__class__(
                Knowledge.KNOWN,
                Convergence.MATCHED,
                Safety.SAFE,
                Service.READY,
            ),
        )

    def test_exact_zero_path_rules_are_matched_safe_isolated(self):
        desired = NetworkRulesSpec(
            routing_domains=(_domain("a"),),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            desired,
            fresh=True,
        )

        state = self.calc.calculate(desired, observed)

        self.assertEqual(
            state,
            state.__class__(
                Knowledge.KNOWN,
                Convergence.MATCHED,
                Safety.SAFE,
                Service.ISOLATED,
            ),
        )

    def test_exact_mixed_path_rules_are_matched_safe_degraded(self):
        desired = NetworkRulesSpec(
            routing_domains=(
                _domain("a", self.path),
                RoutingDomainSpec(
                    name="b",
                    destinations=(IPv4Network("192.168.0.0/16"),),
                    ordered_paths=(),
                    terminal_disposition=TerminalDisposition.DROP,
                ),
            ),
            traffic_allows=(_allow(self.path),),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            desired,
            fresh=True,
        )

        state = self.calc.calculate(desired, observed)

        self.assertEqual(
            state,
            state.__class__(
                Knowledge.KNOWN,
                Convergence.MATCHED,
                Safety.SAFE,
                Service.DEGRADED,
            ),
        )

    def test_diverged_proven_isolation_is_safe(self):
        desired = NetworkRulesSpec(
            routing_domains=(_domain("a", self.path),),
            traffic_allows=(_allow(self.path),),
        )
        actual = NetworkRulesSpec(
            routing_domains=(_domain("a"),),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            actual,
            fresh=True,
        )

        state = self.calc.calculate(desired, observed)

        self.assertEqual(
            state,
            state.__class__(
                Knowledge.KNOWN,
                Convergence.DIVERGED,
                Safety.SAFE,
                Service.ISOLATED,
            ),
        )

    def test_diverged_nonisolated_rules_are_not_guessed_safe_or_unsafe(self):
        desired = NetworkRulesSpec(
            routing_domains=(_domain("a", self.path),),
            traffic_allows=(_allow(self.path),),
        )
        other_path = InterfaceIdentity("vpns01", 11)
        actual = NetworkRulesSpec(
            routing_domains=(_domain("a", other_path),),
            traffic_allows=(_allow(other_path),),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            actual,
            fresh=True,
        )

        state = self.calc.calculate(desired, observed)

        self.assertIs(state.knowledge, Knowledge.KNOWN)
        self.assertIs(state.convergence, Convergence.DIVERGED)
        self.assertIs(state.safety, Safety.UNKNOWN)
        self.assertIs(state.service, Service.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
