"""Trusted local owner capability store; no transport or authority policy."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import fcntl
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import stat

from core import Conflict, REPO, canonical, ident, require
from project_tasks import body_hash
from v2_identity import TRANSPORT_ROLES

VERSION = 1
BUSY_MS = 2000
MAX_DB_BYTES = 1024 * 1024
MAX_GENERATION = 2**63 - 1
META_SQL = ("CREATE TABLE owner_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
            "version INTEGER NOT NULL, store_id TEXT NOT NULL, repository TEXT NOT NULL, "
            "journal_epoch TEXT NOT NULL)")
ROWS_SQL = ("CREATE TABLE owners (role TEXT PRIMARY KEY NOT NULL, incarnation TEXT NOT NULL, "
            "generation INTEGER NOT NULL, capability_sha256 TEXT NOT NULL)")
SCHEMA = {("table", "owner_meta", META_SQL), ("table", "owners", ROWS_SQL)}


class OwnerBusy(Conflict):
    """The exclusive owner fence is currently held."""


@dataclass(frozen=True)
class Capability:
    store_id: str
    repository: str
    journal_epoch: str
    transport_role: str
    incarnation: str
    generation: int
    token: str = field(repr=False)


def _repository(value):
    require(type(value) is str and len(value) <= 256 and REPO.fullmatch(value)
            and all(p not in (".", "..") for p in value.split("/")), "invalid owner repository")
    return value.lower()


def _role(role):
    return type(role) is str and role in TRANSPORT_ROLES


def _generation(value):
    return type(value) is int and 0 < value <= MAX_GENERATION


def _path(value):
    try:
        require(os.fspath(value) not in ("", ":memory:"), "durable owner path required")
        return Path(value).absolute()
    except (TypeError, OSError, ValueError):
        raise Conflict("invalid owner path") from None


def _file_id(info):
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
            and info.st_size <= MAX_DB_BYTES, "invalid owner store file")
    return info.st_dev, info.st_ino


def _check_path(path, identity):
    require(_file_id(os.lstat(path)) == identity, "owner store physical identity changed")


def _pin(path):
    fd = None
    try:
        fd = os.open(path, os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW)
        identity = _file_id(os.fstat(fd))
        _check_path(path, identity)
        return fd, identity
    except (Conflict, OSError, ValueError, TypeError):
        if fd is not None:
            os.close(fd)
        raise Conflict("owner store unavailable or invalid") from None


def _connect(path, identity):
    _check_path(path, identity)
    conn = sqlite3.connect(path.as_uri()+"?mode=rw", uri=True,
                           timeout=BUSY_MS/1000, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout="+str(BUSY_MS))
        conn.execute("PRAGMA synchronous=FULL")
        require(conn.execute("PRAGMA synchronous").fetchone() == (2,)
                and conn.execute("PRAGMA journal_mode").fetchone() == ("delete",),
                "unsupported owner store durability settings")
        return conn
    except BaseException:
        conn.close()
        raise


def _validated(conn, store_id, repository, epoch):
    require(set(conn.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL")) == SCHEMA,
            "unknown owner store schema")
    require(conn.execute("SELECT * FROM owner_meta").fetchall() ==
            [(1, VERSION, store_id, repository, epoch)], "owner store identity/version mismatch")
    require(conn.execute("PRAGMA quick_check(1)").fetchall() == [("ok",)],
            "owner store integrity failure")
    require(conn.execute("SELECT count(*) FROM owners").fetchone()[0] <= len(TRANSPORT_ROLES),
            "owner slot bound")
    rows, incarnations = {}, set()
    for role, inc, generation, sha in conn.execute("SELECT * FROM owners"):
        require(_role(role) and ident(inc) and _generation(generation) and body_hash(sha)
                and role not in rows and inc not in incarnations, "invalid owner slot")
        rows[role] = (inc, generation, sha)
        incarnations.add(inc)
    return rows


class OwnerStore:
    """One externally pinned local store. Fresh reopen cannot prove continuity."""
    __slots__ = ("_path", "_store_id", "_repository", "_epoch", "_fd", "_identity")

    def __init__(self, path, store_id, repository, journal_epoch):
        self._fd = None
        self._path = _path(path)
        require(ident(store_id) and ident(journal_epoch), "invalid owner store identity")
        self._store_id, self._repository, self._epoch = store_id, _repository(repository), journal_epoch
        self._fd, self._identity = _pin(self._path)

    def close(self):
        fd, self._fd = self._fd, None
        if fd is not None:
            os.close(fd)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _check(self):
        require(self._fd is not None and _file_id(os.fstat(self._fd)) == self._identity,
                "owner store physical pin unavailable")
        _check_path(self._path, self._identity)

    @contextmanager
    def _lock(self):
        fd = None
        try:
            self._check()
            fd = os.open(self._path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
            require(_file_id(os.fstat(fd)) == self._identity, "owner lock inode mismatch")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise OwnerBusy("OWNER_BUSY") from None
            self._check()
        except OwnerBusy:
            if fd is not None:
                os.close(fd)
            raise
        except (Conflict, OSError, TypeError, ValueError):
            if fd is not None:
                os.close(fd)
            raise Conflict("owner store unavailable or invalid") from None
        try:
            yield
        finally:
            os.close(fd)

    @contextmanager
    def _transaction(self):
        conn = None
        try:
            self._check()
            conn = _connect(self._path, self._identity)
            conn.execute("BEGIN IMMEDIATE")
            self._check()
            rows = _validated(conn, self._store_id, self._repository, self._epoch)
            yield conn, rows
            self._check()
            conn.execute("COMMIT")
            self._check()
        except (Conflict, sqlite3.Error, OSError, TypeError, ValueError, RecursionError):
            raise Conflict("owner store unavailable or invalid") from None
        finally:
            if conn is not None:
                if conn.in_transaction:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                conn.close()

    def _scope(self):
        return dict(store_id=self._store_id, repository=self._repository,
                    journal_epoch=self._epoch)

    def status(self):
        with self._lock(), self._transaction() as (_, rows):
            return {role: dict(incarnation=inc, generation=gen)
                    for role, (inc, gen, _) in sorted(rows.items())}

    def _transition(self, role, incarnation, previous, operation, authorize):
        require(_role(role) and ident(incarnation), "invalid owner role/incarnation")
        require(type(previous) is int and 0 <= previous < MAX_GENERATION,
                "invalid previous owner generation")
        with self._lock(), self._transaction() as (conn, rows):
            old = rows.get(role)
            require((old is None and previous == 0 and operation == "initial_owner_claim")
                    or (old is not None and previous > 0 and operation == "owner_replacement"
                        and old[:2] == (incarnation, previous)), "owner transition conflict")
            require(all(r == role or v[0] != incarnation for r, v in rows.items()),
                    "owner incarnation reused")
            descriptor = dict(self._scope(), operation=operation, transport_role=role,
                              incarnation=incarnation, previous_generation=previous,
                              next_generation=previous+1)
            frozen = canonical(descriptor)
            try:
                allowed = authorize(descriptor)
                require(allowed is True and canonical(descriptor) == frozen,
                        "owner transition authority denied")
            except Exception:
                raise Conflict("owner transition authority denied") from None
            # Generate after authorization. Token is never sent to authority or SQLite.
            token = secrets.token_hex(32)
            sha = hashlib.sha256(token.encode("ascii")).hexdigest()
            require(old is None or not hmac.compare_digest(old[2], sha),
                    "owner capability collision")
            if old is None:
                conn.execute("INSERT INTO owners VALUES(?,?,?,?)", (role, incarnation, 1, sha))
            else:
                changed = conn.execute("UPDATE owners SET generation=?,capability_sha256=? "
                                       "WHERE role=? AND incarnation=? AND generation=?",
                                       (previous+1, sha, role, incarnation, previous)).rowcount
                require(changed == 1, "owner replacement conflict")
            _validated(conn, self._store_id, self._repository, self._epoch)
            cap = Capability(**self._scope(), transport_role=role, incarnation=incarnation,
                             generation=previous+1, token=token)
        return cap

    def claim(self, role, incarnation, authorize):
        return self._transition(role, incarnation, 0, "initial_owner_claim", authorize)

    def replace(self, role, incarnation, expected_generation, authorize):
        require(_generation(expected_generation), "invalid expected owner generation")
        return self._transition(role, incarnation, expected_generation, "owner_replacement", authorize)

    @contextmanager
    def fence(self, capability):
        require(type(capability) is Capability, "invalid owner capability")
        with self._lock():
            with self._transaction() as (_, rows):
                require(all(getattr(capability, k) == v for k, v in self._scope().items())
                        and _role(capability.transport_role) and ident(capability.incarnation)
                        and _generation(capability.generation) and body_hash(capability.token),
                        "invalid owner capability")
                old = rows.get(capability.transport_role)
                sha = hashlib.sha256(capability.token.encode("ascii")).hexdigest()
                require(old is not None and old[:2] == (capability.incarnation, capability.generation)
                        and hmac.compare_digest(old[2], sha), "owner capability rejected")
            # Transaction is closed; flock remains held across the caller's operation.
            self._check()
            yield
            self._check()


def initialize_owner(path, store_id, repository, journal_epoch):
    """Explicit provisioning; leave incomplete files for investigation, never repair."""
    path = _path(path)
    repository = _repository(repository)
    require(ident(store_id) and ident(journal_epoch), "invalid owner store identity")
    fd = pin = conn = None
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC, 0o600)
        os.fchmod(fd, 0o600)
        identity = _file_id(os.fstat(fd))
        pin, pinned = _pin(path)
        require(pinned == identity, "owner store physical identity changed")
        os.close(fd)
        fd = None
        conn = _connect(path, identity)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(META_SQL)
        conn.execute(ROWS_SQL)
        conn.execute("INSERT INTO owner_meta VALUES(1,?,?,?,?)",
                     (VERSION, store_id, repository, journal_epoch))
        _validated(conn, store_id, repository, journal_epoch)
        conn.execute("COMMIT")
        conn.close()
        conn = None
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
        _check_path(path, identity)
        opened = open_owner(path, store_id, repository, journal_epoch)
        if opened._identity != identity:
            opened.close()
            raise Conflict("owner store physical identity changed")
        return opened
    except (Conflict, OSError, sqlite3.Error, TypeError, ValueError):
        raise Conflict("explicit owner store initialization failed") from None
    finally:
        if conn is not None:
            conn.close()
        if fd is not None:
            os.close(fd)
        if pin is not None:
            os.close(pin)


def open_owner(path, expected_store_id, repository, journal_epoch):
    store = OwnerStore(path, expected_store_id, repository, journal_epoch)
    try:
        store.status()
        return store
    except BaseException:
        store.close()
        raise
