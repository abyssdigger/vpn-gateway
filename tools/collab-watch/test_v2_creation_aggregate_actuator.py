"""8e-C: coherent creation admission under the retained STARTED fence."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import copy
import unittest
from unittest.mock import patch

from core import Conflict, canonical, digest
import test_v2_actuator as tf
import test_v2_aggregate_actuator as af
from test_split_journal import CFG, row
from test_v2_aux import aux, signal
from test_v2_create import resource
from v2_actuator import _bound, _ownership_fd
from v2_owner import OwnerBusy
from v2_runtime_state import RuntimeStateStore, open_state
import v2_actuator as actuator


class CreationAggregateActuatorTests(unittest.TestCase):
    setUp = af.AggregateActuatorTests.setUp
    cap = af.AggregateActuatorTests.cap
    run_case = af.AggregateActuatorTests.run_case
    no_claim = af.AggregateActuatorTests.no_claim
    new_checkpoint = af.AggregateActuatorTests.new_checkpoint

    def case(self, extra_control=()):
        return tf.ActuatorTests.creation_case(self, extra_control=extra_control)

    def test_exact_order_binding_owner_attempt_checkpoint_and_no_split(self):
        original, remote = self.case()
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
        expected = dict(action, witness={"kind": "not_applicable"})
        events, observed = [], []
        real_acquire = actuator.acquire_aggregate_v2_for_creation
        real_gate = actuator.gate_creation_aggregate
        real_task = actuator.acquire_v2
        real_inventory = actuator.acquire_creation
        real_start = self.store.start
        def authority(desc):
            events.append("authority")
            self.assertEqual(desc, expected)
            self.assertFalse(remote.read_calls)
            return True
        def acquire(*args, **kwargs):
            events.append("aggregate")
            self.assertFalse(remote.applied)
            self.assertEqual(len(remote.user_reads), 1)
            got = real_acquire(*args, **kwargs)
            observed.append(got)
            return got
        def gate(*args, **kwargs):
            events.append("gate")
            self.assertIs(args[1], observed[0])
            self.assertEqual(args[2:], (data["actor"], data["request"], data["previous"],
                                       saved["state"], data["proof_sha256"]))
            return real_gate(*args, **kwargs)
        def task(*args, **kwargs):
            self.assertTrue(remote.applied, "task-only pre-send read")
            return real_task(*args, **kwargs)
        def inventory(*args, **kwargs):
            self.assertTrue(remote.applied, "split pre-send inventory")
            self.assertFalse(kwargs.get("expect_absent", False))
            return real_inventory(*args, **kwargs)
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
        with patch("v2_actuator.acquire_aggregate_v2_for_creation", side_effect=acquire), \
             patch("v2_actuator.gate_creation_aggregate", side_effect=gate), \
             patch("v2_actuator.acquire_v2", side_effect=task), \
             patch("v2_actuator.acquire_creation", side_effect=inventory), \
             patch.object(self.store, "start", side_effect=start):
            result = self.run_case(original, remote, cap, authority)
        self.assertEqual(result["state"], "VERIFIED", result)
        self.assertEqual(events, ["authority", "aggregate", "gate", "start", "send"])
        claimed = self.store.claimed(effect)
        self.assertEqual(claimed["effect_descriptor"], effect)
        self.assertEqual(claimed["action_descriptor"], expected)
        self.assertEqual(self.retention.load(claimed["action_key"]), original)
        self.assertEqual(remote.sent[0][:2], ("POST", tf.ROOT+"/issues"))
        self.assertEqual(remote.sent[0][2], wire)
        self.assertNotIn("creation_inventory_sha256", canonical(claimed))
        with patch("v2_actuator.acquire_aggregate_v2_for_creation") as acquire, \
             patch("v2_actuator.gate_creation_aggregate") as gate:
            self.assertEqual(self.run_case(original, remote, cap, runtime_state=None), result)
            acquire.assert_not_called()
            gate.assert_not_called()
        self.assertEqual(len(remote.sent), 1)

    def test_checkpoint_scope_and_denials_before_final_acquisition(self):
        original, remote = self.case()
        cap = self.cap(original)
        state = remote.runtime_state.load()["state"]
        bad = copy.deepcopy(state)
        bad["task"]["ledger"] = {}
        for checkpoint in (None, object(), self.new_checkpoint(),
                           self.new_checkpoint(repository="other/project", state=state),
                           self.new_checkpoint(epoch="other", state=state),
                           self.new_checkpoint(state=bad)):
            with patch("v2_actuator.acquire_aggregate_v2_for_creation") as acquire, \
                 patch.object(self.store, "start") as start:
                result = self.run_case(original, remote, cap, runtime_state=checkpoint)
                self.no_claim(original, remote, result)
                self.assertEqual(result["code"], "CHECKPOINT_UNAVAILABLE_OR_STALE")
                acquire.assert_not_called()
                start.assert_not_called()
                self.assertFalse(remote.user_reads or remote.read_calls)
        for mode in ("actor", "authority"):
            remote.actor = 99 if mode == "actor" else 13
            with patch("v2_actuator.acquire_aggregate_v2_for_creation") as acquire, \
                 patch.object(self.store, "start") as start:
                result = self.run_case(original, remote, cap, lambda _: mode != "authority")
                self.no_claim(original, remote, result)
                self.assertEqual(result["code"], "WRITE_ACTOR_UNVERIFIED" if mode == "actor"
                                 else "AUTHORITY_DENIED")
                acquire.assert_not_called()
                start.assert_not_called()
                self.assertFalse(remote.read_calls)

    def test_matching_marker_pr_duplicate_and_task_drift_reject(self):
        original, remote = self.case()
        cap = self.cap(original)
        base = copy.deepcopy(remote.before)
        candidate = remote.response
        duplicate = resource({"title": candidate["title"], "body": candidate["body"]}, 44, 4004)
        for inventory in ([candidate], [dict(candidate, pull_request={})],
                          [candidate, duplicate]):
            remote.before = copy.deepcopy(base)
            remote.before["/issues"] = inventory
            with patch.object(self.store, "start") as start:
                result = self.run_case(original, remote, cap)
                self.no_claim(original, remote, result)
                self.assertEqual(result["code"], "AGGREGATE_ADMISSION_FAILED")
                start.assert_not_called()
        for room in (34, 42):
            remote.before = copy.deepcopy(base)
            remote.before[f"/issues/{room}/comments"].append(
                dict(row(950+room, 99, "ordinary drift", 30), issue_url=tf.ROOT+f"/issues/{room}"))
            result = self.run_case(original, remote, cap)
            self.no_claim(original, remote, result)
            self.assertEqual(result["code"], "AGGREGATE_ADMISSION_FAILED")

    def test_holder_signal_and_unrelated_inventory_bound(self):
        ping = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        original, remote = self.case([ping])
        cap = self.cap(original)
        state = remote.runtime_state.load()["state"]
        data = _bound(original)[0]
        baseline = actuator.acquire_aggregate_v2_for_creation(CFG, opener=tf.Opener(remote.before))
        real_gate = actuator.gate_creation_aggregate
        old = real_gate(CFG, baseline, data["actor"], data["request"], data["previous"],
                        state, data["proof_sha256"], **actuator._selection(data))
        remote.before["/issues/35/comments"].append(
            dict(row(601, 12, "holder input", 25), issue_url=tf.ROOT+"/issues/35"))
        remote.before["/issues/37/comments"].append(
            dict(signal(701, "p", ping, "GUARD", "BUILDER"), issue_url=tf.ROOT+"/issues/37"))
        remote.before["/issues"].append(resource({"title": "unrelated", "body": None}, 44, 4004))
        got = []
        def gate(*args, **kwargs):
            result = real_gate(*args, **kwargs)
            got.append(result)
            return result
        with patch("v2_actuator.gate_creation_aggregate", side_effect=gate):
            result = self.run_case(original, remote, cap)
        self.assertEqual(result["state"], "VERIFIED", result)
        self.assertEqual(len(got), 1)
        for key in ("aggregate_sha256", "aggregate_inventory_sha256", "creation_inventory_sha256"):
            self.assertNotEqual(got[0][key], old[key])
        for key in ("task_compact_sha256", "task_inventory_sha256", "proof_sha256", "effect_sha256"):
            self.assertEqual(got[0][key], old[key])

    def test_gate_binding_mismatch_and_checkpoint_advance(self):
        original, remote = self.case()
        cap = self.cap(original)
        real_gate = actuator.gate_creation_aggregate
        for key in ("aggregate_sha256", "aggregate_inventory_sha256", "task_compact_sha256",
                    "task_inventory_sha256", "creation_inventory_sha256", "proof_sha256",
                    "effect_sha256", "prior_composed_state_sha256"):
            def wrong(*args, **kwargs):
                return dict(real_gate(*args, **kwargs), **{key: "0"*64})
            with patch("v2_actuator.gate_creation_aggregate", side_effect=wrong), \
                 patch.object(self.store, "start") as start:
                result = self.run_case(original, remote, cap)
                self.no_claim(original, remote, result)
                self.assertEqual(result["code"], "AGGREGATE_ADMISSION_FAILED")
                start.assert_not_called()
        saved = remote.runtime_state.load()
        def advance(*args, **kwargs):
            result = real_gate(*args, **kwargs)
            remote.runtime_state.save(saved["state"], saved["generation"])
            return result
        with patch("v2_actuator.gate_creation_aggregate", side_effect=advance), \
             patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap)
            self.no_claim(original, remote, result)
            self.assertEqual(result["code"], "CHECKPOINT_FENCE_OR_INPUT_FAILED")
            start.assert_not_called()

    def assert_no_rearm(self, original, remote, cap):
        with patch("v2_actuator.acquire_aggregate_v2_for_creation") as acquire, \
             patch("v2_actuator.gate_creation_aggregate") as gate, \
             patch.object(self.store, "start") as start:
            result = self.run_case(original, remote, cap, runtime_state=None)
            self.assertIn(result["state"], ("UNRESOLVED", "EFFECT_UNKNOWN"))
            acquire.assert_not_called()
            gate.assert_not_called()
            start.assert_not_called()
        self.assertFalse(remote.sent)

    def test_uncertain_start_never_sends_or_rearms(self):
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
        self.assert_no_rearm(original, remote, cap)

    def test_fence_exit_after_start_never_sends_or_rearms(self):
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

    def test_response_loss_and_restart_reconciliation_without_checkpoint(self):
        original, remote = self.case()
        cap = self.cap(original)
        remote.error = True
        post = remote.after
        remote.after = remote.before
        result = self.run_case(original, remote, cap)
        self.assertEqual(result["state"], "UNRESOLVED")
        remote.after = post
        with patch("v2_actuator.acquire_aggregate_v2_for_creation") as acquire:
            result = self.run_case(original, remote, cap, runtime_state=None)
            self.assertEqual(result["state"], "VERIFIED", result)
            acquire.assert_not_called()
        self.assertEqual(result["locator"], {"issue_number": 43, "issue_id": 4003})
        self.assertEqual(len(remote.sent), 1)

    def test_crash_recovery_does_not_require_checkpoint(self):
        original, remote = self.case()
        cap = self.cap(original)
        remote.crash = True
        with self.assertRaises(tf.Crash):
            self.run_case(original, remote, cap)
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
        remote.crash = False
        with patch("v2_actuator.acquire_aggregate_v2_for_creation") as acquire:
            result = self.run_case(original, remote, cap, runtime_state=None)
            self.assertEqual(result["state"], "VERIFIED", result)
            acquire.assert_not_called()
        self.assertEqual(len(remote.sent), 1)


if __name__ == "__main__":
    unittest.main()
