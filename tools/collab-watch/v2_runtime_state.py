"""Durable local canonical checkpoint only; no projection or authority policy."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import sqlite3
import stat

from core import Conflict, REPO, canonical, ident, require, strict_json
from project_tasks import body_hash
from split_journal import PROTOCOL as TASK_PROTOCOL
from v2_aux import PROTOCOL as AUX_PROTOCOL

VERSION = 1
BUSY_MS = 2000
MAX_GENERATION = 2**63 - 1
MAX_STATE_BYTES = 32*1024*1024
MAX_DB_BYTES = 2*MAX_STATE_BYTES + 4*1024*1024
META_SQL = ("CREATE TABLE state_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
            "version INTEGER NOT NULL, store_id TEXT NOT NULL, repository TEXT NOT NULL, "
            "journal_epoch TEXT NOT NULL)")
CHECKPOINT_SQL = ("CREATE TABLE checkpoint (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                  "generation INTEGER NOT NULL, state BLOB NOT NULL, state_sha256 TEXT NOT NULL)")
SCHEMA = {("table", "state_meta", META_SQL), ("table", "checkpoint", CHECKPOINT_SQL)}


def _repo(value):
    require(type(value) is str and len(value) <= 256 and REPO.fullmatch(value)
            and all(p not in (".", "..") for p in value.split("/")), "invalid state repository")
    return value.lower()


def _path(value):
    try:
        require(os.fspath(value) not in ("", ":memory:"), "durable checkpoint path required")
        return Path(value).absolute()
    except (TypeError, ValueError, OSError):
        raise Conflict("invalid checkpoint path") from None


def _file_id(info):
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
            and info.st_size <= MAX_DB_BYTES, "invalid checkpoint file")
    return info.st_dev, info.st_ino


def _check_path(path, identity):
    require(_file_id(os.lstat(path)) == identity, "checkpoint physical identity changed")


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
        raise Conflict("checkpoint unavailable or invalid") from None


def _connect(path, identity):
    _check_path(path, identity)
    conn = sqlite3.connect(path.as_uri()+"?mode=rw", uri=True,
                           timeout=BUSY_MS/1000, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout="+str(BUSY_MS))
        conn.execute("PRAGMA synchronous=FULL")
        require(conn.execute("PRAGMA synchronous").fetchone() == (2,)
                and conn.execute("PRAGMA journal_mode").fetchone() == ("delete",),
                "unsupported checkpoint durability settings")
        return conn
    except BaseException:
        conn.close()
        raise


def _shape(state):
    """Validate storage shape, not semantic origin or completeness."""
    require(type(state) is dict and set(state) == {"task", "aux"}, "invalid composed state")
    for family, protocol in (("task", TASK_PROTOCOL), ("aux", AUX_PROTOCOL)):
        part = state[family]
        require(type(part) is dict and set(part) == {"protocol", "semantic_config_hash", "ledger"}
                and part["protocol"] == protocol and body_hash(part["semantic_config_hash"])
                and type(part["ledger"]) is dict
                and all(type(k) is str and bool(k) and body_hash(v)
                        for k, v in part["ledger"].items()), "invalid retained-state shape")
    require(state["task"]["semantic_config_hash"] == state["aux"]["semantic_config_hash"],
            "composed state config identity mismatch")


def _decode(blob):
    require(type(blob) is bytes and 0 < len(blob) <= MAX_STATE_BYTES, "checkpoint byte bound")
    state = strict_json(blob.decode("utf-8"))
    _shape(state)
    require(canonical(state).encode("utf-8") == blob, "noncanonical checkpoint bytes")
    return state


def _encode(state):
    try:
        _shape(state)
        blob = canonical(state).encode("utf-8")
        _decode(blob)
        return blob
    except (Conflict, TypeError, ValueError, UnicodeError, RecursionError):
        raise Conflict("invalid checkpoint state") from None


def _generation(value):
    return type(value) is int and 0 < value <= MAX_GENERATION


def _validated(conn, store_id, repository, epoch):
    require(set(conn.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL")) == SCHEMA,
            "unknown checkpoint schema")
    require(conn.execute("SELECT * FROM state_meta").fetchall() ==
            [(1, VERSION, store_id, repository, epoch)], "checkpoint identity/version mismatch")
    require(conn.execute("PRAGMA quick_check(1)").fetchall() == [("ok",)],
            "checkpoint integrity failure")
    rows = conn.execute("SELECT singleton,generation,length(state),typeof(state),state_sha256 "
                        "FROM checkpoint").fetchall()
    if not rows:
        return None
    require(len(rows) == 1, "invalid checkpoint count")
    singleton, generation, size, kind, sha = rows[0]
    require(singleton == 1 and _generation(generation) and kind == "blob"
            and type(size) is int and 0 < size <= MAX_STATE_BYTES
            and body_hash(sha), "invalid checkpoint metadata")
    blob, = conn.execute("SELECT state FROM checkpoint WHERE singleton=1").fetchone()
    require(type(blob) is bytes and len(blob) == size and hashlib.sha256(blob).hexdigest() == sha,
            "checkpoint digest mismatch")
    return {"generation": generation, "state_sha256": sha, "state": _decode(blob)}


class RuntimeStateStore:
    """Existing-only local checkpoint with externally pinned logical identity."""
    __slots__ = ("_path", "_store_id", "_repository", "_epoch", "_fd", "_identity")

    def __init__(self, path, store_id, repository, journal_epoch):
        self._fd = None
        self._path = _path(path)
        require(ident(store_id) and ident(journal_epoch), "invalid checkpoint identity")
        self._store_id, self._repository, self._epoch = store_id, _repo(repository), journal_epoch
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
                "checkpoint physical pin unavailable")
        _check_path(self._path, self._identity)

    @contextmanager
    def _transaction(self):
        conn = None
        try:
            self._check()
            conn = _connect(self._path, self._identity)
            conn.execute("BEGIN IMMEDIATE")
            self._check()
            yield conn, _validated(conn, self._store_id, self._repository, self._epoch)
            self._check()
            conn.execute("COMMIT")
            self._check()
        except (Conflict, OSError, sqlite3.Error, TypeError, ValueError, UnicodeError, RecursionError):
            raise Conflict("checkpoint unavailable or invalid") from None
        finally:
            if conn is not None:
                if conn.in_transaction:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                conn.close()

    def load(self):
        with self._transaction() as (_, checkpoint):
            return checkpoint

    def save(self, state, expected_generation):
        require(type(expected_generation) is int and 0 <= expected_generation < MAX_GENERATION,
                "invalid checkpoint expected generation")
        blob = _encode(state)
        sha = hashlib.sha256(blob).hexdigest()
        with self._transaction() as (conn, old):
            current = 0 if old is None else old["generation"]
            require(current == expected_generation, "stale checkpoint generation")
            if old is None:
                conn.execute("INSERT INTO checkpoint VALUES(1,?,?,?)", (1, blob, sha))
            else:
                changed = conn.execute("UPDATE checkpoint SET generation=?,state=?,state_sha256=? "
                                       "WHERE singleton=1 AND generation=?",
                                       (current+1, blob, sha, current)).rowcount
                require(changed == 1, "checkpoint compare-and-swap failed")
            result = _validated(conn, self._store_id, self._repository, self._epoch)
            return result


def initialize_state(path, store_id, repository, journal_epoch):
    """Explicit provision only; never reset, repair or overwrite."""
    path = _path(path)
    repository = _repo(repository)
    require(ident(store_id) and ident(journal_epoch), "invalid checkpoint identity")
    fd = pin = conn = None
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC, 0o600)
        os.fchmod(fd, 0o600)
        identity = _file_id(os.fstat(fd))
        pin, pinned = _pin(path)
        require(pinned == identity, "checkpoint physical identity changed")
        os.close(fd)
        fd = None
        conn = _connect(path, identity)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(META_SQL)
        conn.execute(CHECKPOINT_SQL)
        conn.execute("INSERT INTO state_meta VALUES(1,?,?,?,?)", (VERSION, store_id, repository, journal_epoch))
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
        opened = open_state(path, store_id, repository, journal_epoch)
        if opened._identity != identity:
            opened.close()
            raise Conflict("checkpoint physical identity changed")
        return opened
    except (Conflict, OSError, sqlite3.Error, TypeError, ValueError):
        raise Conflict("explicit checkpoint initialization failed") from None
    finally:
        if conn is not None:
            conn.close()
        if fd is not None:
            os.close(fd)
        if pin is not None:
            os.close(pin)


def open_state(path, expected_store_id, repository, journal_epoch):
    store = RuntimeStateStore(path, expected_store_id, repository, journal_epoch)
    try:
        store.load()
        return store
    except BaseException:
        store.close()
        raise
