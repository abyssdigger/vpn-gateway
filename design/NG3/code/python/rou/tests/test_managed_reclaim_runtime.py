"""Non-exposing runtime plan composition tests for #41."""
from dataclasses import replace
from ipaddress import IPv4Address
from unittest import TestCase
from unittest.mock import Mock

from rou.accepted_effective_state import AcceptedEffectiveState, observe_pre_reclaim
from rou.alpha_runtime import AlphaPreparedPolicy
from rou.managed_device_manager import ManagedDeviceManager
from rou.managed_reclaim_runtime import (
    build_runtime_reclaim_plan, exact_survivor_bindings,
    previously_admitted_deferred_bindings, replacement_managed_interfaces,
    recovery_eligibility_seed, recovery_managed_interfaces,
    structural_retirement_precondition, execute_reclaim_batch,
)
from rou.release1_config import ManagedReclaimPolicy
from rou.managed_reclaim_projection import ReclaimReason
from rou.managed_wireguard_adapter import ManagedWireGuardObservation, ManagedWireGuardState

from test_accepted_effective_state import A, EXT, CONFIG, PRESENT, peer, request


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
        kwargs = dict(already_retired=frozenset(), replacement_bindings=frozenset({EXT}))
        self.assertTrue(structural_retirement_precondition(plan, cfg, e, **kwargs))
        self.assertFalse(structural_retirement_precondition(
            plan, cfg, self.evidence(cfg, bindings=(A,)), **kwargs))
        self.assertFalse(structural_retirement_precondition(
            plan, cfg, e, already_retired=frozenset(), replacement_bindings=frozenset()))
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
            self.assertEqual(out.requires_recovery, expected_touched)
            self.assertEqual(retire.call_count, int(expected_attempt))
            self.assertEqual(out.retired, frozenset({"a"}) if expected_attempt else frozenset())
            self.assertEqual(out.problem is None, expected_attempt)

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
        self.assertEqual(verify.call_args_list[-1].args, (candidates[1], frozenset({"a"})))
        self.assertIn("b:", out.problem)
