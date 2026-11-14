from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_adapter import LinuxNetworkRulesAdapter
from rou.linux_driver import LinuxDriverResult, LinuxNetworkVerification
from rou.network_rules import (
    DispatchRuleSpec,
    NetworkEndpoint,
    NetworkRulesSpec,
    RoutingDomainSpec,
    StateKnowledge,
    TerminalDisposition,
    TrafficAllowSpec,
    TrafficPredicate,
)


class EqualOwner:
    def __eq__(self, other):
        return isinstance(other, EqualOwner)

    def __hash__(self):
        return 1


class FakeBackend:
    def __init__(self):
        self.materialize_success = True
        self.verify_ok = True
        self.materialize_calls = []
        self.verify_calls = []
        self.interfaces = ()

    def observe_interfaces(self):
        return self.interfaces

    def materialize_structural(self, desired):
        self.materialize_calls.append(desired)
        if self.materialize_success:
            return LinuxDriverResult(True)
        return LinuxDriverResult(False, "injected materialization failure")

    def verify_current(self, desired):
        self.verify_calls.append(desired)
        if self.verify_ok:
            return LinuxNetworkVerification(True, ())
        return LinuxNetworkVerification(False, ("injected drift",))


def _path_rules(
    identity: InterfaceIdentity,
    destination: str,
) -> NetworkRulesSpec:
    network = IPv4Network(destination)
    local = NetworkEndpoint.local_network()
    path = NetworkEndpoint.interface_path(identity)
    return NetworkRulesSpec(
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
    )


class LinuxNetworkRulesAdapterTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.adapter = LinuxNetworkRulesAdapter(
            self.backend,
            local_interface="host0",
        )

    def test_successful_apply_commits_fresh_known_owner_state(self):
        owner = object()
        rules = NetworkRulesSpec()

        result = self.adapter.apply(owner, rules)
        state = self.adapter.get_last_state(owner)

        self.assertTrue(result.success)
        self.assertIs(state.knowledge, StateKnowledge.KNOWN)
        self.assertEqual(state.rules, rules)
        self.assertTrue(state.fresh)

    def test_equal_but_distinct_owners_remain_separate(self):
        first = EqualOwner()
        second = EqualOwner()
        first_rules = NetworkRulesSpec()
        second_rules = NetworkRulesSpec()

        self.assertTrue(self.adapter.apply(first, first_rules).success)
        self.assertTrue(self.adapter.apply(second, second_rules).success)

        self.assertEqual(self.adapter.get_last_state(first).rules, first_rules)
        self.assertEqual(self.adapter.get_last_state(second).rules, second_rules)

    def test_failed_first_apply_registers_owner_but_does_not_commit_candidate(self):
        owner = object()
        candidate = NetworkRulesSpec()
        self.backend.materialize_success = False

        result = self.adapter.apply(owner, candidate)
        state = self.adapter.get_last_state(owner)

        self.assertFalse(result.success)
        self.assertIs(state.knowledge, StateKnowledge.UNKNOWN)

        # Physical verification of the unchanged committed empty composition can later
        # prove this owner's empty owned scope.
        self.backend.verify_ok = True
        renewed = self.adapter.renew_state(owner)
        state = self.adapter.get_last_state(owner)

        self.assertTrue(renewed.success)
        self.assertIs(state.knowledge, StateKnowledge.KNOWN)
        self.assertEqual(state.rules, NetworkRulesSpec())

    def test_failed_replacement_keeps_previous_committed_generation(self):
        owner = object()
        path = InterfaceIdentity("vpns00", 10)
        self.backend.interfaces = (path,)
        old = _path_rules(path, "10.0.0.0/8")
        self.assertTrue(self.adapter.apply(owner, old).success)

        candidate = _path_rules(path, "192.168.0.0/16")
        self.backend.materialize_success = False

        result = self.adapter.apply(owner, candidate)
        self.assertFalse(result.success)
        self.assertIs(
            self.adapter.get_last_state(owner).knowledge,
            StateKnowledge.UNKNOWN,
        )

        self.backend.materialize_success = True
        self.assertTrue(self.adapter.renew_state(owner).success)
        self.assertEqual(self.adapter.get_last_state(owner).rules, old)

    def test_failed_shared_mutation_marks_other_owner_unknown(self):
        first = object()
        second = object()
        self.assertTrue(self.adapter.apply(first, NetworkRulesSpec()).success)
        self.assertTrue(self.adapter.apply(second, NetworkRulesSpec()).success)

        self.backend.materialize_success = False
        result = self.adapter.apply(first, NetworkRulesSpec())

        self.assertFalse(result.success)
        self.assertIs(
            self.adapter.get_last_state(first).knowledge,
            StateKnowledge.UNKNOWN,
        )
        self.assertIs(
            self.adapter.get_last_state(second).knowledge,
            StateKnowledge.UNKNOWN,
        )

    def test_renew_exact_committed_physical_state_refreshes_all_owners(self):
        first = object()
        second = object()
        self.assertTrue(self.adapter.apply(first, NetworkRulesSpec()).success)
        self.assertTrue(self.adapter.apply(second, NetworkRulesSpec()).success)

        self.backend.verify_ok = False
        self.assertFalse(self.adapter.renew_state(first).success)
        self.assertIs(
            self.adapter.get_last_state(second).knowledge,
            StateKnowledge.UNKNOWN,
        )

        self.backend.verify_ok = True
        self.assertTrue(self.adapter.renew_state(first).success)
        self.assertIs(
            self.adapter.get_last_state(first).knowledge,
            StateKnowledge.KNOWN,
        )
        self.assertIs(
            self.adapter.get_last_state(second).knowledge,
            StateKnowledge.KNOWN,
        )

    def test_sequential_multi_owner_generation_update_does_not_deadlock(self):
        first = object()
        second = object()
        old = InterfaceIdentity("vpns00", 10)
        new = InterfaceIdentity("vpns00", 11)
        self.backend.interfaces = (old,)

        first_old = _path_rules(old, "10.0.0.0/8")
        second_old = _path_rules(old, "192.168.0.0/16")
        self.assertTrue(self.adapter.apply(first, first_old).success)
        self.assertTrue(self.adapter.apply(second, second_old).success)

        self.backend.interfaces = (new,)
        first_new = _path_rules(new, "10.0.0.0/8")
        result = self.adapter.apply(first, first_new)

        self.assertTrue(result.success, result.diagnostic)
        self.assertEqual(
            self.adapter.get_last_state(first).rules,
            first_new,
        )
        second_projected = self.adapter.get_last_state(second)
        self.assertIs(
            second_projected.knowledge,
            StateKnowledge.KNOWN,
        )
        self.assertEqual(
            second_projected.rules.routing_domains[0].ordered_paths,
            (),
        )
        self.assertEqual(
            second_projected.rules.traffic_allows,
            (),
        )

        second_new = _path_rules(new, "192.168.0.0/16")
        result = self.adapter.apply(second, second_new)

        self.assertTrue(result.success, result.diagnostic)
        self.assertEqual(
            self.adapter.get_last_state(second).rules,
            second_new,
        )
        self.assertEqual(
            self.adapter.get_last_state(first).rules,
            first_new,
        )

    def test_cleanup_rebuilds_without_removed_owner_then_forgets_identity(self):
        first = object()
        second = object()
        self.assertTrue(self.adapter.apply(first, NetworkRulesSpec()).success)
        self.assertTrue(self.adapter.apply(second, NetworkRulesSpec()).success)
        before = len(self.backend.materialize_calls)

        result = self.adapter.cleanup(first)

        self.assertTrue(result.success)
        self.assertEqual(len(self.backend.materialize_calls), before + 1)
        self.assertIs(
            self.adapter.get_last_state(first).knowledge,
            StateKnowledge.UNKNOWN,
        )
        self.assertIs(
            self.adapter.get_last_state(second).knowledge,
            StateKnowledge.KNOWN,
        )

    def test_cleanup_of_failed_first_apply_repairs_committed_composition(self):
        owner = object()
        self.backend.materialize_success = False
        self.assertFalse(self.adapter.apply(owner, NetworkRulesSpec()).success)

        self.backend.materialize_success = True
        before = len(self.backend.materialize_calls)
        result = self.adapter.cleanup(owner)

        self.assertTrue(result.success)
        self.assertEqual(len(self.backend.materialize_calls), before + 1)

    def test_failed_cleanup_keeps_owner_committed_and_unknown(self):
        owner = object()
        rules = NetworkRulesSpec()
        self.assertTrue(self.adapter.apply(owner, rules).success)

        self.backend.materialize_success = False
        result = self.adapter.cleanup(owner)

        self.assertFalse(result.success)
        self.assertIs(
            self.adapter.get_last_state(owner).knowledge,
            StateKnowledge.UNKNOWN,
        )

        self.backend.materialize_success = True
        self.assertTrue(self.adapter.renew_state(owner).success)
        self.assertEqual(self.adapter.get_last_state(owner).rules, rules)

    def test_cleanup_unknown_owner_is_idempotent_without_physical_mutation(self):
        before = len(self.backend.materialize_calls)

        result = self.adapter.cleanup(object())

        self.assertTrue(result.success)
        self.assertEqual(len(self.backend.materialize_calls), before)

    def test_get_last_state_unknown_owner_has_no_io(self):
        before_materialize = len(self.backend.materialize_calls)
        before_verify = len(self.backend.verify_calls)

        state = self.adapter.get_last_state(object())

        self.assertIs(state.knowledge, StateKnowledge.UNKNOWN)
        self.assertEqual(len(self.backend.materialize_calls), before_materialize)
        self.assertEqual(len(self.backend.verify_calls), before_verify)


if __name__ == "__main__":
    unittest.main()
