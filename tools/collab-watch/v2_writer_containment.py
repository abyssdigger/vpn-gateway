"""B1 draft: read-only delegation preflight and pinned cgroup identity.

Local B1 development draft; no production admission is supplied.
"""
from __future__ import annotations

import os
import select
import signal
import socket
import time
import re
import stat
from dataclasses import dataclass
from pathlib import PurePosixPath


class Unavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Pin:
    dev: int
    ino: int
    mount_id: int


def pin(fd: int) -> Pin:
    st = os.fstat(fd)
    with open(f'/proc/self/fdinfo/{fd}', encoding='ascii') as stream:
        ids = [line.split()[1] for line in stream if line.startswith('mnt_id:')]
    if len(ids) != 1 or not ids[0].isdigit():
        raise Unavailable('ambiguous mount identity')
    return Pin(st.st_dev, st.st_ino, int(ids[0]))


def read_control(root_fd: int, name: str, limit: int = 65536) -> str:
    if name not in {'cgroup.type', 'cgroup.controllers', 'cgroup.subtree_control',
                    'cgroup.events', 'cgroup.procs'}:
        raise Unavailable('unexpected control name')
    fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=root_fd)
    try:
        if pin(fd).mount_id != pin(root_fd).mount_id:
            raise Unavailable('control on different mount')
        out = bytearray()
        while len(out) <= limit:
            part = os.read(fd, min(4096, limit + 1 - len(out)))
            if not part:
                return out.decode('ascii', errors='strict')
            out.extend(part)
        raise Unavailable('control exceeds bound')
    finally:
        os.close(fd)


def unescape_mount(s: str) -> str:
    return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), s)


def resolve_cgroup_path(mountinfo: str, membership: str, fd_path: str,
                        mount_id: int, *, membership_check: bool = False) -> tuple[PurePosixPath, PurePosixPath]:
    """Resolve only an unambiguous unified view; reject foreign/namespace roots.

    The deliberately restricted proof vehicle requires a visible hierarchy root
    at the mount root. This is not a generic cgroup namespace resolver.
    """
    entries = []
    for row in mountinfo.splitlines():
        pre, sep, post = row.partition(' - ')
        if not sep:
            raise Unavailable('malformed mountinfo')
        fields, fs = pre.split(), post.split()
        if len(fields) < 6 or len(fs) < 3:
            raise Unavailable('malformed mountinfo fields')
        if fs[0] == 'cgroup':
            raise Unavailable('mixed cgroup hierarchy')
        if fields[0] == str(mount_id):
            entries.append((fields, fs))
    if len(entries) != 1:
        raise Unavailable('mount not unique')
    fields, fs = entries[0]
    if fs[0] != 'cgroup2' or unescape_mount(fields[3]) != '/':
        raise Unavailable('not a visible unified hierarchy root')
    if 'rw' not in fields[5].split(',') or 'ro' in fields[5].split(','):
        raise Unavailable('read-only cgroup mount')
    rows = membership.splitlines()
    if len(rows) != 1 or not rows[0].startswith('0::/'):
        raise Unavailable('ambiguous manager membership')
    mountpoint = PurePosixPath(unescape_mount(fields[4]))
    path = PurePosixPath(fd_path)
    manager = PurePosixPath(rows[0][3:])
    if any(not p.is_absolute() or '..' in p.parts or str(p).startswith('//')
           for p in (path, manager, mountpoint)):
        raise Unavailable('ambiguous cgroup path')
    try:
        root = PurePosixPath('/') / path.relative_to(mountpoint)
    except ValueError as exc:
        raise Unavailable('fd outside mountpoint') from exc
    if (root == PurePosixPath('/') or
            (not membership_check and (root == manager or root in manager.parents))):
        raise Unavailable('unsafe root or manager ancestor')
    return root, manager


