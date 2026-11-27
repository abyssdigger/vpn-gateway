import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from unittest.mock import patch

from core import Conflict, canonical
from v2_inputs import initialize_inputs, open_inputs

KEY = "a"*64
OTHER = "b"*64
ORIGINAL = canonical({"material":"private retained prose"})
DIFFERENT = canonical({"material":"different private prose"})


class InputStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/"inputs.db"
        self.store = initialize_inputs(self.path, "provider", "attempt")

    def mutate(self, statement, args=()):
        with sqlite3.connect(self.path) as conn:
            conn.execute(statement, args)

    def test_explicit_provision_and_existing_only(self):
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.store.save(KEY, ORIGINAL)
        with self.assertRaises(Conflict):
            initialize_inputs(self.path, "provider", "attempt")
        self.assertEqual(open_inputs(self.path, "provider", "attempt").load(KEY), ORIGINAL)
        missing = self.path.parent/"missing.db"
        with self.assertRaises(Conflict):
            open_inputs(missing, "provider", "attempt")
        self.assertFalse(missing.exists())

    def test_identity_pair_version_schema_and_permissions(self):
        for provider, pair in (("wrong","attempt"), ("provider","wrong")):
            with self.assertRaises(Conflict):
                open_inputs(self.path, provider, pair)
        with self.assertRaises(Conflict):
            self.store.validate_pair("different")
        os.chmod(self.path, 0o644)
        with self.assertRaises(Conflict):
            self.store.load(KEY)
        os.chmod(self.path, 0o600)
        self.mutate("UPDATE input_meta SET version=99")
        with self.assertRaises(Conflict):
            self.store.validate_pair("attempt")
        self.mutate("UPDATE input_meta SET version=1")
        self.mutate("CREATE TABLE unexpected (x TEXT)")
        with self.assertRaises(Conflict):
            self.store.validate_pair("attempt")

    def test_immutable_insert_repeat_and_conflict(self):
        self.store.save(KEY, ORIGINAL)
        self.store.save(KEY, ORIGINAL)
        with self.assertRaises(Conflict) as exc:
            self.store.save(KEY, DIFFERENT)
        self.assertNotIn("private", str(exc.exception))
        self.assertEqual(self.store.load(KEY), ORIGINAL)
        with self.assertRaises(Conflict):
            self.store.load(OTHER)

    def test_concurrent_identical_and_different_saves(self):
        def concurrent(key, values):
            barrier = Barrier(2, timeout=5)
            def save(value):
                provider = open_inputs(self.path, "provider", "attempt")
                barrier.wait()
                try:
                    provider.save(key, value)
                    return True
                except Conflict:
                    return False
            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(save, values))
        self.assertEqual(concurrent(KEY, [ORIGINAL, ORIGINAL]), [True, True])
        self.assertEqual(sorted(concurrent(OTHER, [ORIGINAL, DIFFERENT])), [False, True])
        self.assertIn(self.store.load(OTHER), (ORIGINAL, DIFFERENT))

    def test_invalid_original_and_key(self):
        for value in ('{"private":1, "x":2}', '{"secret":1,"secret":2}',
                      '{"x":NaN}', '{"x":1,"private":2}', '["private"]',
                      b'{"private":1}'):
            with self.subTest(value=type(value).__name__), self.assertRaises(Conflict) as exc:
                self.store.save(KEY, value)
            self.assertNotIn("private", str(exc.exception))
            self.assertNotIn("secret", str(exc.exception))
        with self.assertRaises(Conflict):
            self.store.save("bad", ORIGINAL)

    def test_stored_digest_canonical_and_key_tamper(self):
        self.store.save(KEY, ORIGINAL)
        self.mutate("UPDATE originals SET original_sha256=? WHERE action_key=?", (OTHER, KEY))
        with self.assertRaises(Conflict):
            self.store.load(KEY)
        raw = b'{"x": 1}'
        self.mutate("UPDATE originals SET original=?,original_sha256=? WHERE action_key=?",
                    (raw, hashlib.sha256(raw).hexdigest(), KEY))
        with self.assertRaises(Conflict):
            self.store.load(KEY)
        self.mutate("UPDATE originals SET action_key='bad' WHERE action_key=?", (KEY,))
        with self.assertRaises(Conflict):
            self.store.validate_pair("attempt")

    def test_row_count_row_bytes_total_bounds(self):
        with patch("v2_inputs.MAX_INPUT_BYTES", 8):
            with self.assertRaises(Conflict):
                self.store.save(KEY, ORIGINAL)
        self.store.save(KEY, ORIGINAL)
        with patch("v2_inputs.MAX_INPUT_BYTES", 8):
            with self.assertRaises(Conflict):
                self.store.load(KEY)
        with patch("v2_inputs.MAX_ROWS", 1):
            with self.assertRaises(Conflict):
                self.store.save(OTHER, DIFFERENT)
            self.store.save(KEY, ORIGINAL)
        with patch("v2_inputs.MAX_TOTAL_BYTES", len(ORIGINAL.encode())+1):
            with self.assertRaises(Conflict):
                self.store.save(OTHER, DIFFERENT)
        with patch("v2_inputs.MAX_TOTAL_BYTES", 1):
            with self.assertRaises(Conflict):
                self.store.load(KEY)

    def test_deleted_replaced_and_symlink_rejected(self):
        self.store.save(KEY, ORIGINAL)
        self.path.unlink()
        with self.assertRaises(Conflict):
            self.store.load(KEY)
        self.assertFalse(self.path.exists())
        initialize_inputs(self.path, "replacement", "attempt")
        with self.assertRaises(Conflict):
            self.store.load(KEY)
        alias = self.path.parent/"alias.db"
        alias.symlink_to(self.path)
        with self.assertRaises(Conflict):
            open_inputs(alias, "replacement", "attempt")
