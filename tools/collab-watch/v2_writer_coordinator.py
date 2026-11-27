"""Staged 9b-C-B1 pair coordinator; not launcher, credential custody or scheduler.

Only trusted code constructs this composition or selects a durable recovery
record. The ordinary interface has no route to recovery or new-send re-arm.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import stat

from core import Conflict, ident, require, strict_json
from v2_trusted_writer import TrustedWriter
from v2_writer_ipc import SessionBinding
from v2_writer_spool import (Spool, ResourcePolicy, INITIAL, FORCED, READY,
                             MARKED, RESULT, RR)
from v2_attempts import AttemptStore
from v2_inputs import InputStore
from v2_owner import OwnerStore, Capability
from v2_runtime_state import RuntimeStateStore


class CoordinatorBlocked(Conflict):
    """This coordinator did not enter its delegate."""


class CoordinatorBusy(CoordinatorBlocked):
    """Pair admission lock is occupied; no admission or invocation."""


class CoordinatorUncertain(Conflict):
    """A marker or invocation may have occurred without a retained result."""


def _inode(info):
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
            "invalid pinned store")
    return info.st_dev, info.st_ino


@dataclass(frozen=True, slots=True)
class FilePin:
    """Externally trusted expected identity, never inferred on reopen."""
    store_id: str
    path: Path
    inode: tuple

    def __post_init__(self):
        require(type(self.store_id) is str and ident(self.store_id)
                and isinstance(self.path, Path) and self.path.is_absolute()
                and type(self.inode) is tuple and len(self.inode) == 2
                and all(type(n) is int and n >= 0 for n in self.inode),
                "invalid trusted file pin")

    def check(self):
        require(_inode(os.lstat(self.path)) == self.inode,
                "pinned store path changed")


@dataclass(frozen=True, slots=True)
class StorePins:
    spool: FilePin
    attempt: FilePin
    input: FilePin
    owner: FilePin
    checkpoint: FilePin | None

    def __post_init__(self):
        pins = self.values()
        require(all(type(pin) is FilePin for pin in pins)
                and len({pin.store_id for pin in pins}) == len(pins)
                and len({pin.path for pin in pins}) == len(pins)
                and len({pin.inode for pin in pins}) == len(pins),
                "invalid distinct store pins")

    def values(self):
        base = (self.spool, self.attempt, self.input, self.owner)
        return base if self.checkpoint is None else base + (self.checkpoint,)


@dataclass(frozen=True, slots=True)
class CommittedResult:
    """Trusted local observation of a persisted delegate result, not IPC delivery."""
    request_id: str
    execution: str
    classification: str
    result: dict


class Coordinator:
    """One process-local trusted view of the single pair admission domain.

    All effect-capable users must cooperate in this lock; trusted installation,
    stable directory and external pin continuity are assumptions, not hostile
    replacement or filesystem rollback proofs. No fork while an invocation
    holds the lock. Lower accepted writer independently owns its effect fences.
    """
    __slots__ = ("_spool", "_writer", "_pins", "_session", "_policy", "_pid",
                 "_attempt_fd")

    def __init__(self, spool, writer, *, pins, session, resource_policy):
        self._attempt_fd = None
        try:
            require(type(spool) is Spool and type(writer) is TrustedWriter
                    and type(pins) is StorePins and type(session) is SessionBinding
                    and type(resource_policy) is ResourcePolicy,
                    "invalid trusted coordinator bootstrap")
            self._spool, self._writer, self._pins = spool, writer, pins
            self._session = SessionBinding(session.role, session.incarnation,
                                           session.owner_generation, session.session_id)
            self._policy = ResourcePolicy(resource_policy.policy_id, resource_policy.sha256)
            self._pid = os.getpid()
            # AttemptStore itself reopens its path per operation. Retain a
            # separate O_PATH physical pin in this effect-capable process.
            self._attempt_fd = os.open(pins.attempt.path,
                                       os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW)
            self._check()
        except BaseException as exc:
            self.close()
            if not isinstance(exc, Exception):
                raise
            raise CoordinatorBlocked("coordinator bootstrap rejected") from None

    def close(self):
        fd = self._attempt_fd
        self._attempt_fd = None
        if fd is not None:
            os.close(fd)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _check(self):
        require(os.getpid() == self._pid and self._attempt_fd is not None,
                "coordinator process/pin mismatch")
        s, w, p = self._spool, self._writer, self._pins
        require(type(w._store) is AttemptStore and type(w._retention) is InputStore
                and type(w._owner) is OwnerStore and type(w._capability) is Capability,
                "writer composition changed")
        cap = w._capability
        require(s._scope == (p.spool.store_id, p.attempt.store_id, p.input.store_id,
                             w._repository, w._epoch)
                and s._cfg == w._config_pin.encode("utf-8")
                and (s._role, s._incarnation, s._actor) == (w._role, w._incarnation, w._actor)
                and s._session == self._session and s._policy == self._policy
                and (cap.transport_role, cap.incarnation, cap.generation)
                == (self._session.role, self._session.incarnation, self._session.owner_generation),
                "trusted session, scope or policy mismatch")
        w._check_scope()  # actual owner fence still occurs inside invoke
        require(s._path == p.spool.path and s.inode == p.spool.inode
                and w._store.path == p.attempt.path and w._store.store_id == p.attempt.store_id
                and _inode(os.fstat(self._attempt_fd)) == p.attempt.inode
                and w._retention.path == p.input.path
                and w._retention.provider_id == p.input.store_id
                and w._retention.attempt_store_id == p.attempt.store_id
                and w._retention._identity == p.input.inode
                and w._owner._path == p.owner.path and w._owner._store_id == p.owner.store_id
                and w._owner._identity == p.owner.inode, "trusted store pin mismatch")
        w._retention._check_pin()
        w._owner._check()
        state = w._runtime_state
        if p.checkpoint is None:
            require(state is None, "unexpected checkpoint")
        else:
            require(type(state) is RuntimeStateStore and state._path == p.checkpoint.path
                    and state._store_id == p.checkpoint.store_id
                    and state._identity == p.checkpoint.inode
                    and (state._repository, state._epoch) == (w._repository, w._epoch),
                    "trusted checkpoint pin mismatch")
            state._check()
        for pin in p.values():
            pin.check()

    @contextmanager
    def _pair_lock(self):
        fd = None
        try:
            self._check()
            fd = os.open(self._pins.spool.path, os.O_RDONLY | os.O_CLOEXEC |
                         os.O_NOFOLLOW | os.O_NONBLOCK)
            require(_inode(os.fstat(fd)) == self._pins.spool.inode, "lock pin mismatch")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise CoordinatorBusy("pair admission busy") from None
            self._check()
        except BaseException as exc:
            if fd is not None:
                os.close(fd)
            if not isinstance(exc, Exception) or isinstance(exc, CoordinatorBusy):
                raise
            raise CoordinatorBlocked("pair admission unavailable") from None
        try:
            yield
        finally:
            # All short SQLite transactions have closed before releasing this
            # ordinary fd; it is not a transaction-spanning SQLite lock.
            os.close(fd)

    def _delegate(self, request_id, version, execution):
        s = self._spool
        # From the first marker attempt onward, any failure is conservatively
        # uncertain, including commit succeeded but post-commit pin check failed.
        try:
            self._check()
            mark = s.mark_initial if execution == INITIAL else s.mark_recovery
            request = mark(request_id, version)
            self._check()
            value = self._writer.invoke(request)
            self._check()
            classification = s.persist_result(request_id, version + 1, execution, value)
            self._check()
            row = s.load(request_id)
            require(row["state"] == RESULT and row["version"] == version + 2
                    and row["classification"] == classification
                    and row["execution"] == execution, "delegate result not retained")
            result = strict_json(row["result"].decode("utf-8"))["result"]
            self._check()
            return CommittedResult(request_id, execution, classification, result)
        except Exception:
            raise CoordinatorUncertain("delegate result not established") from None

    def ordinary(self, request):
        """Only new-send ordinary ingress; worker mode cannot select recovery."""
        if (type(request) is not dict or set(request) != {"original", "reconcile_only"}
                or type(request.get("original")) is not str
                or request.get("reconcile_only") is not False):
            raise CoordinatorBlocked("ordinary request rejected")
        with self._pair_lock():
            s = self._spool
            try:
                inventory = s.list_metadata()
                require(not any(r["state"] == MARKED or
                                (r["state"] == RESULT and r["classification"] == RR)
                                for r in inventory), "pair recovery pending")
                request_id = s.admit(request)
                row = s.load(request_id)
                require(row["state"] == READY, "ordinary request not ready")
                self._check()
            except Exception:
                raise CoordinatorBlocked("ordinary admission blocked") from None
            return self._delegate(request_id, row["version"], INITIAL)

    def recover(self, request_id, expected_version):
        """Trusted scheduler-only exact durable selector, no worker replay input."""
        with self._pair_lock():
            s = self._spool
            try:
                row = s.load(request_id)
                require(type(expected_version) is int and row["version"] == expected_version
                        and (row["state"] == MARKED or
                             (row["state"] == RESULT and row["classification"] == RR)),
                        "recovery selection stale or not pending")
                self._check()
            except Exception:
                raise CoordinatorBlocked("trusted recovery selection blocked") from None
            return self._delegate(request_id, expected_version, FORCED)