def preflight(root_fd: int, expected: Pin, required: frozenset[str]) -> Pin:
    """Check explicit trusted pin, not inferred authority from a supplied path.

    Caller must separately establish trusted exclusive delegated-root custody.
    """
    if not required or not required <= {'cpu', 'memory', 'pids'}:
        raise Unavailable('invalid controller requirements')
    actual = pin(root_fd)
    if actual != expected or not stat.S_ISDIR(os.fstat(root_fd).st_mode):
        raise Unavailable('root identity mismatch')
    if os.fstatvfs(root_fd).f_flag & os.ST_RDONLY:
        raise Unavailable('read-only cgroup mount')
    path = os.readlink(f'/proc/self/fd/{root_fd}')
    if path.endswith(' (deleted)'):
        raise Unavailable('root removed')
    with open('/proc/self/mountinfo', encoding='utf-8') as stream:
        mounts = stream.read()
    with open('/proc/self/cgroup', encoding='ascii') as stream:
        membership = stream.read()
    root, _ = resolve_cgroup_path(mounts, membership, path, actual.mount_id)
    if path != "/sys/fs/cgroup" + str(root):
        raise Unavailable('unsupported fixed evidence mount path')
    if read_control(root_fd, 'cgroup.type').strip() != 'domain':
        raise Unavailable('not a domain cgroup')
    if not required <= set(read_control(root_fd, 'cgroup.controllers').split()):
        raise Unavailable('required controllers unavailable')
    if not required <= set(read_control(root_fd, 'cgroup.subtree_control').split()):
        raise Unavailable('required controllers not delegated to descendants')
    if read_control(root_fd, 'cgroup.procs').strip():
        raise Unavailable('root contains processes')
    st = os.fstat(root_fd)
    if st.st_uid != 0 or st.st_mode & 0o022:
        raise Unavailable('root not protected from non-owner writes')
    if pin(root_fd) != expected or os.readlink(f'/proc/self/fd/{root_fd}') != path:
        raise Unavailable('root changed during preflight')
    return actual


def child_directories(fd: int) -> set[str]:
    # A symlink or unusual entry is not a trusted cgroup control file.
    result = set()
    for name in os.listdir(fd):
        mode = os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode
        if stat.S_ISDIR(mode):
            result.add(name)
        elif not stat.S_ISREG(mode):
            raise Unavailable('unexpected delegated-root entry')
    return result


def read_populated(fd: int) -> bool:
    rows = [line.split() for line in read_control(fd, 'cgroup.events').splitlines()]
    values = [row for row in rows if row and row[0] == 'populated']
    if len(values) != 1 or len(values[0]) != 2 or values[0][1] not in {'0', '1'}:
        raise Unavailable('invalid populated observation')
    return values[0][1] == '1'


def verify_empty_root(fd: int) -> None:
    if child_directories(fd):
        raise Unavailable('delegated root has existing descendants')
    if read_populated(fd):
        raise Unavailable('delegated root not empty')


