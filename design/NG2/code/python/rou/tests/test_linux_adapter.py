from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.availability_routing import AvailabilityWindowPolicy
from rou.interface_identity import InterfaceIdentity
from rou.linux_adapter import LinuxNetworkRulesAdapter
from rou.linux_driver import LinuxDriverResult, LinuxNetworkVerification
from rou.linux_local_process import LinuxLocalProcessConfig
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
    ProbeRulesCalculator,
)
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
        self.route_priority_calls = []
        self.verify_calls = []
        self.interfaces = ()

    def observe_interfaces(self):
        return self.interfaces

    def materialize_structural(self, desired):
        self.materialize_calls.append(desired)
        if self.materialize_success:
            return LinuxDriverResult(True)
        return LinuxDriverResult(False, "injected materialization failure")

    def materialize_route_priority(self, current, desired):
        self.route_priority_calls.append((current, desired))
        if self.materialize_success:
            return LinuxDriverResult(True)
        return LinuxDriverResult(False, "injected route-priority failure")

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

    def test_pure_path_reorder_uses_route_priority_fast_path(self):
        owner = object()
        first = InterfaceIdentity("vpns00", 10)
        second = InterfaceIdentity("vpns01", 11)
        self.backend.interfaces = (first, second)
        network = IPv4Network("10.0.0.0/8")
        local = NetworkEndpoint.local_network()

        def rules(order):
            return NetworkRulesSpec(
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
            )

        initial = rules((first, second))
        reordered = rules((second, first))

        self.assertTrue(self.adapter.apply(owner, initial).success)
        structural_count = len(self.backend.materialize_calls)

        result = self.adapter.apply(owner, reordered)

        self.assertTrue(result.success, result.diagnostic)
        self.assertEqual(
            len(self.backend.materialize_calls),
            structural_count,
        )
        self.assertEqual(len(self.backend.route_priority_calls), 1)
        current, desired = self.backend.route_priority_calls[0]
        self.assertEqual(
            [
                route.path
                for route in current.routing.routes
                if route.path is not None
            ],
            [first, second],
        )
        self.assertEqual(
            [
                route.path
                for route in desired.routing.routes
                if route.path is not None
            ],
            [second, first],
        )
        self.assertEqual(
            self.adapter.get_last_state(owner).rules,
            reordered,
        )

    def test_semantic_live_prefix_change_with_same_linux_state_is_verified_noop(self):
        owner = object()
        first = InterfaceIdentity("vpns00", 10)
        second = InterfaceIdentity("vpns01", 11)
        self.backend.interfaces = (first, second)
        network = IPv4Network("10.0.0.0/8")
        local = NetworkEndpoint.local_network()

        def rules(prefix):
            return NetworkRulesSpec(
                routing_domains=(
                    RoutingDomainSpec(
                        "corp",
                        (network,),
                        (first, second),
                        TerminalDisposition.DROP,
                        confirmed_live_prefix_length=prefix,
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
            )

        initial = rules(None)
        managed_all_live = rules(2)

        self.assertTrue(self.adapter.apply(owner, initial).success)
        structural_count = len(self.backend.materialize_calls)
        priority_count = len(self.backend.route_priority_calls)
        verify_count = len(self.backend.verify_calls)

        result = self.adapter.apply(owner, managed_all_live)

        self.assertTrue(result.success, result.diagnostic)
        self.assertEqual(len(self.backend.materialize_calls), structural_count)
        self.assertEqual(len(self.backend.route_priority_calls), priority_count)
        self.assertEqual(len(self.backend.verify_calls), verify_count + 1)
        self.assertEqual(
            self.adapter.get_last_state(owner).rules,
            managed_all_live,
        )

    def test_unavailable_first_candidate_reconciles_empty_committed_state(self):
        owner = object()
        missing = InterfaceIdentity("vpns00", 10)
        candidate = _path_rules(missing, "10.0.0.0/8")
        self.backend.interfaces = ()

        result = self.adapter.apply(owner, candidate)

        self.assertFalse(result.success)
        self.assertEqual(len(self.backend.materialize_calls), 1)
        physical = self.backend.materialize_calls[-1]
        self.assertEqual(physical.routing.allocation.domain_tables, ())
        state = self.adapter.get_last_state(owner)
        self.assertIs(state.knowledge, StateKnowledge.KNOWN)
        self.assertEqual(state.rules, NetworkRulesSpec())

        # The rejected candidate was not committed implicitly.
        self.backend.interfaces = (missing,)
        self.assertTrue(self.adapter.renew_state(owner).success)
        self.assertEqual(
            self.adapter.get_last_state(owner).rules,
            NetworkRulesSpec(),
        )

        result = self.adapter.apply(owner, candidate)
        self.assertTrue(result.success, result.diagnostic)
        self.assertEqual(self.adapter.get_last_state(owner).rules, candidate)

    def test_unavailable_replacement_reconciles_previous_committed_generation(self):
        owner = object()
        old = InterfaceIdentity("vpns00", 10)
        missing = InterfaceIdentity("vpns01", 11)
        self.backend.interfaces = (old,)
        committed = _path_rules(old, "10.0.0.0/8")
        candidate = _path_rules(missing, "192.168.0.0/16")
        self.assertTrue(self.adapter.apply(owner, committed).success)

        result = self.adapter.apply(owner, candidate)

        self.assertFalse(result.success)
        physical = self.backend.materialize_calls[-1]
        self.assertEqual(
            [
                str(rule.destination)
                for rule in physical.routing.dispatch_rules
            ],
            ["10.0.0.0/8"],
        )
        self.assertEqual(
            self.adapter.get_last_state(owner).rules,
            committed,
        )

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


    def test_local_process_requires_explicit_linux_identity_config(self):
        owner = object()
        path = InterfaceIdentity("vpns00", 10)
        self.backend.interfaces = (path,)
        rules = ProbeRulesCalculator().calculate(
            AvailabilityProbeSetRequest(
                (
                    AvailabilityProbeRequest(
                        "probe",
                        path,
                        IPv4Address("203.0.113.24"),
                        policy=AvailabilityWindowPolicy(10, 3),
                    ),
                )
            )
        )

        result = self.adapter.apply(owner, rules)

        self.assertFalse(result.success)
        self.assertIn(
            "configured Linux local-process uid",
            result.diagnostic,
        )
        self.assertEqual(self.backend.materialize_calls, [])

    def test_local_process_explicit_linux_identity_reaches_backend(self):
        backend = FakeBackend()
        path = InterfaceIdentity("vpns00", 10)
        backend.interfaces = (path,)
        adapter = LinuxNetworkRulesAdapter(
            backend,
            local_interface="host0",
            local_process=LinuxLocalProcessConfig(
                uid=65534,
                ct_mark=0x24,
            ),
        )
        rules = ProbeRulesCalculator().calculate(
            AvailabilityProbeSetRequest(
                (
                    AvailabilityProbeRequest(
                        "probe",
                        path,
                        IPv4Address("203.0.113.24"),
                        policy=AvailabilityWindowPolicy(10, 3),
                    ),
                )
            )
        )

        result = adapter.apply(object(), rules)

        self.assertTrue(result.success, result.diagnostic)
        desired = backend.materialize_calls[-1]
        dispatch = desired.routing.dispatch_rules[0]
        self.assertEqual(dispatch.local_process_uid, 65534)
        self.assertIn("meta skuid 65534", desired.filter.definition)
        self.assertIn("ct mark set 0x24", desired.filter.definition)

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
