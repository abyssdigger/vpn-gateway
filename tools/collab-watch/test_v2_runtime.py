"""One-shot runtime using accepted synthetic remote acquisition and durable CAS."""
from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from core import Conflict
from test_split_journal import CFG, fixture
from test_project_tasks import row
from test_v2_aux import aux, signal
from test_v2_acquisition import Opener, ROOT
from test_v2_aux_actuator import graph
from test_v2_scheduler import bindings, G, B
from v2_acquisition import acquire_aggregate_v2
from v2_aux import project_aux
from v2_identity import IdentityConflict
from v2_runtime_state import initialize_state, open_state
from v2_scheduler import project_scheduler
from v2_runtime import run_once


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/"state.db"
        self.store = initialize_state(self.path, "runtime-state", CFG["repository"], CFG["journal_epoch"])
        self.addCleanup(self.store.close)
        self.rows, self.task = fixture()
        self.p = aux("p", "PING", 301, "GUARD", "BUILDER", ping_id="p")
        self.s = signal(501, "p", self.p, "GUARD", "BUILDER")
        self.holder = row(401, 12, "!COLLAB STOP cycle=test", 25)
        self.raw = ({"34": self.rows+[self.p]}, {"42": self.task}, [self.holder], [self.s])
        self.graph = graph(self.raw[0]["34"], self.task, [self.holder], [self.s])
        self.state = project_aux(CFG, *self.raw)[1]

    def reopen(self):
        store = open_state(self.path, "runtime-state", CFG["repository"], CFG["journal_epoch"])
        self.addCleanup(store.close)
        return store

    def run_case(self, mode, opener=None, store=None, cfg=CFG, model=B, role="BUILDER"):
        return run_once(cfg, bindings(), model, store or self.store, history_mode=mode,
                        selected_role=role, read_token="private-read-token",
                        read_opener=opener or Opener(self.graph))

    def test_retained_exact_pipeline(self):
        old = self.store.save(self.state, 0)
        opener = Opener(self.graph)
        sequence = []
        acquire = acquire_aggregate_v2
        schedule = project_scheduler
        def acquire_check(*a, **kw):
            sequence.append("acquire")
            return acquire(*a, **kw)
        def schedule_check(*a, **kw):
            sequence.append("project")
            self.assertEqual(a[2], old["state"])
            self.assertEqual(kw["selected_role"], "BUILDER")
            return schedule(*a, **kw)
        with patch("v2_runtime.acquire_aggregate_v2", side_effect=acquire_check) as acq, \
             patch("v2_runtime.project_scheduler", side_effect=schedule_check) as proj:
            result = self.run_case("retained", opener)
            acq.assert_called_once()
            proj.assert_called_once()
        self.assertEqual(sequence, ["acquire", "project"])
        expected_view, expected_state = project_scheduler(CFG, self.raw, self.state, bindings(), B,
                                                          selected_role="BUILDER")
        self.assertEqual(result["view"], expected_view)
        committed = self.store.load()
        self.assertEqual(committed["state"], expected_state)
        self.assertEqual(result["checkpoint"], {"generation": 2, "state_sha256": committed["state_sha256"]})
        self.assertEqual(result["history"], "retained")
        self.assertEqual(set(result), {"history", "view", "checkpoint"})
        self.assertNotIn("private-read-token", repr(result))
        self.assertEqual(opener.scan, 1)
        self.assertTrue(all(method == "GET" for _, method, _ in opener.calls))

    def test_fresh_and_mode_failures_before_acquisition(self):
        opener = Opener(self.graph)
        for mode in ("retained", None, "auto"):
            with self.assertRaises(Conflict):
                self.run_case(mode, opener)
        self.assertEqual(opener.calls, [])
        result = self.run_case("fresh-current", opener)
        self.assertEqual(result["history"], "fresh-current-only")
        self.assertEqual(result["checkpoint"]["generation"], 1)
        self.assertEqual(self.store.load()["state"], self.state)
        again = Opener(self.graph)
        with self.assertRaises(Conflict):
            self.run_case("fresh-current", again)
        self.assertEqual(again.calls, [])

    def test_unstable_acquisition_preserves_checkpoint(self):
        old = self.store.save(self.state, 0)
        changed = copy.deepcopy(self.graph)
        changed["/issues/37/comments"] = []
        with patch("v2_runtime.project_scheduler") as scheduler:
            with self.assertRaises(Conflict):
                self.run_case("retained", Opener(self.graph, changed))
            scheduler.assert_not_called()
        self.assertEqual(self.store.load(), old)

    def test_identity_and_semantic_conflict_preserve_checkpoint(self):
        old = self.store.save(self.state, 0)
        with self.assertRaises(IdentityConflict):
            self.run_case("retained", model=G, role=None)
        self.assertEqual(self.store.load(), old)
        missing = graph(self.rows, self.task, [self.holder], [])
        with self.assertRaises(Conflict):
            self.run_case("retained", Opener(missing))
        self.assertEqual(self.store.load(), old)

    def test_signal_rotation_and_holder_command_data(self):
        first = self.run_case("fresh-current", model=B)
        self.assertEqual(len(first["view"]["signal_diagnostics"]["incoming"]), 1)
        old = self.store.load()
        rotated = dict(CFG, signal_room=38)
        snapshot = copy.deepcopy(self.graph)
        del snapshot["/issues/37/comments"]
        snapshot["/issues/38/comments"] = []
        opener = Opener(snapshot)
        second = self.run_case("retained", opener, cfg=rotated)
        self.assertEqual(second["view"]["work"], first["view"]["work"])
        self.assertFalse(second["view"]["signal_diagnostics"]["incoming"])
        self.assertEqual(self.store.load()["state"], old["state"])
        fact = second["view"]["work"]["holder_inputs"]["issue:35#issuecomment-401"]
        self.assertEqual(fact["event"]["command"]["id"], "STOP")
        self.assertTrue(all(method == "GET" for _, method, _ in opener.calls))

    def test_concurrent_runtime_cas_loser_no_view(self):
        self.store.save(self.state, 0)
        stores = [self.reopen(), self.reopen()]
        barrier = threading.Barrier(2)
        def synchronized(*a, **kw):
            result = project_scheduler(*a, **kw)
            barrier.wait(timeout=5)
            return result
        def run(store):
            try:
                return self.run_case("retained", store=store)
            except Conflict:
                return None
        with patch("v2_runtime.project_scheduler", side_effect=synchronized):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(run, stores))
        self.assertEqual(sum(x is not None for x in results), 1)
        self.assertEqual(self.store.load()["generation"], 2)

    def test_checkpoint_changes_between_load_and_save(self):
        self.store.save(self.state, 0)
        other = self.reopen()
        def raced(*a, **kw):
            projected = project_scheduler(*a, **kw)
            other.save(self.state, 1)
            return projected
        with patch("v2_runtime.project_scheduler", side_effect=raced):
            with self.assertRaises(Conflict):
                self.run_case("retained")
        self.assertEqual(self.store.load()["generation"], 2)

    def test_scope_mismatch_no_remote_or_reset(self):
        wrong = initialize_state(Path(self.tmp.name)/"other.db", "other",
                                 CFG["repository"], "other-epoch")
        self.addCleanup(wrong.close)
        opener = Opener(self.graph)
        with self.assertRaises(Conflict):
            self.run_case("fresh-current", opener, store=wrong)
        self.assertFalse(opener.calls)
        self.assertIsNone(wrong.load())

    def test_save_exception_no_success_result(self):
        old = self.store.save(self.state, 0)
        with patch("v2_runtime_state.RuntimeStateStore.save", side_effect=Conflict("uncertain save")):
            with self.assertRaises(Conflict):
                self.run_case("retained")
        self.assertEqual(self.store.load(), old)