# A generation is private to one trusted owner. No public path/kill API.
# Caller must guarantee no external privileged actor can rename, migrate into,
# or modify the delegated subtree while this object is live.
class Generation:
    def __init__(self, root_fd: int, expected: Pin, required: frozenset[str]):
        import uuid
        self.root_fd = os.dup(root_fd)
        self.fd = -1
        self.name = 'vpng-b1-' + uuid.uuid4().hex
        self.expected = expected
        self.required = required
        self.identity = None
        self.quarantined = False
        self.removed = False
        try:
            preflight(self.root_fd, self.expected, self.required)
            verify_empty_root(self.root_fd)
            # mkdir must succeed; never adopt an existing generation.
            os.mkdir(self.name, mode=0o700, dir_fd=self.root_fd)
            self.fd = os.open(self.name, os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                              dir_fd=self.root_fd)
            self.identity = pin(self.fd)
            self._verify()
            if read_control(self.fd, 'cgroup.procs').strip() or not self.empty():
                raise Unavailable('new generation not empty')
        except BaseException:
            # Do not delete an unverified or possibly foreign directory.
            self.quarantined = True
            self.close_handles()
            raise

    def _verify(self) -> None:
        if self.removed or self.quarantined or self.fd < 0 or self.identity is None:
            raise Unavailable('generation not operable')
        preflight(self.root_fd, self.expected, self.required)
        if self.identity.mount_id != self.expected.mount_id or pin(self.fd) != self.identity:
            raise Unavailable('generation pin mismatch')
        if child_directories(self.root_fd) != {self.name}:
            raise Unavailable('unexpected delegated-root generation inventory')
        if child_directories(self.fd):
            raise Unavailable('unexpected nested generation; quarantine')
        current = os.open(self.name, os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                          dir_fd=self.root_fd)
        try:
            if pin(current) != self.identity:
                raise Unavailable('generation path substituted')
        finally:
            os.close(current)

    def empty(self) -> bool:
        self._verify()
        return not read_populated(self.fd)

    def open_placement(self) -> int:
        self._verify()
        return self._open_write_control('cgroup.procs')

    def _open_write_control(self, name: str) -> int:
        if name not in {'cgroup.procs', 'cgroup.kill'}:
            raise Unavailable('unexpected mutation control')
        fd = os.open(name, os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.fd)
        try:
            if pin(fd).mount_id != self.identity.mount_id:
                raise Unavailable('control substituted')
            self._verify()
            return fd
        except BaseException:
            os.close(fd)
            raise

    def kill_owned(self) -> None:
        # Do not use PID enumeration or climb to a parent on failure.
        try:
            self._verify()
            fd = self._open_write_control('cgroup.kill')
            try:
                if os.write(fd, b'1') != 1:
                    raise Unavailable('short cgroup.kill write')
            finally:
                os.close(fd)
        except BaseException:
            self.quarantined = True
            raise

    def remove_empty(self, reaper: DedicatedReaper) -> None:
        # Dedicated owner, not an external caller assertion.
        try:
            if (type(reaper) is not DedicatedReaper or reaper.owner != os.getpid()
                    or reaper.generation != self.identity or not self.empty()):
                raise Unavailable('cleanup premises unmet')
            reaper.verify_drained(self.identity)
            self._verify()
            # No recursive rmdir: unexpected children cause quarantine.
            os.rmdir(self.name, dir_fd=self.root_fd)
            self.removed = True
        except BaseException:
            self.quarantined = True
            raise
        finally:
            self.close_handles()

    def close_handles(self) -> None:
        for attr in ('fd', 'root_fd'):
            fd = getattr(self, attr)
            if fd >= 0:
                os.close(fd)
                setattr(self, attr, -1)


def exact_membership(gen_fd: int, pid: int, pidfd: int) -> None:
    """Check live process and exact generation in the manager's unified view.

    The PID must belong to an unreaped direct/adopted child, or self. A pidfd
    is used to exclude exit across the observation; no numeric PID is signalled.
    """
    if type(pid) is not int or pid <= 0:
        raise Unavailable('invalid process identity')
    poll = select.poll()
    poll.register(pidfd, select.POLLIN)
    def live():
        with open(f'/proc/self/fdinfo/{pidfd}', encoding='ascii') as f:
            ids = [x.split()[1] for x in f if x.startswith('Pid:')]
        if ids != [str(pid)] or poll.poll(0):
            raise Unavailable('pidfd not bound to a live process')
    live()
    with open(f'/proc/{pid}/cgroup', encoding='ascii') as f:
        member = f.read()
    with open('/proc/self/mountinfo', encoding='utf-8') as f:
        mounts = f.read()
    path = os.readlink(f'/proc/self/fd/{gen_fd}')
    with open('/proc/self/cgroup', encoding='ascii') as f:
        own = f.read()
    expected, _ = resolve_cgroup_path(mounts, own, path, pin(gen_fd).mount_id,
                                      membership_check=pid==os.getpid())
    if member != f'0::{expected}\n':
        raise Unavailable('process not in exact generation')
    members = read_control(gen_fd, 'cgroup.procs').split()
    if str(pid) not in members:
        raise Unavailable('process absent from pinned generation')
    live()


