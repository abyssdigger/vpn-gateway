"""Explicit durable original-input storage; no authority or task semantics."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import sqlite3
import stat

from collab_watch import MAX_LOCAL_BYTES
from core import Conflict, canonical, ident, require, strict_json
from project_tasks import body_hash

VERSION = 1
BUSY_MS = 2000
MAX_INPUT_BYTES = MAX_LOCAL_BYTES * 4
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_DB_BYTES = MAX_TOTAL_BYTES + 64 * 1024 * 1024
MAX_ROWS = 10000
META_SQL = ("CREATE TABLE input_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
            "version INTEGER NOT NULL, provider_id TEXT NOT NULL, attempt_store_id TEXT NOT NULL)")
ROWS_SQL = ("CREATE TABLE originals (action_key TEXT PRIMARY KEY NOT NULL, "
            "original BLOB NOT NULL, original_sha256 TEXT NOT NULL)")
SCHEMA = {("table", "input_meta", META_SQL), ("table", "originals", ROWS_SQL)}


def _path(path):
    try:
        require(os.fspath(path) not in ("", ":memory:"), "durable input path required")
        return Path(path).absolute()
    except (TypeError, ValueError, OSError):
        raise Conflict("invalid input store path") from None


def _check_file(path):
    info = os.lstat(path)
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size <= MAX_DB_BYTES, "invalid input store file")


def _connect(path):
    _check_file(path)
    conn = sqlite3.connect(path.as_uri()+"?mode=rw", uri=True,
                           timeout=BUSY_MS/1000, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout="+str(BUSY_MS))
        conn.execute("PRAGMA synchronous=FULL")
        require(conn.execute("PRAGMA synchronous").fetchone() == (2,)
                and conn.execute("PRAGMA journal_mode").fetchone() == ("delete",),
                "unsupported input store durability settings")
        return conn
    except BaseException:
        conn.close()
        raise


def _validated(conn, provider_id, attempt_store_id):
    require(set(conn.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL")) == SCHEMA,
            "unknown input store schema")
    require(conn.execute("SELECT singleton,version,provider_id,attempt_store_id FROM input_meta").fetchall()
            == [(1, VERSION, provider_id, attempt_store_id)], "input store identity/pair mismatch")
    require(conn.execute("PRAGMA quick_check(1)").fetchall() == [("ok",)],
            "input store integrity failure")
    count, total, largest, invalid = conn.execute(
        "SELECT count(*),coalesce(sum(length(original)),0),coalesce(max(length(original)),0),"
        "coalesce(sum(CASE WHEN typeof(original)!='blob' OR typeof(action_key)!='text' "
        "OR typeof(original_sha256)!='text' OR length(action_key)!=64 "
        "OR action_key GLOB '*[^0-9a-f]*' OR length(original_sha256)!=64 "
        "OR original_sha256 GLOB '*[^0-9a-f]*' THEN 1 ELSE 0 END),0) FROM originals"
    ).fetchone()
    require(count <= MAX_ROWS and total <= MAX_TOTAL_BYTES and largest <= MAX_INPUT_BYTES
            and invalid == 0, "input store bounds or identity metadata invalid")
    return count, total


def _canonical_bytes(original):
    # strict_json errors may contain untrusted prose; never propagate them.
    try:
        require(type(original) is str and len(original) <= MAX_INPUT_BYTES, "invalid input")
        blob = original.encode("utf-8")
        require(0 < len(blob) <= MAX_INPUT_BYTES, "invalid input")
        value = strict_json(original)
        require(type(value) is dict and canonical(value) == original, "invalid input")
        return blob
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise Conflict("invalid retained canonical original") from None


def _stored(row, expected_key):
    require(row is not None, "retained original missing")
    key, blob, sha = row
    require(key == expected_key and body_hash(key) and type(blob) is bytes
            and 0 < len(blob) <= MAX_INPUT_BYTES and body_hash(sha)
            and hashlib.sha256(blob).hexdigest() == sha, "retained original integrity mismatch")
    try:
        original = blob.decode("utf-8")
    except UnicodeError:
        raise Conflict("invalid retained canonical original") from None
    require(_canonical_bytes(original) == blob, "retained original encoding mismatch")
    return original


class InputStore:
    """Existing-only immutable local provider with externally pinned identities."""
    __slots__ = ("_path", "_provider_id", "_attempt_store_id")

    def __init__(self, path, provider_id, attempt_store_id):
        self._path = _path(path)
        require(ident(provider_id) and ident(attempt_store_id)
                and provider_id != attempt_store_id, "invalid distinct input store identities")
        self._provider_id = provider_id
        self._attempt_store_id = attempt_store_id

    @property
    def path(self):
        return self._path

    @property
    def provider_id(self):
        return self._provider_id

    @property
    def attempt_store_id(self):
        return self._attempt_store_id

    @contextmanager
    def _transaction(self):
        conn = None
        try:
            conn = _connect(self.path)
            conn.execute("BEGIN IMMEDIATE")
            count, total = _validated(conn, self.provider_id, self.attempt_store_id)
            yield conn, count, total
            conn.execute("COMMIT")
        except (Conflict, sqlite3.Error, OSError, ValueError, TypeError, UnicodeError, RecursionError):
            # Never expose SQLite data, path, original contents or exception text.
            raise Conflict("input store unavailable or invalid") from None
        finally:
            if conn is not None:
                if conn.in_transaction:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                conn.close()

    def validate_pair(self, attempt_store_id):
        require(attempt_store_id == self.attempt_store_id, "input store pair mismatch")
        with self._transaction():
            pass

    def save(self, action_key, original):
        require(body_hash(action_key), "invalid retained action key")
        blob = _canonical_bytes(original)
        sha = hashlib.sha256(blob).hexdigest()
        with self._transaction() as (conn, count, total):
            old = conn.execute("SELECT action_key,original,original_sha256 FROM originals WHERE action_key=?",
                               (action_key,)).fetchone()
            if old is not None:
                require(_stored(old, action_key) == original, "immutable original conflict")
                return
            require(count < MAX_ROWS and total + len(blob) <= MAX_TOTAL_BYTES, "input store capacity")
            conn.execute("INSERT INTO originals VALUES(?,?,?)", (action_key, blob, sha))

    def load(self, action_key):
        require(body_hash(action_key), "invalid retained action key")
        with self._transaction() as (conn, _, __):
            row = conn.execute("SELECT action_key,original,original_sha256 FROM originals WHERE action_key=?",
                               (action_key,)).fetchone()
            return _stored(row, action_key)


def initialize_inputs(path, provider_id, attempt_store_id):
    """Explicit provisioning only. Never overwrite or repair a used path."""
    store = InputStore(path, provider_id, attempt_store_id)
    conn = None
    try:
        fd = os.open(store.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC, 0o600)
        try:
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        conn = _connect(store.path)
        conn.execute("BEGIN IMMEDIATE")
        for statement in (META_SQL, ROWS_SQL):
            conn.execute(statement)
        conn.execute("INSERT INTO input_meta VALUES(1,?,?,?)", (VERSION, provider_id, attempt_store_id))
        _validated(conn, provider_id, attempt_store_id)
        conn.execute("COMMIT")
        # Persist the newly created directory entry as well as SQLite contents.
        parent = os.open(store.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    except (Conflict, sqlite3.Error, OSError, ValueError, TypeError):
        # Leave an incomplete provisioning for explicit investigation; never recreate.
        raise Conflict("explicit input store initialization failed") from None
    finally:
        if conn is not None:
            conn.close()
    return open_inputs(path, provider_id, attempt_store_id)


def open_inputs(path, expected_provider_id, expected_attempt_store_id):
    store = InputStore(path, expected_provider_id, expected_attempt_store_id)
    store.validate_pair(expected_attempt_store_id)
    return store
