"""Durable checkpoint shape, identity, CAS and tamper tests."""
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from core import Conflict, canonical
from test_split_journal import CFG, fixture
from test_v2_aux import aux, signal
from test_project_tasks import row
from v2_aux import project_aux
from v2_runtime_state import MAX_GENERATION, initialize_state, open_state

SID = "state-test"
REPO, EPOCH = CFG["repository"], CFG["journal_epoch"]


class RuntimeStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/"checkpoint.db"
        self.store = initialize_state(self.path, SID, REPO.upper(), EPOCH)
        self.addCleanup(self.store.close)
        rows, task = fixture()
        ping = aux("p", "PING", 301, "GUARD", "BUILDER", ping_id="p")
        holder = row(401, 12, "private holder prose", 25)
        delivery = signal(501, "p", ping, "GUARD", "BUILDER")
        self.state = project_aux(CFG, {"34": rows+[ping]}, {"42": task}, [holder], [delivery])[1]

    def reopen(self):
        store = open_state(self.path, SID, REPO, EPOCH)
        self.addCleanup(store.close)
        return store

    def test_explicit_provision_empty_and_exact_identity(self):
        self.assertIsNone(self.store.load())
        self.assertIsNone(self.reopen().load())
        for args in (("wrong", REPO, EPOCH), (SID, "other/project", EPOCH), (SID, REPO, "other")):
            with self.assertRaises(Conflict):
                open_state(self.path, *args)
        with self.assertRaises(Conflict):
            initialize_state(self.path, SID, REPO, EPOCH)
        missing = self.path.with_suffix(".missing")
        with self.assertRaises(Conflict):
            open_state(missing, SID, REPO, EPOCH)
        self.assertFalse(missing.exists())

    def test_physical_hardening(self):
        os.chmod(self.path, 0o644)
        with self.assertRaises(Conflict):
            self.store.load()
        os.chmod(self.path, 0o600)
        alias = self.path.with_suffix(".link")
        alias.symlink_to(self.path)
        with self.assertRaises(Conflict):
            open_state(alias, SID, REPO, EPOCH)
        alias.unlink()
        os.link(self.path, alias)
        with self.assertRaises(Conflict):
            self.store.load()
        alias.unlink()
        self.assertIsNone(self.store.load())

    def test_exact_round_trip_and_detachment(self):
        frozen = copy.deepcopy(self.state)
        blob = canonical(frozen).encode()
        saved = self.store.save(self.state, 0)
        self.assertEqual(saved, {"generation": 1, "state_sha256": hashlib.sha256(blob).hexdigest(),
                                 "state": frozen})
        self.state["task"]["ledger"].clear()
        saved["state"]["aux"]["ledger"].clear()
        loaded = self.reopen().load()
        self.assertEqual(loaded["state"], frozen)
        loaded["state"].clear()
        self.assertEqual(self.store.load()["state"], frozen)
        with sqlite3.connect(self.path) as conn:
            actual, = conn.execute("SELECT state FROM checkpoint").fetchone()
        self.assertEqual(actual, blob)
        self.assertNotIn(b"private holder prose", actual)
        self.assertEqual(set(frozen), {"task", "aux"})
        self.assertEqual(set(frozen["task"]), {"protocol", "semantic_config_hash", "ledger"})

    def test_generation_cas_and_identical_save(self):
        with self.assertRaises(Conflict):
            self.store.save(self.state, 1)
        first = self.store.save(self.state, 0)
        for wrong in (0, 2, True, -1):
            with self.assertRaises(Conflict):
                self.store.save(self.state, wrong)
        second = self.store.save(self.state, 1)
        self.assertEqual(second["generation"], 2)
        self.assertEqual(first["state_sha256"], second["state_sha256"])
        self.assertEqual(second["state"], first["state"])

    def test_concurrent_cas(self):
        self.store.save(self.state, 0)
        stores = [self.reopen(), self.reopen()]
        barrier = threading.Barrier(2)
        def run(store):
            barrier.wait(timeout=3)
            try:
                return store.save(self.state, 1)
            except Conflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, stores))
        self.assertEqual(sum(x is not None for x in results), 1)
        self.assertEqual(self.store.load()["generation"], 2)

    def test_bad_state_shapes_fail_without_mutation(self):
        for bad in ({}, dict(self.state, work={}), dict(self.state, task={}),
                    dict(self.state, aux=dict(self.state["aux"], ledger={"x": "prose"})),
                    dict(self.state, aux=dict(self.state["aux"], protocol="other")),
                    dict(self.state, aux=dict(self.state["aux"], semantic_config_hash="a"*64)),
                    dict(self.state, task=dict(self.state["task"], clock=0))):
            with self.assertRaises(Conflict):
                self.store.save(bad, 0)
            self.assertIsNone(self.store.load())

    def test_bytes_digest_schema_tamper(self):
        self.store.save(self.state, 0)
        blob = canonical(self.state).encode()
        variants = [(blob, "0"*64), (blob+b"\n", hashlib.sha256(blob+b"\n").hexdigest()),
                    (b"{}", hashlib.sha256(b"{}").hexdigest()),
                    (b"\xff", hashlib.sha256(b"\xff").hexdigest())]
        for data, sha in variants:
            with sqlite3.connect(self.path) as conn:
                conn.execute("UPDATE checkpoint SET state=?,state_sha256=?", (data, sha))
            with self.assertRaises(Conflict):
                self.store.load()
            with self.assertRaises(Conflict):
                self.store.save(self.state, 1)
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE checkpoint SET state=?,state_sha256=?",
                         (blob, hashlib.sha256(blob).hexdigest()))
            conn.execute("CREATE TABLE unexpected (x)")
        with self.assertRaises(Conflict):
            self.store.load()

    def test_overflow_fails(self):
        self.store.save(self.state, 0)
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE checkpoint SET generation=?", (MAX_GENERATION,))
        old = self.store.load()
        with self.assertRaises(Conflict):
            self.store.save(self.state, MAX_GENERATION)
        self.assertEqual(self.store.load(), old)

    def test_live_path_replacement(self):
        self.store.save(self.state, 0)
        self.path.rename(self.path.with_suffix(".old"))
        new = initialize_state(self.path, SID, REPO, EPOCH)
        self.addCleanup(new.close)
        with self.assertRaises(Conflict):
            self.store.load()
        with self.assertRaises(Conflict):
            self.store.save(self.state, 1)
        self.assertIsNone(new.load())
