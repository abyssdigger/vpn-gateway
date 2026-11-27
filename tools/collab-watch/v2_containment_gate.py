"""B1 draft: exact one-shot release and fixed privilege transition.

Fixed test-only gate. Not a deployment launcher.
"""
from __future__ import annotations

import ctypes
import os
import socket
import sys
import time


class GateRejected(RuntimeError):
    pass


class ReleaseRejected(GateRejected):
    pass


PLACED = b'PLACED'
RELEASE = b'RELEASE'


def await_release(channel: socket.socket, deadline: float) -> None:
    if (channel.family != socket.AF_UNIX or
            channel.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_SEQPACKET):
        raise ReleaseRejected('not a local sequenced-packet channel')
    left = deadline - time.monotonic()
    if left <= 0:
        raise ReleaseRejected('release deadline expired')
    channel.settimeout(left)
    try:
        msg, ancillary, flags, _ = channel.recvmsg(len(RELEASE) + 1, 0)
    except TimeoutError as exc:
        raise ReleaseRejected('release timeout') from exc
    if (time.monotonic() >= deadline or msg != RELEASE or ancillary or
            flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC)):
        raise ReleaseRejected('missing or invalid release')


def _prctl(option: int, arg: int = 0, arg2: int = 0) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.prctl
    fn.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    fn.restype = ctypes.c_int
    if fn(option, arg, arg2, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'prctl failed')


def drop_probe_privileges(uid: int, gid: int) -> None:
    if type(uid) is not int or type(gid) is not int or not (0 < uid < 2**32-1 and 0 < gid < 2**32-1):
        raise GateRejected('invalid probe IDs')
    if os.getresuid() != (0, 0, 0):
        raise GateRejected('trusted gate not root')
    with open('/proc/sys/kernel/cap_last_cap', encoding='ascii') as stream:
        last = int(stream.read())
    if not 0 <= last <= 1024:
        raise GateRejected('unexpected capability range')
    _prctl(47, 4)  # PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL
    for cap in range(last + 1):
        _prctl(24, cap)  # PR_CAPBSET_DROP
    os.setgroups([])
    os.setresgid(gid, gid, gid)
    os.setresuid(uid, uid, uid)
    _prctl(38, 1)  # PR_SET_NO_NEW_PRIVS
    verify_probe_privileges(uid, gid)


def verify_probe_privileges(uid: int, gid: int) -> None:
    if os.getresuid() != (uid, uid, uid) or os.getresgid() != (gid, gid, gid) or os.getgroups():
        raise GateRejected('IDs/groups not dropped')
    with open('/proc/self/status', encoding='ascii') as stream:
        fields = dict(line.rstrip().split(':', 1) for line in stream if ':' in line)
    for key in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'):
        if int(fields[key], 16) != 0:
            raise GateRejected('residual capability')
    if fields['NoNewPrivs'].strip() != '1':
        raise GateRejected('NNP absent')


def close_nonstdio() -> None:
    # Dedicated single-threaded child only; no concurrent descriptor allocation.
    # listdir's own temporary FD has closed before the loop starts.
    for name in os.listdir('/proc/self/fd'):
        fd = int(name)
        if fd > 2:
            try:
                os.close(fd)
            except OSError as exc:
                import errno
                if exc.errno != errno.EBADF:
                    raise


# Fixed probe code, no worker-selected executable or command. The probe has
# only the report descriptor (stdout) and no privileged inherited handles.
PROBE = r"""
import os, time, pathlib, errno
with open('/proc/self/status') as f:
    d=dict(x.rstrip().split(':',1) for x in f if ':' in x)
if (any(int(d[k],16) for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb'))
    or d['NoNewPrivs'].strip()!='1' or os.getgroups()
    or os.getresuid()!=(65534,)*3 or os.getresgid()!=(65534,)*3):
    os._exit(31)
if set(os.listdir('/proc/self/fd')) - {'0','1','2','3'}:
    os._exit(32)
try:
    os.setuid(0)
except PermissionError:
    pass
else:
    os._exit(33)
# Restricted evidence view: root cgroup mount must be /sys/fs/cgroup.
with open('/proc/self/cgroup') as f:
    member=f.read().strip()
if not member.startswith('0::/') or '\n' in member:
    os._exit(34)
path=pathlib.Path('/sys/fs/cgroup') / member[4:]
mount=pathlib.Path('/sys/fs/cgroup')
# Attempt write-open only; never write migration/delegation controls from
# the probe, even if an unexpected permission would allow it.
for group in (path, *path.parents):
    if group != mount and mount not in group.parents:
        break
    if os.access(group, os.W_OK):
        os._exit(35)
    for name in ('cgroup.procs', 'cgroup.threads', 'cgroup.subtree_control'):
        try:
            fd=os.open(group/name, os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EPERM, errno.EROFS):
                os._exit(36)
        else:
            os.close(fd)
            os._exit(37)
os.write(1, b'PARENT:'+str(os.getpid()).encode()+b'\n')
# A single fork followed by immediate parent exit. The descendant reports
# separately and remains live for bounded parent-side membership checks.
child=os.fork()
if child:
    os._exit(0)
os.write(1, b'CHILD:'+str(os.getpid()).encode()+b'\n')
# No unbounded sleep or fork loop; owner may kill before this deadline.
time.sleep(8)
os._exit(0)
"""


def gate_main(gen_fd: int, placement_fd: int, channel: socket.socket,
              deadline: float) -> None:
    """Called only in the trusted, dedicated fork child, not a public CLI.

    No external parameters from a worker are parsed. On any error the child
    exits without executing the fixed probe. The manager owns cleanup.
    """
    from v2_writer_containment import exact_membership
    # Only self-placement. Never accept a numeric target PID.
    if os.write(placement_fd, b'0') != 1:
        raise GateRejected('placement write incomplete')
    os.close(placement_fd)
    self_fd = os.pidfd_open(os.getpid())
    try:
        exact_membership(gen_fd, os.getpid(), self_fd)
    finally:
        os.close(self_fd)
    os.close(gen_fd)
    if time.monotonic() >= deadline:
        raise GateRejected('placement deadline expired')
    channel.settimeout(max(0.001, deadline-time.monotonic()))
    if channel.send(PLACED) != len(PLACED):
        raise GateRejected('PLACED write incomplete')
    await_release(channel, deadline)
    channel.close()
    close_nonstdio()
    drop_probe_privileges(65534, 65534)
    # Fixed trusted interpreter and inline probe. -I excludes user import
    # configuration; the runner must independently trust the interpreter.
    os.execve(sys.executable, [sys.executable, '-I', '-S', '-c', PROBE],
              {'PATH':'/usr/bin:/bin','LANG':'C'})


def await_placed(channel: socket.socket, deadline: float) -> None:
    if (channel.family != socket.AF_UNIX or
            channel.getsockopt(socket.SOL_SOCKET,socket.SO_TYPE)!=socket.SOCK_SEQPACKET):
        raise GateRejected('invalid PLACED transport')
    left = deadline-time.monotonic()
    if left <= 0:
        raise GateRejected('placement deadline expired')
    channel.settimeout(left)
    msg, ancillary, flags, _ = channel.recvmsg(len(PLACED)+1, 0)
    if (time.monotonic() >= deadline or msg != PLACED or ancillary or
            flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC)):
        raise GateRejected('missing or invalid PLACED')

