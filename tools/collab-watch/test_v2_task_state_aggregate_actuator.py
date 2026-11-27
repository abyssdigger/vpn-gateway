"""8d-B: task-state physical effects through the retained aggregate send fence."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import copy
import unittest
from unittest.mock import patch

from core import Conflict, canonical
import test_v2_actuator as tf
import test_v2_aggregate_actuator as af
from test_split_journal import CFG, fixture, row
from test_v2_aux import aux, signal
from v2_actuator import _bound, _ownership_fd, _witness
from v2_owner import OwnerBusy
from v2_runtime_state import RuntimeStateStore, open_state
import v2_actuator as actuator

OPS = ("material_comment", "issue_close")


class TaskStateAggregateActuatorTests(unittest.TestCase):
    setUp = af.AggregateActuatorTests.setUp
    cap = af.AggregateActuatorTests.cap
    run_case = af.AggregateActuatorTests.run_case
    no_claim = af.AggregateActuatorTests.no_claim
    new_checkpoint = af.AggregateActuatorTests.new_checkpoint

    def case(self, op, extra_control=()):
        fn = (tf.ActuatorTests.material_case if op == "material_comment"
              else tf.ActuatorTests.close_case)
        return fn(self, extra_control=extra_control)

    def test_exact_order_and_owner_attempt_checkpoint_fence_both(self):
        for op in OPS:
            original, remote = self.case(op)
            cap = self.cap(original)
            data, baseline, proof, effect, action, wire = _bound(original)
            saved = remote.runtime_state.load()
            saved = remote.runtime_state.save(saved["state"], saved["generation"])
            self.assertEqual(data["previous"], saved["state"]["task"])
            self.assertNotEqual(data["previous"], saved["state"])
            checkpoint = remote.runtime_state
            rival = open_state(checkpoint._path, checkpoint._store_id,
                               CFG["repository"], CFG["journal_epoch"])
            self.addCleanup(rival.close)
            events, observed = [], []
            real_acquire = actuator.acquire_aggregate_v2
            real_gate = actuator.gate_task_state_aggregate
            real_task = actuator.acquire_v2
            real_start = self.store.start
            expected = dict(action, witness=_witness(proof, baseline, None))
            if op == "material_comment":
                self.assertEqual(expected["witness"], {"kind": "not_applicable"})
            else:
                self.assertNotEqual(expected["witness"], {"kind": "not_applicable"})
                self.assertIsNotNone(expected["witness"])
            def authority(desc):
                events.append("authority")
                self.assertEqual(desc, expected)
                self.assertFalse(remote.read_calls)
                return True
            def acquire(*args, **kwargs):
                events.append("aggregate")
                self.assertFalse(remote.applied)
                self.assertEqual(len(remote.user_reads), 1)
                return real_acquire(*args, **kwargs)
            def gate(*args, **kwargs):
                events.append("gate")
                self.assertEqual(args[2:7], (op, data["actor"], data["previous"],
                                            saved["state"], data["proof_sha256"]))
                self.assertEqual(kwargs["task_key"], data["task_key"])
                self.assertEqual(kwargs["body"], data["body"])
                self.assertEqual(kwargs["request"], data["request"])
                result = real_gate(*args, **kwargs)
                observed.append(result)
                return result
            def task(*args, **kwargs):
                self.assertTrue(remote.applied, "task-only pre-send scan")
                return real_task(*args, **kwargs)
            def start(key):
                events.append("start")
                with self.assertRaises(OwnerBusy):
                    self.other_owner.replace(cap.transport_role, cap.incarnation,
                                             cap.generation, lambda _: True)
                with self.assertRaises(BlockingIOError):
                    _ownership_fd(self.store)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(rival.save, saved["state"], saved["generation"])
                    with self.assertRaises(Conflict):
                        future.result(timeout=10)
                return real_start(key)
            def send():
                events.append("send")
                self.assertEqual(self.store.claimed(effect)["state"], "STARTED")
                self.assertEqual(rival.save(saved["state"], saved["generation"])["generation"],
                                 saved["generation"]+1)
            remote.store_check = send
            with patch("v2_actuator.acquire_aggregate_v2", side_effect=acquire), \
                 patch("v2_actuator.gate_task_state_aggregate", side_effect=gate), \
                 patch("v2_actuator.acquire_v2", side_effect=task), \
                 patch.object(self.store, "start", side_effect=start):
                result = self.run_case(original, remote, cap, authority)
            self.assertEqual(result["state"], "VERIFIED", result)
            self.assertEqual(events, ["authority", "aggregate", "gate", "start", "send"])
            self.assertEqual(observed[0]["proof_sha256"], data["proof_sha256"])
            claimed = self.store.claimed(effect)
            self.assertEqual(claimed["effect_descriptor"], effect)
            self.assertEqual(claimed["action_descriptor"], expected)
            self.assertEqual(self.retention.load(claimed["action_key"]), original)
            self.assertEqual(remote.sent[0][2], wire)
            self.assertNotIn("checkpoint_generation", canonical(claimed))
            self.assertNotIn("aggregate_inventory_sha256", canonical(claimed["action_descriptor"]))
            with patch("v2_actuator.acquire_aggregate_v2") as acquire, \
                 patch("v2_actuator.gate_task_state_aggregate") as gate:
                self.assertEqual(self.run_case(original, remote, cap, runtime_state=None), result)
                acquire.assert_not_called()
                gate.assert_not_called()
            self.assertEqual(len(remote.sent), 1)

    def test_checkpoint_and_actor_authority_fail_before_acquisition(self):
        for op in OPS:
            original, remote = self.case(op)
            cap = self.cap(original)
            state = remote.runtime_state.load()["state"]
            bad = copy.deepcopy(state)
            bad["task"]["ledger"] = {}
            for checkpoint in (None, object(), self.new_checkpoint(),
                               self.new_checkpoint(repository="other/project", state=state),
                               self.new_checkpoint(epoch="other", state=state),
                               self.new_checkpoint(state=bad)):
                with patch("v2_actuator.acquire_aggregate_v2") as acquire, \
                     patch.object(self.store, "start") as start:
                    result = self.run_case(original, remote, cap, runtime_state=checkpoint)
                    self.no_claim(original, remote, result)
                    self.assertEqual(result["code"], "CHECKPOINT_UNAVAILABLE_OR_STALE")
                    acquire.assert_not_called()
                    start.assert_not_called()
                    self.assertFalse(remote.user_reads or remote.read_calls)
            actual = remote.actor
            for mode in ("actor", "authority"):
                remote.actor = 99 if mode == "actor" else actual
                with patch("v2_actuator.acquire_aggregate_v2") as acquire, \
                     patch.object(self.store, "start") as start:
                    result = self.run_case(original, remote, cap, lambda _: mode != "authority")
                    self.no_claim(original, remote, result)
                    self.assertEqual(result["code"], "WRITE_ACTOR_UNVERIFIED" if mode == "actor"
                                     else "AUTHORITY_DENIED")
                    acquire.assert_not_called()
                    start.assert_not_called()
                    self.assertFalse(remote.read_calls)

    def test_task_semantic_and_inventory_drift_fail_before_start(self):
        for op in OPS:
            original, remote = self.case(op)
            cap = self.cap(original)
            base = copy.deepcopy(remote.before)
            changed = []
            for room in (34, 42):
                graph = copy.deepcopy(base)
                graph[f"/issues/{room}/comments"].append(
                    dict(row(950+room, 99, "ordinary drift", 30),
                         issue_url=tf.ROOT+f"/issues/{room}"))
                changed.append(graph)
            graph = copy.deepcopy(base)
            graph["/issues/34/comments"].append(dict(
                aux("p", "PING", 901, "GUARD", "SPEC", ping_id="p"),
                issue_url=tf.ROOT+"/issues/34"))
            changed.append(graph)
            if op == "material_comment":
                graph = copy.deepcopy(base)
                graph["/issues/42/comments"].append(remote.response)
                changed.append(graph)
                rows, task = fixture()
                graph = tf.snapshots(rows, [task])
                graph["/issues/35/comments"] = []
                graph["/issues/37/comments"] = []
                changed.append(graph)
            else:
                changed.append(copy.deepcopy(remote.after))
                graph = copy.deepcopy(base)
                graph["/issues/34/comments"][2]["body"] += " changed ACCEPT"
                changed.append(graph)
            for graph in changed:
                remote.before = graph
                with patch.object(self.store, "start") as start:
                    result = self.run_case(original, remote, cap)
                    self.no_claim(original, remote, result)
                    self.assertEqual(result["code"], "AGGREGATE_ADMISSION_FAILED")
                    start.assert_not_called()

    def test_holder_and_signal_change_preserves_task_proof(self):
        for op in OPS:
            ping = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
            original, remote = self.case(op, [ping])
            cap = self.cap(original)
            state = remote.runtime_state.load()["state"]
            # Compare a pure gate on the exact pre-change aggregate.
            before = actuator.acquire_aggregate_v2(CFG, token="read-token",
                                                  opener=tf.Opener(remote.before))
            aggregate = actuator.compact_aggregate_v2(CFG, *before, state)
            data = _bound(original)[0]
            baseline = actuator.gate_task_state_aggregate(
                CFG, aggregate, op, data["actor"], data["previous"], state,
                data["proof_sha256"], task_key=data["task_key"], body=data["body"],
                request=data["request"], **actuator._selection(data))
            remote.before["/issues/35/comments"].append(
                dict(row(601, 12, "holder input", 25), issue_url=tf.ROOT+"/issues/35"))
            remote.before["/issues/37/comments"].append(
                dict(signal(701, "p", ping, "GUARD", "BUILDER"), issue_url=tf.ROOT+"/issues/37"))
            got = []
            real_gate = actuator.gate_task_state_aggregate
            def gate(*args, **kwargs):
                result = real_gate(*args, **kwargs)
                got.append(result)
                return result
            with patch("v2_actuator.gate_task_state_aggregate", side_effect=gate):
                result = self.run_case(original, remote, cap)
            self.assertEqual(result["state"], "VERIFIED", result)
            self.assertEqual(len(got), 1)
            for key in ("aggregate_sha256", "aggregate_inventory_sha256"):
                self.assertNotEqual(got[0][key], baseline[key])
            for key in ("task_compact_sha256", "task_inventory_sha256", "proof_sha256"):
                self.assertEqual(got[0][key], baseline[key])
            self.assertEqual(len(remote.sent), 1)

    def test_final_witness_and_checkpoint_advance_fail_before_start(self):
        for op in OPS:
            original, remote = self.case(op)
            cap = self.cap(original)
            real_witness = actuator._witness
            seen = []
            def mismatch(*args):
                value = real_witness(*args)
                seen.append(value)
                return value if len(seen) == 1 else {"kind": "wrong"}
            with patch("v2_actuator._witness", side_effect=mismatch), \
                 patch.object(self.store, "start") as start:
                result = self.run_case(original, remote, cap)
                self.no_claim(original, remote, result)
                self.assertEqual(result["code"], "AGGREGATE_ADMISSION_FAILED")
                self.assertEqual(len(seen), 2)
                start.assert_not_called()
            saved = remote.runtime_state.load()
            real_gate = actuator.gate_task_state_aggregate
            def advance(*args, **kwargs):
                result = real_gate(*args, **kwargs)
                remote.runtime_state.save(saved["state"], saved["generation"])
                return result
            with patch("v2_actuator.gate_task_state_aggregate", side_effect=advance), \
                 patch.object(self.store, "start") as start:
                result = self.run_case(original, remote, cap)
                self.no_claim(original, remote, result)
                self.assertEqual(result["code"], "CHECKPOINT_FENCE_OR_INPUT_FAILED")
                start.assert_not_called()

    def assert_no_rearm(self, original, remote, cap):
        with patch("v2_actuator.acquire_aggregate_v2") as acquire, \
             patch("v2_actuator.gate_task_state_aggregate") as gate, \
             patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap, runtime_state=None)
            self.assertIn(result["state"], ("UNRESOLVED", "EFFECT_UNKNOWN"))
            acquire.assert_not_called()
            gate.assert_not_called()
            start.assert_not_called()
        self.assertFalse(remote.sent)

    def test_uncertain_started_no_send_and_reconciliation_only(self):
        for op in OPS:
            original, remote = self.case(op)
            cap = self.cap(original)
            real_start = self.store.start
            def uncertain(key):
                real_start(key)
                raise OSError("uncertain durable start")
            with patch.object(self.store, "start", side_effect=uncertain):
                result = self.run_case(original, remote, cap)
            self.assertEqual(result["state"], "EFFECT_UNKNOWN")
            self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
            self.assert_no_rearm(original, remote, cap)
            self.assert_no_rearm(original, remote, cap)

    def test_post_started_fence_exit_failure_no_send_or_rearm(self):
        real_fence = RuntimeStateStore.fence
        @contextmanager
        def fail_exit(store, *args):
            with real_fence(store, *args) as value:
                yield value
            raise Conflict("exit failure")
        for op in OPS:
            original, remote = self.case(op)
            cap = self.cap(original)
            with patch.object(RuntimeStateStore, "fence", fail_exit):
                result = self.run_case(original, remote, cap)
            self.assertEqual(result["state"], "EFFECT_UNKNOWN")
            self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
            self.assert_no_rearm(original, remote, cap)

    def test_response_loss_reconciles_without_checkpoint_or_resend(self):
        for op in OPS:
            original, remote = self.case(op)
            cap = self.cap(original)
            remote.error = True
            result = self.run_case(original, remote, cap)
            self.assertEqual(result["state"], "VERIFIED", result)
            self.assertEqual(self.run_case(original, remote, cap, runtime_state=None), result)
            self.assertEqual(len(remote.sent), 1)

    def test_crash_restart_reconciliation_never_resends(self):
        for op in OPS:
            original, remote = self.case(op)
            cap = self.cap(original)
            remote.crash = True
            with self.assertRaises(tf.Crash):
                self.run_case(original, remote, cap)
            self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
            remote.crash = False
            with patch("v2_actuator.acquire_aggregate_v2") as acquire:
                result = self.run_case(original, remote, cap, runtime_state=None)
                self.assertEqual(result["state"], "VERIFIED", result)
                acquire.assert_not_called()
            self.assertEqual(len(remote.sent), 1)


if __name__ == "__main__":
    unittest.main()
