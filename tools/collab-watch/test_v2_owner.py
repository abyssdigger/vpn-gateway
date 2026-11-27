"""Adversarial local owner-store and flock tests."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from core import Conflict
from v2_owner import (Capability, MAX_GENERATION, OwnerBusy, initialize_owner,
                      open_owner)

REPO, EPOCH, SID = "example/project", "epoch-1", "owner-1"
ROLE, INC = "BUILDER", "builder-1"


def yes(_):
    return True


class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"owner.sqlite"
        self.store = initialize_owner(self.path, SID, "Example/Project", EPOCH)
        self.addCleanup(self.store.close)

    def reopen(self):
        store = open_owner(self.path, SID, REPO, EPOCH)
        self.addCleanup(store.close)
        return store

    def claim(self):
        return self.store.claim(ROLE, INC, yes)

    def test_provision_and_open(self):
        self.assertEqual(self.store.status(), {})
        self.assertEqual(self.reopen().status(), {})
        for args in (("wrong", REPO, EPOCH), (SID, "other/project", EPOCH),
                     (SID, REPO, "other")):
            with self.assertRaises(Conflict):
                open_owner(self.path, *args)
        with self.assertRaises(Conflict):
            initialize_owner(self.path, SID, REPO, EPOCH)
        missing = self.path.with_suffix(".missing")
        with self.assertRaises(Conflict):
            open_owner(missing, SID, REPO, EPOCH)
        self.assertFalse(missing.exists())

    def test_file_permissions_symlink_and_hardlink(self):
        os.chmod(self.path, 0o644)
        with self.assertRaises(Conflict):
            self.store.status()
        with self.assertRaises(Conflict):
            self.reopen()
        os.chmod(self.path, 0o600)
        link = self.path.with_suffix(".link")
        link.symlink_to(self.path)
        with self.assertRaises(Conflict):
            open_owner(link, SID, REPO, EPOCH)
        link.unlink()
        os.link(self.path, link)
        with self.assertRaises(Conflict):
            self.store.status()
        link.unlink()
        self.assertEqual(self.store.status(), {})

    def test_authority_denial_error_and_mutation(self):
        def error(_):
            raise RuntimeError("private diagnostic")
        def mutate(d):
            d["next_generation"] = True
            return True
        for authorize in (lambda _: False, lambda _: 1, error, mutate):
            with self.assertRaises(Conflict) as ex:
                self.store.claim(ROLE, INC, authorize)
            self.assertNotIn("private diagnostic", str(ex.exception))
            self.assertEqual(self.store.status(), {})
        seen = []
        cap = self.store.claim(ROLE, INC, lambda d: seen.append(dict(d)) or True)
        self.assertEqual(seen, [dict(operation="initial_owner_claim", store_id=SID,
            repository=REPO, journal_epoch=EPOCH, transport_role=ROLE,
            incarnation=INC, previous_generation=0, next_generation=1)])
        self.assertEqual(cap.generation, 1)
        self.assertNotIn(cap.token, repr(cap))
        self.assertNotIn(cap.token, repr(seen))
        self.assertNotIn(cap.token, repr(self.store.status()))
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT * FROM owners").fetchone()
        self.assertEqual(row, (ROLE, INC, 1, hashlib.sha256(cap.token.encode()).hexdigest()))
        self.assertNotIn(cap.token.encode(), self.path.read_bytes())
        self.assertNotIn(row[3], repr(self.store.status()))

    def test_capability_exact_and_constant_time(self):
        cap = self.claim()
        with patch("v2_owner.hmac.compare_digest", wraps=__import__("hmac").compare_digest) as cmp:
            with self.reopen().fence(cap):
                pass
            self.assertEqual(cmp.call_count, 1)
        for invalid in (replace(cap, token="0"*64), replace(cap, generation=True),
                        replace(cap, generation=2), replace(cap, transport_role="GUARD"),
                        replace(cap, incarnation="other"), replace(cap, store_id="other"),
                        replace(cap, repository="other/project"), replace(cap, journal_epoch="other"),
                        replace(cap, token="private diagnostic"), {}):
            with self.assertRaises(Conflict) as ex:
                with self.store.fence(invalid):
                    self.fail("invalid capability fenced")
            self.assertNotIn("private diagnostic", str(ex.exception))

    def test_replacement_and_stale(self):
        old = self.claim()
        for previous in (0, 2, True, MAX_GENERATION):
            with self.assertRaises(Conflict):
                self.store.replace(ROLE, INC, previous, yes)
        with self.assertRaises(Conflict):
            self.store.replace(ROLE, "new-incarnation", 1, yes)
        with self.assertRaises(Conflict):
            self.store.claim("GUARD", INC, yes)
        with self.assertRaises(Conflict):
            self.store.replace(ROLE, INC, 1, lambda _: False)
        with self.store.fence(old):
            pass
        seen = []
        new = self.reopen().replace(ROLE, INC, 1, lambda d: seen.append(dict(d)) or True)
        self.assertEqual((new.generation, seen[0]["operation"], seen[0]["previous_generation"],
                          seen[0]["next_generation"]), (2, "owner_replacement", 1, 2))
        self.assertNotEqual(old.token, new.token)
        with self.assertRaises(Conflict):
            with self.store.fence(old):
                self.fail("stale owner fenced")
        with self.store.fence(new):
            pass

    def test_overflow(self):
        self.claim()
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE owners SET generation=?", (MAX_GENERATION,))
        with self.assertRaises(Conflict):
            self.store.replace(ROLE, INC, MAX_GENERATION, yes)
        self.assertEqual(self.store.status()[ROLE]["generation"], MAX_GENERATION)

    def race(self, call):
        barrier = threading.Barrier(2)
        stores = [self.reopen(), self.reopen()]
        def run(store):
            barrier.wait(timeout=3)
            try:
                return call(store)
            except Conflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, stores))

    def test_concurrent_claim(self):
        results = self.race(lambda store: store.claim(ROLE, INC, yes))
        self.assertEqual(sum(isinstance(x, Capability) for x in results), 1)
        self.assertEqual(self.store.status()[ROLE]["generation"], 1)

    def test_concurrent_replace(self):
        old = self.claim()
        results = self.race(lambda store: store.replace(ROLE, INC, 1, yes))
        self.assertEqual(sum(isinstance(x, Capability) for x in results), 1)
        self.assertEqual(self.store.status()[ROLE]["generation"], 2)
        with self.assertRaises(Conflict):
            with self.store.fence(old):
                pass

    def test_fence_busy_and_exception_release(self):
        old = self.claim()
        other = self.reopen()
        seen = []
        with self.assertRaisesRegex(RuntimeError, "caller error"):
            with self.store.fence(old):
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(other.replace, ROLE, INC, 1,
                                         lambda d: seen.append(d) or True)
                    with self.assertRaises(OwnerBusy):
                        future.result(timeout=3)
                raise RuntimeError("caller error")
        self.assertEqual(seen, [])
        self.assertEqual(other.status()[ROLE]["generation"], 1)
        new = other.replace(ROLE, INC, 1, yes)
        self.assertEqual(new.generation, 2)

    def test_path_replacement_fails_open_handle(self):
        cap = self.claim()
        self.path.rename(self.path.with_suffix(".old"))
        fresh = initialize_owner(self.path, SID, REPO, EPOCH)
        self.addCleanup(fresh.close)
        with self.assertRaises(Conflict):
            self.store.status()
        with self.assertRaises(Conflict):
            with self.store.fence(cap):
                pass
        self.assertEqual(fresh.status(), {})

    def test_tamper_schema_and_rows(self):
        self.claim()
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE owners SET capability_sha256='bad'")
        with self.assertRaises(Conflict):
            self.store.status()
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE owners SET capability_sha256=?", ("a"*64,))
            conn.execute("CREATE TABLE surprise (x)")
        with self.assertRaises(Conflict):
            self.store.status()

    def test_closed_handle(self):
        self.store.close()
        with self.assertRaises(Conflict):
            self.store.status()
