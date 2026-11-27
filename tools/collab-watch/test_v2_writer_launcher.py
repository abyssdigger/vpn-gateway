"""Staged process boundary tests. No GitHub transport or live credentials."""
from dataclasses import replace
import hashlib
import math
import os
from pathlib import Path
import signal
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import v2_writer_ipc as ipc
import v2_writer_launcher as launch
from v2_writer_child import worker_report

MIB = 1024 * 1024
OK = {"state": "RESULT", "result": {"state": "NO_ATTEMPT", "code": "TRUSTED_INGRESS_REJECTED", "action_key": None}}
UNCERTAIN = {"state": "HANDOFF_UNCERTAIN"}


def spec(**changes):
    return replace(launch.LaunchSpec(ipc.SessionBinding("GUARD", "g", 1, "s"),
                   ("owner", "runtime", "attempt", "input"),
                   launch.Limits(512*MIB, 5, 64, 10), 12), **changes)


def exchange(client, invocation, text="dummy"):
    return ipc.exchange(client, dict(original=text, reconcile_only=False), deadline=invocation.deadline)


class LauncherTests(unittest.TestCase):
    def test_closed_spec(self):
        for changes in ({"wall_seconds": math.inf}, {"wall_seconds": True}, {"wall_seconds": 0},
                        {"stores": ("owner", "runtime", "attempt", "owner")},
                        {"stores": ("owner", "runtime", "attempt", "a\n")},
                        {"probe": "arbitrary command"}, {"session": {}}, {"limits": {}}):
            with self.subTest(changes=changes), self.assertRaises(launch.LaunchError):
                spec(**changes)
        for key in ("env", "cwd", "argv", "executable", "pass_fds", "credential"):
            with self.assertRaises(TypeError):
                spec(**{key: "untrusted"})
        for values in ((True, 2, 32, 2), (512*MIB, 0, 32, 2), (512*MIB, 2, 4, 2)):
            with self.assertRaises(launch.LaunchError):
                launch.Limits(*values)
        with self.assertRaises(launch.LaunchError):
            launch.Isolation(61001, 61001, 61001, 61002)

    def test_single_slot_and_endpoint_pin(self):
        supervisor = launch.Supervisor(spec())
        client, run = supervisor.start()
        with client:
            duplicate = client.dup()
            with self.assertRaises(launch.Busy):
                supervisor.start()
            self.assertEqual(exchange(duplicate, run, '{"role":"BUILDER","owner_generation":999}'), OK)
            done = run.wait(15)
        self.assertTrue(done.reaped and done.entered)
        self.assertEqual(done.writer_status, 0)
        self.assertEqual(len(done.report["setup"]["fds"]), 5)
        self.assertEqual(done.report["setup"]["dumpable"], 0)
        self.assertEqual(done.report["setup"]["nnp"], 1)
        client2, run2 = supervisor.start()
        self.assertEqual(exchange(client2, run2), OK)
        self.assertEqual(run2.wait(15).report["pin"], done.report["pin"])
        new = launch.Supervisor(spec(session=ipc.SessionBinding("GUARD", "g", 2, "s2")))
        c, r = new.start()
        self.assertEqual(exchange(c, r), OK)
        self.assertNotEqual(r.wait(15).report["pin"], done.report["pin"])

    def test_worker_abrupt_eof(self):
        for first in (False, True):
            with self.subTest(worker_first=first):
                sup = launch.Supervisor(spec(probe="worker"))
                done = sup.start_pair(worker_first=first, abrupt_worker=True).wait(15)
                self.assertTrue(done.reaped)
                self.assertFalse(done.timed_out or done.entered)
                self.assertEqual(done.worker_status, 20)
                self.assertEqual(done.report["outcome"], "INGRESS_REJECTED")
                normal = sup.start_pair(worker_first=first).wait(15)
                self.assertEqual((normal.writer_status, normal.worker_status), (0, 0))
                self.assertTrue(normal.entered)

    def test_partial_launch_in_both_orders(self):
        real = launch._spawn
        for worker_first, fail in ((False, "worker"), (True, "writer")):
            sup = launch.Supervisor(spec(probe="worker"))
            started = []
            def inject(kind, *args):
                if kind == fail:
                    raise OSError("synthetic spawn fault")
                proc = real(kind, *args)
                started.append(proc)
                return proc
            with patch.object(launch, "_spawn", side_effect=inject), self.assertRaises(launch.LaunchError):
                sup.start_pair(worker_first=worker_first)
            self.assertEqual(len(started), 1)
            self.assertIsNotNone(started[0].returncode)
            done = sup.start_pair().wait(15)
            self.assertEqual((done.writer_status, done.worker_status), (0, 0))

    def test_interrupted_watcher_start_cannot_release_next_invocation(self):
        sup = launch.Supervisor(spec())
        real_start = threading.Thread.start
        release = threading.Event()
        interrupted = []

        def start_then_interrupt(thread):
            target = thread._target
            def delayed():
                release.wait(5)
                target()
            thread._target = delayed
            real_start(thread)
            interrupted.append(thread)
            raise KeyboardInterrupt("injected after actual thread start")

        self.addCleanup(release.set)
        with patch.object(threading.Thread, "start", start_then_interrupt), self.assertRaises(launch.LaunchError):
            sup.start()
        self.assertEqual(len(interrupted), 1)
        client, run = sup.start()
        with client:
            release.set()
            interrupted[0].join(5)
            self.assertFalse(interrupted[0].is_alive())
            self.assertFalse(run._done.is_set())
            # The old watcher must not release the second invocation's slot.
            with self.assertRaises(launch.Busy):
                sup.start()
            self.assertEqual(exchange(client.dup(), run), OK)
            self.assertTrue(run.wait(15).reaped)
        c, r = sup.start()
        self.assertEqual(exchange(c, r), OK)
        self.assertTrue(r.wait(15).reaped)

    def test_crash_and_wall_no_retry(self):
        for probe, deadline in (("crash", 12), ("wall", 2)):
            with self.subTest(probe=probe):
                sup = launch.Supervisor(spec(probe=probe, wall_seconds=deadline))
                c, r = sup.start()
                self.assertEqual(exchange(c, r), UNCERTAIN)
                done = r.wait(15)
                self.assertTrue(done.reaped and done.entered)
                self.assertEqual(done.timed_out, probe == "wall")
                self.assertEqual(done.writer_status, -signal.SIGKILL if probe == "wall" else 23)
                # A distinct explicit launch is permitted only after reaping; never automatic resend.
                c, r = sup.start()
                c.close()
                self.assertFalse(r.wait(15).entered)

    def test_resource_failures(self):
        for probe, fault in (("memory", "MEMORY"), ("fd", "FD"), ("cpu", None)):
            with self.subTest(probe=probe):
                sup = launch.Supervisor(spec(probe=probe, limits=launch.Limits(256*MIB, 2, 32, 10)))
                c, r = sup.start()
                self.assertEqual(exchange(c, r), UNCERTAIN)
                done = r.wait(15)
                self.assertTrue(done.reaped and done.entered)
                self.assertFalse(done.timed_out)
                if fault:
                    self.assertEqual(done.report["fault"], fault)
                else:
                    self.assertEqual(done.writer_status, -signal.SIGKILL)
                    self.assertIsNone(done.report)

    def test_worker_report_rejects_raw_text(self):
        good = dict(uid=1, euid=1, gid=1, egid=1, groups=[], caps={k: 0 for k in
                    ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")}, nnp=1,
                    dumpable=1, fds=[0, 1, 2, 3], file_denied=True, proc_denied=True)
        self.assertEqual(worker_report(good), good)
        for changed in (dict(good, uid="dummy"), dict(good, groups=["dummy"]),
                        dict(good, caps={"dummy": 1}), dict(good, file_denied="dummy")):
            with self.assertRaises(RuntimeError):
                worker_report(changed)

    @unittest.skipUnless(os.geteuid() == 0, "requires privileged distinct UID/GID launch")
    def test_distinct_uid_dummy_isolation(self):
        # Reviewed installation itself must be readable but not writable by test UIDs.
        ids = launch.Isolation(61001, 61001, 61002, 61002)
        with tempfile.TemporaryDirectory() as tmp:
            os.chown(tmp, ids.writer_uid, ids.writer_gid)
            path = Path(tmp)/"dummy"
            dummy = os.urandom(24)
            path.write_bytes(dummy)
            os.chmod(path, 0o600)
            os.chown(path, ids.writer_uid, ids.writer_gid)
            sup = launch.Supervisor(spec(probe="worker", isolation=ids,
                    dummy=launch.DummyFile(str(path), hashlib.sha256(dummy).hexdigest())))
            with open("/dev/null", "rb") as unrelated, patch.dict(os.environ, {"VPNG_DUMMY_PARENT": "dummy"}):
                unrelated_fd = unrelated.fileno()
                os.set_inheritable(unrelated_fd, True)
                done = sup.start_pair().wait(15)
            self.assertEqual((done.writer_status, done.worker_status), (0, 0))
            self.assertTrue(done.reaped and done.entered)
            self.assertTrue(done.report["dummy_ok"] and done.report["argv_clean"])
            writer, worker = done.report["setup"], done.report["worker"]
            self.assertEqual((writer["uid"], writer["gid"], worker["uid"], worker["gid"]),
                             (61001, 61001, 61002, 61002))
            for report, fd_count in ((writer, 5), (worker, 4)):
                self.assertFalse(any(report["caps"].values()) or report["groups"])
                self.assertEqual(report["nnp"], 1)
                self.assertEqual(len(report["fds"]), fd_count)
                self.assertNotIn(unrelated_fd, report["fds"])
            self.assertTrue(worker["file_denied"] and worker["proc_denied"])
            self.assertEqual(writer["dumpable"], 0)

    def test_valid_large_frozen_actions(self):
        # Real accepted proof primitives, not padding an invalid request. No remote write.
        from test_project_tasks import row
        from test_split_journal import CFG, fixture
        from test_v2_aux import aux
        from test_v2_aux_actuator import original_for
        from v2_aux import project_aux
        from v2_compact import compact_aggregate_v2
        for flavor, body in (("ascii", "x"*65536), ("escaped", '\\"'*32768),
                             ("sparse_non_bmp", "x"*65535+chr(0x1f642))):
            with self.subTest(flavor=flavor):
                rows, task = fixture()
                holder = [row(1000+i, 12, f"{i:04d} "+body, 25) for i in range(20)]
                previous = project_aux(CFG, {"34": rows}, {"42": task}, holder, [])[1]
                baseline = compact_aggregate_v2(CFG, {"34": rows}, {"42": task}, holder, [], previous)
                candidate = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
                original = original_for("aux_comment", baseline, candidate, previous)
                size = len(original.encode())
                self.assertGreater(size, MIB)
                sup = launch.Supervisor(spec(probe="bound", limits=launch.Limits(1024*MIB, 20, 128, 10), wall_seconds=30))
                c, r = sup.start()
                self.assertEqual(exchange(c, r, original), OK)
                done = r.wait(35)
                self.assertTrue(done.reaped and done.report["validated"])
                print(f"9b-B valid frozen {flavor}: bytes={size} rss_kib={done.report['rss_kib']} cpu_seconds={done.report['cpu_seconds']:.6f}", flush=True)


if __name__ == "__main__":
    unittest.main()
