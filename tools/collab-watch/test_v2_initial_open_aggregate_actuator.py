"""8c-C: initial OPEN joins the retained aggregate/checkpoint send chain."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import copy
import unittest
from unittest.mock import patch

from core import Conflict, canonical, digest
import test_v2_actuator as tf
import test_v2_aggregate_actuator as af
from test_split_journal import CFG, fixture, issue, opening, row
from test_v2_aux import aux
from v2_actuator import _bound, _ownership_fd, _witness, freeze_inputs
from v2_aux import project_aux
from v2_compact import compact_v2
from v2_owner import OwnerBusy
from v2_preflight import preflight_initial_open_compact
from v2_runtime_state import RuntimeStateStore, open_state
import v2_actuator as actuator


class InitialOpenAggregateActuatorTests(unittest.TestCase):
    setUp = af.AggregateActuatorTests.setUp
    cap = af.AggregateActuatorTests.cap
    run_case = af.AggregateActuatorTests.run_case
    no_claim = af.AggregateActuatorTests.no_claim
    new_checkpoint = af.AggregateActuatorTests.new_checkpoint

    def case(self):
        return tf.ActuatorTests.initial_case(self)

    def test_exact_coherent_order_owner_attempt_checkpoint_and_identity(self):
        original, remote = self.case()
        cap = self.cap(original)
        data, baseline, proof, effect, action, wire = _bound(original)
        checkpoint = remote.runtime_state
        saved = checkpoint.load()
        saved = checkpoint.save(saved["state"], saved["generation"])
        self.assertEqual(data["previous"], saved["state"]["task"])
        self.assertNotEqual(data["previous"], saved["state"])
        rival = open_state(checkpoint._path, checkpoint._store_id,
                           CFG["repository"], CFG["journal_epoch"])
        self.addCleanup(rival.close)
        events, seen, observed = [], [], []
        real_acquire = actuator.acquire_aggregate_v2_for_initial_open
        real_task = actuator.acquire_v2
        real_gate = actuator.gate_initial_open_aggregate
        real_start = self.store.start
        expected = dict(action, witness=_witness(proof, baseline, data["extra_task"]))
        def authority(descriptor):
            events.append("authority")
            seen.append(descriptor)
            self.assertFalse(remote.read_calls)
            self.assertEqual(descriptor, expected)
            return True
        def acquire(*args, **kwargs):
            events.append("acquire")
            self.assertFalse(remote.applied)
            self.assertEqual(remote.user_reads, [("https://api.github.com/user", "Bearer write-token")])
            self.assertEqual(args, (CFG, data["actor"], data["body"]))
            self.assertEqual(kwargs["selected_role"], "SPEC")
            self.assertEqual(kwargs["selected_incarnation"], "s")
            result = real_acquire(*args, **kwargs)
            observed.append(result)
            return result
        def gate(*args, **kwargs):
            events.append("gate")
            self.assertIs(args[1], observed[0])
            return real_gate(*args, **kwargs)
        def task(*args, **kwargs):
            self.assertTrue(remote.applied, "task-only pre-send scan")
            return real_task(*args, **kwargs)
        def start(key):
            events.append("start")
            with self.assertRaises(OwnerBusy):
                self.other_owner.replace(cap.transport_role, cap.incarnation, cap.generation, lambda _: True)
            with self.assertRaises(BlockingIOError):
                _ownership_fd(self.store)
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(rival.save, saved["state"], saved["generation"])
                with self.assertRaises(Conflict):
                    pending.result(timeout=10)
            result = real_start(key)
            self.assertEqual(result["state"], "STARTED")
            return result
        def at_send():
            events.append("send")
            self.assertEqual(self.store.claimed(effect)["state"], "STARTED")
            self.assertEqual(rival.save(saved["state"], saved["generation"])["generation"],
                             saved["generation"]+1)
            self.assertEqual(self.retention.load(self.store.claimed(effect)["action_key"]), original)
        remote.store_check = at_send
        with patch("v2_actuator.acquire_aggregate_v2_for_initial_open", side_effect=acquire), \
             patch("v2_actuator.gate_initial_open_aggregate", side_effect=gate), \
             patch("v2_actuator.acquire_v2", side_effect=task), \
             patch("v2_actuator.acquire_v2_for_initial_open") as legacy, \
             patch("v2_actuator.acquire_aggregate_v2") as generic, \
             patch.object(self.store, "start", side_effect=start):
            result = self.run_case(original, remote, cap, authority)
            legacy.assert_not_called()
            generic.assert_not_called()
        self.assertEqual(result["state"], "VERIFIED", result)
        self.assertEqual(events, ["authority", "acquire", "gate", "start", "send"])
        claimed = self.store.claimed(effect)
        self.assertEqual(claimed["action_descriptor"], expected)
        self.assertEqual(claimed["effect_descriptor"], effect)
        self.assertEqual(effect["operation"], "control_comment")
        self.assertEqual(remote.sent[0][2], wire)
        self.assertEqual(len(remote.sent), 1)
        self.assertEqual(self.retention.load(claimed["action_key"]), original)
        self.assertNotIn("checkpoint_generation", canonical(claimed))
        self.assertNotIn("checkpoint_state_sha256", canonical(claimed))
        self.assertNotIn("aggregate_inventory_sha256", canonical(claimed["action_descriptor"]))
        with patch("v2_actuator.gate_initial_open_aggregate") as gate, \
             patch("v2_actuator.acquire_aggregate_v2_for_initial_open") as acquire:
            self.assertEqual(self.run_case(original, remote, cap, runtime_state=None), result)
            gate.assert_not_called()
            acquire.assert_not_called()
        self.assertEqual(len(remote.sent), 1)

    def test_missing_wrong_empty_and_stale_checkpoint(self):
        original, remote = self.case()
        cap = self.cap(original)
        state = remote.runtime_state.load()["state"]
        bad = copy.deepcopy(state)
        bad["task"]["ledger"] = {}
        for checkpoint in (None, object(), self.new_checkpoint(),
                           self.new_checkpoint(repository="other/project", state=state),
                           self.new_checkpoint(epoch="other", state=state),
                           self.new_checkpoint(state=bad)):
            with self.subTest(checkpoint=type(checkpoint)), \
                 patch("v2_actuator.acquire_aggregate_v2_for_initial_open") as acquire, \
                 patch.object(self.store, "start") as start:
                result = self.run_case(original, remote, cap, runtime_state=checkpoint)
                self.no_claim(original, remote, result)
                self.assertEqual(result["code"], "CHECKPOINT_UNAVAILABLE_OR_STALE")
                acquire.assert_not_called()
                start.assert_not_called()
                self.assertFalse(remote.user_reads)
                self.assertFalse(remote.read_calls)

    def test_actor_authority_denied_before_final_acquisition(self):
        original, remote = self.case()
        cap = self.cap(original)
        for mode in ("actor", "authority"):
            remote.actor = 99 if mode == "actor" else 13
            with patch("v2_actuator.acquire_aggregate_v2_for_initial_open") as acquire, \
                 patch.object(self.store, "start") as start:
                result = self.run_case(original, remote, cap, lambda _: mode != "authority")
                self.no_claim(original, remote, result)
                self.assertEqual(result["code"], "WRITE_ACTOR_UNVERIFIED" if mode == "actor"
                                 else "AUTHORITY_DENIED")
                acquire.assert_not_called()
                start.assert_not_called()
                self.assertFalse(remote.read_calls)

    def test_no_chronology_witness_before_actor_authority_acquisition(self):
        extra = issue(43, 4003)
        out = opening(extra, task="O2", mid="o2", cid=200, second=20)
        state = project_aux(CFG, {"34": []}, {}, [], [])[1]
        baseline = compact_v2(CFG, {"34": []}, {}, state["task"])
        proof = preflight_initial_open_compact(CFG, baseline, extra, 13, out["body"],
                                                state["task"], **tf.SPEC)
        original = freeze_inputs("initial_open", CFG, baseline, 13, **tf.SPEC,
                                 expected_proof_sha256=digest(canonical(proof)), body=out["body"],
                                 extra_task=extra, previous=state["task"])
        remote = tf.Remote({}, {}, 13, {})
        tf.attach_checkpoint(self, remote, state)
        cap = self.cap(original)
        with patch("v2_actuator.acquire_aggregate_v2_for_initial_open") as acquire, \
             patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap, lambda _: self.fail("authority called"))
            self.no_claim(original, remote, result)
            self.assertEqual(result["code"], "CHRONOLOGY_INELIGIBLE")
            acquire.assert_not_called()
            start.assert_not_called()
            self.assertFalse(remote.user_reads)

    def test_whole_graph_drift_in_each_partition_fails_before_start(self):
        original, remote = self.case()
        cap = self.cap(original)
        real_acquire = actuator.acquire_aggregate_v2_for_initial_open
        for room in (34, 42, 35, 37, 43):
            second = copy.deepcopy(remote.before)
            second[f"/issues/{room}/comments"].append(
                dict(row(900+room, 99, "ordinary drift", 30),
                     issue_url=tf.ROOT+f"/issues/{room}"))
            def drift(*args, **kwargs):
                kwargs["opener"] = tf.Opener(remote.before, second)
                return real_acquire(*args, **kwargs)
            with self.subTest(room=room), \
                 patch("v2_actuator.acquire_aggregate_v2_for_initial_open", side_effect=drift), \
                 patch.object(self.store, "start") as start:
                result = self.run_case(original, remote, cap)
                self.no_claim(original, remote, result)
                self.assertEqual(result["code"], "AGGREGATE_ADMISSION_FAILED")
                start.assert_not_called()

    def test_already_admitted_alias_and_global_collision(self):
        original, remote = self.case()
        cap = self.cap(original)
        base = copy.deepcopy(remote.before)
        alias = opening(issue(43, 4003), task="O3", mid="alias", cid=201, second=20)
        for observed in (remote.response, dict(alias, issue_url=tf.ROOT+"/issues/34")):
            remote.before = copy.deepcopy(base)
            remote.before["/issues/34/comments"].append(observed)
            with patch.object(self.store, "start") as start:
                result = self.run_case(original, remote, cap)
                self.no_claim(original, remote, result)
                self.assertEqual(result["code"], "AGGREGATE_ADMISSION_FAILED")
                start.assert_not_called()
        # The frozen task proof itself admits the candidate on this exact
        # colliding task compact; the composed gate must reject the aux ID.
        rows, task = fixture()
        rows.append(aux("o2", "PING", 901, "GUARD", "BUILDER", ping_id="o2"))
        extra = issue(43, 4003)
        out = opening(extra, task="O2", mid="o2", cid=200, second=20)
        original, remote = tf.initial_open_fixture(self, rows, task, extra, out)
        with patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap)
            self.no_claim(original, remote, result)
            self.assertEqual(result["code"], "AGGREGATE_ADMISSION_FAILED")
            start.assert_not_called()

    def test_final_witness_and_aggregate_binding_mismatch(self):
        original, remote = self.case()
        cap = self.cap(original)
        real_witness = actuator._witness
        calls = []
        def mismatch(*args):
            result = real_witness(*args)
            calls.append(result)
            return result if len(calls) == 1 else dict(result, row_sha256="0"*64)
        with patch("v2_actuator._witness", side_effect=mismatch), \
             patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap)
            self.no_claim(original, remote, result)
            self.assertEqual(result["code"], "AGGREGATE_ADMISSION_FAILED")
            self.assertEqual(len(calls), 2)
            start.assert_not_called()
        real_gate = actuator.gate_initial_open_aggregate
        def bad_gate(*args, **kwargs):
            result = real_gate(*args, **kwargs)
            return dict(result, aggregate_inventory_sha256="0"*64)
        with patch("v2_actuator.gate_initial_open_aggregate", side_effect=bad_gate), \
             patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap)
            self.no_claim(original, remote, result)
            self.assertEqual(result["code"], "AGGREGATE_ADMISSION_FAILED")
            start.assert_not_called()

    def test_checkpoint_advance_after_gate_prevents_started(self):
        original, remote = self.case()
        cap = self.cap(original)
        checkpoint = remote.runtime_state
        saved = checkpoint.load()
        real_gate = actuator.gate_initial_open_aggregate
        def advance(*args, **kwargs):
            result = real_gate(*args, **kwargs)
            checkpoint.save(saved["state"], saved["generation"])
            return result
        with patch("v2_actuator.gate_initial_open_aggregate", side_effect=advance), \
             patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap)
            self.no_claim(original, remote, result)
            self.assertEqual(result["code"], "CHECKPOINT_FENCE_OR_INPUT_FAILED")
            start.assert_not_called()

    def assert_no_rearm(self, original, remote, cap):
        with patch("v2_actuator.acquire_aggregate_v2_for_initial_open") as acquire, \
             patch("v2_actuator.gate_initial_open_aggregate") as gate, \
             patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap, runtime_state=None)
            self.assertIn(result["state"], ("UNRESOLVED", "EFFECT_UNKNOWN"))
            acquire.assert_not_called()
            gate.assert_not_called()
            start.assert_not_called()
        self.assertFalse(remote.sent)

    def test_uncertain_started_no_send_no_rearm(self):
        original, remote = self.case()
        cap = self.cap(original)
        real_start = self.store.start
        def uncertain(key):
            real_start(key)
            raise OSError("uncertain durable start")
        with patch.object(self.store, "start", side_effect=uncertain):
            result = self.run_case(original, remote, cap)
        self.assertEqual(result["state"], "EFFECT_UNKNOWN")
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
        self.assertFalse(remote.sent)
        self.assert_no_rearm(original, remote, cap)
        self.assert_no_rearm(original, remote, cap)

    def test_post_started_fence_exit_failure_no_send_no_rearm(self):
        original, remote = self.case()
        cap = self.cap(original)
        real_fence = RuntimeStateStore.fence
        @contextmanager
        def fail_exit(store, *args):
            with real_fence(store, *args) as value:
                yield value
            raise Conflict("exit failure")
        with patch.object(RuntimeStateStore, "fence", fail_exit):
            result = self.run_case(original, remote, cap)
        self.assertEqual(result["state"], "EFFECT_UNKNOWN")
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
        self.assert_no_rearm(original, remote, cap)

    def test_response_loss_reconciles_and_never_resends(self):
        original, remote = self.case()
        cap = self.cap(original)
        remote.error = True
        result = self.run_case(original, remote, cap)
        self.assertEqual(result["state"], "VERIFIED", result)
        self.assertEqual(self.run_case(original, remote, cap, runtime_state=None), result)
        self.assertEqual(len(remote.sent), 1)

    def test_crash_then_reconciliation_without_checkpoint_or_resend(self):
        original, remote = self.case()
        cap = self.cap(original)
        remote.crash = True
        with self.assertRaises(tf.Crash):
            self.run_case(original, remote, cap)
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
        remote.crash = False
        with patch("v2_actuator.acquire_aggregate_v2_for_initial_open") as acquire:
            result = self.run_case(original, remote, cap, runtime_state=None)
            self.assertEqual(result["state"], "VERIFIED", result)
            acquire.assert_not_called()
        self.assertEqual(len(remote.sent), 1)


if __name__ == "__main__":
    unittest.main()
