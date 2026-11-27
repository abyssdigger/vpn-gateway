import os
import socket
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from v2_writer_containment import (Generation, Pin, Unavailable, pin, preflight,
                                   resolve_cgroup_path)
from v2_containment_gate import GateRejected, await_release

MOUNT = '59 20 0:24 / /sys/fs/cgroup rw,nosuid,nodev,noexec - cgroup2 cgroup rw\n'
ROOT = '/sys/fs/cgroup/b1-delegated'
MEMBER = '0::/manager\n'
REQUIRED = frozenset({'cpu', 'memory', 'pids'})


class MountIdentityTests(unittest.TestCase):
    def test_sibling(self):
        root, manager = resolve_cgroup_path(MOUNT, MEMBER, ROOT, 59)
        self.assertEqual(str(root), '/b1-delegated')
        self.assertEqual(str(manager), '/manager')

    def test_unsafe_paths(self):
        for path in ['/sys/fs/cgroup', '/sys/fs/cgroup/manager',
                     '/sys/fs/cgroup/manager/../foreign', '/tmp/foreign']:
            with self.subTest(path=path), self.assertRaises(Unavailable):
                resolve_cgroup_path(MOUNT, MEMBER, path, 59)
        with self.assertRaises(Unavailable):
            resolve_cgroup_path(MOUNT, '0::/b1-delegated/manager\n', ROOT, 59)

    def test_ambiguous_views(self):
        for mounts, member, mount_id in [
            (MOUNT.replace('rw,nosuid', 'ro,nosuid'), MEMBER, 59),
            (MOUNT.replace('0:24 / ', '0:24 /delegated '), MEMBER, 59),
            (MOUNT + MOUNT, MEMBER, 59),
            (MOUNT, MEMBER, 60),
            (MOUNT, MEMBER + '1:cpu:/other\n', 59),
            (MOUNT + '60 20 0:25 / /other rw - cgroup cgroup rw\n', MEMBER, 59),
        ]:
            with self.subTest(mounts=mounts, member=member, mount_id=mount_id), self.assertRaises(Unavailable):
                resolve_cgroup_path(mounts, member, ROOT, mount_id)

    def test_pin_mismatch_before_mutation(self):
        fd = os.open('/tmp', os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            p = pin(fd)
            with patch('v2_writer_containment.os.mkdir') as mkdir:
                with self.assertRaises(Unavailable):
                    Generation(fd, Pin(p.dev, p.ino + 1, p.mount_id), REQUIRED)
                mkdir.assert_not_called()
        finally:
            os.close(fd)

    def test_read_only_actual_mount_before_mutation(self):
        fd = os.open('/sys/fs/cgroup', os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if not os.fstatvfs(fd).f_flag & os.ST_RDONLY:
                self.skipTest('this negative case specifically requires a read-only cgroup mount')
            with patch('v2_writer_containment.os.mkdir') as mkdir:
                with self.assertRaisesRegex(Unavailable, 'read-only'):
                    Generation(fd, pin(fd), REQUIRED)
                mkdir.assert_not_called()
        finally:
            os.close(fd)


class ReleaseTests(unittest.TestCase):
    def test_closed_tokens(self):
        for token in [b'RELEASE', b'RELEAS', b'RELEASE\0', b'RELEASE'*100, None, False]:
            with self.subTest(token=token):
                a,b = socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
                with a,b:
                    if token is None:
                        b.close()
                    elif token is not False:
                        b.send(token)
                    if token == b'RELEASE':
                        await_release(a,time.monotonic()+0.2)
                    else:
                        with self.assertRaises(GateRejected):
                            await_release(a,time.monotonic()+0.02)

    def test_stream_not_admitted(self):
        a,b = socket.socketpair()
        with a,b,self.assertRaises(GateRejected):
            await_release(a,time.monotonic()+0.2)

    def test_expired_deadline(self):
        a,b = socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        with a,b,self.assertRaises(GateRejected):
            b.send(b'RELEASE')
            await_release(a,time.monotonic()-1)


class AdoptedReapTests(unittest.TestCase):
    def test_adopted_descendant_pidfd_and_reap(self):
        # Dedicated subprocess avoids changing subreaper state of unittest runner.
        code = r"""
import ctypes, os, select
libc = ctypes.CDLL(None, use_errno=True)
assert libc.prctl(36, 1, 0, 0, 0) == 0  # PR_SET_CHILD_SUBREAPER
report_r, report_w = os.pipe()
release_r, release_w = os.pipe()
parent = os.fork()
if parent == 0:
    os.close(report_r); os.close(release_w)
    grandchild = os.fork()
    if grandchild == 0:
        os.close(report_w)
        token = os.read(release_r, 1)
        os._exit(23 if token == b'R' else 24)
    os.write(report_w, str(grandchild).encode('ascii'))
    os._exit(0)
os.close(report_w); os.close(release_r)
try:
    assert select.select([report_r], [], [], 2)[0]
    grandchild = int(os.read(report_r, 32))
    assert os.waitpid(parent, 0) == (parent, 0)
    with open(f'/proc/{grandchild}/status') as f:
        fields = dict(x.rstrip().split(':', 1) for x in f if ':' in x)
    assert int(fields['PPid']) == os.getpid()
    # This process is now the reaper and the child is held on a private pipe.
    fd = os.pidfd_open(grandchild)
    try:
        assert os.write(release_w, b'R') == 1
        poll = select.poll(); poll.register(fd, select.POLLIN)
        assert poll.poll(2000)
        observed = os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOWAIT | os.WNOHANG)
        assert observed.si_pid == grandchild and observed.si_status == 23
        reaped = os.waitid(os.P_PIDFD, fd, os.WEXITED)
        assert reaped.si_pid == grandchild and reaped.si_status == 23
        try: os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG)
        except ChildProcessError: pass
        else: raise AssertionError('child not reaped')
    finally: os.close(fd)
finally:
    os.close(release_w); os.close(report_r)
"""
        p = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True,
                           text=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)


class GateIntegrationTests(unittest.TestCase):
    def test_placed_closed_frames(self):
        from v2_containment_gate import await_placed
        for token in [b'PLACED',b'PLACED\x00',b'PLACED'*100,b'',None]:
            with self.subTest(token=token):
                a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
                with a,b:
                    if token is None: b.close()
                    else: b.send(token)
                    if token==b'PLACED': await_placed(a,time.monotonic()+.1)
                    else:
                        with self.assertRaises(GateRejected): await_placed(a,time.monotonic()+.1)

    def test_bad_placement_never_releases_or_execs(self):
        from v2_containment_gate import gate_main
        a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        fd=os.open('/dev/null',os.O_RDONLY)
        with a,b,patch('v2_containment_gate.os.execve') as execute:
            try:
                with self.assertRaises(OSError): gate_main(-1,fd,a,time.monotonic()+.1)
                execute.assert_not_called()
            finally: os.close(fd)

    def test_failed_membership_never_emits_placed(self):
        from v2_containment_gate import gate_main
        a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        fd=os.open('/dev/null',os.O_WRONLY)
        with a,b,patch('v2_writer_containment.exact_membership',side_effect=Unavailable('bad')),patch('v2_containment_gate.os.execve') as execute:
            with self.assertRaises(Unavailable): gate_main(-1,fd,a,time.monotonic()+.1)
            execute.assert_not_called()
            b.setblocking(False)
            with self.assertRaises(BlockingIOError): b.recv(32)

    def test_bounded_report(self):
        from v2_writer_containment import _read_report
        for msg in [b'PARENT:21\nCHILD:22\n',b'PARENT:21\nCHILD:22\nextra',b'X'*129,b'CHILD:1\n']:
            with self.subTest(msg=msg):
                r,w=os.pipe()
                try:
                    os.write(w,msg);os.close(w);w=-1
                    if msg==b'PARENT:21\nCHILD:22\n':
                        self.assertEqual(_read_report(r,time.monotonic()+.1),(21,22))
                    else:
                        with self.assertRaises(Unavailable): _read_report(r,time.monotonic()+.1)
                finally:
                    os.close(r)
                    if w>=0: os.close(w)

    def test_parent_placement_gate_and_rejected_release_cleanup(self):
        # Real fork, seqpacket, pidfd and reap; generation/control writes and
        # cgroup membership are explicitly simulated. Never a positive cgroup proof.
        # -S avoids startup hooks that can create threads in the test owner.
        code = r"""
import os, socket
from unittest.mock import patch
import v2_writer_containment as m
import v2_containment_gate as gate
owner=os.getpid()
for case in ('parent-reject','eof','invalid','timeout'):
    calls=[]; sends=[]
    class FakeGeneration:
        def __init__(self,*args):
            self.fd=os.open('/dev/null',os.O_RDONLY|os.O_CLOEXEC)
            self.identity=m.Pin(1,2,3); self.removed=False; self.quarantined=False
        def open_placement(self): return os.open('/dev/null',os.O_WRONLY|os.O_CLOEXEC)
        def _verify(self): calls.append('verify')
        def kill_owned(self): calls.append('exact-kill')
        def remove_empty(self,reaper):
            reaper.verify_drained(self.identity)
            assert len(reaper.reaped)==1
            calls.append('reap-and-remove'); self.removed=True; os.close(self.fd)
        def close_handles(self): calls.append('close'); os.close(self.fd)
        def empty(self): raise AssertionError('unexpected positive probe')
    def member(gen,pid,pidfd):
        if case=='parent-reject' and pid!=os.getpid():
            raise m.Unavailable('independent parent membership rejected')
    original_send=socket.socket.send
    def send(self,data,*args,**kwargs):
        if os.getpid()==owner: sends.append(data)
        return original_send(self,data,*args,**kwargs)
    with patch.object(m,'Generation',FakeGeneration),patch.object(m,'exact_membership',member),patch.object(m,'preflight'),patch.object(m,'verify_empty_root'),patch.object(m.os,'geteuid',return_value=0),patch.object(socket.socket,'send',send),patch.object(gate,'drop_probe_privileges',side_effect=AssertionError('unexpected release')):
        if case=='parent-reject':
            try: m.run_generation(-1,m.Pin(1,2,3),frozenset({'cpu'}))
            except m.Unavailable as exc: assert str(exc)=='independent parent membership rejected',str(exc)
            else: raise AssertionError('invalid release')
        else:
            row=m.run_generation(-1,m.Pin(1,2,3),frozenset({'cpu'}),case=case)
            assert row['case']==case and row['reaped']==1 and row['removed'] is True
            assert row['probe_report_verified'] is False
            assert row['reap_statuses']==[[os.CLD_EXITED,43]]
    assert sends==([b'INVALID'] if case=='invalid' else []),sends
    assert calls==(['verify'] if case=='parent-reject' else ['verify','verify'])+['exact-kill','reap-and-remove'],calls
    try: os.waitid(os.P_ALL,0,os.WEXITED|os.WNOHANG|os.WNOWAIT)
    except ChildProcessError: pass
    else: raise AssertionError('leaked child')
"""
        result=subprocess.run([sys.executable,'-S','-c',code],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_reap_known_child_when_generation_cleanup_rejected(self):
        # Actual direct child/reap; no cgroup writes, no privileged exec.
        code = r"""
import os
from unittest.mock import patch
import v2_writer_containment as m
import v2_containment_gate as gate
children=[]; calls=[]; gens=[]
class FakeGeneration:
    def __init__(self,*args):
        self.fd=os.open('/dev/null',os.O_RDONLY|os.O_CLOEXEC)
        self.identity=m.Pin(1,2,3); self.removed=False; self.quarantined=False
        gens.append(self)
    def open_placement(self): return os.open('/dev/null',os.O_WRONLY|os.O_CLOEXEC)
    def _verify(self): pass
    def kill_owned(self): calls.append('kill-rejected'); raise m.Unavailable('custody lost')
    def remove_empty(self,reaper): raise AssertionError('unsafe removal')
    def close_handles(self): calls.append('close'); os.close(self.fd)
def member(gen,pid,pidfd):
    if pid!=os.getpid():
        children.append(pid); raise m.Unavailable('parent rejected')
with patch.object(m,'Generation',FakeGeneration),patch.object(m,'exact_membership',member),patch.object(m.os,'geteuid',return_value=0),patch.object(gate,'drop_probe_privileges',side_effect=AssertionError('unexpected release')):
    try: m.run_generation(-1,m.Pin(1,2,3),frozenset({'cpu'}))
    except m.Unavailable as exc: assert str(exc)=='custody lost',str(exc)
    else: raise AssertionError('cleanup unexpectedly succeeded')
assert len(gens)==1 and gens[0].quarantined and not gens[0].removed
assert calls==['kill-rejected','close'],calls
try: os.waitid(os.P_ALL,0,os.WEXITED|os.WNOHANG|os.WNOWAIT)
except ChildProcessError: pass
else:
    # Test teardown only: known direct child, no numeric PID signal.
    for pid in children:
        try: os.waitpid(pid,0)
        except ChildProcessError: pass
    raise AssertionError('known child was not reaped after rejected cleanup')
"""
        result=subprocess.run([sys.executable,'-S','-c',code],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_multithreaded_owner_rejects_before_generation(self):
        import threading
        from v2_writer_containment import run_generation
        ready, done = threading.Event(), threading.Event()
        def worker():
            ready.set(); done.wait(3)
        thread=threading.Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(ready.wait(1))
            with patch('v2_writer_containment.os.geteuid',return_value=0),patch('v2_writer_containment.Generation') as create:
                with self.assertRaisesRegex(Unavailable,'invalid trusted test owner'):
                    run_generation(-1,Pin(1,2,3),REQUIRED)
                create.assert_not_called()
        finally:
            done.set(); thread.join(2)
        self.assertFalse(thread.is_alive())

    def test_generation_run_actual_readonly_rejects_before_fork(self):
        from v2_writer_containment import run_generation
        if os.geteuid()!=0: self.skipTest('requires root to reach preflight')
        fd=os.open('/sys/fs/cgroup',os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            if not os.fstatvfs(fd).f_flag & os.ST_RDONLY: self.skipTest('read-only mount needed')
            # DedicatedReaper is tested separately; no mutation to test runner subreaper.
            with patch('v2_writer_containment.DedicatedReaper'),patch('v2_writer_containment.os.fork') as fork,patch('v2_writer_containment.os.mkdir') as mkdir,patch('v2_writer_containment.os.listdir',return_value=['mock-single-thread']):
                with self.assertRaisesRegex(Unavailable,'read-only'): run_generation(fd,pin(fd),REQUIRED)
                fork.assert_not_called(); mkdir.assert_not_called()
        finally: os.close(fd)


class DedicatedOwnerTests(unittest.TestCase):
    def test_reaper_actual_direct_and_adopted(self):
        # Run the real new reaper in a clean dedicated parent. No cgroup
        # action, no numerical PID signal, no unrelated-child reap.
        code = """
import os,time
from v2_writer_containment import DedicatedReaper,Pin
r=DedicatedReaper()
pid=os.fork()
if pid==0:
    if os.fork()==0:
        time.sleep(.1); os._exit(23)
    os._exit(0)
r.bind(pid,Pin(1,2,3))
assert not r.drained
r.drain(time.monotonic()+2)
assert r.drained and len(r.reaped)==2
assert r.statuses[pid]==(os.CLD_EXITED,0)
assert sorted(x[1] for x in r.statuses.values())==[0,23]
r.close()
"""
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_reaper_rejects_unrelated_child(self):
        code="""
import os,time
from v2_writer_containment import DedicatedReaper,Unavailable
pid=os.fork()
if pid==0:
    time.sleep(.15); os._exit(0)
try:
    try: DedicatedReaper()
    except Unavailable: pass
    else: raise AssertionError('owner admitted with existing child')
finally: os.waitpid(pid,0)
"""
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_strict_runner_rejects_namespace_mismatch(self):
        from run_v2_containment_evidence import main,namespace_ids
        from contextlib import redirect_stdout
        import io,json
        fd=os.open('/sys/fs/cgroup',os.O_DIRECTORY)
        try:
            p=pin(fd); n=list(namespace_ids());n[0]+=1
            out=io.StringIO()
            with redirect_stdout(out),patch('run_v2_containment_evidence.run_generation') as run:
                rc=main(['--root-fd',str(fd),'--root-pin',*map(str,(p.dev,p.ino,p.mount_id)), '--namespace-pins',*map(str,n),'--source-commit','0'*40])
                run.assert_not_called()
            self.assertEqual(rc,2)
            self.assertEqual(json.loads(out.getvalue())['completed'],0)
        finally: os.close(fd)

class GenerationFenceTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.root_fd = os.open(self.root, os.O_DIRECTORY)
        self.addCleanup(os.close, self.root_fd)
        os.mkdir(self.root + '/owned')
        gen = Generation.__new__(Generation)
        gen.root_fd = os.dup(self.root_fd)
        gen.fd = os.open('owned', os.O_DIRECTORY, dir_fd=self.root_fd)
        gen.name = 'owned'
        gen.expected = pin(gen.root_fd)
        gen.identity = pin(gen.fd)
        gen.required = REQUIRED
        gen.quarantined = gen.removed = False
        self.gen = gen
        self.addCleanup(gen.close_handles)
        fake = patch('v2_writer_containment.preflight')
        fake.start(); self.addCleanup(fake.stop)

    def assert_no_kill(self):
        # Pure fence test, never opens/writes an actual cgroup control.
        with patch.object(self.gen, '_open_write_control') as op:
            with self.assertRaises(Unavailable): self.gen.kill_owned()
            op.assert_not_called()
        self.assertTrue(self.gen.quarantined)
        with self.assertRaises(Unavailable): self.gen._verify()

    def test_substituted_name_same_mount(self):
        os.rename(self.root + '/owned', self.root + '/parked')
        os.mkdir(self.root + '/owned')
        # Same inventory name, old pinned inode is now unlinked.
        os.rmdir(self.root + '/parked')
        self.assert_no_kill()

    def test_unexpected_sibling(self):
        os.mkdir(self.root + '/foreign')
        self.assert_no_kill()

    def test_observed_custody_loss_stays_quarantined(self):
        os.mkdir(self.root + '/foreign')
        with self.assertRaises(Unavailable): self.gen.open_placement()
        self.assertTrue(self.gen.quarantined)
        os.rmdir(self.root + '/foreign')
        with patch.object(self.gen, '_open_write_control') as op:
            with self.assertRaises(Unavailable): self.gen.kill_owned()
            op.assert_not_called()

    def test_observation_custody_loss_stays_quarantined(self):
        os.mkdir(self.root + '/foreign')
        with self.assertRaises(Unavailable): self.gen.empty()
        os.rmdir(self.root + '/foreign')
        self.assert_no_kill()

    def test_placement_control_failure_stays_quarantined(self):
        with patch.object(self.gen, '_open_write_control', side_effect=OSError('unavailable')):
            with self.assertRaises(OSError): self.gen.open_placement()
        self.assertTrue(self.gen.quarantined)
        self.assert_no_kill()

    def test_unexpected_nested_generation(self):
        os.mkdir(self.root + '/owned/foreign')
        self.assert_no_kill()

    def test_symlink_entry(self):
        os.symlink('/tmp', self.root + '/link')
        self.assert_no_kill()

    def test_wrong_reap_generation_never_removes(self):
        from v2_writer_containment import DedicatedReaper
        r = DedicatedReaper.__new__(DedicatedReaper)
        r.owner = os.getpid()
        r.generation = Pin(0, 0, 0)
        with patch('v2_writer_containment.os.rmdir') as remove:
            with self.assertRaises(Unavailable): self.gen.remove_empty(r)
            remove.assert_not_called()
        self.assertTrue(self.gen.quarantined)
        self.assertFalse(self.gen.removed)

    def test_reap_rechecked_after_drain(self):
        code = r"""
import os,time
from v2_writer_containment import DedicatedReaper,Pin,Unavailable
r=DedicatedReaper(); g=Pin(1,2,3)
p=os.fork()
if p==0: os._exit(0)
r.bind(p,g); r.drain(time.monotonic()+2); r.verify_drained(g)
p=os.fork()
if p==0: time.sleep(.1); os._exit(0)
try:
    try: r.verify_drained(g)
    except Unavailable: pass
    else: raise AssertionError('stale drain accepted')
finally:
    os.waitpid(p,0); r.close()
"""
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)


class EvidenceInventoryTests(unittest.TestCase):
    def test_closed_case_evidence(self):
        import copy, signal
        from run_v2_containment_evidence import verify_case, CASES
        for case in CASES:
            success = case == 'release'
            row = {'case': 'released' if success else case, 'reaped': 2 if success else 1,
                   'removed': True, 'placement_verified': True,
                   'adopted_membership_verified': success, 'probe_report_verified': success,
                   'root_empty_verified': True,
                   'reap_statuses': sorted([[os.CLD_EXITED, 0], [os.CLD_KILLED, int(signal.SIGKILL)]])
                                    if success else [[os.CLD_EXITED, 43]]}
            verify_case(case, row)
            for key in row:
                with self.subTest(case=case, missing=key), self.assertRaises(Unavailable):
                    verify_case(case, {k:v for k,v in row.items() if k != key})
            for key, val in [('removed', 1), ('reaped', True), ('placement_verified', False),
                             ('root_empty_verified', False), ('reap_statuses', [[os.CLD_EXITED, 41]])]:
                with self.subTest(case=case, invalid=key), self.assertRaises(Unavailable):
                    bad=copy.deepcopy(row); bad[key]=val; verify_case(case,bad)
            with self.assertRaises(Unavailable): verify_case(case,{**row,'unexpected':True})

    def test_verify_empty_root_rejects_invalid_events(self):
        from v2_writer_containment import verify_empty_root
        with patch('v2_writer_containment.child_directories',return_value=set()):
            for events in ['populated 1\n','populated 0\npopulated 1\n','populated 0\npopulated 0\n','populated 0\npopulated 2\n','populated 0\npopulated\n','']:
                with patch('v2_writer_containment.read_control',return_value=events),self.assertRaises(Unavailable):
                    verify_empty_root(-1)
            with patch('v2_writer_containment.read_control',return_value='populated 0\nfrozen 0\n'):
                verify_empty_root(-1)


class StableProcessIdentityTests(unittest.TestCase):
    def test_pidfd_wrong_numeric_pid(self):
        from v2_writer_containment import exact_membership
        fd = os.pidfd_open(os.getpid())
        try:
            with self.assertRaisesRegex(Unavailable, 'pidfd not bound'):
                exact_membership(-1, os.getpid()+1, fd)
        finally:
            os.close(fd)

    def test_pidfd_observed_exit_not_live_membership(self):
        code = r"""
import os,select
from v2_writer_containment import exact_membership,Unavailable
pid=os.fork()
if pid==0: os._exit(0)
fd=os.pidfd_open(pid)
try:
    poll=select.poll(); poll.register(fd,select.POLLIN)
    assert poll.poll(2000)
    try: exact_membership(-1,pid,fd)
    except Unavailable as exc: assert 'pidfd not bound' in str(exc)
    else: raise AssertionError('dead pidfd accepted')
    # Rejected membership has not reaped the child.
    row=os.waitid(os.P_PIDFD,fd,os.WEXITED|os.WNOWAIT|os.WNOHANG)
    assert row.si_pid==pid
finally:
    os.waitpid(pid,0); os.close(fd)
"""
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)



class SystemdVehicleTests(unittest.TestCase):
    def test_bad_unit_or_commit_rejects_before_service_or_mutation(self):
        import contextlib, io, json
        from run_v2_containment_evidence import provision_systemd
        for unit, sha in [('../system.slice', 'a'*40),
                          ('vpng-b1-1-1Xservice', 'a'*40),
                          ('vpng-b1-0-1.service', 'a'*40),
                          ('vpng-b1-1-1.service', 'main')]:
            with self.subTest(unit=unit, sha=sha), \
                    patch('run_v2_containment_evidence._systemctl') as systemctl, \
                    patch('run_v2_containment_evidence.os.mkdir') as mkdir, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(provision_systemd(unit, sha), 2)
                self.assertEqual(json.loads(output.getvalue())['phase'], 'service-identity')
                systemctl.assert_not_called()
                mkdir.assert_not_called()

    def test_delegation_missing_or_internal_process_never_opens_write(self):
        from run_v2_containment_evidence import _enable_required
        for observations in [('cpu memory',), ('cpu memory pids', '123')]:
            with self.subTest(observations=observations), \
                    patch('run_v2_containment_evidence.read_control', side_effect=observations), \
                    patch('run_v2_containment_evidence.os.open') as op:
                with self.assertRaises(Unavailable):
                    _enable_required(99)
                op.assert_not_called()

    def test_already_delegated_is_read_only(self):
        from run_v2_containment_evidence import _enable_required
        with patch('run_v2_containment_evidence.read_control',
                   side_effect=['cpu memory pids', '', 'cpu memory pids', 'cpu memory pids']), \
                patch('run_v2_containment_evidence.os.open') as op:
            _enable_required(99)
            op.assert_not_called()

    def test_delegates_only_missing_required_controllers(self):
        import stat
        from types import SimpleNamespace
        from run_v2_containment_evidence import _enable_required
        with patch('run_v2_containment_evidence.read_control',
                   side_effect=['cpu memory pids io', '', 'cpu io', 'cpu io memory pids']), \
                patch('run_v2_containment_evidence.os.open', return_value=100) as op, \
                patch('run_v2_containment_evidence.os.fstat',
                      return_value=SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o644)), \
                patch('v2_writer_containment.pin', return_value=Pin(1, 2, 3)), \
                patch('run_v2_containment_evidence.os.write', return_value=13) as write, \
                patch('run_v2_containment_evidence.os.close') as close:
            _enable_required(99)
            op.assert_called_once_with('cgroup.subtree_control',
                 os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=99)
            write.assert_called_once_with(100, b'+memory +pids')
            close.assert_called_once_with(100)



if __name__ == '__main__':
    unittest.main()
