"""9b-C-A durable spool evidence; no real writer invocation or remote I/O."""
import copy
from dataclasses import replace
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core import Conflict, canonical, strict_json
from test_split_journal import CFG, fixture
from test_project_tasks import row
from test_v2_trusted_writer import BINDINGS
import test_v2_actuator as tf
import test_v2_aux_actuator as af
from test_v2_aux import aux
from v2_aux import project_aux
from v2_compact import compact_aggregate_v2
from v2_trusted_writer import RESULT_CODES
from v2_writer_ipc import SessionBinding
import v2_writer_spool as sp

KEY = "a" * 64
RECEIPT = "b" * 64
MIB = 1024 * 1024
NO_CLAIM = dict(state="NO_ATTEMPT", code="NO_CLAIMED_EFFECT", action_key=None)
REJECTED = dict(state="NO_ATTEMPT", code="TRUSTED_INGRESS_REJECTED", action_key=None)
UNKNOWN = dict(state="EFFECT_UNKNOWN", code="TRUSTED_RESULT_INVALID", action_key=None)
VERIFIED = dict(state="VERIFIED", code="CANONICAL_RECEIPT_RECORDED", action_key=KEY,
                receipt_sha256=RECEIPT, locator={"room": 42, "comment_id": 5})
BUSY = dict(state="BUSY", code="OWNER_BUSY", action_key=None)
CONFLICT = dict(state="CONFLICT", code="EFFECT_CLAIM_CONFLICT", action_key=KEY)
PREPARED = dict(state="PREPARED", code="AUTHORITY_DENIED", action_key=KEY)


def quotas(records=100, **changes):
    return replace(sp.Quotas(records, 100*MIB, records*sp.META_RESERVE,
                            records*sp.RESULT_RESERVE, 200, 100, 100*MIB), **changes)


def trusted(q=None, role="BUILDER", **changes):
    cfg = copy.deepcopy(CFG)
    result = dict(cfg=cfg, bindings=copy.deepcopy(BINDINGS),
                  runtime_model="GPT-6.2" if role == "BUILDER" else "GPT-5.6 Sol",
                  session=SessionBinding(role, cfg["roles"][role]["incarnation"], 1, "session-one"),
                  spool_id="spool", attempt_store_id="attempt", input_store_id="input",
                  quotas=q if q is not None else quotas(),
                  resource_policy=sp.ResourcePolicy("policy-one", "c"*64))
    result.update(changes)
    return result


def request(original, mode=False):
    return dict(original=original, reconcile_only=mode)


def run_race(path, inode, args, barrier, output, operation, payload):
    """Fresh SQLite connections in separate processes, no inherited open DB."""
    try:
        store = sp.Spool.open(path, expected_inode=inode, **args)
        try:
            barrier.wait(10)
            if operation == "admit":
                value = store.admit(payload)
            else:
                value = store.mark_initial(*payload)["reconcile_only"]
            output.put(("OK", value))
        finally:
            store.close()
    except Conflict:
        output.put(("REJECTED", None))
    except Exception as exc:
        output.put(("TEST_ERROR", type(exc).__name__))


def uncommitted_result(path, rid):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA synchronous=FULL")
    db.execute("BEGIN IMMEDIATE")
    db.execute("UPDATE spool_records SET state='RESULT',version=version+1,uncertain=0,"
               "classification=?,result=? WHERE request_id=?",
               (sp.TV, canonical({"state": "RESULT", "result": VERIFIED}).encode(), rid))
    # Real abrupt process exit with no commit, rollback, or normal connection cleanup.
    os._exit(0)


