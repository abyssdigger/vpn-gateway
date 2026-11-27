"""Staged trusted, no-queue supervisor for one reviewed non-forking writer child.

Not a hostile-worker tree boundary, credential provisioner, or transport.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

from core import ident
from v2_writer_ipc import SessionBinding

ROOT = Path(__file__).resolve().parent
PYTHON = str(Path(sys.executable).resolve(strict=True))
CHILD = str(ROOT / "v2_writer_child.py")
SETPRIV = "/usr/bin/setpriv"
ENV = {"LC_ALL": "C.UTF-8"}
MAX_CONTROL = 16384
PROBES = frozenset({"ok", "bound", "memory", "cpu", "fd", "wall", "crash", "worker"})


class LaunchError(Exception):
    """No semantic outcome or retry authority follows from launch failure."""


class Busy(LaunchError):
    pass


def _require(ok):
    if not ok:
        raise LaunchError("staged launch rejected")


def _integer(value, minimum=1, maximum=2**63-1):
    return type(value) is int and minimum <= value <= maximum


def _remaining(deadline):
    value = deadline - time.monotonic()
    _require(value > 0)
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class Limits:
    address_bytes: int
    cpu_seconds: int
    files: int
    processes: int

    def __post_init__(self):
        _require(_integer(self.address_bytes, 1) and _integer(self.cpu_seconds)
                 and _integer(self.files, 16) and _integer(self.processes))


@dataclass(frozen=True, slots=True)
class Isolation:
    writer_uid: int
    writer_gid: int
    worker_uid: int
    worker_gid: int

    def __post_init__(self):
        _require(all(_integer(x, 1, 2**31-1) for x in (self.writer_uid, self.writer_gid,
                     self.worker_uid, self.worker_gid)) and self.writer_uid != self.worker_uid
                 and self.writer_gid != self.worker_gid)


@dataclass(frozen=True, slots=True)
class DummyFile:
    """Test-only protected dummy material; never a real credential."""
    path: str
    sha256: str

    def __post_init__(self):
        _require(type(self.path) is str and len(self.path) <= 1024
                 and os.path.isabs(self.path) and "\0" not in self.path
                 and type(self.sha256) is str and len(self.sha256) == 64
                 and all(c in "0123456789abcdef" for c in self.sha256))


@dataclass(frozen=True, slots=True)
class LaunchSpec:
    session: SessionBinding
    stores: tuple[str, str, str, str]
    limits: Limits
    wall_seconds: float
    probe: str = "ok"
    isolation: Isolation | None = None  # explicit same-identity test mode when absent
    dummy: DummyFile | None = None

    def __post_init__(self):
        _require(type(self.session) is SessionBinding and type(self.limits) is Limits
                 and type(self.stores) is tuple and len(self.stores) == 4
                 and all(type(x) is str and ident(x) for x in self.stores)
                 and len(set(self.stores)) == 4 and type(self.wall_seconds) in (int, float)
                 and math.isfinite(self.wall_seconds) and 0 < self.wall_seconds <= 3600
                 and type(self.probe) is str and self.probe in PROBES
                 and (self.isolation is None or type(self.isolation) is Isolation)
                 and (self.dummy is None or (type(self.dummy) is DummyFile
                                            and self.isolation is not None)))


def _spawn(kind, spec, args, fds):
    _require(kind in ("writer", "worker", "coord_ordinary", "coord_recovery"))
    isolated = spec.isolation is not None
    if isolated:
        _require(os.geteuid() == 0)
        ids = spec.isolation
        uid, gid = ((ids.writer_uid, ids.writer_gid) if kind != "worker"
                    else (ids.worker_uid, ids.worker_gid))
    else:
        uid, gid = os.geteuid(), os.getegid()
    argv = [PYTHON, "-I", "-S", "-B", CHILD, kind, str(uid), str(gid),
            str(int(isolated)), *map(str, args)]
    if isolated:
        argv = [SETPRIV, f"--reuid={uid}", f"--regid={gid}", "--clear-groups",
                "--inh-caps=-all", "--ambient-caps=-all", "--bounding-set=-all",
                "--no-new-privs", "--", *argv]
    return subprocess.Popen(argv, cwd=ROOT, env=dict(ENV), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            close_fds=True, pass_fds=tuple(fds), start_new_session=True)


def _kill_reap(children):
    # Kill the reviewed immediate children, not a purported hostile process tree.
    failed = False
    for child in children:
        try:
            if child.poll() is None:
                child.kill()
        except ProcessLookupError:
            pass
        except OSError:
            failed = True
    for child in children:
        try:
            child.wait()
        except OSError:
            failed = True
    return not failed and all(child.returncode is not None for child in children)


def _close_all(endpoints):
    closed = True
    for endpoint in endpoints:
        try:
            endpoint.close()
        except BaseException:
            closed = False
    return closed


def _control_report(sock):
    data = bytearray()
    sock.settimeout(0.5)
    while len(data) <= MAX_CONTROL:
        part = sock.recv(min(4096, MAX_CONTROL + 1 - len(data)))
        if not part:
            break
        data.extend(part)
    _require(len(data) <= MAX_CONTROL)
    entered = data.startswith(b"E")
    if entered:
        del data[:1]
    if not data:
        return entered, None
    _require(data.startswith(b"D"))
    report = json.loads(data[1:].decode("utf-8"))
    _require(type(report) is dict and set(report) == {"setup", "pin", "fault", "validated",
             "worker", "rss_kib", "cpu_seconds", "outcome", "dummy_ok", "argv_clean"})
    # Diagnostic only: never an action result, identity grant, or no-attempt proof.
    return entered, report


@dataclass(frozen=True, slots=True)
class Completion:
    writer_status: int | None
    worker_status: int | None
    timed_out: bool
    reaped: bool
    entered: bool
    report: dict | None


class Invocation:
    def __init__(self, deadline):
        self.deadline = deadline
        self._done = threading.Event()
        self._completion = None

    def wait(self, timeout=None):
        if not self._done.wait(timeout):
            raise TimeoutError("invocation not reaped")
        return self._completion


class Supervisor:
    """One slot per trusted pinned store set; no queue or worker launch fields."""
    def __init__(self, spec):
        _require(type(spec) is LaunchSpec)
        self._spec = spec
        self._admission = threading.Lock()
        self._active = None

    def _reserve(self, invocation):
        with self._admission:
            if self._active is not None:
                raise Busy("staged invocation slot busy")
            self._active = invocation

    def _release(self, invocation):
        # A stale or duplicate cleanup must never release a later invocation.
        with self._admission:
            if self._active is invocation:
                self._active = None

    def start(self):
        """Return sole client endpoint to trusted test caller and reaper handle."""
        _require(self._spec.probe != "worker")
        return self._start(False, False, False)

    def start_pair(self, *, worker_first=False, abrupt_worker=False):
        """Launch only the reviewed dummy worker, not arbitrary worker code."""
        _require(type(worker_first) is bool and type(abrupt_worker) is bool
                 and self._spec.probe in {"worker", "crash", "wall"}
                 and not (worker_first and self._spec.dummy is not None))
        _, invocation = self._start(True, worker_first, abrupt_worker)
        return invocation

    def start_coordinated(self, bootstrap):
        """Trusted staged synthetic-only launch; recovery returns no data endpoint."""
        from v2_writer_scheduler import Bootstrap
        _require(type(bootstrap) is Bootstrap and self._spec == bootstrap.route.launch_spec(bootstrap.recovery))
        return self._start(False, False, False, coordinated=bootstrap)

    def _start(self, paired, worker_first, abrupt, coordinated=None):
        spec = self._spec
        recovery = coordinated is not None and coordinated.recovery
        deadline = time.monotonic() + spec.wall_seconds
        invocation = Invocation(deadline)
        endpoints, children = [], []
        writer = worker = client = server = None
        handoff = threading.Event()
        watcher_owned = False
        self._reserve(invocation)
        try:
            if not recovery:
                server, client = socket.socketpair()
                endpoints.extend((server, client))
            parent, control = socket.socketpair()
            endpoints.extend((parent, control))
            control_fd = control.fileno()

            def spawn_writer():
                nonlocal writer
                _remaining(deadline)
                kind = ("writer" if coordinated is None else
                        "coord_recovery" if recovery else "coord_ordinary")
                server_fd = -1 if recovery else server.fileno()
                fds = (control_fd,) if recovery else (server_fd, control_fd)
                writer = _spawn(kind, spec, (server_fd, control_fd, deadline,
                                spec.limits.address_bytes, spec.limits.cpu_seconds,
                                spec.limits.files, spec.limits.processes), fds)
                children.append(writer)
                # Transfer, not retain, each data/control endpoint.
                if server is not None:
                    server.close()
                control.close()
                if coordinated is None:
                    bootstrap = _canonical(dict(session=asdict(spec.session), stores=spec.stores,
                                      probe=spec.probe, dummy=asdict(spec.dummy) if spec.dummy else None)).encode()
                    _require(len(bootstrap) <= MAX_CONTROL)
                else:
                    bootstrap = coordinated.wire()
                parent.settimeout(_remaining(deadline))
                parent.sendall(bootstrap)
                parent.shutdown(socket.SHUT_WR)
                parent.settimeout(_remaining(deadline))
                _require(parent.recv(1) == b"R")

            def spawn_worker():
                nonlocal worker
                _remaining(deadline)
                worker = _spawn("worker", spec, (client.fileno(), deadline, int(abrupt),
                                spec.dummy.path if spec.dummy else "", writer.pid if writer else 0,
                                control_fd), (client.fileno(),))
                children.append(worker)
                client.close()

            if paired and worker_first:
                spawn_worker()
            spawn_writer()
            if paired and not worker_first:
                spawn_worker()
            _remaining(deadline)
            def watch_after_transfer():
                handoff.wait()
                if watcher_owned:
                    self._watch(invocation, writer, worker, parent)

            threading.Thread(target=watch_after_transfer, daemon=True).start()
            # Thread.start can raise after actually starting the thread. Until
            # this assignment the watcher cannot own cleanup, even if running.
            watcher_owned = True
            handoff.set()
            return (None if paired or recovery else client), invocation
        except BaseException:
            # Publish cancel or commit to any already-started watcher. Only the
            # selected owner may close control, reap children and release.
            handoff.set()
            if watcher_owned:
                # No client endpoint was successfully returned to the caller.
                if not paired and client is not None:
                    client.close()
            else:
                try:
                    closed = _close_all(endpoints)
                    if _kill_reap(children) and closed:
                        self._release(invocation)
                except BaseException:
                    # Fail closed on unconfirmed closure/exit, never release.
                    pass
            raise LaunchError("staged launch failed; no result established") from None

    def _watch(self, invocation, writer, worker, control):
        children = [writer] + ([worker] if worker is not None else [])
        timed_out = False
        reaped = False
        entered, report = False, None
        try:
            for child in children:
                child.wait(timeout=max(0, invocation.deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out = True
        except BaseException:
            pass
        finally:
            try:
                reaped = _kill_reap(children)
                if reaped:
                    entered, report = _control_report(control)
            except BaseException:
                pass
            finally:
                try:
                    if _close_all((control,)) and reaped:
                        self._release(invocation)
                finally:
                    invocation._completion = Completion(writer.returncode, worker.returncode if worker else None,
                                                        timed_out, reaped, entered, report)
                    invocation._done.set()
