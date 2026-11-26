from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
import sqlite3
import tempfile
from threading import Barrier
import unittest

from core import Conflict, canonical, digest
from v2_attempts import initialize, open_store, MAX_DESCRIPTOR_BYTES

ACTION = {"operation": "test", "proof_sha256": "a"*64, "target": {"id": 42}}
EFFECT = {"operation": "test", "id": 42}
RECEIPT = "b"*64


class AttemptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "attempts.db"
        self.store = initialize(self.path, "store-1")

    def reopen(self):
        return open_store(self.path, "store-1")

    def prepared(self, action=ACTION, effect=EFFECT):
        return self.store.prepare(action, effect)["action_key"]

    def test_initialization_and_identity(self):
        self.assertIsNone(self.reopen().status("0"*64))
        for path, sid in ((self.path, "store-2"), (self.path.parent/"missing.db", "store-1"),
                          (":memory:", "store-1")):
            with self.assertRaises(Conflict):
                open_store(path, sid)
        self.assertFalse((self.path.parent/"missing.db").exists())
        with self.assertRaises(Conflict):
            initialize(self.path, "store-1")
        empty = self.path.parent/"empty.db"
        empty.touch()
        with self.assertRaises(Conflict):
            open_store(empty, "store-1")
        self.assertEqual(empty.stat().st_size, 0)
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE store_meta SET version=99")
        with self.assertRaises(Conflict):
            self.store.prepare(ACTION, EFFECT)

    def test_distinct_and_idempotent_prepare(self):
        key = self.prepared()
        row = self.reopen().prepare(dict(reversed(list(ACTION.items()))), EFFECT)
        self.assertEqual(row["action_key"], digest(canonical(ACTION)))
        self.assertEqual(row["effect_key"], digest(canonical(EFFECT)))
        self.assertEqual(row["state"], "PREPARED")
        self.assertEqual(row, self.store.status(key))
        with self.assertRaises(Conflict):
            self.store.prepare(ACTION, dict(EFFECT, id=43))
        other = self.prepared(dict(ACTION, target={"id": 43}), dict(EFFECT, id=43))
        self.assertNotEqual(key, other)
        self.store.start(key)
        self.reopen().start(other)
        self.assertEqual(self.reopen().prepare(ACTION, EFFECT)["state"], "STARTED")

    def test_lifecycle_restart_and_invalid_transitions(self):
        key = self.prepared()
        for action in (lambda: self.store.mark_unresolved(key, "ambiguous"),
                       lambda: self.store.mark_verified(key, RECEIPT)):
            with self.assertRaises(Conflict):
                action()
        self.assertEqual(self.reopen().start(key)["state"], "STARTED")
        with self.assertRaises(Conflict):
            self.reopen().start(key)
        self.assertEqual(self.reopen().mark_unresolved(key, "transport_unknown")["state"], "UNRESOLVED")
        self.assertEqual(self.reopen().status(key)["diagnostic_code"], "transport_unknown")
        for action in (lambda: self.reopen().start(key),
                       lambda: self.reopen().mark_unresolved(key, "another")):
            with self.assertRaises(Conflict):
                action()
        locator = {"issue_number": 42, "comment_id": 123}
        verified = self.reopen().mark_verified(key, RECEIPT, locator)
        self.assertEqual(verified["state"], "VERIFIED")
        self.assertEqual(verified["receipt_sha256"], RECEIPT)
        self.assertEqual(verified["locator"], locator)
        self.assertEqual(self.reopen().status(key), verified)
        for action in (lambda: self.reopen().start(key),
                       lambda: self.reopen().mark_unresolved(key, "again"),
                       lambda: self.reopen().mark_verified(key, RECEIPT, locator)):
            with self.assertRaises(Conflict):
                action()
        self.assertEqual(self.reopen().prepare(ACTION, EFFECT), verified)
        other = self.prepared(dict(ACTION, target={"id": 43}), dict(EFFECT, id=43))
        self.reopen().start(other)
        self.assertEqual(self.reopen().mark_verified(other, RECEIPT)["state"], "VERIFIED")

    def race(self, keys):
        gate = Barrier(2)
        def claim(key):
            s = self.reopen()
            gate.wait(timeout=5)
            try:
                return s.start(key)["action_key"]
            except Conflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(claim, keys))

    def test_same_action_concurrent_start(self):
        key = self.prepared()
        self.assertEqual(self.race([key, key]).count(key), 1)
        self.assertEqual(self.reopen().status(key)["state"], "STARTED")

    def test_same_effect_distinct_actions_concurrent_start(self):
        first = self.prepared()
        second = self.prepared(dict(ACTION, proof_sha256="c"*64))
        self.assertNotEqual(first, second)
        self.assertEqual(self.reopen().status(second)["state"], "PREPARED")
        winners = [k for k in self.race([first, second]) if k is not None]
        self.assertEqual(len(winners), 1)
        winner = winners[0]
        loser = second if winner == first else first
        for state in ("STARTED", "UNRESOLVED", "VERIFIED"):
            self.assertEqual(self.reopen().status(winner)["state"], state)
            self.assertEqual(self.reopen().status(loser)["state"], "PREPARED")
            with self.assertRaises(Conflict):
                self.reopen().start(loser)
            if state == "STARTED":
                self.reopen().mark_unresolved(winner, "unknown")
            elif state == "UNRESOLVED":
                self.reopen().mark_verified(winner, RECEIPT)
        fresh = self.prepared(dict(ACTION, proof_sha256="d"*64))
        with self.assertRaises(Conflict):
            self.reopen().start(fresh)

    def test_invalid_metadata_and_bounds(self):
        for bad in (None, {}, ["a"], {"id": 1.2}, {"id": (1,)}, {"id": 2**64},
                    {"token": "test"}, {"nested": {"password": "test"}},
                    {"body": "prose"}, {"name": "two words"}, {"name": "x"*513},
                    {"a": ["x"*500]*20}, {"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}}):
            with self.subTest(type=type(bad).__name__), self.assertRaises(Conflict):
                self.store.prepare(bad, EFFECT)
            with self.assertRaises(Conflict):
                self.store.prepare(ACTION, bad)
        key = self.prepared()
        self.store.start(key)
        for code in ("a"*129, "bad diagnostic\nsecret"):
            with self.assertRaises(Conflict):
                self.store.mark_unresolved(key, code)
        for receipt, locator in (("wrong", None), (RECEIPT, {"token": "test"}),
                                 (RECEIPT, {"id": ["x"*500]*5})):
            with self.assertRaises(Conflict):
                self.store.mark_verified(key, receipt, locator)
        self.assertEqual(self.reopen().status(key)["state"], "STARTED")
        self.assertEqual(self.reopen().mark_verified(key, RECEIPT, {"id": 1})["state"], "VERIFIED")

    def test_tampered_rows_fail_closed_even_for_other_actions(self):
        key = self.prepared()
        self.store.start(key)
        self.store.mark_verified(key, RECEIPT, {"id": 1})
        mutations = (
            ("action_descriptor", canonical(dict(ACTION, operation="changed"))),
            ("effect_descriptor", canonical(dict(EFFECT, id=43))),
            ("action_key", "0"*64), ("effect_key", "0"*64),
            ("state", "UNKNOWN"), ("state", "PREPARED"), ("receipt_sha256", "bad"),
            ("locator", '{"token":"test"}'), ("locator", '{"id": 1}'),
            ("diagnostic_code", "bad code"),
        )
        for column, value in mutations:
            with self.subTest(column=column), sqlite3.connect(self.path) as conn:
                original = conn.execute("SELECT "+column+" FROM attempts").fetchone()[0]
                conn.execute("UPDATE attempts SET "+column+"=?", (value,))
                conn.commit()
                with self.assertRaises(Conflict):
                    self.reopen()
                with self.assertRaises(Conflict):
                    self.store.prepare(dict(ACTION, target={"id": 99}), dict(EFFECT, id=99))
                conn.execute("UPDATE attempts SET "+column+"=?", (original,))
                conn.commit()
        self.assertEqual(self.reopen().status(key)["state"], "VERIFIED")

    def test_schema_and_missing_store_fail_closed(self):
        key = self.prepared()
        self.store.start(key)
        with sqlite3.connect(self.path) as conn:
            conn.execute("DROP INDEX effect_started_once")
        with self.assertRaises(Conflict):
            self.reopen()
        with self.assertRaises(Conflict):
            self.store.start(key)
        self.path.unlink()
        with self.assertRaises(Conflict):
            self.store.prepare(ACTION, EFFECT)
        self.assertFalse(self.path.exists())
        initialize(self.path, "new-store")
        with self.assertRaises(Conflict):
            self.reopen()


if __name__ == "__main__":
    unittest.main()
