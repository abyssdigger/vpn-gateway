"""9b-C-B2: actual exec, accepted stores and writer, fixed synthetic-only transport."""
from dataclasses import replace
import ctypes
import fcntl
import hashlib
import multiprocessing
import os
from pathlib import Path
import signal
import struct
import time
import unittest
from unittest.mock import patch

from core import canonical, Conflict, strict_json
from test_split_journal import CFG
from test_v2_trusted_writer import BINDINGS
import test_v2_actuator as tf
import test_v2_writer_coordinator as ct
from test_v2_writer_coordinator import file_pin, pins_for
from test_v2_writer_spool import quotas, request
from v2_actuator import _bound
import v2_writer_ipc as ipc
import v2_writer_launcher as launch
import v2_writer_spool as sp
from v2_writer_scheduler import (ExecutionPolicy, SyntheticFixture, Route, Bootstrap,
                                 Scheduler, SchedulingBlocked)

MIB = 1024 * 1024


class SchedulerTests(unittest.TestCase):
    setUp = ct.CoordinatorTests.setUp
    case = ct.CoordinatorTests.case
    new_checkpoint = ct.CoordinatorTests.new_checkpoint
    writer = ct.CoordinatorTests.writer
    cap = ct.CoordinatorTests.cap
    counts = ct.CoordinatorTests.counts
    view = ct.CoordinatorTests.view

    def policy(self):
        return ExecutionPolicy("policy-one", launch.Limits(512*MIB, 5, 64, 10), 12,
                               launch.Limits(768*MIB, 8, 96, 12), 16)

    def route(self, original, remote, q, *, prior=None, fault="none"):
        w = self.writer(original, remote)
        policy = self.policy()
        spool = self.view(w, q, prior=prior, policy=policy.identity())
        role = spool._session.role
        root = Path(self.tmp.name)
        data = root / ("fixture-"+role.lower())
        counter = root / ("counter-"+role.lower())
        raw = canonical(dict(before=remote.before, after=remote.after, actor=remote.actor,
                             response=remote.response)).encode("utf-8")
        data.write_bytes(raw)
        counter.write_bytes(struct.pack(">Q", 0))
        data.chmod(0o600)
        counter.chmod(0o600)
        fixture = SyntheticFixture(file_pin(data.name, data), hashlib.sha256(raw).hexdigest(),
                                   file_pin(counter.name, counter), fault)
        route = Route(canonical(CFG), canonical(BINDINGS),
                      "GPT-6.2" if role == "BUILDER" else "GPT-5.6 Sol",
                      spool._session, w._capability, pins_for(spool, w), q, policy, fixture)
        return spool, route

    def count(self, route):
        return struct.unpack(">Q", route.fixture.counter.path.read_bytes())[0]

    def ordinary(self, scheduler, route, original, mode=False):
        client, inv = scheduler.start_ordinary(*route.key())
        outcome = ipc.exchange(client, request(original, mode), deadline=inv.deadline)
        return outcome, inv.wait(25)

    def report(self, completion, recovery, route):
        self.assertTrue(completion.reaped)
        self.assertEqual(completion.writer_status, 0)
        self.assertIsNotNone(completion.report)
        r = completion.report
        limits, _ = route.policy.lane(recovery)
        self.assertEqual(r["setup"]["limits"], [limits.address_bytes, limits.cpu_seconds,
                                                limits.files, limits.processes])
        self.assertEqual(len(r["setup"]["fds"]), 4 if recovery else 5)
        return r

    def test_actual_ordinary_policy_slot_and_worker_no_recovery(self):
        original, remote = tf.ActuatorTests.material_case(self)
        spool, route = self.route(original, remote, quotas(2))
        scheduler = Scheduler(spool, (route,))
        self.assertNotEqual(route.policy.identity(),
                            replace(route.policy, recovery_wall=17).identity())
        for recovery in (False, True):
            selection = ("a"*64, 2) if recovery else None
            deadline = time.monotonic()+route.policy.lane(recovery)[1]
            wire = strict_json(Bootstrap(route, selection).wire(deadline).decode())
            self.assertEqual(wire["deadline"], deadline)
            policy = wire["route"]["policy"]
            self.assertEqual(set(policy), {"resource", "limits", "wall", "recovery"})
            limits, wall = route.policy.lane(recovery)
            self.assertEqual(policy["limits"], dict(address_bytes=limits.address_bytes,
                                                  cpu_seconds=limits.cpu_seconds,
                                                  files=limits.files, processes=limits.processes))
            self.assertEqual(policy["wall"], wall)
            self.assertEqual(policy["recovery"], recovery)
            self.assertEqual(policy["resource"]["sha256"], route.policy.identity().sha256)
            unselected, other_wall = route.policy.lane(not recovery)
            self.assertNotIn(str(unselected.address_bytes), canonical(wire))
            self.assertNotEqual(policy["wall"], other_wall)
            child = Bootstrap.from_wire(wire)
            self.assertEqual(child.route.policy.identity(), route.policy.identity())
            self.assertEqual(child.route.policy.lane(recovery), (limits, wall))
            with self.assertRaises(Conflict):
                child.route.policy.lane(not recovery)
            with self.assertRaises(Conflict):
                child.wire(deadline)
            with self.assertRaises(SchedulingBlocked):
                Scheduler(spool, (child.route,))
        with self.assertRaises(launch.LaunchError):
            launch.Supervisor(route.launch_spec(True)).start_coordinated(Bootstrap(route))
        out, done = self.ordinary(scheduler, route, original, True)
        self.assertEqual(out["state"], "HANDOFF_UNCERTAIN")
        self.report(done, False, route)
        self.assertEqual(spool.list_metadata(), [])
        self.assertEqual(self.count(route), 0)
        before = time.monotonic()
        client, inv = scheduler.start_ordinary(*route.key())
        try:
            self.assertAlmostEqual(inv.deadline-before, route.policy.ordinary_wall, delta=0.5)
            with self.assertRaises(launch.Busy):
                scheduler.start_ordinary(*route.key())
            with self.assertRaises(launch.Busy):
                scheduler.recover_next()
            out = ipc.exchange(client, request(original), deadline=inv.deadline)
        finally:
            client.close()
        done = inv.wait(25)
        self.report(done, False, route)
        self.assertEqual(out["state"], "RESULT", out)
        self.assertEqual(out["result"]["state"], "VERIFIED")
        row, = spool.list_metadata()
        self.assertEqual((row["state"], row["classification"]), (sp.RESULT, sp.TV))
        self.assertEqual(self.count(route), 1)
        out, _ = self.ordinary(scheduler, route, original)
        self.assertEqual(out["state"], "HANDOFF_UNCERTAIN")
        self.assertEqual(self.count(route), 1)

    def test_exec_crash_marker_full_quota_and_recovery_no_endpoint(self):
        original, remote = tf.ActuatorTests.material_case(self)
        spool, route = self.route(original, remote, quotas(1), fault="after_marker")
        scheduler = Scheduler(spool, (route,))
        out, done = self.ordinary(scheduler, route, original)
        self.assertEqual(out["state"], "HANDOFF_UNCERTAIN")
        self.assertEqual(done.writer_status, 23)
        row, = spool.list_metadata()
        self.assertEqual((row["state"], row["version"]), (sp.MARKED, 2))
        charges = spool.status()
        self.assertEqual(charges["records"], 1)
        with self.assertRaises(SchedulingBlocked):
            scheduler.start_ordinary(*route.key())
        before = time.monotonic()
        recovery = scheduler.recover_next()
        self.assertAlmostEqual(recovery.deadline-before, route.policy.recovery_wall, delta=0.5)
        done = recovery.wait(25)
        self.assertEqual(self.report(done, True, route)["outcome"], "RESULT")
        row, = spool.list_metadata()
        self.assertEqual((row["state"], row["classification"]), (sp.RESULT, sp.NC))
        self.assertEqual(spool.status(), charges)
        self.assertEqual(self.count(route), 0)
        self.assertEqual(self.counts(), [0, 0])
        with self.assertRaises(SchedulingBlocked):
            scheduler.recover_next()
        out, _ = self.ordinary(scheduler, route, original)
        self.assertEqual(out["state"], "HANDOFF_UNCERTAIN")
        self.assertEqual(self.count(route), 0)

    def test_exec_crash_after_writer_no_duplicate_and_missing_routes(self):
        original, remote = tf.ActuatorTests.material_case(self)
        other, other_remote = tf.ActuatorTests.creation_case(self)
        q = quotas(2)
        spool, route = self.route(original, remote, q, fault="after_writer")
        second, other_route = self.route(other, other_remote, q, prior=spool)
        scheduler = Scheduler(spool, (route, other_route))
        out, done = self.ordinary(scheduler, route, original)
        self.assertEqual(out["state"], "HANDOFF_UNCERTAIN")
        self.assertEqual(done.writer_status, 24)
        row, = spool.list_metadata()
        self.assertEqual(row["state"], sp.MARKED)
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "VERIFIED")
        self.assertEqual(self.count(route), 1)
        missing = Scheduler(second, (other_route,))
        with self.assertRaises(SchedulingBlocked):
            missing.recover_next()
        with self.assertRaises(SchedulingBlocked):
            missing.start_ordinary(*other_route.key())
        wrong = replace(route, policy=replace(route.policy, recovery_wall=17))
        with self.assertRaises(SchedulingBlocked):
            Scheduler(spool, (wrong,)).recover_next()
        supervisor = launch.Supervisor(route.launch_spec(True))
        endpoint, inv = supervisor.start_coordinated(
            Bootstrap(route, (row["request_id"], row["version"]+1)))
        self.assertIsNone(endpoint)
        self.assertEqual(self.report(inv.wait(25), True, route)["outcome"], "HANDOFF_UNCERTAIN")
        self.assertEqual(spool.list_metadata(), [row])
        done = scheduler.recover_next().wait(25)
        self.assertEqual(self.report(done, True, route)["outcome"], "RESULT")
        self.assertEqual(spool.list_metadata()[0]["classification"], sp.TV)
        self.assertEqual(self.count(route), 1)
        self.assertEqual(self.count(other_route), 0)

    def test_deterministic_priority_revalidated_in_child(self):
        a, ar = tf.ActuatorTests.material_case(self)
        b, br = tf.ActuatorTests.creation_case(self)
        q = quotas(2)
        spool, route = self.route(a, ar, q)
        second, other = self.route(b, br, q, prior=spool)
        for view, original in ((spool, a), (second, b)):
            rid = view.admit(request(original))
            view.mark_initial(rid, 1)
        first, later = spool.list_metadata()
        routes = {r.session.role: r for r in (route, other)}
        r1, r2 = routes[first["role"]], routes[later["role"]]
        with self.assertRaises(SchedulingBlocked):
            Scheduler(spool, (r2,)).recover_next()
        sup = launch.Supervisor(r2.launch_spec(True))
        endpoint, inv = sup.start_coordinated(Bootstrap(r2, (later["request_id"], later["version"])))
        self.assertIsNone(endpoint)
        self.assertEqual(self.report(inv.wait(25), True, r2)["outcome"], "HANDOFF_UNCERTAIN")
        self.assertEqual(spool.list_metadata(), [first, later])
        s = Scheduler(spool, (route, other))
        self.report(s.recover_next().wait(25), True, r1)
        rows = spool.list_metadata()
        self.assertEqual(rows[0]["classification"], sp.NC)
        self.assertEqual(rows[1], later)
        self.report(s.recover_next().wait(25), True, r2)
        self.assertEqual([r["classification"] for r in spool.list_metadata()], [sp.NC, sp.NC])
        self.assertEqual((self.count(route), self.count(other)), (0, 0))

    def test_bad_trusted_pin_and_session_no_admission(self):
        original, remote = tf.ActuatorTests.material_case(self)
        spool, route = self.route(original, remote, quotas(1))
        with self.assertRaises(Conflict):
            replace(route, session=replace(route.session, owner_generation=99))
        bad_pin = replace(route.pins.attempt, inode=(0, 0))
        wrong = replace(route, pins=replace(route.pins, attempt=bad_pin))
        with self.assertRaises(launch.LaunchError):
            Scheduler(spool, (wrong,)).start_ordinary(*route.key())
        self.assertEqual(spool.list_metadata(), [])
        self.assertEqual(self.count(route), 0)

    def test_supervisor_loss_does_not_release_child_pair_lock(self):
        original, remote = tf.ActuatorTests.material_case(self)
        spool, route = self.route(original, remote, quotas(1), fault="hold_marker")
        ctx = multiprocessing.get_context("fork")
        reader, sender = ctx.Pipe(False)
        libc = ctypes.CDLL(None, use_errno=True)
        old = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(old), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        def supervisor_work():
            reader.close()
            spawn = launch._spawn
            def capture(*args, **kwargs):
                p = spawn(*args, **kwargs)
                sender.send(p.pid)
                return p
            with patch.object(launch, "_spawn", side_effect=capture):
                self.ordinary(Scheduler(spool, (route,)), route, original)
        supervisor = ctx.Process(target=supervisor_work)
        pid = None
        fd = None
        try:
            supervisor.start()
            sender.close()
            self.assertTrue(reader.poll(10))
            pid = reader.recv()
            limit = time.monotonic()+10
            while time.monotonic() < limit:
                rows = spool.list_metadata()
                if rows and rows[0]["state"] == sp.MARKED:
                    break
                time.sleep(0.01)
            else:
                self.fail("writer child never marked")
            supervisor.kill()
            supervisor.join(5)
            self.assertFalse(supervisor.is_alive())
            fd = os.open(spool._path, os.O_RDONLY | os.O_CLOEXEC)
            with self.assertRaises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            pid = None
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.close(fd)
            fd = None
            self.assertEqual(spool.list_metadata()[0]["state"], sp.MARKED)
            self.assertEqual(self.count(route), 0)
            recovery = Scheduler(spool, (route,)).recover_next()
            self.report(recovery.wait(25), True, route)
            self.assertEqual(spool.list_metadata()[0]["classification"], sp.NC)
        finally:
            if fd is not None:
                os.close(fd)
            if supervisor.is_alive():
                supervisor.kill()
            supervisor.join(5)
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
            reader.close()
            sender.close()
            libc.prctl(36, old.value, 0, 0, 0)


if __name__ == "__main__":
    unittest.main()
