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
    TrafficSelector,
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

    def test_semantically_unordered_collections_do_not_fake_divergence(self):
        second = InterfaceIdentity("vpns01", 11)
        desired = NetworkRulesSpec(
            routing_domains=(
                _domain("a", self.path),
                RoutingDomainSpec(
                    name="b",
                    destinations=(
                        IPv4Network("192.168.0.0/16"),
                        IPv4Network("172.16.0.0/12"),
                    ),
                    ordered_paths=(second,),
                    terminal_disposition=TerminalDisposition.DROP,
                ),
            ),
            traffic_allows=(
                _allow(self.path),
                _allow(second),
            ),
        )
        actual = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    name="b",
                    destinations=(
                        IPv4Network("172.16.0.0/12"),
                        IPv4Network("192.168.0.0/16"),
                    ),
                    ordered_paths=(second,),
                    terminal_disposition=TerminalDisposition.DROP,
                ),
                _domain("a", self.path),
            ),
            traffic_allows=(
                _allow(second),
                _allow(self.path),
            ),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            actual,
            fresh=True,
        )

        state = self.calc.calculate(desired, observed)

        self.assertIs(state.convergence, Convergence.MATCHED)
        self.assertIs(state.safety, Safety.SAFE)
        self.assertIs(state.service, Service.READY)

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

    def test_removed_backup_path_is_provably_safe_degradation(self):
        backup = InterfaceIdentity("vpns01", 11)
        desired = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    name="a",
                    destinations=(IPv4Network("10.0.0.0/8"),),
                    ordered_paths=(self.path, backup),
                    terminal_disposition=TerminalDisposition.DROP,
                ),
            ),
            traffic_allows=(_allow(self.path),),
        )
        actual = NetworkRulesSpec(
            routing_domains=(_domain("a", self.path),),
            traffic_allows=(_allow(self.path),),
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
                Service.DEGRADED,
            ),
        )

    def test_removed_allow_is_provably_safe_degradation(self):
        second = InterfaceIdentity("vpns01", 11)
        desired = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    name="a",
                    destinations=(IPv4Network("10.0.0.0/8"),),
                    ordered_paths=(self.path, second),
                    terminal_disposition=TerminalDisposition.DROP,
                ),
            ),
            traffic_allows=(
                _allow(self.path),
                _allow(second),
            ),
        )
        actual = NetworkRulesSpec(
            routing_domains=desired.routing_domains,
            traffic_allows=(_allow(self.path),),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            actual,
            fresh=True,
        )

        state = self.calc.calculate(desired, observed)

        self.assertIs(state.safety, Safety.SAFE)
        self.assertIs(state.service, Service.DEGRADED)

    def test_reordered_paths_are_not_assumed_restrictive(self):
        backup = InterfaceIdentity("vpns01", 11)
        desired = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    name="a",
                    destinations=(IPv4Network("10.0.0.0/8"),),
                    ordered_paths=(self.path, backup),
                    terminal_disposition=TerminalDisposition.DROP,
                ),
            ),
            traffic_allows=(_allow(self.path),),
        )
        actual = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    name="a",
                    destinations=(IPv4Network("10.0.0.0/8"),),
                    ordered_paths=(backup, self.path),
                    terminal_disposition=TerminalDisposition.DROP,
                ),
            ),
            traffic_allows=(_allow(self.path),),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            actual,
            fresh=True,
        )

        state = self.calc.calculate(desired, observed)

        self.assertIs(state.safety, Safety.UNKNOWN)
        self.assertIs(state.service, Service.UNKNOWN)

    def test_new_endpoint_pair_is_provably_unsafe(self):
        desired = NetworkRulesSpec(
            routing_domains=(_domain("a", self.path),),
            traffic_allows=(_allow(self.path),),
        )
        foreign_path = InterfaceIdentity("vpns01", 11)
        actual = NetworkRulesSpec(
            routing_domains=desired.routing_domains,
            traffic_allows=(
                _allow(self.path),
                _allow(foreign_path),
            ),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            actual,
            fresh=True,
        )

        state = self.calc.calculate(desired, observed)

        self.assertIs(state.safety, Safety.UNSAFE)
        self.assertIs(state.service, Service.UNKNOWN)

    def test_extra_allow_on_existing_endpoint_pair_remains_unknown(self):
        local = NetworkEndpoint.local_network()
        path = NetworkEndpoint.interface_path(self.path)
        desired_allow = TrafficAllowSpec(
            source=local,
            destination=path,
            predicate=TrafficPredicate.match(
                TrafficSelector(destination=IPv4Network("10.0.0.0/8"))
            ),
        )
        actual_allow = TrafficAllowSpec(
            source=local,
            destination=path,
            predicate=TrafficPredicate.always(),
        )
        desired = NetworkRulesSpec(
            routing_domains=(_domain("a", self.path),),
            traffic_allows=(desired_allow,),
        )
        actual = NetworkRulesSpec(
            routing_domains=desired.routing_domains,
            traffic_allows=(desired_allow, actual_allow),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            actual,
            fresh=True,
        )

        state = self.calc.calculate(desired, observed)

        self.assertIs(state.safety, Safety.UNKNOWN)
        self.assertIs(state.service, Service.UNKNOWN)

    def test_changed_to_unapproved_endpoint_is_provably_unsafe(self):
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
        self.assertIs(state.safety, Safety.UNSAFE)
        self.assertIs(state.service, Service.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
