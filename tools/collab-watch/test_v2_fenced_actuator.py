"""Owner fencing around real accepted task/aux actuator with synthetic transport."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from core import Conflict, canonical
import test_v2_actuator as task_fixtures
import test_v2_aux_actuator as aux_fixtures
from test_split_journal import CFG
from v2_actuator import _bound, _ownership_fd, actuate
from v2_attempts import initialize
from v2_inputs import initialize_inputs
from v2_owner import OwnerBusy, initialize_owner, open_owner
from v2_fenced_actuator import actuate_fenced
import os


class FencedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.path, self.input_path, self.owner_path = (
            root/"attempt.db", root/"input.db", root/"owner.db")
        self.store = initialize(self.path, "attempt-test")
        self.retention = initialize_inputs(self.input_path, "input-test", "attempt-test")
        self.addCleanup(self.retention.close)
        self.owner = initialize_owner(self.owner_path, "owner-test",
                                      CFG["repository"], CFG["journal_epoch"])
        self.addCleanup(self.owner.close)
        self.other = open_owner(self.owner_path, "owner-test",
                                CFG["repository"], CFG["journal_epoch"])
        self.addCleanup(self.other.close)

    def task_case(self):
        return task_fixtures.ActuatorTests.material_case(self)

    def aux_case(self):
        return aux_fixtures.AuxActuatorTests.case(self)

    def cap(self, original):
        action = _bound(original)[4]
        return self.owner.claim(action["role"], action["incarnation"], lambda _: True)

    def takeover(self, cap):
        return self.other.replace(cap.transport_role, cap.incarnation, cap.generation,
                                  lambda _: True)

    def run_case(self, cap, original, remote, authorize=lambda _: True, **kwargs):
        with patch("v2_actuator._write_transport", return_value=remote):
            return actuate_fenced(self.owner, cap, self.store, original, self.retention, authorize,
                                  read_token="read-token", write_token="write-token",
                                  read_opener=task_fixtures.ReadOpener(remote), **kwargs)

    def count(self, path, table):
        with sqlite3.connect(path) as conn:
            return conn.execute("SELECT count(*) FROM "+table).fetchone()[0]

    def untouched(self, remote):
        self.assertFalse(remote.sent or remote.user_reads or remote.read_calls)
        self.assertEqual(self.count(self.path, "attempts"), 0)
        self.assertEqual(self.count(self.input_path, "originals"), 0)

    def test_task_and_aux_unchanged_identity(self):
        for original, remote in (self.task_case(), self.aux_case()):
            cap = self.cap(original)
            # A non-initial generation must not enter semantic identities.
            cap = self.takeover(cap)
            seen = []
            result = self.run_case(cap, original, remote, lambda d: seen.append(d) or True)
            self.assertEqual(result["state"], "VERIFIED", result)
            claimed = self.store.claimed(_bound(original)[3])
            self.assertEqual(claimed["effect_descriptor"], _bound(original)[3])
            self.assertEqual(claimed["action_descriptor"], seen[0])
            self.assertEqual(self.retention.load(claimed["action_key"]), original)
            self.assertEqual(len(remote.sent), 1)
            self.assertEqual(remote.sent[0][2], _bound(original)[5])
            for value in (claimed, seen, result, original, repr(remote.sent)):
                rendered = str(value)
                self.assertNotIn(cap.token, rendered)
                self.assertNotIn("owner_generation", rendered)
                self.assertNotIn("capability_sha256", rendered)
                self.assertNotIn("store_id", rendered)
            self.assertNotIn(cap.token.encode(), self.path.read_bytes())
            self.assertNotIn(cap.token.encode(), self.input_path.read_bytes())
            self.assertNotIn("generation", seen[0])
            # Exact receipt returned by the accepted actuator itself.
            self.assertEqual(actuate(self.store, original, self.retention, lambda _: False,
                                     reconcile_only=True), result)

    def test_invalid_scope_or_capability_before_actuator(self):
        original, remote = self.task_case()
        cap = self.cap(original)
        for bad in (replace(cap, repository="other/project"), replace(cap, journal_epoch="other"),
                    replace(cap, transport_role="GUARD"), replace(cap, incarnation="other"),
                    replace(cap, token="0"*64), replace(cap, generation=2),
                    replace(cap, store_id="other"), None):
            with patch("v2_fenced_actuator.actuate") as send:
                result = self.run_case(bad, original, remote)
                send.assert_not_called()
            self.assertEqual(result, dict(state="NO_ATTEMPT", code="OWNER_CAPABILITY_REJECTED",
                                          action_key=None))
            self.untouched(remote)

    def test_malformed_original_no_fence(self):
        original, remote = self.task_case()
        cap = self.cap(original)
        with patch("v2_owner.OwnerStore.fence") as fence:
            result = self.run_case(cap, '{"private":"secret"}', remote)
            fence.assert_not_called()
        self.assertEqual(result["code"], "FROZEN_ACTION_UNBINDABLE")
        self.assertNotIn("secret", repr(result))
        self.untouched(remote)

    def test_owner_busy_no_attempt(self):
        original, remote = self.task_case()
        cap = self.cap(original)
        with self.other.fence(cap):
            with patch("v2_fenced_actuator.actuate") as send:
                result = self.run_case(cap, original, remote)
                send.assert_not_called()
        self.assertEqual((result["state"], result["code"]), ("BUSY", "OWNER_BUSY"))
        self.untouched(remote)

    def test_takeover_excluded_during_send_and_readback(self):
        original, remote = self.task_case()
        cap = self.cap(original)
        entered, release = Event(), Event()
        def at_send():
            entered.set()
            self.assertTrue(release.wait(5))
        remote.store_check = at_send
        read = remote.read
        after_checked = []
        def at_read(req, timeout):
            if remote.applied and not after_checked:
                with self.assertRaises(OwnerBusy):
                    self.takeover(cap)
                after_checked.append(True)
            return read(req, timeout)
        remote.read = at_read
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.run_case, cap, original, remote)
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
                with self.assertRaises(OwnerBusy):
                    self.takeover(cap)
            finally:
                release.set()
            result = pending.result(5)
        self.assertEqual(result["state"], "VERIFIED", result)
        self.assertEqual(after_checked, [True])
        new = self.takeover(cap)
        self.assertEqual(self.run_case(cap, original, remote, reconcile_only=True)["code"],
                         "OWNER_CAPABILITY_REJECTED")
        self.assertEqual(self.run_case(new, original, remote, reconcile_only=True), result)
        self.assertEqual(len(remote.sent), 1)

    def test_new_owner_reconciles_unresolved_without_resend(self):
        original, remote = self.aux_case()
        cap = self.cap(original)
        post = remote.after
        remote.after = remote.before
        remote.error = True
        result = self.run_case(cap, original, remote)
        self.assertEqual(result["state"], "UNRESOLVED")
        new = self.takeover(cap)
        remote.after = post
        result = self.run_case(new, original, remote, reconcile_only=True)
        self.assertEqual(result["state"], "VERIFIED", result)
        self.assertEqual(len(remote.sent), 1)

    def test_crash_releases_fence_and_started_never_resends(self):
        original, remote = self.task_case()
        cap = self.cap(original)
        remote.crash = True
        with self.assertRaises(task_fixtures.Crash):
            self.run_case(cap, original, remote)
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
        new = self.takeover(cap)
        self.assertEqual(self.run_case(cap, original, remote)["code"], "OWNER_CAPABILITY_REJECTED")
        result = self.run_case(new, original, remote, reconcile_only=True)
        self.assertEqual(result["state"], "VERIFIED", result)
        self.assertEqual(len(remote.sent), 1)

    def test_action_authority_denial_while_fenced(self):
        original, remote = self.task_case()
        cap = self.cap(original)
        seen = []
        def deny(_):
            with self.assertRaises(OwnerBusy):
                self.takeover(cap)
            seen.append(True)
            return False
        result = self.run_case(cap, original, remote, deny)
        self.assertEqual(seen, [True])
        self.assertEqual((result["state"], result["code"]), ("PREPARED", "AUTHORITY_DENIED"))
        self.assertIsNone(self.store.claimed(_bound(original)[3]))
        self.assertFalse(remote.sent)
        self.assertEqual(self.takeover(cap).generation, 2)

    def test_attempt_busy_releases_owner_fence(self):
        original, remote = self.task_case()
        cap = self.cap(original)
        fd = _ownership_fd(self.store)
        try:
            result = self.run_case(cap, original, remote)
            self.assertEqual((result["state"], result["code"]), ("BUSY", "ACTUATOR_BUSY"))
            self.untouched(remote)
            self.assertEqual(self.takeover(cap).generation, 2)
        finally:
            os.close(fd)

    def test_unexpected_invocation_failure_is_not_no_attempt(self):
        original, remote = self.task_case()
        cap = self.cap(original)
        with patch("v2_fenced_actuator.actuate", side_effect=RuntimeError(cap.token)):
            result = self.run_case(cap, original, remote)
        self.assertEqual((result["state"], result["code"]),
                         ("EFFECT_UNKNOWN", "FENCED_INVOCATION_UNCONFIRMED"))
        self.assertNotIn(cap.token, repr(result))
        self.assertEqual(self.takeover(cap).generation, 2)