class DedicatedReaper:
    """Single-purpose trusted owner with no unrelated children.

    Drained is established only by the actual ECHILD observation after reaping
    all adopted/direct children. This is not a general supervisor API.
    """
    def __init__(self):
        from v2_containment_gate import _prctl
        self.owner = os.getpid()
        self.generation = None
        self.direct = None
        self.pidfd = None
        self.reaped = []
        self.statuses = {}
        self.drained = False
        try:
            os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            pass
        else:
            raise Unavailable('dedicated owner already has children')
        _prctl(36, 1)

    def bind(self, pid, generation):
        if self.owner != os.getpid() or self.direct is not None:
            raise Unavailable('invalid direct child binding')
        self.direct = pid
        self.generation = generation
        self.pidfd = os.pidfd_open(pid)

    def drain(self, deadline):
        if self.owner != os.getpid() or self.pidfd is None:
            raise Unavailable('no bound direct child')
        while time.monotonic() < deadline:
            try:
                row = os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError:
                if self.direct not in self.reaped:
                    raise Unavailable('direct child not observed reaped')
                self.drained = True
                return
            if row is None:
                time.sleep(.01)
                continue
            # An observed waitable zombie cannot have its PID reused before reap
            # by this single-threaded dedicated parent. Bind a pidfd nonetheless.
            fd = self.pidfd if row.si_pid == self.direct else os.pidfd_open(row.si_pid)
            try:
                actual = os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG)
                if actual is None or actual.si_pid != row.si_pid:
                    raise Unavailable('reaping identity mismatch')
                self.reaped.append(actual.si_pid)
                self.statuses[actual.si_pid] = (int(actual.si_code), int(actual.si_status))
            finally:
                if fd != self.pidfd:
                    os.close(fd)
            if len(self.reaped) > 16:
                raise Unavailable('unexpected descendant count')
        raise Unavailable('bounded reap incomplete')

    def verify_drained(self, generation):
        if (self.owner != os.getpid() or self.generation != generation
                or not self.drained or self.pidfd is None
                or self.direct not in self.reaped):
            raise Unavailable('stale or absent reap evidence')
        try:
            os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            return
        raise Unavailable('child appeared after drain')

    def close(self):
        if self.pidfd is not None:
            os.close(self.pidfd)
            self.pidfd = None


def _read_report(fd, deadline):
    """Bounded exact report, no propagation of uncontrolled output."""
    data = bytearray()
    poll = select.poll()
    poll.register(fd, select.POLLIN | select.POLLHUP)
    while time.monotonic() < deadline:
        if not poll.poll(max(1, int((deadline-time.monotonic())*1000))):
            break
        block = os.read(fd, 129-len(data))
        if not block:
            break
        data.extend(block)
        if len(data)>128:
            raise Unavailable('probe report exceeds bound')
        if data.count(b'\n') >= 2:
            match = re.fullmatch(rb'PARENT:([1-9][0-9]{0,9})\nCHILD:([1-9][0-9]{0,9})\n',data)
            if not match:
                raise Unavailable('invalid probe report')
            return tuple(int(x) for x in match.groups())
    raise Unavailable('incomplete probe report')


def _adopted_member(pid, gen_fd, deadline):
    while time.monotonic() < deadline:
        try:
            with open(f'/proc/{pid}/status',encoding='ascii') as f:
                fields=dict(x.rstrip().split(':',1) for x in f if ':' in x)
            if int(fields['PPid']) == os.getpid():
                fd=os.pidfd_open(pid)
                try:
                    exact_membership(gen_fd,pid,fd)
                    return fd
                except BaseException:
                    os.close(fd)
                    raise
        except FileNotFoundError as exc:
            raise Unavailable('probe descendant absent') from exc
        time.sleep(.01)
    raise Unavailable('probe descendant not adopted')


