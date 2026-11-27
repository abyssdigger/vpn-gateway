"""9b-C-B1: actual accepted writer and stores, synthetic remote only."""
from contextlib import contextmanager
from dataclasses import replace
import fcntl
import multiprocessing
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from core import Conflict
import test_v2_actuator as tf
import test_v2_trusted_writer as wt
from test_v2_writer_spool import quotas, trusted, request
from v2_actuator import _bound
from v2_trusted_writer import TrustedWriter
from v2_writer_ipc import SessionBinding
import v2_writer_spool as sp
from v2_writer_coordinator import (Coordinator, CoordinatorBlocked, CoordinatorBusy,
                                   CoordinatorUncertain, FilePin, StorePins)


def file_pin(store_id, path):
    """Test provisioning captures trusted physical identities once."""
    info = path.stat()
    return FilePin(store_id, path, (info.st_dev, info.st_ino))


def pins_for(spool, writer):
    state = writer._runtime_state
    return StorePins(
        file_pin(spool._scope[0], spool._path),
        file_pin(writer._store.store_id, writer._store.path),
        file_pin(writer._retention.provider_id, writer._retention.path),
        file_pin(writer._owner._store_id, writer._owner._path),
        None if state is None else file_pin(state._store_id, state._path))


class CoordinatorTests(unittest.TestCase):
    setUp = wt.WriterTests.setUp
    case = wt.WriterTests.case
    new_checkpoint = wt.WriterTests.new_checkpoint
    writer = wt.WriterTests.writer
    cap = wt.WriterTests.cap
    counts = wt.WriterTests.counts
    assert_untouched = wt.WriterTests.assert_untouched

    def view(self, writer, q=None, *, prior=None, policy=None):
        cap = writer._capability
        role = cap.transport_role
        session = SessionBinding(role, cap.incarnation, cap.generation, "session-"+role.lower())
        args = trusted(q, role=role, session=session, attempt_store_id=self.store.store_id,
                       input_store_id=self.retention.provider_id)
        if policy is not None:
            args["resource_policy"] = policy
        if prior is None:
            spool = sp.Spool.provision(Path(self.tmp.name)/"spool.db",
                                       verified_empty_pair=True, **args)
        else:
            spool = sp.Spool.open(prior._path, expected_inode=prior.inode, **args)
        self.addCleanup(spool.close)
        return spool

    def coordinator(self, spool, writer, **changes):
        kwargs = dict(pins=pins_for(spool, writer), session=spool._session,
                      resource_policy=spool._policy)
        kwargs.update(changes)
        obj = Coordinator(spool, writer, **kwargs)
        self.addCleanup(obj.close)
        return obj

    def ordinary(self, coordinator, original, remote, mode=False):
        with patch("v2_actuator._write_transport", return_value=remote):
            return coordinator.ordinary(request(original, mode))

    def recover(self, coordinator, row, remote):
        with patch("v2_actuator._write_transport", return_value=remote):
            return coordinator.recover(row["request_id"], row["version"])

    def join(self, child, exitcode=0):
        child.join(15)
        if child.is_alive():
            child.kill()
            child.join()
            self.fail("coordinator child timed out")
        self.assertEqual(child.exitcode, exitcode)

    def test_committed_marker_lock_and_delegate_result_order(self):
        original, remote = tf.ActuatorTests.material_case(self)
        writer = self.writer(original, remote)
        spool = self.view(writer)
        c = self.coordinator(spool, writer)
        checked = []
        def at_send():
            row, = spool.list_metadata()
            self.assertEqual((row["state"], row["version"], row["uncertain"]),
                             (sp.MARKED, 2, 1))
            fd = os.open(spool._path, os.O_RDONLY | os.O_CLOEXEC)
            try:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(fd)
            checked.append(True)
        remote.store_check = at_send
        result = self.ordinary(c, original, remote)
        self.assertEqual(checked, [True])
        self.assertEqual((result.execution, result.classification, result.result["state"]),
                         (sp.INITIAL, sp.TV, "VERIFIED"))
        row = spool.load(result.request_id)
        self.assertEqual((row["state"], row["version"], row["classification"]), (sp.RESULT, 3, sp.TV))
        self.assertEqual(len(remote.sent), 1)
        before = spool.status()
        with self.assertRaises(CoordinatorBlocked):
            self.ordinary(c, original, remote)
        with self.assertRaises(CoordinatorBlocked):
            self.recover(c, row, remote)
        self.assertEqual(spool.status(), before)
        self.assertEqual(len(remote.sent), 1)

    def test_worker_read_only_and_pre_admission_fail_closed(self):
        original, remote = tf.ActuatorTests.material_case(self)
        writer = self.writer(original, remote)
        spool = self.view(writer)
        c = self.coordinator(spool, writer)
        with patch.object(TrustedWriter, "invoke", side_effect=AssertionError("unexpected invoke")) as delegate:
            for bad in (request(original, True), request(original, 0),
                        dict(request(original), recovery=True), {"original": original}, None):
                with self.assertRaises(CoordinatorBlocked):
                    c.ordinary(bad)
            with patch.object(sp.Spool, "admit", side_effect=Conflict("synthetic failure")):
                with self.assertRaises(CoordinatorBlocked):
                    c.ordinary(request(original))
            delegate.assert_not_called()
        self.assertEqual(spool.list_metadata(), [])
        self.assert_untouched(remote)

    def test_independent_processes_roles_contend_before_admit(self):
        original, remote = tf.ActuatorTests.material_case(self)
        other, other_remote = tf.ActuatorTests.creation_case(self)
        w, other_w = self.writer(original, remote), self.writer(other, other_remote)
        spool = self.view(w)
        other_spool = self.view(other_w, prior=spool)
        # Pin in trusted parent at provisioning; actual lock only in each child.
        p, other_p = pins_for(spool, w), pins_for(other_spool, other_w)
        ctx = multiprocessing.get_context("fork")
        entered, release = ctx.Event(), ctx.Event()
        def hold():
            entered.set()
            if not release.wait(10):
                os._exit(31)
        remote.store_check = hold
        def first():
            with _managed(spool, w, p) as c:
                result = self.ordinary(c, original, remote)
                self.assertEqual(result.classification, sp.TV)
        def rival():
            with _managed(other_spool, other_w, other_p) as c:
                with patch.object(sp.Spool, "admit", side_effect=AssertionError("admit reached")) as admit, \
                     patch.object(sp.Spool, "mark_initial", side_effect=AssertionError("marker reached")) as mark, \
                     patch.object(TrustedWriter, "invoke", side_effect=AssertionError("invoke reached")) as invoke:
                    with self.assertRaises(CoordinatorBusy):
                        self.ordinary(c, other, other_remote)
                    admit.assert_not_called()
                    mark.assert_not_called()
                    invoke.assert_not_called()
        child = ctx.Process(target=first)
        child.start()
        try:
            self.assertTrue(entered.wait(10))
            competitor = ctx.Process(target=rival)
            competitor.start()
            self.join(competitor)
            inventory = spool.list_metadata()
            self.assertEqual(len(inventory), 1)
            self.assertEqual((inventory[0]["role"], inventory[0]["state"]), ("BUILDER", sp.MARKED))
        finally:
            release.set()
            self.join(child)
        row, = spool.list_metadata()
        self.assertEqual(row["classification"], sp.TV)
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "VERIFIED")

    def test_pair_wide_other_role_rr_blocks_ordinary_and_policy_mismatch(self):
        original, remote = tf.ActuatorTests.material_case(self)
        other, other_remote = tf.ActuatorTests.creation_case(self)
        w, other_w = self.writer(original, remote), self.writer(other, other_remote)
        spool = self.view(w)
        other_spool = self.view(other_w, prior=spool)
        c, other_c = self.coordinator(spool, w), self.coordinator(other_spool, other_w)
        post = remote.after
        remote.after = remote.before
        remote.error = True
        result = self.ordinary(c, original, remote)
        self.assertEqual(result.classification, sp.RR)
        row = spool.load(result.request_id)
        before = spool.status()
        with patch.object(sp.Spool, "admit", side_effect=AssertionError("admit reached")) as admit:
            with self.assertRaises(CoordinatorBlocked):
                self.ordinary(other_c, other, other_remote)
            admit.assert_not_called()
        with self.assertRaises(CoordinatorBlocked):
            self.recover(other_c, row, other_remote)
        wrong_policy = self.view(w, prior=spool, policy=sp.ResourcePolicy("other-policy", "d"*64))
        wrong = self.coordinator(wrong_policy, w)
        with self.assertRaises(CoordinatorBlocked):
            self.recover(wrong, row, remote)
        self.assertEqual(spool.load(result.request_id), row)
        self.assertEqual(spool.status(), before)
        self.assertFalse(other_remote.sent)
        remote.after = post
        result2 = self.recover(c, row, remote)
        self.assertEqual((result2.execution, result2.classification), (sp.FORCED, sp.TV))
        self.assertEqual(len(remote.sent), 1)

    def test_real_process_death_after_marker_recovery_full_quota_and_nc_parked(self):
        original, remote = tf.ActuatorTests.material_case(self)
        w = self.writer(original, remote)
        q = quotas(1)
        spool = self.view(w, q)
        p = pins_for(spool, w)
        ctx = multiprocessing.get_context("fork")
        def child_work():
            with _managed(spool, w, p) as c:
                real_mark = sp.Spool.mark_initial
                def mark_then_die(store, rid, version):
                    real_mark(store, rid, version)
                    os._exit(23)
                with patch.object(sp.Spool, "mark_initial", mark_then_die):
                    self.ordinary(c, original, remote)
        child = ctx.Process(target=child_work)
        child.start()
        self.join(child, 23)
        row, = spool.list_metadata()
        self.assertEqual((row["state"], row["version"], row["uncertain"]), (sp.MARKED, 2, 1))
        self.assertEqual(spool.status()["records"], 1)
        self.assertEqual(self.counts(), [0, 0])
        reopened = self.view(w, q, prior=spool)
        c = self.coordinator(reopened, w)
        charges = reopened.status()
        with self.assertRaises(CoordinatorBlocked):
            self.ordinary(c, original, remote)
        result = self.recover(c, row, remote)
        self.assertEqual((result.execution, result.classification, result.result["code"]),
                         (sp.FORCED, sp.NC, "NO_CLAIMED_EFFECT"))
        self.assertEqual(reopened.status(), charges)
        self.assert_untouched(remote)
        terminal = reopened.load(result.request_id)
        for operation in (lambda: self.ordinary(c, original, remote),
                          lambda: self.recover(c, terminal, remote)):
            with self.assertRaises(CoordinatorBlocked):
                operation()
        self.assertEqual(reopened.load(result.request_id), terminal)

    def test_real_process_death_after_writer_return_before_spool_result(self):
        original, remote = tf.ActuatorTests.material_case(self)
        w = self.writer(original, remote)
        spool = self.view(w)
        p = pins_for(spool, w)
        ctx = multiprocessing.get_context("fork")
        sends = ctx.Value("i", 0)
        def count_send():
            with sends.get_lock():
                sends.value += 1
        remote.store_check = count_send
        def child_work():
            with _managed(spool, w, p) as c:
                def die_before_result(store, rid, version, execution, value):
                    self.assertEqual(value["state"], "VERIFIED")
                    os._exit(24)
                with patch.object(sp.Spool, "persist_result", die_before_result):
                    self.ordinary(c, original, remote)
        child = ctx.Process(target=child_work)
        child.start()
        self.join(child, 24)
        row, = spool.list_metadata()
        self.assertEqual((row["state"], row["version"], row["uncertain"]), (sp.MARKED, 2, 1))
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "VERIFIED")
        self.assertEqual(sends.value, 1)
        # Owner replacement is allowed only by the accepted owner store and
        # current capability; first spool generation is diagnostic provenance.
        cap = w._capability
        new_cap = self.other_owner.replace(cap.transport_role, cap.incarnation,
                                           cap.generation, lambda _: True)
        stale = self.coordinator(spool, w)
        result = self.recover(stale, row, remote)
        self.assertEqual((result.classification, result.result["code"]),
                         (sp.RR, "OWNER_CAPABILITY_REJECTED"))
        self.assertEqual(sends.value, 1)
        w2 = self.writer(original, remote, capability=new_cap)
        current = self.view(w2, prior=spool)
        c = self.coordinator(current, w2)
        row = current.load(result.request_id)
        self.assertEqual(row["first_generation"], cap.generation)
        remote.applied = True  # synthetic remote observation after known child send
        result = self.recover(c, row, remote)
        self.assertEqual((result.execution, result.classification), (sp.FORCED, sp.TV))
        self.assertEqual(sends.value, 1)
        self.assertEqual(len(remote.sent), 0)
        with self.assertRaises(CoordinatorBlocked):
            self.ordinary(c, original, remote)
        self.assertEqual(sends.value, 1)

    def test_rn_parked_and_no_automatic_retry(self):
        original, remote = tf.ActuatorTests.material_case(self)
        w = self.writer(original, remote, authorize=lambda _: False)
        spool = self.view(w)
        c = self.coordinator(spool, w)
        result = self.ordinary(c, original, remote)
        self.assertEqual((result.classification, result.result["state"]), (sp.RN, "PREPARED"))
        row = spool.load(result.request_id)
        for operation in (lambda: self.ordinary(c, original, remote),
                          lambda: self.recover(c, row, remote)):
            with self.assertRaises(CoordinatorBlocked):
                operation()
        self.assertEqual(spool.load(result.request_id), row)
        self.assertFalse(remote.sent)

    def test_trusted_bootstrap_and_attempt_path_continuity(self):
        original, remote = tf.ActuatorTests.material_case(self)
        w = self.writer(original, remote)
        spool = self.view(w)
        p = pins_for(spool, w)
        # Guaranteed different from every real pinned file even on adjacent inode allocation.
        wrong_inode = (max(pin.inode[0] for pin in p.values())+1, p.attempt.inode[1])
        for changes in (
            dict(pins=replace(p, attempt=replace(p.attempt, inode=wrong_inode))),
            dict(pins=replace(p, attempt=replace(p.attempt, store_id="wrong-attempt"))),
            dict(pins=replace(p, owner=replace(p.owner, store_id="wrong-owner"))),
            dict(pins=replace(p, input=replace(p.input, store_id="wrong-input"))),
            dict(session=replace(spool._session, owner_generation=spool._session.owner_generation+1)),
            dict(resource_policy=sp.ResourcePolicy("other", "d"*64)),
        ):
            with self.subTest(changes=tuple(changes)), self.assertRaises(CoordinatorBlocked):
                self.coordinator(spool, w, **changes)
        c = self.coordinator(spool, w, pins=p)
        old = self.store.path.with_name("old-attempt.db")
        self.store.path.rename(old)
        shutil.copyfile(old, self.store.path)
        os.chmod(self.store.path, 0o600)
        try:
            with self.assertRaises(CoordinatorBlocked):
                self.ordinary(c, original, remote)
            self.assertEqual(spool.list_metadata(), [])
        finally:
            self.store.path.unlink()
            old.rename(self.store.path)
        self.assert_untouched(remote)
        alias = spool._path.with_name("alias-spool.db")
        os.link(spool._path, alias)
        try:
            with self.assertRaises(CoordinatorBlocked):
                self.ordinary(c, original, remote)
        finally:
            alias.unlink()
        self.assertEqual(spool.list_metadata(), [])
        self.assert_untouched(remote)

    def test_marker_commit_then_exception_conservative_uncertainty(self):
        original, remote = tf.ActuatorTests.material_case(self)
        w = self.writer(original, remote)
        spool = self.view(w)
        c = self.coordinator(spool, w)
        real_mark = sp.Spool.mark_initial
        def mark_then_error(store, rid, version):
            real_mark(store, rid, version)
            raise OSError("private error")
        with patch.object(sp.Spool, "mark_initial", mark_then_error), \
             patch.object(TrustedWriter, "invoke", side_effect=AssertionError("unexpected invoke")) as invoke:
            with self.assertRaises(CoordinatorUncertain) as caught:
                c.ordinary(request(original))
            invoke.assert_not_called()
        self.assertNotIn("private", str(caught.exception))
        row, = spool.list_metadata()
        self.assertEqual((row["state"], row["uncertain"]), (sp.MARKED, 1))
        self.assert_untouched(remote)
        result = self.recover(c, row, remote)
        self.assertEqual(result.classification, sp.NC)


@contextmanager
def _managed(spool, writer, pins):
    obj = Coordinator(spool, writer, pins=pins, session=spool._session,
                      resource_policy=spool._policy)
    try:
        yield obj
    finally:
        obj.close()


if __name__ == "__main__":
    unittest.main()
