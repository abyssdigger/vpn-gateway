"""8b-B canonical control send: aggregate/fence ordering and failure boundaries."""
from contextlib import contextmanager
import copy
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

from core import Conflict, canonical
import test_v2_actuator as tf
import test_v2_aux_actuator as af
from test_split_journal import CFG, fixture, row
from test_v2_aux import aux
from v2_actuator import _bound, _ownership_fd, _witness
from v2_attempts import initialize
from v2_inputs import initialize_inputs
from v2_owner import OwnerBusy, initialize_owner, open_owner
from v2_fenced_actuator import actuate_fenced
from v2_runtime_state import RuntimeStateStore, initialize_state, open_state
import v2_actuator as actuator


class AggregateActuatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.store = initialize(root/"attempt.db", "aggregate-attempt")
        self.retention = initialize_inputs(root/"inputs.db", "aggregate-input", "aggregate-attempt")
        self.addCleanup(self.retention.close)
        self.owner = initialize_owner(root/"owner.db", "aggregate-owner",
                                      CFG["repository"], CFG["journal_epoch"])
        self.addCleanup(self.owner.close)
        self.other_owner = open_owner(root/"owner.db", "aggregate-owner",
                                      CFG["repository"], CFG["journal_epoch"])
        self.addCleanup(self.other_owner.close)

    def task_case(self):
        return tf.ActuatorTests.control_case(self)

    def aux_case(self):
        return af.AuxActuatorTests.case(self)

    def cap(self, original):
        action = _bound(original)[4]
        return self.owner.claim(action["role"], action["incarnation"], lambda _: True)

    def run_case(self, original, remote, cap, authority=lambda _: True, **kwargs):
        kwargs.setdefault("runtime_state", remote.runtime_state)
        with patch("v2_actuator._write_transport", return_value=remote):
            return actuate_fenced(self.owner, cap, self.store, original, self.retention,
                                  authority, read_token="read-token", write_token="write-token",
                                  read_opener=tf.ReadOpener(remote), **kwargs)

    def no_claim(self, original, remote, result):
        self.assertEqual(result["state"], "PREPARED", result)
        self.assertIsNone(self.store.claimed(_bound(original)[3]))
        self.assertFalse(remote.sent)

    def new_checkpoint(self, repository=CFG["repository"], epoch=CFG["journal_epoch"], state=None):
        path = Path(mkdtemp(dir=self.tmp.name))/"checkpoint.db"
        store = initialize_state(path, "other-checkpoint", repository, epoch)
        self.addCleanup(store.close)
        if state is not None:
            store.save(state, 0)
        return store

    def test_both_families_one_final_aggregate_and_fenced_start(self):
        for case in (self.task_case, self.aux_case):
            original, remote = case()
            cap = self.cap(original)
            data, baseline, proof, effect, action, wire = _bound(original)
            checkpoint = remote.runtime_state
            saved = checkpoint.load()
            # Make generation non-initial without altering the frozen previous.
            saved = checkpoint.save(saved["state"], saved["generation"])
            rival = open_state(checkpoint._path, checkpoint._store_id,
                               CFG["repository"], CFG["journal_epoch"])
            self.addCleanup(rival.close)
            events, seen = [], []
            real_aggregate = actuator.acquire_aggregate_v2
            real_task = actuator.acquire_v2
            real_gate = actuator.gate_aggregate_candidate
            real_start = self.store.start
            def aggregate(*args, **kwargs):
                if not remote.applied:
                    events.append("aggregate")
                    self.assertEqual(remote.user_reads, [("https://api.github.com/user", "Bearer write-token")])
                return real_aggregate(*args, **kwargs)
            def task(*args, **kwargs):
                self.assertTrue(remote.applied, "task-only pre-send scan")
                return real_task(*args, **kwargs)
            def gate(*args, **kwargs):
                events.append("gate")
                return real_gate(*args, **kwargs)
            def authority(descriptor):
                events.append("authority")
                seen.append(descriptor)
                self.assertEqual(remote.read_calls, [])
                self.assertEqual(descriptor, dict(action, witness=_witness(proof, baseline, data["extra_task"])))
                return True
            def start(key):
                events.append("start")
                with self.assertRaises(OwnerBusy):
                    self.other_owner.replace(cap.transport_role, cap.incarnation, cap.generation, lambda _: True)
                with self.assertRaises(BlockingIOError):
                    _ownership_fd(self.store)
                # Actual concurrent transaction cannot commit while STARTED is entered.
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
                # Fence must already have exited before physical send.
                self.assertEqual(rival.save(saved["state"], saved["generation"])["generation"],
                                 saved["generation"]+1)
                self.assertEqual(self.retention.load(self.store.claimed(effect)["action_key"]), original)
            remote.store_check = at_send
            with patch("v2_actuator.acquire_aggregate_v2", side_effect=aggregate), \
                 patch("v2_actuator.acquire_v2", side_effect=task), \
                 patch("v2_actuator.gate_aggregate_candidate", side_effect=gate), \
                 patch.object(self.store, "start", side_effect=start):
                result = self.run_case(original, remote, cap, authority)
            self.assertEqual(result["state"], "VERIFIED", result)
            self.assertEqual(events, ["authority", "aggregate", "gate", "start", "send"])
            claimed = self.store.claimed(effect)
            self.assertEqual(claimed["action_descriptor"], seen[0])
            self.assertEqual(claimed["effect_descriptor"], effect)
            self.assertEqual(remote.sent[0][2], wire)
            self.assertEqual(len(remote.sent), 1)
            self.assertNotIn("checkpoint_generation", canonical(claimed))
            self.assertNotIn("checkpoint_state_sha256", canonical(claimed))
            self.assertEqual(self.run_case(original, remote, cap, runtime_state=None), result)
            self.assertEqual(len(remote.sent), 1)

    def test_missing_empty_wrong_scope_and_wrong_frontier(self):
        for case in (self.task_case, self.aux_case):
            original, remote = case()
            cap = self.cap(original)
            saved = remote.runtime_state.load()["state"]
            bad = copy.deepcopy(saved)
            family = "task" if _bound(original)[0]["operation"] == "control_comment" else "aux"
            bad[family]["ledger"] = {}
            for store in (None, object(), self.new_checkpoint(),
                          self.new_checkpoint(repository="other/project", state=saved),
                          self.new_checkpoint(epoch="other", state=saved),
                          self.new_checkpoint(state=bad)):
                with self.subTest(store=type(store), family=family), \
                     patch.object(self.store, "start") as start, \
                     patch("v2_actuator.acquire_aggregate_v2") as acquire:
                    result = self.run_case(original, remote, cap, runtime_state=store)
                    self.no_claim(original, remote, result)
                    self.assertEqual(result["code"], "CHECKPOINT_UNAVAILABLE_OR_STALE")
                    start.assert_not_called()
                    acquire.assert_not_called()
                    self.assertFalse(remote.user_reads)

    def test_actor_authority_before_aggregate_and_start(self):
        for case in (self.task_case, self.aux_case):
            original, remote = case()
            cap = self.cap(original)
            actual_actor = remote.actor
            for mode in ("actor", "authority"):
                remote.actor = 99 if mode == "actor" else actual_actor
                with patch("v2_actuator.acquire_aggregate_v2") as acquire, \
                     patch.object(self.store, "start") as start:
                    result = self.run_case(original, remote, cap, lambda _: mode != "authority")
                    self.no_claim(original, remote, result)
                    self.assertEqual(result["code"], "WRITE_ACTOR_UNVERIFIED" if mode == "actor"
                                     else "AUTHORITY_DENIED")
                    acquire.assert_not_called()
                    start.assert_not_called()

    def test_fresh_collisions_and_drift_fail_before_start(self):
        # The fresh graph has an aux ID colliding with the frozen task candidate.
        original, remote = self.task_case()
        cap = self.cap(original)
        collision = aux("r1", "PING", 901, "GUARD", "SPEC", ping_id="r1")
        remote.before["/issues/34/comments"].append(dict(collision, issue_url=tf.ROOT+"/issues/34"))
        with patch.object(self.store, "start") as start:
            self.no_claim(original, remote, self.run_case(original, remote, cap))
            start.assert_not_called()
        # Aux frozen proof admitted before task RESULT; fresh graph adds that RESULT.
        rows, task = fixture()
        task["comments"] = task["comments"][:1]
        original, remote = af.AuxActuatorTests.case(
            self, aux("r1", "PING", 902, "GUARD", "SPEC", ping_id="r1"),
            rows=rows[:1], task=task)
        cap = self.cap(original)
        remote.before["/issues/34/comments"].append(dict(rows[1], issue_url=tf.ROOT+"/issues/34"))
        with patch.object(self.store, "start") as start:
            self.no_claim(original, remote, self.run_case(original, remote, cap))
            start.assert_not_called()

    def test_checkpoint_advance_after_gate_stops_before_start(self):
        original, remote = self.task_case()
        cap = self.cap(original)
        checkpoint = remote.runtime_state
        saved = checkpoint.load()
        real_gate = actuator.gate_aggregate_candidate
        def advancing_gate(*args, **kwargs):
            result = real_gate(*args, **kwargs)
            checkpoint.save(saved["state"], saved["generation"])
            return result
        with patch("v2_actuator.gate_aggregate_candidate", side_effect=advancing_gate), \
             patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap)
            self.no_claim(original, remote, result)
            self.assertEqual(result["code"], "CHECKPOINT_FENCE_OR_INPUT_FAILED")
            start.assert_not_called()

    def test_post_started_fence_exit_failure_no_send_or_rearm(self):
        original, remote = self.task_case()
        cap = self.cap(original)
        real_fence = RuntimeStateStore.fence
        @contextmanager
        def fail_exit(store, *args):
            with real_fence(store, *args) as value:
                yield value
            raise Conflict("exit failure")
        with patch.object(RuntimeStateStore, "fence", fail_exit):
            result = self.run_case(original, remote, cap)
        self.assertEqual(result["state"], "EFFECT_UNKNOWN", result)
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
        self.assertFalse(remote.sent)
        saved = remote.runtime_state.load()
        remote.runtime_state.save(saved["state"], saved["generation"])
        result = self.run_case(original, remote, cap, runtime_state=None)
        self.assertIn(result["state"], ("UNRESOLVED", "EFFECT_UNKNOWN"))
        self.assertFalse(remote.sent)

    def test_uncertain_start_no_send_and_reconciliation_only(self):
        original, remote = self.aux_case()
        cap = self.cap(original)
        real_start = self.store.start
        def start_then_raise(key):
            real_start(key)
            raise OSError("uncertain durable start")
        with patch.object(self.store, "start", side_effect=start_then_raise):
            result = self.run_case(original, remote, cap)
        self.assertEqual(result["state"], "EFFECT_UNKNOWN")
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
        self.assertFalse(remote.sent)
        with patch("v2_actuator.gate_aggregate_candidate") as gate, \
             patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap, runtime_state=None)
            self.assertIn(result["state"], ("UNRESOLVED", "EFFECT_UNKNOWN"))
            gate.assert_not_called()
            start.assert_not_called()
        self.assertFalse(remote.sent)