class ClassifierTests(unittest.TestCase):
    def test_all_source_families_and_modes(self):
        values = []
        for state, codes in RESULT_CODES.items():
            for code in codes:
                if state == "VERIFIED":
                    result = VERIFIED
                else:
                    key = None if state in ("NO_ATTEMPT", "BUSY") or code == "FENCED_INVOCATION_UNCONFIRMED" else KEY
                    result = dict(state=state, code=code, action_key=key)
                values.append(result)
        values += [REJECTED, UNKNOWN]
        for value in values:
            state, code = value["state"], value["code"]
            for mode in (False, True):
                for execution in (sp.INITIAL, sp.FORCED):
                    reconcile = mode or execution == sp.FORCED
                    impossible = ((reconcile and (state == "PREPARED" or code in
                                   ("START_NOT_CONFIRMED", "START_OR_FENCE_EXIT_UNCONFIRMED")))
                                  or (not reconcile and code == "NO_CLAIMED_EFFECT"))
                    with self.subTest(state=state, code=code, mode=mode, execution=execution):
                        if impossible:
                            with self.assertRaises(sp.ProvenanceError):
                                sp.classify_result(value, "material_comment", mode, execution)
                            continue
                        if state == "VERIFIED":
                            expected = sp.TV
                        elif code == "NO_CLAIMED_EFFECT":
                            expected = sp.TN if mode else sp.NC
                        elif execution == sp.FORCED or state in ("EFFECT_UNKNOWN", "UNRESOLVED"):
                            expected = sp.RR
                        else:
                            expected = sp.RN
                        envelope, classification = sp.classify_result(value, "material_comment", mode, execution)
                        self.assertEqual(classification, expected)
                        self.assertEqual(strict_json(envelope.decode()), {"state": "RESULT", "result": value})
        # Signal is admitted only as an original reconcile-only operation.
        with self.assertRaises(Conflict):
            sp.classify_result(NO_CLAIM, "signal_comment", False, sp.FORCED)

    def test_impossible_keys_and_operation_bound_result(self):
        for code in RESULT_CODES["NO_ATTEMPT"]:
            value = dict(state="NO_ATTEMPT", code=code, action_key=KEY)
            with self.subTest(code=code), self.assertRaises(sp.ProvenanceError):
                sp.classify_result(value, "material_comment", True, sp.FORCED)
        for code in RESULT_CODES["EFFECT_UNKNOWN"]:
            value = dict(state="EFFECT_UNKNOWN", code=code,
                         action_key=KEY if code == "FENCED_INVOCATION_UNCONFIRMED" else None)
            with self.subTest(code=code), self.assertRaises(sp.ProvenanceError):
                sp.classify_result(value, "material_comment", False, sp.INITIAL)
        for value in (dict(UNKNOWN, action_key=KEY), dict(REJECTED, action_key=KEY),
                      dict(VERIFIED, extra="not admitted"), dict(VERIFIED, locator={"room": 42, "physical_ref": "issue:42#issuecomment-5"}),
                      dict(VERIFIED, locator={"room": True, "comment_id": 5})):
            with self.assertRaises(Conflict):
                sp.classify_result(value, "material_comment", False, sp.INITIAL)
        # Valid operation-specific locator accepted; cross-room ref rejected.
        control = dict(VERIFIED, locator={"room": 34, "physical_ref": "issue:34#issuecomment-5"})
        self.assertEqual(sp.classify_result(control, "control_comment", False, sp.INITIAL)[1], sp.TV)
        with self.assertRaises(Conflict):
            sp.classify_result(dict(control, locator={"room": 42, "physical_ref": "issue:34#issuecomment-5"}),
                               "control_comment", False, sp.INITIAL)
        # Bound includes the wrapper, not only the union body.
        body_size = len(canonical(VERIFIED).encode())
        with patch.object(sp, "RESULT_RESERVE", body_size):
            with self.assertRaises(Conflict):
                sp.classify_result(VERIFIED, "material_comment", False, sp.INITIAL)


class SpoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Pure accepted material proof fixture. Its synthetic checkpoint is
        # fixture construction only, outside the spool path.
        self.original, self.remote = tf.ActuatorTests.material_case(self)
        self.other, _ = tf.ActuatorTests.material_case(self, extra_row=True)
        self.assertNotEqual(self.original, self.other)
        self.size = len(self.original.encode())
        self.paths = 0

    def provision(self, q=None, **changes):
        self.paths += 1
        path = Path(self.tmp.name)/f"spool-{self.paths}.db"
        args = trusted(q, **changes)
        store = sp.Spool.provision(path, verified_empty_pair=True, **args)
        self.addCleanup(store.close)
        return store, path, args

    def reopen(self, store, path, args, **changes):
        opened = sp.Spool.open(path, expected_inode=store.inode, **dict(args, **changes))
        self.addCleanup(opened.close)
        return opened

    def test_explicit_pin_and_no_implicit_repair(self):
        path = Path(self.tmp.name)/"missing.db"
        args = trusted()
        with self.assertRaises(Conflict):
            sp.Spool.open(path, expected_inode=(0, 0), **args)
        self.assertFalse(path.exists())
        for value in (False, 1, None):
            with self.assertRaises(Conflict):
                sp.Spool.provision(path, verified_empty_pair=value, **args)
        self.assertFalse(path.exists())
        store, path, args = self.provision()
        inode = store.inode
        with self.assertRaises(Conflict):
            sp.Spool.provision(path, verified_empty_pair=True, **args)
        for changes in (dict(spool_id="other"), dict(attempt_store_id="different"),
                        dict(input_store_id="different"), dict(quotas=quotas(99)),
                        dict(cfg=dict(CFG, signal_room=38)),
                        dict(cfg=dict(CFG, repository=CFG["repository"].upper())),
                        dict(session=SessionBinding("GUARD", "g", 1, "bad-model"))):
            with self.subTest(changes=tuple(changes)), self.assertRaises(Conflict):
                sp.Spool.open(path, expected_inode=inode, **dict(args, **changes))
        with self.assertRaises(Conflict):
            sp.Spool.open(path, expected_inode=(inode[0], inode[1]+1), **args)
        with sqlite3.connect(path) as db:
            db.execute("UPDATE spool_meta SET version=999")
        with self.assertRaises(Conflict):
            store.status()
        with self.assertRaises(Conflict):
            sp.Spool.open(path, expected_inode=inode, **args)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute("SELECT version FROM spool_meta").fetchone(), (999,))
            db.execute("UPDATE spool_meta SET version=?", (sp.VERSION,))
            db.execute("CREATE TABLE unexpected(x)")
        with self.assertRaises(Conflict):
            store.status()

    def test_detect_replaced_file(self):
        store, path, args = self.provision()
        inode = store.inode
        old = path.with_suffix(".old")
        path.rename(old)
        path.write_bytes(old.read_bytes())
        path.chmod(0o600)
        with self.assertRaises(Conflict):
            store.status()
        with self.assertRaises(Conflict):
            sp.Spool.open(path, expected_inode=inode, **args)

    def test_pure_admission_before_ready(self):
        store, _, _ = self.provision()
        original = self.original
        data = strict_json(original)
        cases = [None, {}, request(original+" "), request('{"x":1,"x":2}'),
                 request(original, 1), dict(request(original), credential="never"),
                 request(canonical(dict(data, cfg=dict(data["cfg"], signal_room=38)))),
                 request(canonical(dict(data, role="GUARD"))),
                 request(canonical(dict(data, actor=True))),
                 request(canonical(dict(data, incarnation="wrong"))),
                 request(canonical(dict(data, operation="signal_comment"))),
                 request(canonical(dict(data, proof_sha256="d"*64)))]
        with patch("v2_trusted_writer.actuate_fenced") as delegate:
            for bad in cases:
                with self.assertRaises(Conflict):
                    store.admit(bad)
            delegate.assert_not_called()
        self.assertEqual(store.status()["records"], 0)
        self.assertFalse(self.remote.sent or self.remote.read_calls or self.remote.user_reads)
        with patch.object(sp, "MAX_INPUT_BYTES", 4), patch.object(sp, "strict_json") as decode:
            with self.assertRaises(Conflict):
                store.admit(request("ééé"))
            decode.assert_not_called()
        self.assertEqual(store.status()["records"], 0)

    def test_reservations_replay_modes_and_reopen(self):
        store, path, args = self.provision()
        normal = store.admit(request(self.original))
        read = store.admit(request(self.original, True))
        self.assertNotEqual(normal, read)
        self.assertEqual(store.admit(request(self.original)), normal)
        self.assertEqual(store.admit(request(self.original, True)), read)
        expected = dict(records=2, original_bytes=2*self.size, metadata_bytes=2*sp.META_RESERVE,
                        result_bytes=2*sp.RESULT_RESERVE, attempt_rows=2, input_rows=1,
                        input_bytes=self.size)
        self.assertEqual(store.status(), expected)
        changed = self.reopen(store, path, args,
                              session=SessionBinding("BUILDER", "b", 2, "new-session"))
        self.assertEqual(changed.admit(request(self.original)), normal)
        self.assertEqual(changed.load(normal)["first_generation"], 1)
        self.assertEqual(changed.load(normal)["first_session"], "session-one")
        self.assertEqual(changed.status(), expected)
        other_policy = self.reopen(store, path, args,
                                   resource_policy=sp.ResourcePolicy("policy-two", "d"*64))
        with self.assertRaises(Conflict):
            other_policy.admit(request(self.original))
        self.assertEqual(other_policy.status(), expected)
        self.assertNotEqual(changed.admit(request(self.other)), normal)
        self.assertEqual(changed.status()["attempt_rows"], 4)
        # Same request hash is not sufficient: compare actual retained bytes.
        with sqlite3.connect(path) as db:
            db.execute("UPDATE spool_records SET original=? WHERE request_id=?",
                       (b"x"*self.size, normal))
        with self.assertRaises(Conflict):
            changed.admit(request(self.original))

    def test_exact_quota_edges(self):
        exact = sp.Quotas(1, self.size, sp.META_RESERVE, sp.RESULT_RESERVE, 2, 1, self.size)
        store, _, _ = self.provision(exact)
        rid = store.admit(request(self.original))
        self.assertEqual(store.admit(request(self.original)), rid)
        self.assertEqual(tuple(store.status()[k] for k in sp.QUOTA_NAMES), exact.values())
        with self.assertRaises(Conflict):
            store.admit(request(self.original, True))
        for name, val in zip(sp.QUOTA_NAMES, exact.values()):
            with self.subTest(quota=name):
                short, _, _ = self.provision(replace(exact, **{name: val-1}))
                with self.assertRaises(Conflict):
                    short.admit(request(self.original))
                self.assertTrue(all(v == 0 for v in short.status().values()))
        # Read/reconciliation consumes spool resources but no new downstream rows.
        ro = replace(exact, attempt_rows=0, input_rows=0, input_bytes=0)
        store, _, _ = self.provision(ro)
        with self.assertRaises(Conflict):
            store.admit(request(self.original))
        rid = store.admit(request(self.original, True))
        self.assertEqual(store.admit(request(self.original, True)), rid)
        self.assertEqual(tuple(store.status()[k] for k in sp.QUOTA_NAMES), ro.values())

    def test_guarded_recovery_sticky_and_bounded_replacement(self):
        store, path, args = self.provision()
        rid = store.admit(request(self.original))
        before = store.status()
        self.assertEqual(store.mark_initial(rid, 1), request(self.original))
        self.assertEqual(store.load(rid)["state"], sp.MARKED)
        with self.assertRaises(Conflict):
            store.mark_initial(rid, 1)
        with self.assertRaises(Conflict):
            store.persist_result(rid, 2, sp.FORCED, VERIFIED)
        self.assertEqual(store.persist_result(rid, 2, sp.INITIAL, UNKNOWN), sp.RR)
        current = self.reopen(store, path, args)
        for value in (REJECTED, BUSY, CONFLICT, PREPARED,
                      dict(NO_CLAIM, action_key=KEY), dict(VERIFIED, locator={"room": 42}),
                      UNKNOWN):
            r = current.load(rid)
            self.assertEqual(current.mark_recovery(rid, r["version"]), request(self.original, True))
            marker = current.load(rid)
            self.assertEqual(marker["state"], sp.MARKED)
            self.assertEqual(marker["uncertain"], 1)
            self.assertIsNone(marker["result"])
            self.assertEqual(current.persist_result(rid, marker["version"], sp.FORCED, value), sp.RR)
            r = current.load(rid)
            self.assertEqual(r["uncertain"], 1)
            if value in (PREPARED, dict(NO_CLAIM, action_key=KEY)):
                self.assertEqual((r["state"], r["diagnostic"], r["result"]),
                                 (sp.MARKED, "PROVENANCE_INVALID", None))
            self.assertEqual(current.status(), before)
        r = current.load(rid)
        current.mark_recovery(rid, r["version"])
        self.assertEqual(current.persist_result(rid, r["version"]+1, sp.FORCED, NO_CLAIM), sp.NC)
        r = current.load(rid)
        self.assertEqual((r["state"], r["uncertain"], r["reconcile_only"]), (sp.RESULT, 0, 0))
        for mark in (current.mark_initial, current.mark_recovery):
            with self.assertRaises(Conflict):
                mark(rid, r["version"])
        self.assertEqual(current.status(), before)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM spool_records").fetchone(), (1,))

    def test_original_read_never_rearms_and_valid_receipts(self):
        store, path, args = self.provision()
        rid = store.admit(request(self.original, True))
        self.assertEqual(store.mark_initial(rid, 1), request(self.original, True))
        self.assertEqual(store.persist_result(rid, 2, sp.INITIAL, PREPARED), sp.RR)
        marker = store.load(rid)
        self.assertEqual(marker["diagnostic"], "PROVENANCE_INVALID")
        store.mark_recovery(rid, marker["version"])
        self.assertEqual(store.persist_result(rid, marker["version"]+1, sp.FORCED, NO_CLAIM), sp.TN)
        r = store.load(rid)
        self.assertEqual((r["reconcile_only"], r["uncertain"], r["classification"]), (1, 0, sp.TN))
        self.assertEqual(self.reopen(store, path, args).load(rid)["classification"], sp.TN)
        for mark in (store.mark_initial, store.mark_recovery):
            with self.assertRaises(Conflict):
                mark(rid, r["version"])
        self.assertEqual(store.status()["attempt_rows"], 0)
        rid = store.admit(request(self.other))
        store.mark_initial(rid, 1)
        self.assertEqual(store.persist_result(rid, 2, sp.INITIAL, VERIFIED), sp.TV)
        self.assertEqual(strict_json(store.load(rid)["result"].decode())["result"], VERIFIED)

    def test_no_claim_classification_metadata_cannot_cross_original_mode(self):
        for mode, forged in ((True, sp.NC), (False, sp.TN)):
            with self.subTest(mode=mode):
                store, path, _ = self.provision()
                rid = store.admit(request(self.original, mode))
                store.mark_initial(rid, 1)
                store.mark_recovery(rid, 2)
                self.assertEqual(store.persist_result(rid, 3, sp.FORCED, NO_CLAIM),
                                 sp.TN if mode else sp.NC)
                with sqlite3.connect(path) as db:
                    db.execute("UPDATE spool_records SET classification=? WHERE request_id=?",
                               (forged, rid))
                with self.assertRaises(Conflict):
                    store.status()

    def test_wrong_blob_storage_classes_fail_closed(self):
        for col, table in (("config", "spool_meta"), ("original", "spool_records"),
                           ("result", "spool_records")):
            with self.subTest(col=col):
                store, path, args = self.provision()
                inode = store.inode
                rid = store.admit(request(self.original))
                store.mark_initial(rid, 1)
                store.persist_result(rid, 2, sp.INITIAL, VERIFIED)
                with sqlite3.connect(path) as db:
                    db.execute(f"UPDATE {table} SET {col}=CAST({col} AS TEXT)")
                    self.assertEqual(db.execute(f"SELECT typeof({col}) FROM {table}").fetchone(),
                                     ("text",))
                with self.assertRaises(Conflict):
                    store.status()
                with self.assertRaises(Conflict):
                    sp.Spool.open(path, expected_inode=inode, **args)

    def test_initial_no_claim_and_forced_verified_resolution(self):
        store, _, _ = self.provision()
        rid = store.admit(request(self.original, True))
        store.mark_initial(rid, 1)
        self.assertEqual(store.persist_result(rid, 2, sp.INITIAL, NO_CLAIM), sp.TN)
        self.assertEqual(store.load(rid)["uncertain"], 0)
        rid = store.admit(request(self.original))
        store.mark_initial(rid, 1)
        self.assertEqual(store.persist_result(rid, 2, sp.INITIAL, NO_CLAIM), sp.RR)
        self.assertEqual(store.load(rid)["diagnostic"], "PROVENANCE_INVALID")
        store.mark_recovery(rid, 3)
        self.assertEqual(store.persist_result(rid, 4, sp.FORCED, VERIFIED), sp.TV)
        self.assertEqual(store.load(rid)["uncertain"], 0)
        with self.assertRaises(Conflict):
            store.mark_recovery(rid, 5)

    def test_version_exhaustion_and_partial_transaction(self):
        store, path, args = self.provision()
        rid = store.admit(request(self.original))
        store.mark_initial(rid, 1)
        ctx = multiprocessing.get_context("fork")
        child = ctx.Process(target=uncommitted_result, args=(path, rid))
        child.start()
        child.join(15)
        if child.is_alive():
            child.kill()
            child.join()
            self.fail("crash test timed out")
        self.assertEqual(child.exitcode, 0)
        opened = self.reopen(store, path, args)
        r = opened.load(rid)
        self.assertEqual((r["state"], r["version"], r["uncertain"], r["result"]),
                         (sp.MARKED, 2, 1, None))
        with sqlite3.connect(path) as db:
            db.execute("UPDATE spool_records SET version=? WHERE request_id=?", (sp.MAX_VERSION, rid))
        for invoke in (lambda: opened.mark_recovery(rid, sp.MAX_VERSION),
                       lambda: opened.persist_result(rid, sp.MAX_VERSION, sp.INITIAL, VERIFIED)):
            with self.assertRaises(Conflict):
                invoke()
        self.assertEqual(opened.load(rid)["state"], sp.MARKED)

    def race(self, store, path, args, operation, left, right):
        ctx = multiprocessing.get_context("fork")
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=run_race, args=(path, store.inode, args, barrier, queue, operation, x))
                     for x in (left, right)]
        try:
            for p in processes:
                p.start()
            results = [queue.get(timeout=20) for _ in processes]
            for p in processes:
                p.join(15)
                self.assertEqual(p.exitcode, 0)
            self.assertNotIn("TEST_ERROR", [x[0] for x in results])
            return results
        finally:
            for p in processes:
                if p.is_alive():
                    p.kill()
                    p.join()
            queue.close()
            queue.join_thread()

    def test_concurrent_admission_and_mark(self):
        store, path, args = self.provision(quotas(1))
        req = request(self.original)
        results = self.race(store, path, args, "admit", req, req)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], "OK")
        rid = results[0][1]
        self.assertEqual(store.status()["records"], 1)
        results = self.race(store, path, args, "mark", (rid, 1), (rid, 1))
        self.assertEqual(sorted(x[0] for x in results), ["OK", "REJECTED"])
        self.assertEqual(store.load(rid)["version"], 2)
        store, path, args = self.provision(quotas(1))
        results = self.race(store, path, args, "admit", req, request(self.other))
        self.assertEqual(sorted(x[0] for x in results), ["OK", "REJECTED"])
        self.assertEqual(store.status()["records"], 1)

    def test_pair_wide_budget_and_large_metadata_only_queries(self):
        # Two real large, independently pure-bound auxiliary originals, same
        # pair budget across role views. Use established proof primitives.
        store, path, args = self.provision(quotas(3))
        guard = self.reopen(store, path, trusted(quotas(3), role="GUARD"))
        sizes = []
        for flavor in ("x"*65536, "x"*65535+chr(0x1f642)):
            rows, task = fixture()
            holder = [row(1000+i, 12, f"{i:04d} "+flavor, 25) for i in range(20)]
            previous = project_aux(CFG, {"34": rows}, {"42": task}, holder, [])[1]
            baseline = compact_aggregate_v2(CFG, {"34": rows}, {"42": task}, holder, [], previous)
            candidate = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
            original = af.original_for("aux_comment", baseline, candidate, previous)
            size = len(original.encode())
            self.assertGreater(size, MIB)
            sizes.append(size)
            rid = guard.admit(request(original))
            self.assertEqual(guard.load(rid)["original_bytes"], size)
            if chr(0x1f642) in flavor:
                self.assertGreater(size, len(original))
                with sqlite3.connect(path) as db:
                    self.assertEqual(db.execute("SELECT typeof(original),length(original) "
                                                "FROM spool_records WHERE request_id=?", (rid,)).fetchone(),
                                     ("blob", size))
        store.admit(request(self.original, True))
        real = sp._connect
        queries = []
        def traced(*args):
            conn = real(*args)
            conn.set_trace_callback(queries.append)
            return conn
        with patch.object(sp.Spool, "_selected", side_effect=AssertionError("must not load BLOB")), \
             patch.object(sp, "_connect", side_effect=traced):
            totals = store.status()
            inventory = guard.list_metadata()
        self.assertEqual(totals["records"], 3)
        self.assertEqual(totals["original_bytes"], sum(sizes)+self.size)
        self.assertEqual(totals["attempt_rows"], 4)
        self.assertEqual(totals["input_bytes"], sum(sizes))
        self.assertEqual(len(inventory), 3)
        self.assertTrue(all("original" not in r and "result" not in r for r in inventory))
        self.assertTrue(any("sum(original_bytes)" in sql for sql in queries))
        self.assertFalse(any(sql.startswith("SELECT request_id,original,") for sql in queries))
        with self.assertRaises(Conflict):
            guard.admit(request(original, True))


if __name__ == "__main__":
    unittest.main()
