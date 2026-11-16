from ipaddress import IPv4Address
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    NetworkRulesSpec,
    NetworkRulesState,
    StateKnowledge,
)
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
    ProbeRulesCalculator,
)
from rou.probe_rules_state import (
    Convergence,
    Knowledge,
    ProbeRulesState,
    ProbeRulesStateCalculator,
    Usability,
)


class ProbeRulesStateCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.calc = ProbeRulesStateCalculator()
        self.path = InterfaceIdentity("vpns00", 10)
        self.desired = ProbeRulesCalculator().calculate(
            AvailabilityProbeSetRequest(
                (
                    AvailabilityProbeRequest(
                        "probe",
                        self.path,
                        IPv4Address("203.0.113.24"),
                    ),
                )
            )
        )

    def test_unknown_knowledge_requires_unknown_dependent_axes(self):
        with self.assertRaises(ValueError):
            ProbeRulesState(
                Knowledge.UNKNOWN,
                Convergence.DIVERGED,
                Usability.INVALID,
            )

    def test_matched_rules_must_be_ready(self):
        with self.assertRaises(ValueError):
            ProbeRulesState(
                Knowledge.KNOWN,
                Convergence.MATCHED,
                Usability.INVALID,
            )

    def test_diverged_rules_must_invalidate_probe_evidence(self):
        with self.assertRaises(ValueError):
            ProbeRulesState(
                Knowledge.KNOWN,
                Convergence.DIVERGED,
                Usability.READY,
            )

    def test_unknown_observation_is_unknown(self):
        state = self.calc.calculate(
            self.desired,
            NetworkRulesState(
                StateKnowledge.UNKNOWN,
                None,
                fresh=False,
            ),
        )

        self.assertEqual(
            state,
            ProbeRulesState(
                Knowledge.UNKNOWN,
                Convergence.UNKNOWN,
                Usability.UNKNOWN,
            ),
        )

    def test_stale_known_observation_is_unknown(self):
        state = self.calc.calculate(
            self.desired,
            NetworkRulesState(
                StateKnowledge.KNOWN,
                self.desired,
                fresh=False,
            ),
        )

        self.assertEqual(
            state,
            ProbeRulesState(
                Knowledge.UNKNOWN,
                Convergence.UNKNOWN,
                Usability.UNKNOWN,
            ),
        )

    def test_exact_observation_is_ready(self):
        state = self.calc.calculate(
            self.desired,
            NetworkRulesState(
                StateKnowledge.KNOWN,
                self.desired,
                fresh=True,
            ),
        )

        self.assertEqual(
            state,
            ProbeRulesState(
                Knowledge.KNOWN,
                Convergence.MATCHED,
                Usability.READY,
            ),
        )

    def test_restrictive_projection_invalidates_probe_evidence(self):
        projected = NetworkRulesSpec(
            routing_domains=tuple(
                domain.__class__(
                    domain.name,
                    domain.destinations,
                    (),
                    domain.terminal_disposition,
                )
                for domain in self.desired.routing_domains
            )
        )

        state = self.calc.calculate(
            self.desired,
            NetworkRulesState(
                StateKnowledge.KNOWN,
                projected,
                fresh=True,
            ),
        )

        self.assertEqual(
            state,
            ProbeRulesState(
                Knowledge.KNOWN,
                Convergence.DIVERGED,
                Usability.INVALID,
            ),
        )

    def test_empty_authoritative_rules_are_invalid_not_unreachable(self):
        state = self.calc.calculate(
            self.desired,
            NetworkRulesState(
                StateKnowledge.KNOWN,
                NetworkRulesSpec(),
                fresh=True,
            ),
        )

        self.assertIs(state.knowledge, Knowledge.KNOWN)
        self.assertIs(state.convergence, Convergence.DIVERGED)
        self.assertIs(state.usability, Usability.INVALID)

    def test_semantically_unordered_allow_rules_still_match(self):
        two = ProbeRulesCalculator().calculate(
            AvailabilityProbeSetRequest(
                (
                    AvailabilityProbeRequest(
                        "a",
                        self.path,
                        IPv4Address("203.0.113.24"),
                    ),
                    AvailabilityProbeRequest(
                        "b",
                        InterfaceIdentity("vpns01", 11),
                        IPv4Address("203.0.113.25"),
                    ),
                )
            )
        )
        reordered = NetworkRulesSpec(
            routing_domains=tuple(reversed(two.routing_domains)),
            dispatch_rules=two.dispatch_rules,
            traffic_allows=tuple(reversed(two.traffic_allows)),
            flow_initiation_allows=tuple(
                reversed(two.flow_initiation_allows)
            ),
            source_nat=two.source_nat,
        )

        state = self.calc.calculate(
            two,
            NetworkRulesState(
                StateKnowledge.KNOWN,
                reordered,
                fresh=True,
            ),
        )

        self.assertIs(state.convergence, Convergence.MATCHED)
        self.assertIs(state.usability, Usability.READY)


if __name__ == "__main__":
    unittest.main()
