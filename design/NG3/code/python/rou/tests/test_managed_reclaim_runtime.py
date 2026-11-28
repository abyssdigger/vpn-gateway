"""Non-exposing runtime plan composition tests for #41."""
from dataclasses import replace
from ipaddress import IPv4Address, IPv4Network
from unittest import TestCase
from unittest.mock import Mock, patch
from types import SimpleNamespace

from rou.accepted_effective_state import AcceptedEffectiveState, observe_pre_reclaim
from rou.alpha_runtime import (
    AlphaPreparedPolicy, AlphaReconcileResult, AlphaReconcileStatus,
    capture_reclaim_replacement_evidence, reclaim_replacement_policy_exact,
    release_alpha_reclaim_batch, _managed_device_problem,
    refresh_alpha_managed_reclaim_status, complete_alpha_reclaim_reconciliation,
    AlphaPostReleaseResult,
)
from rou.forwarding_gate import ForwardingGateState
from rou.interface_identity import InterfaceIdentity
from rou.alpha_runtime import StackReturnAffinityOwnerStatus
from rou.managed_device_manager import (
    ManagedDeviceManager, ManagedDeviceDesiredState, ManagedDeviceIntentBasis,
)
from rou.managed_reclaim_runtime import (
    build_runtime_reclaim_plan, exact_survivor_bindings,
    previously_admitted_deferred_bindings, replacement_managed_interfaces,
    recovery_eligibility_seed, recovery_managed_interfaces,
    structural_retirement_precondition, execute_reclaim_batch,
    replacement_peer_ownership_exact, cleanup_ownership_desired,
    project_managed_reclaim_realizations, ReclaimBatchOutcome,
)
from rou.release1_config import ManagedReclaimPolicy
from rou.managed_reclaim_projection import ReclaimReason
from rou.managed_device_demand import ManagedOrdinaryContribution
from rou.managed_wireguard_adapter import ManagedWireGuardObservation, ManagedWireGuardState
from rou.wireguard_peer_ownership import WireGuardPeerOwnershipObservation

from test_accepted_effective_state import A, EXT, CONFIG, PRESENT, peer, request, availability