def run_generation(root_fd, expected, required, *, case="release"):
    """Fixed B1 probe only, isolated single-purpose trusted owner.

    External trusted provisioner must pin and exclusively own root, namespace
    and interpreter. This does not establish those external premises.
    Failure quarantines; no reuse of foreign generations or fallback kill.
    """
    from v2_containment_gate import gate_main, await_placed, RELEASE, ReleaseRejected
    if case not in {"release", "eof", "invalid", "timeout"} or os.geteuid()!=0 or len(os.listdir('/proc/self/task'))!=1:
        raise Unavailable('invalid trusted test owner')
    reaper = DedicatedReaper()
    gen = Generation(root_fd,expected,required)
    placement = -1
    report_r = report_w = nullfd = -1
    peer = control = None
    descendant_fd = None
    launched = False
    placed = False
    outcome = None
    try:
        placement=gen.open_placement()
        report_r,report_w=os.pipe2(os.O_CLOEXEC)
        nullfd=os.open('/dev/null',os.O_RDWR|os.O_CLOEXEC)
        control,peer=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        deadline=time.monotonic()+3
        pid=os.fork()
        if pid==0:
            try:
                control.close()
                os.close(report_r)
                os.dup2(nullfd,0); os.dup2(report_w,1); os.dup2(nullfd,2)
                os.close(report_w); os.close(nullfd)
                gate_main(gen.fd,placement,peer,deadline)
            except ReleaseRejected:
                os._exit(43)
            except BaseException:
                os._exit(41)
            os._exit(42)
        launched=True
        reaper.bind(pid,gen.identity)
        peer.close(); peer=None
        os.close(placement); placement=-1
        os.close(report_w); report_w=-1
        os.close(nullfd); nullfd=-1
        await_placed(control,deadline)
        gen._verify()
        exact_membership(gen.fd,pid,reaper.pidfd)
        gen._verify()
        placed=True
        if case == "release":
            if control.send(RELEASE)!=len(RELEASE):
                raise Unavailable('short release')
            parent,descendant=_read_report(report_r,time.monotonic()+3)
            if parent!=pid or descendant==pid:
                raise Unavailable('unexpected probe identity')
            descendant_fd=_adopted_member(descendant,gen.fd,time.monotonic()+2)
            # The direct parent exited, the adopted descendant is still live.
            if gen.empty():
                raise Unavailable('unexpected empty generation')
            outcome='released'
        else:
            if case == 'eof':
                control.close(); control=None
            elif case == 'invalid':
                if control.send(b'INVALID') != len(b'INVALID'):
                    raise Unavailable('short invalid frame')
            # In timeout case do not send/close before observing exit.
            # None of these paths may enter the probe.
            poll=select.poll(); poll.register(reaper.pidfd,select.POLLIN)
            if not poll.poll(3500):
                raise Unavailable('gate did not exit after rejected release')
            os.set_blocking(report_r,False)
            if os.read(report_r,1):
                raise Unavailable('probe executed after rejected release')
            outcome=case
    finally:
        if control is not None: control.close()
        if peer is not None: peer.close()
        for fd in (placement,report_w,nullfd,descendant_fd):
            if fd is not None and fd>=0: os.close(fd)
        try:
            if launched and reaper.pidfd is None:
                raise Unavailable('child identity not established; quarantine')
            if launched and not placed:
                # May still be outside the generation, but only its pidfd is
                # eligible for signalling. No numerical PID fallback.
                try: signal.pidfd_send_signal(reaper.pidfd,signal.SIGKILL)
                except ProcessLookupError: pass
            gen.kill_owned()
            if launched:
                reaper.drain(time.monotonic()+3)
            if not launched or not reaper.drained:
                raise Unavailable('cleanup not proven; quarantine')
            if outcome=='released':
                if (len(reaper.reaped)!=2 or reaper.statuses.get(pid)!=(os.CLD_EXITED,0)
                    or reaper.statuses.get(descendant)!=(os.CLD_KILLED,signal.SIGKILL)):
                    raise Unavailable('unexpected direct/adopted exit evidence')
            elif outcome in {'eof','invalid','timeout'} and (len(reaper.reaped)!=1 or reaper.statuses.get(pid)!=(os.CLD_EXITED,43)):
                raise Unavailable('unexpected rejected gate exit evidence')
            if report_r>=0:
                os.set_blocking(report_r,False)
                if os.read(report_r,1):
                    raise Unavailable('unexpected trailing probe output')
            gen.remove_empty(reaper)
            preflight(root_fd, expected, required)
            verify_empty_root(root_fd)
        except BaseException:
            gen.quarantined=True
            gen.close_handles()
            raise
        finally:
            if report_r>=0: os.close(report_r)
            reaper.close()
    return {'case': outcome, 'reaped': len(reaper.reaped), 'removed': gen.removed,
            'placement_verified': placed, 'adopted_membership_verified': outcome == 'released',
            'probe_report_verified': outcome == 'released', 'root_empty_verified': True,
            'reap_statuses': sorted([list(status) for status in reaper.statuses.values()])}
