from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    NetworkRulesSpec,
    NetworkRulesState,
    RoutingDomainSpec,
    StateKnowledge,
    TerminalDisposition,
)
from rou.payload_rules_state import (
    Convergence,
    Knowledge,
    PayloadRulesState,
    Safety,
    Service,
)
from rou.payload_traffic_state import (
    PayloadTrafficStateInfo,
    project_payload_traffic_state,
)


def _domain(
    name: str,
    destination: str,
    *paths: InterfaceIdentity,
) -> RoutingDomainSpec:
    return RoutingDomainSpec(
        name=name,
        destinations=(IPv4Network(destination),),
        ordered_paths=paths,
        terminal_disposition=TerminalDisposition.DROP,
    )


class PayloadTrafficStateProjectionTests(unittest.TestCase):
    def setUp(self):
        self.pri = InterfaceIdentity("vpns00", 10)
        self.sec = InterfaceIdentity("vpns01", 11)
        self.desired = NetworkRulesSpec(
            routing_domains=(
                _domain("corp", "10.0.0.0/8", self.pri, self.sec),
                _domain("lab", "192.168.0.0/16", self.pri),
            ),
        )

    def test_known_state_exposes_materialized_paths_in_profile_order(self):
        actual = NetworkRulesSpec(
            routing_domains=(
                _domain("lab", "192.168.0.0/16", self.pri),
                _domain("corp", "10.0.0.0/8", self.pri),
            ),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            actual,
            fresh=True,
        )
        rules_state = PayloadRulesState(
            Knowledge.KNOWN,
            Convergence.DIVERGED,
            Safety.SAFE,
            Service.UNKNOWN,
        )

        info = project_payload_traffic_state(
            self.desired,
            observed,
            rules_state,
        )

        self.assertEqual(
            [item.profile_name for item in info.profiles],
            ["corp", "lab"],
        )
        self.assertEqual(info.profiles[0].materialized_paths, (self.pri,))
        self.assertEqual(info.profiles[1].materialized_paths, (self.pri,))

    def test_missing_observed_profile_is_known_empty_path_projection(self):
        actual = NetworkRulesSpec(
            routing_domains=(
                _domain("corp", "10.0.0.0/8", self.pri),
            ),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            actual,
            fresh=True,
        )
        rules_state = PayloadRulesState(
            Knowledge.KNOWN,
            Convergence.DIVERGED,
            Safety.UNKNOWN,
            Service.UNKNOWN,
        )

        info = project_payload_traffic_state(
            self.desired,
            observed,
            rules_state,
        )

        self.assertEqual(info.profiles[1].profile_name, "lab")
        self.assertEqual(info.profiles[1].materialized_paths, ())

    def test_unknown_rules_state_does_not_publish_cached_paths(self):
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            self.desired,
            fresh=False,
        )
        rules_state = PayloadRulesState(
            Knowledge.UNKNOWN,
            Convergence.UNKNOWN,
            Safety.UNKNOWN,
            Service.UNKNOWN,
        )

        info = project_payload_traffic_state(
            self.desired,
            observed,
            rules_state,
        )

        self.assertTrue(
            all(item.materialized_paths is None for item in info.profiles)
        )

    def test_foreign_observed_profile_is_not_published_as_requested_profile(self):
        actual = NetworkRulesSpec(
            routing_domains=(
                _domain("corp", "10.0.0.0/8", self.pri),
                _domain("foreign", "172.16.0.0/12", self.sec),
            ),
        )
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            actual,
            fresh=True,
        )
        rules_state = PayloadRulesState(
            Knowledge.KNOWN,
            Convergence.DIVERGED,
            Safety.UNKNOWN,
            Service.UNKNOWN,
        )

        info = project_payload_traffic_state(
            self.desired,
            observed,
            rules_state,
        )

        self.assertEqual(
            [item.profile_name for item in info.profiles],
            ["corp", "lab"],
        )

    def test_known_rules_state_requires_authoritative_observation(self):
        observed = NetworkRulesState(
            StateKnowledge.KNOWN,
            self.desired,
            fresh=False,
        )
        rules_state = PayloadRulesState(
            Knowledge.KNOWN,
            Convergence.MATCHED,
            Safety.SAFE,
            Service.READY,
        )

        with self.assertRaises(ValueError):
            project_payload_traffic_state(
                self.desired,
                observed,
                rules_state,
            )

    def test_info_rejects_path_claims_when_rules_knowledge_unknown(self):
        rules_state = PayloadRulesState(
            Knowledge.UNKNOWN,
            Convergence.UNKNOWN,
            Safety.UNKNOWN,
            Service.UNKNOWN,
        )

        with self.assertRaises(ValueError):
            PayloadTrafficStateInfo(
                rules_state=rules_state,
                profiles=(
                    __import__(
                        "rou.payload_traffic_state",
                        fromlist=["PayloadProfileTrafficState"],
                    ).PayloadProfileTrafficState(
                        "corp",
                        (self.pri,),
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