class RuntimeReclaimPlanTests(TestCase):
    def setUp(self):
        self.cfg = AlphaPreparedPolicy.from_text(
            CONFIG, local_address=IPv4Address("198.19.255.2")).current_config
        self.previous = AcceptedEffectiveState((
            request(self.cfg, "corp", A, EXT),
            request(self.cfg, "other", EXT),
            request(self.cfg, "z", A, EXT),
        ), (A, EXT), (peer(),))
        self.adapter = Mock()
        self.adapter.observe.return_value = replace(PRESENT, confirmed_generation=None)
        self.adapter.desired_generation.return_value = "base-a"
        self.adapter.confirm_present.return_value = PRESENT
        self.manager = ManagedDeviceManager(self.adapter)

    def evidence(self, config=None, previous=True, bindings=(A, EXT)):
        return observe_pre_reclaim(
            config or self.cfg, self.previous if previous else None,
            self.manager, lambda: bindings)

    def test_careful_survivor_not_structurally_demanded(self):
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(), self.previous)
        self.assertNotIn("a", plan.evidence.demand.desired_device_ids)
        self.assertEqual(plan.mandatory_device_ids, frozenset())
        self.assertEqual(exact_survivor_bindings(plan), frozenset({A}))
        self.assertEqual(plan.projection.retirement_candidates, ())
        self.assertEqual({p.profile_id for p in plan.profiles}, {"corp", "other", "z"})
        self.adapter.converge_absent.assert_not_called()
        self.adapter.converge_present.assert_not_called()
        self.adapter.retire_exact.assert_not_called()

    def test_strict_surplus_excluded_from_survivor_set(self):
        cfg = replace(self.cfg, managed_reclaim=ManagedReclaimPolicy.STRICT)
        plan = build_runtime_reclaim_plan(cfg, self.evidence(cfg), self.previous)
        self.assertEqual([r.device_id for r in plan.projection.retirement_candidates], ["a"])
        self.assertEqual(exact_survivor_bindings(plan), frozenset())
        self.assertEqual(dict(plan.projection.floors), {"corp": 1, "other": 1, "z": 1})

    def test_unknown_no_previous_does_not_authorize_new_exposure(self):
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(previous=False), None)
        self.assertEqual([r.device_id for r in plan.projection.deferred], ["a"])
        self.assertFalse(plan.projection.retirement_candidates)
        self.assertFalse(previously_admitted_deferred_bindings(plan))

    def test_exact_previously_admitted_deferred_binding(self):
        e = self.evidence(previous=False)
        plan = build_runtime_reclaim_plan(self.cfg, e, self.previous)
        self.assertEqual(previously_admitted_deferred_bindings(plan), frozenset({A}))
        # Same interface, different confirmed base generation is not prior exposure.
        self.adapter.desired_generation.return_value = "base-new"
        self.adapter.confirm_present.return_value = replace(PRESENT, confirmed_generation="base-new")
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(previous=False), self.previous)
        self.assertFalse(previously_admitted_deferred_bindings(plan))

    def test_unconfirmed_identity_neither_retired_nor_admitted(self):
        self.adapter.confirm_present.side_effect = RuntimeError("unconfirmed")
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(), self.previous)
        self.assertFalse(plan.projection.retirement_candidates)
        self.assertFalse(exact_survivor_bindings(plan))
        self.assertFalse(previously_admitted_deferred_bindings(plan))

    def test_inconsistent_global_inventory_aborts_plan(self):
        e = self.evidence()
        for bad in (replace(e, demand=None), replace(e, bindings=(A, A, EXT)),
                    replace(e, bindings=(A,))):
            with self.assertRaises(ValueError):
                build_runtime_reclaim_plan(self.cfg, bad, self.previous)

    def test_startup_unknown_allows_independent_exact_structural_demand(self):
        e = self.evidence(previous=False, bindings=(A,))
        plan = build_runtime_reclaim_plan(self.cfg, e, None)
        self.assertIn("a", e.demand.desired_device_ids)
        self.assertFalse(plan.projection.retirement_candidates)
        self.assertEqual(replacement_managed_interfaces(plan), frozenset({A.endpoint}))

    def test_startup_surplus_deferred_has_no_exposure(self):
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(previous=False), None)
        self.assertEqual(replacement_managed_interfaces(plan), frozenset())

    def test_recovery_preserves_survivor_only_on_matching_generation(self):
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(), self.previous)
        seed = recovery_eligibility_seed(plan)
        self.assertEqual(recovery_managed_interfaces(self.cfg, self.evidence(), seed),
                         frozenset({A.endpoint}))
        self.adapter.desired_generation.return_value = "base-new"
        self.adapter.confirm_present.return_value = replace(PRESENT, confirmed_generation="base-new")
        self.assertFalse(recovery_managed_interfaces(self.cfg, self.evidence(), seed))

    def test_cancelled_retirement_reenters_only_via_structural_demand(self):
        cfg = replace(self.cfg, managed_reclaim=ManagedReclaimPolicy.STRICT)
        plan = build_runtime_reclaim_plan(cfg, self.evidence(cfg), self.previous)
        seed = recovery_eligibility_seed(plan)
        self.assertFalse(seed)
        self.assertFalse(recovery_managed_interfaces(cfg, self.evidence(cfg), seed))
        self.assertEqual(recovery_managed_interfaces(
            cfg, self.evidence(cfg, bindings=(A,)), seed), frozenset({A.endpoint}))

    def test_structural_guard_rejects_drift_and_unavailable_replacement(self):
        cfg = replace(self.cfg, managed_reclaim=ManagedReclaimPolicy.STRICT)
        e = self.evidence(cfg)
        plan = build_runtime_reclaim_plan(cfg, e, self.previous)
        kwargs = dict(candidate_id="a", already_retired=frozenset(), replacement_bindings=frozenset({EXT}))
        self.assertTrue(structural_retirement_precondition(plan, cfg, e, **kwargs))
        self.assertFalse(structural_retirement_precondition(
            plan, cfg, self.evidence(cfg, bindings=(A,)), **kwargs))
        self.assertFalse(structural_retirement_precondition(
            plan, cfg, e, candidate_id="a", already_retired=frozenset(), replacement_bindings=frozenset()))
        self.assertFalse(structural_retirement_precondition(
            plan, replace(cfg), e, **kwargs))

    def strict_plan(self):
        cfg = replace(self.cfg, managed_reclaim=ManagedReclaimPolicy.STRICT)
        return build_runtime_reclaim_plan(cfg, self.evidence(cfg), self.previous)

    def test_manager_calls_only_exact_retirement_and_rejects_unconfirmed_result(self):
        plan = self.strict_plan()
        candidate = plan.projection.retirement_candidates[0]
        absent = ManagedWireGuardObservation("a", ManagedWireGuardState.ABSENT)
        self.adapter.retire_exact.return_value = absent
        self.assertEqual(self.manager.retire_reclaim_candidate(plan.config, candidate), absent)
        self.adapter.retire_exact.assert_called_once_with(
            "a", A.endpoint, "base-a", plan.config.managed_vpns["a"])
        self.adapter.converge_absent.assert_not_called()
        self.adapter.retire_exact.return_value = PRESENT
        with self.assertRaises(RuntimeError):
            self.manager.retire_reclaim_candidate(plan.config, candidate)
        with self.assertRaises(ValueError):
            self.manager.retire_reclaim_candidate(
                plan.config, replace(candidate, reason=ReclaimReason.CAPACITY))

    def test_batch_pre_and_post_cleanup_checks_and_touch_boundary(self):
        plan = self.strict_plan()
        for checks, cleaned, expected_touched, expected_attempt in (
            ([False], True, False, False),
            ([True], False, True, False),
            ([True, False], True, True, False),
            ([True, True], True, True, True),
        ):
            verify = Mock(side_effect=checks)
            cleanup = Mock(return_value=cleaned)
            retire = Mock()
            out = execute_reclaim_batch(plan, verify=verify, cleanup=cleanup, retire=retire)
            self.assertEqual(out.dependencies_touched, expected_touched)
            self.assertEqual(out.retirement_attempted, expected_attempt)
            # Replacement policy was already applied, so even the first
            # pre-cleanup guard failure requires fresh recovery.
            self.assertTrue(out.requires_recovery)
            self.assertEqual(cleanup.call_count, int(expected_touched))
            self.assertEqual(retire.call_count, int(expected_attempt))
            self.assertEqual(out.retired, frozenset({"a"}) if expected_attempt else frozenset())
            self.assertEqual(out.problem is None, expected_attempt)

    def test_empty_batch_without_problem_does_not_require_recovery(self):
        plan = self.strict_plan()
        plan = replace(plan, projection=replace(plan.projection, retirement_candidates=()))
        verify, cleanup, retire = Mock(), Mock(), Mock()
        out = execute_reclaim_batch(plan, verify=verify, cleanup=cleanup, retire=retire)
        self.assertIsNone(out.problem)
        self.assertFalse(out.requires_recovery)
        self.assertFalse(out.retired)
        verify.assert_not_called()
        cleanup.assert_not_called()
        retire.assert_not_called()

    def test_batch_failure_after_success_stops_remaining_without_rollback(self):
        plan = self.strict_plan()
        candidate = plan.projection.retirement_candidates[0]
        # Synthetic decisions exercise orchestration only, not plan selection.
        candidates = (candidate, replace(candidate, device_id="b"),
                      replace(candidate, device_id="c"))
        plan = replace(plan, projection=replace(plan.projection, retirement_candidates=candidates))
        verify = Mock(return_value=True)
        cleanup = Mock(return_value=True)
        retire = Mock(side_effect=[None, RuntimeError("drift")])
        out = execute_reclaim_batch(plan, verify=verify, cleanup=cleanup, retire=retire)
        self.assertEqual(out.retired, frozenset({"a"}))
        self.assertTrue(out.requires_recovery)
        self.assertEqual(cleanup.call_count, 2)
        self.assertEqual(retire.call_count, 2)
        self.assertEqual(verify.call_args_list[-1].args, (candidates[1], frozenset({"a"}), True))
        self.assertIn("b:", out.problem)

    def test_peer_guard_rechecks_actual_ownership_and_original_careful_proof(self):
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(), self.previous)
        # Synthetic candidate b contributes to corp; A is its retained shared support.
        plan = replace(plan, profiles=tuple(
            replace(p, contributions=p.contributions + (ManagedOrdinaryContribution("b", 1),))
            if p.profile_id == "corp" else p for p in plan.profiles))
        observe = Mock(side_effect=lambda desired: WireGuardPeerOwnershipObservation(
            desired.device_id, desired.interface, desired.peers))
        replacement = frozenset({A, EXT})
        self.assertTrue(replacement_peer_ownership_exact(
            plan, self.evidence(), replacement, "b", (peer(),), observe))
        self.assertFalse(replacement_peer_ownership_exact(
            plan, self.evidence(), replacement, "b",
            (replace(peer(), generation="different"),), observe))
        observe.side_effect = lambda desired: WireGuardPeerOwnershipObservation(
            desired.device_id, desired.interface, ())
        self.assertFalse(replacement_peer_ownership_exact(
            plan, self.evidence(), replacement, "b", (peer(),), observe))

    def test_cleanup_keeps_only_permanent_probe_prefix(self):
        plan = self.strict_plan()
        desired = cleanup_ownership_desired(plan.config, plan.projection.retirement_candidates[0])
        self.assertEqual(desired.device_id, "a")
        self.assertEqual(desired.interface, A.endpoint)
        self.assertEqual(tuple(str(n) for n in desired.peers[0].allowed_ips),
                         ("10.201.0.1/32",))

    def test_exact_retained_lifecycle_present_is_not_structural_demand(self):
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(), self.previous)
        result, = project_managed_reclaim_realizations(
            self.cfg, plan.evidence, (), replacement_managed_interfaces(plan))
        self.assertNotIn("a", plan.evidence.demand.desired_device_ids)
        self.assertIs(result.desired_state, ManagedDeviceDesiredState.PRESENT)
        self.assertEqual(result.desired_generation, result.confirmed_generation)
        self.assertIs(result.intent_basis, ManagedDeviceIntentBasis.RECLAIM_RETENTION)
        self.assertTrue(result.payload_eligible)
        self.assertFalse(result.waiting_for_dependencies)
        self.assertIsNone(result.problem)
        self.adapter.converge_present.assert_not_called()

    def test_deferred_physical_hold_has_no_eligibility_or_dependency_wait(self):
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(previous=False), None)
        result, = project_managed_reclaim_realizations(
            self.cfg, plan.evidence, (), replacement_managed_interfaces(plan))
        self.assertIs(result.confirmed_state, ManagedWireGuardState.PRESENT)
        self.assertIs(result.desired_state, ManagedDeviceDesiredState.ABSENT)
        self.assertIs(result.intent_basis, ManagedDeviceIntentBasis.RECLAIM_DEFERRED_HOLD)
        self.assertFalse(result.payload_eligible)
        self.assertFalse(result.waiting_for_dependencies)
        self.assertIsNone(result.problem)

    def test_reclaim_hold_and_pre_touch_retirement_are_not_failed_absence(self):
        deferred = build_runtime_reclaim_plan(self.cfg, self.evidence(previous=False), None)
        held, = project_managed_reclaim_realizations(
            self.cfg, deferred.evidence, (), replacement_managed_interfaces(deferred))
        strict = self.strict_plan()
        retiring, = project_managed_reclaim_realizations(
            strict.config, strict.evidence, (), replacement_managed_interfaces(strict),
            frozenset({"a"}))
        self.assertIs(retiring.intent_basis, ManagedDeviceIntentBasis.RECLAIM_RETIREMENT)
        self.assertTrue(retiring.waiting_for_dependencies)
        for row in (held, retiring):
            with self.subTest(basis=row.intent_basis):
                self.assertIsNone(_managed_device_problem((row,)))
                self.assertIsNotNone(_managed_device_problem((row,), require_absent=True))
                self.assertIsNotNone(_managed_device_problem((
                    replace(row, waiting_for_dependencies=False, problem="drift"),)))
                self.assertIsNotNone(_managed_device_problem((
                    replace(row, confirmed_interface=None),)))
                self.assertIsNotNone(_managed_device_problem((
                    replace(row, confirmed_generation=None),)))
                self.assertIsNotNone(_managed_device_problem((
                    replace(row, confirmed_state=None, waiting_for_dependencies=False),)))
        self.assertIsNotNone(_managed_device_problem((
            replace(held, intent_basis=None),)))
        absent = replace(held, intent_basis=None, confirmed_state=ManagedWireGuardState.ABSENT,
                         confirmed_interface=None, confirmed_generation=None)
        self.assertIsNone(_managed_device_problem((absent,), require_absent=True))

    def test_structural_presence_health_still_requires_confirmed_generation(self):
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(), self.previous)
        retained, = project_managed_reclaim_realizations(
            self.cfg, plan.evidence, (), replacement_managed_interfaces(plan))
        row = replace(retained, intent_basis=ManagedDeviceIntentBasis.STRUCTURAL)
        self.assertIsNone(_managed_device_problem((row,)))
        self.assertIsNotNone(_managed_device_problem((replace(row, confirmed_state=None),)))
        self.assertIsNotNone(_managed_device_problem((
            replace(row, confirmed_generation="different"),)))
        self.assertIsNotNone(_managed_device_problem((replace(row, confirmed_interface=None),)))

    def test_final_reclaim_status_does_not_reuse_no_candidate_plan(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG, local_address=IPv4Address("198.19.255.2"))
        prepared.accepted_effective_state = self.previous
        initial = build_runtime_reclaim_plan(self.cfg, self.evidence(), self.previous)
        self.assertEqual(initial.projection.retirement_candidates, ())
        self.assertEqual([row.device_id for row in initial.projection.survivors], ["a"])
        prepared.pre_reclaim_evidence = initial.evidence
        self.adapter.observe.return_value = ManagedWireGuardObservation(
            "a", ManagedWireGuardState.ABSENT)
        agent = Mock()
        with patch("rou.alpha_runtime._observe_presence_bindings", return_value=(EXT,)):
            refresh_alpha_managed_reclaim_status(
                prepared, Mock(), Mock(), self.manager, agent)
        projection = agent.confirm_managed_reclaim.call_args.args[0]
        self.assertIsNotNone(projection)
        self.assertFalse(projection.survivors)
        self.assertFalse(projection.retirement_candidates)
        self.assertIsNotNone(agent.confirm_managed_demand.call_args.args[0])
        self.assertIs(prepared.pre_reclaim_evidence, initial.evidence)
        self.adapter.retire_exact.assert_not_called()
        self.adapter.converge_present.assert_not_called()
        self.adapter.converge_absent.assert_not_called()

    def test_final_reclaim_status_clears_unconfirmed_generation_or_inventory(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG, local_address=IPv4Address("198.19.255.2"))
        agent = Mock()
        with patch("rou.alpha_runtime._observe_presence_bindings") as observe:
            refresh_alpha_managed_reclaim_status(
                prepared, Mock(), Mock(), self.manager, agent)
            observe.assert_not_called()
        agent.confirm_managed_reclaim.assert_called_once_with(None)
        agent.confirm_managed_demand.assert_called_once_with(None)
        prepared.accepted_effective_state = self.previous
        agent.reset_mock()
        with patch("rou.alpha_runtime._observe_presence_bindings", side_effect=RuntimeError("drift")):
            refresh_alpha_managed_reclaim_status(
                prepared, Mock(), Mock(), self.manager, agent)
        agent.confirm_managed_reclaim.assert_called_once_with(None)
        agent.confirm_managed_demand.assert_called_once_with(None)

    def test_replacement_capture_requires_confirmed_final_result_and_reobserves_policy(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG, local_address=IPv4Address("198.19.255.2"))
        prepared.confirmed_managed_interfaces = frozenset()
        desired = prepared.build_current(InterfaceIdentity("host0", 99), (A.endpoint, EXT.endpoint))
        result = AlphaReconcileResult(AlphaReconcileStatus.EXACT, desired)
        confirmed = availability(prepared.last_profiles)
        self.assertIsNone(capture_reclaim_replacement_evidence(
            prepared, result, availability(prepared.last_profiles, confirmed=False),
            SimpleNamespace(confirmed=True), None))
        replacement = capture_reclaim_replacement_evidence(
            prepared, result, confirmed, SimpleNamespace(confirmed=True), None)
        self.assertIsNotNone(replacement)
        domain = SimpleNamespace(namespace="ns")
        runner = Mock()
        with patch("rou.alpha_runtime.LinuxStructuralPolicyBackend") as backend, \
             patch("rou.alpha_runtime.compare_structural_policy") as compare, \
             patch("rou.alpha_runtime.verify_probe_execution_precondition") as probe, \
             patch("rou.alpha_runtime.LinuxStackReturnAffinityBackend") as affinity, \
             patch("rou.alpha_runtime.LinuxForwardingGateDriver") as gate:
            compare.return_value.desired_confirmed = True
            probe.return_value.confirmed = True
            affinity.return_value.observe.return_value.status = StackReturnAffinityOwnerStatus.EXACT
            gate.return_value.observe_forwarding_gate.return_value = ForwardingGateState.ENABLED
            self.assertTrue(reclaim_replacement_policy_exact(
                prepared, domain, runner, replacement, frozenset({"a"})))
            backend.return_value.observe_structural_snapshot.assert_called_once()
            probe.return_value.confirmed = False
            self.assertFalse(reclaim_replacement_policy_exact(
                prepared, domain, runner, replacement, frozenset({"a"})))
            probe.return_value.confirmed = True
            compare.return_value.desired_confirmed = False
            self.assertFalse(reclaim_replacement_policy_exact(
                prepared, domain, runner, replacement, frozenset({"a"})))
        runner.assert_not_called()

    def test_scoped_guard_allows_unrelated_unprovable_floor(self):
        extra = """
[device.b]
enabled = true
use_outbound_nat = true
[device.b.managed_vpn]
kind = "wireguard"
interface = "wg2"
address = "10.200.0.2/32"
private_key_file = "/secret/b.key"
[[device.b.managed_vpn.peers]]
id = "peer"
public_key = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
endpoint = "198.51.100.2:51820"
probe_target = "10.201.0.2"
[profile.isolated]
enabled = true
direction = "outbound"
destinations = ["10.80.0.0/24"]
device_order = ["b"]
warm_paths = 1
"""
        from rou.binding import PathBinding, LogicalPathId
        from rou.interface_identity import InterfaceIdentity
        from rou.release1_config import parse_current_config
        cfg = parse_current_config('managed_reclaim = "strict"\n' + CONFIG + extra)
        b = PathBinding(LogicalPathId("b", 0, 0), InterfaceIdentity("wg2", 12))

        def observe_base(config, device_id):
            if device_id == "b":
                raise RuntimeError("unconfirmed isolated base")
            return "base-a", PRESENT

        with patch.object(ManagedDeviceManager, "observe_exact_base", side_effect=observe_base):
            evidence = observe_pre_reclaim(cfg, self.previous, self.manager, lambda: (A, EXT, b))
        plan = build_runtime_reclaim_plan(cfg, evidence, self.previous)
        self.assertEqual([r.device_id for r in plan.projection.retirement_candidates], ["a"])
        self.assertIn("b", {r.device_id for r in plan.projection.deferred})
        self.assertEqual(dict(plan.projection.floors)["isolated"], 1)
        self.assertTrue(structural_retirement_precondition(
            plan, cfg, evidence, candidate_id="a", already_retired=frozenset(),
            replacement_bindings=frozenset({EXT})))
        self.assertFalse(structural_retirement_precondition(
            plan, cfg, evidence, candidate_id="a", already_retired=frozenset(),
            replacement_bindings=frozenset()))

    def complete_reclaim(self, plan, initial, prepared=None):
        prepared = prepared or SimpleNamespace(current_config=plan.config)
        return complete_alpha_reclaim_reconciliation(
            prepared, Mock(), Mock(), self.manager, plan, Mock(), Mock(),
            Mock(), initial,
        )

    def test_completion_no_candidates_does_not_release_or_recover(self):
        plan = build_runtime_reclaim_plan(self.cfg, self.evidence(), self.previous)
        initial = AlphaPostReleaseResult((), Mock(), None, None, None)
        with patch("rou.alpha_runtime.capture_reclaim_replacement_evidence") as capture, \
             patch("rou.alpha_runtime.release_alpha_reclaim_batch") as batch, \
             patch("rou.alpha_runtime.reconcile_alpha_after_managed_release") as recover:
            out = self.complete_reclaim(plan, initial)
        self.assertIs(out.final, initial)
        self.assertIsNone(out.batch)
        self.assertIsNone(out.problem)
        capture.assert_not_called()
        batch.assert_not_called()
        recover.assert_not_called()

    def test_completion_missing_replacement_recovers_without_retirement(self):
        plan = self.strict_plan()
        initial = AlphaPostReleaseResult((), Mock(), None, None, "unconfirmed")
        recovered = AlphaPostReleaseResult((), Mock(), Mock(), None, None)
        with patch("rou.alpha_runtime.capture_reclaim_replacement_evidence", return_value=None), \
             patch("rou.alpha_runtime.release_alpha_reclaim_batch") as batch, \
             patch("rou.alpha_runtime.reconcile_alpha_after_managed_release",
                   return_value=recovered) as recover:
            out = self.complete_reclaim(plan, initial)
        self.assertIs(out.final, recovered)
        self.assertIsNone(out.batch)
        self.assertIsNotNone(out.problem)
        batch.assert_not_called()
        recover.assert_called_once()
        self.assertEqual(recover.call_args.kwargs["recovery_seed"], recovery_eligibility_seed(plan))

    def test_completion_recovers_once_and_keeps_batch_outcome(self):
        plan = self.strict_plan()
        initial = AlphaPostReleaseResult((), Mock(), Mock(), None, None)
        recovered = AlphaPostReleaseResult((), Mock(), Mock(), None, None)
        for batch_outcome in (
            ReclaimBatchOutcome(frozenset(), False, False, "pre-cleanup drift"),
            ReclaimBatchOutcome(frozenset({"a"}), True, True, None),
            ReclaimBatchOutcome(frozenset({"a"}), True, True, "later candidate failed"),
        ):
            with self.subTest(batch=batch_outcome), \
                 patch("rou.alpha_runtime.capture_reclaim_replacement_evidence", return_value=Mock()), \
                 patch("rou.alpha_runtime.release_alpha_reclaim_batch",
                       return_value=batch_outcome) as batch, \
                 patch("rou.alpha_runtime.reconcile_alpha_after_managed_release",
                       return_value=recovered) as recover, \
                 patch("rou.alpha_runtime.publish_alpha_accepted_effective") as publish:
                out = self.complete_reclaim(plan, initial)
            self.assertIs(out.final, recovered)
            self.assertIs(out.batch, batch_outcome)
            self.assertEqual(out.problem, batch_outcome.problem)
            batch.assert_called_once()
            recover.assert_called_once()
            self.assertEqual(recover.call_args.kwargs["recovery_seed"],
                             recovery_eligibility_seed(plan))
            publish.assert_not_called()

    def test_completion_changed_config_does_not_reuse_seed_or_release(self):
        plan = self.strict_plan()
        initial = AlphaPostReleaseResult((), Mock(), Mock(), None, None)
        recovered = AlphaPostReleaseResult((), Mock(), Mock(), None, None)
        with patch("rou.alpha_runtime.release_alpha_reclaim_batch") as batch, \
             patch("rou.alpha_runtime.reconcile_alpha_after_managed_release",
                   return_value=recovered) as recover:
            out = self.complete_reclaim(
                plan, initial, SimpleNamespace(current_config=self.cfg))
        self.assertIs(out.final, recovered)
        self.assertIsNotNone(out.problem)
        batch.assert_not_called()
        recover.assert_called_once()
        self.assertEqual(recover.call_args.kwargs["recovery_seed"], frozenset())

    def test_alpha_batch_composes_fresh_guards_and_exact_retirement(self):
        plan = self.strict_plan()
        prepared = SimpleNamespace(current_config=plan.config)
        replacement = SimpleNamespace(bindings=(EXT,))
        ownership = Mock()
        ownership.converge.return_value.confirmed = True
        ownership.observe.side_effect = lambda desired: WireGuardPeerOwnershipObservation(
            desired.device_id, desired.interface, desired.peers)
        self.adapter.retire_exact.return_value = ManagedWireGuardObservation(
            "a", ManagedWireGuardState.ABSENT)
        with patch("rou.alpha_runtime.observe_alpha_pre_reclaim",
                   return_value=plan.evidence) as observe, \
             patch("rou.alpha_runtime.reclaim_replacement_policy_exact",
                   return_value=True) as policy:
            out = release_alpha_reclaim_batch(
                prepared, SimpleNamespace(namespace="ns"), Mock(), self.manager,
                plan, replacement, None, ownership)
        self.assertEqual(out.retired, frozenset({"a"}))
        self.assertTrue(out.requires_recovery)
        self.assertEqual(observe.call_count, 2)
        self.assertEqual(policy.call_count, 2)
        ownership.converge.assert_called_once()
        ownership.observe.assert_called_once()
        self.adapter.retire_exact.assert_called_once_with(
            "a", A.endpoint, "base-a", plan.config.managed_vpns["a"])
        self.adapter.converge_absent.assert_not_called()

    def test_alpha_batch_rejects_post_cleanup_policy_drift(self):
        plan = self.strict_plan()
        ownership = Mock()
        ownership.converge.return_value.confirmed = True
        with patch("rou.alpha_runtime.observe_alpha_pre_reclaim", return_value=plan.evidence), \
             patch("rou.alpha_runtime.reclaim_replacement_policy_exact", side_effect=[True, False]):
            out = release_alpha_reclaim_batch(
                SimpleNamespace(current_config=plan.config), SimpleNamespace(namespace="ns"),
                Mock(), self.manager, plan, SimpleNamespace(bindings=(EXT,)), None, ownership)
        self.assertTrue(out.requires_recovery)
        self.assertFalse(out.retirement_attempted)
        self.assertFalse(out.retired)
        self.adapter.retire_exact.assert_not_called()

    def test_alpha_batch_rejects_reappearing_candidate_payload_after_cleanup(self):
        plan = self.strict_plan()
        ownership = Mock()
        ownership.converge.return_value.confirmed = True

        def drift(desired):
            original = desired.peers[0]
            restored = replace(original, allowed_ips=(
                *original.allowed_ips, IPv4Network("10.253.0.0/24"),
            ))
            return WireGuardPeerOwnershipObservation(
                desired.device_id, desired.interface, (restored, *desired.peers[1:]))
        ownership.observe.side_effect = drift
        with patch("rou.alpha_runtime.observe_alpha_pre_reclaim", return_value=plan.evidence), \
             patch("rou.alpha_runtime.reclaim_replacement_policy_exact", return_value=True):
            out = release_alpha_reclaim_batch(
                SimpleNamespace(current_config=plan.config), SimpleNamespace(namespace="ns"),
                Mock(), self.manager, plan, SimpleNamespace(bindings=(EXT,)), None, ownership)
        ownership.converge.assert_called_once()
        ownership.observe.assert_called_once()
        self.assertTrue(out.requires_recovery)
        self.assertFalse(out.retirement_attempted)
        self.assertFalse(out.retired)
        self.adapter.retire_exact.assert_not_called()
