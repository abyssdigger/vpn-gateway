"""Durable noncanonical attempt integrity. No network, authority, or rearm."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import re
import sqlite3

from core import Conflict, canonical, digest, ident, require, strict_json
from project_tasks import body_hash

VERSION = 1
MAX_DESCRIPTOR_BYTES = 4096
MAX_LOCATOR_BYTES = 1024
MAX_ROWS = 10000
BUSY_MS = 2000
STATES = {"PREPARED", "STARTED", "UNRESOLVED", "VERIFIED"}
KEY = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,511}\Z")
FORBIDDEN = {"token", "credential", "credentials", "secret", "password", "authorization",
             "auth", "bearer", "prose", "payload", "body", "private_key", "raw"}
META_SQL = ("CREATE TABLE store_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
            "version INTEGER NOT NULL, store_id TEXT NOT NULL)")
ATTEMPTS_SQL = ("CREATE TABLE attempts (action_key TEXT PRIMARY KEY NOT NULL, "
                "action_descriptor TEXT NOT NULL, effect_key TEXT NOT NULL, "
                "effect_descriptor TEXT NOT NULL, state TEXT NOT NULL, "
                "diagnostic_code TEXT, receipt_sha256 TEXT, locator TEXT)")
INDEX_SQL = ("CREATE UNIQUE INDEX effect_started_once ON attempts(effect_key) "
             "WHERE state != 'PREPARED'")
SCHEMA = {("table", "store_meta", META_SQL), ("table", "attempts", ATTEMPTS_SQL),
          ("index", "effect_started_once", INDEX_SQL)}
COLUMNS = ("action_key", "action_descriptor", "effect_key", "effect_descriptor",
           "state", "diagnostic_code", "receipt_sha256", "locator")


def _identity_data(value, max_bytes):
    """Only bounded JSON identity metadata, never arbitrary prose/credential fields.

    A semantic caller owns closed descriptor schemas and must not hide secrets in
    identity values. Generic storage cannot prove that arbitrary IDs are non-secret.
    """
    nodes = 0

    def check(v, depth):
        nonlocal nodes
        nodes += 1
        require(nodes <= 256 and depth <= 6, "identity metadata structural bound")
        if type(v) is dict:
            require(len(v) <= 64, "identity metadata object bound")
            for key, item in v.items():
                require(type(key) is str and KEY.fullmatch(key) is not None
                        and key.lower() not in FORBIDDEN
                        and not set(key.lower().split("_")) & {"token", "secret", "password", "credential"},
                        "unsupported identity metadata field")
                check(item, depth+1)
        elif type(v) is list:
            require(len(v) <= 64, "identity metadata array bound")
            for item in v:
                check(item, depth+1)
        elif type(v) is str:
            require(VALUE.fullmatch(v) is not None, "unsupported identity metadata string")
        elif type(v) is int:
            require(-(2**63) <= v < 2**63, "identity metadata integer bound")
        else:
            require(v is None or type(v) is bool, "unsupported identity metadata type")

    require(type(value) is dict and bool(value), "nonempty identity object required")
    check(value, 0)
    text = canonical(value)
    require(len(text.encode("utf-8")) <= max_bytes, "identity metadata byte bound")
    return text


def _decode(text, max_bytes):
    require(type(text) is str and len(text.encode("utf-8")) <= max_bytes,
            "stored identity metadata bound")
    try:
        value = strict_json(text)
    except Conflict:
        raise Conflict("invalid stored identity metadata") from None
    require(_identity_data(value, max_bytes) == text, "noncanonical stored identity metadata")
    return value


def _path(path):
    try:
        require(os.fspath(path) not in ("", ":memory:"), "durable file path required")
        return Path(path).absolute()
    except (TypeError, ValueError, OSError):
        raise Conflict("invalid attempt store path") from None


def _connect(path):
    require(path.is_file(), "existing durable attempt store required")
    # mode=rw forbids SQLite's implicit creation even on a path-removal race.
    conn = sqlite3.connect(path.as_uri()+"?mode=rw", uri=True,
                           timeout=BUSY_MS/1000, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout="+str(BUSY_MS))
        conn.execute("PRAGMA synchronous=FULL")
        require(conn.execute("PRAGMA synchronous").fetchone() == (2,)
                and conn.execute("PRAGMA journal_mode").fetchone() == ("delete",),
                "unsupported attempt store durability settings")
        return conn
    except BaseException:
        conn.close()
        raise


def _validated(conn, store_id):
    require(set(conn.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL")) == SCHEMA,
            "unknown attempt store schema")
    require(conn.execute("SELECT singleton,version,store_id FROM store_meta").fetchall()
            == [(1, VERSION, store_id)], "attempt store identity/version mismatch")
    require(conn.execute("PRAGMA quick_check(1)").fetchall() == [("ok",)], "attempt store integrity failure")
    count, largest_action, largest_effect, largest_locator = conn.execute(
        "SELECT count(*),coalesce(max(length(action_descriptor)),0),"
        "coalesce(max(length(effect_descriptor)),0),coalesce(max(length(locator)),0) FROM attempts"
    ).fetchone()
    require(count <= MAX_ROWS and largest_action <= MAX_DESCRIPTOR_BYTES
            and largest_effect <= MAX_DESCRIPTOR_BYTES and largest_locator <= MAX_LOCATOR_BYTES,
            "stored attempt bound")
    rows, effects, claimed = {}, {}, set()
    for values in conn.execute("SELECT "+",".join(COLUMNS)+" FROM attempts"):
        row = dict(zip(COLUMNS, values))
        ak, ek, state = row["action_key"], row["effect_key"], row["state"]
        require(body_hash(ak) and body_hash(ek) and state in STATES, "invalid stored attempt identity/state")
        action = _decode(row["action_descriptor"], MAX_DESCRIPTOR_BYTES)
        effect = _decode(row["effect_descriptor"], MAX_DESCRIPTOR_BYTES)
        require(digest(row["action_descriptor"]) == ak and digest(row["effect_descriptor"]) == ek,
                "stored attempt descriptor digest mismatch")
        require(ek not in effects or effects[ek] == row["effect_descriptor"],
                "conflicting stored effect identity")
        effects[ek] = row["effect_descriptor"]
        diagnostic, receipt, locator = row["diagnostic_code"], row["receipt_sha256"], row["locator"]
        require(diagnostic is None or ident(diagnostic), "invalid stored diagnostic code")
        if state != "PREPARED":
            require(ek not in claimed, "multiple started attempts for one effect")
            claimed.add(ek)
        if state in ("PREPARED", "STARTED"):
            require(diagnostic is None and receipt is None and locator is None,
                    "unexpected prepared/started metadata")
        elif state == "UNRESOLVED":
            require(diagnostic is not None and receipt is None and locator is None,
                    "invalid unresolved metadata")
        else:
            require(body_hash(receipt), "invalid verified receipt digest")
        if locator is not None:
            locator = _decode(locator, MAX_LOCATOR_BYTES)
        require(ak not in rows, "duplicate stored action identity")
        rows[ak] = dict(row, action_descriptor=action, effect_descriptor=effect, locator=locator)
    return rows


class AttemptStore:
    """All operations re-open and validate the same explicitly pinned store."""

    def __init__(self, path, store_id):
        self.path = _path(path)
        require(ident(store_id), "invalid attempt store identity")
        self.store_id = store_id

    @contextmanager
    def _transaction(self):
        conn = None
        try:
            conn = _connect(self.path)
            # Serialize decisions and writes across independent local connections.
            conn.execute("BEGIN IMMEDIATE")
            rows = _validated(conn, self.store_id)
            yield conn, rows
            conn.execute("COMMIT")
        except Conflict:
            raise
        except (sqlite3.Error, OSError, ValueError, TypeError, UnicodeError, RecursionError):
            raise Conflict("attempt store unavailable or invalid") from None
        finally:
            if conn is not None:
                if conn.in_transaction:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                conn.close()

    def status(self, action_key):
        require(body_hash(action_key), "invalid action key")
        with self._transaction() as (_, rows):
            return rows.get(action_key)

    def claimed(self, effect_descriptor):
        """Locate the one attempt that crossed the external-effect boundary."""
        effect = _identity_data(effect_descriptor, MAX_DESCRIPTOR_BYTES)
        ek = digest(effect)
        with self._transaction() as (_, rows):
            matches = [r for r in rows.values() if r["effect_key"] == ek]
            require(all(canonical(r["effect_descriptor"]) == effect for r in matches),
                    "effect descriptor binding mismatch")
            started = [r for r in matches if r["state"] != "PREPARED"]
            require(len(started) <= 1, "multiple claimed attempts")
            return started[0] if started else None

    def prepare(self, action_descriptor, effect_descriptor):
        action = _identity_data(action_descriptor, MAX_DESCRIPTOR_BYTES)
        effect = _identity_data(effect_descriptor, MAX_DESCRIPTOR_BYTES)
        ak, ek = digest(action), digest(effect)
        with self._transaction() as (conn, rows):
            if ak in rows:
                old = rows[ak]
                require(canonical(old["action_descriptor"]) == action and old["effect_key"] == ek
                        and canonical(old["effect_descriptor"]) == effect, "action/effect binding mismatch")
                return old
            require(len(rows) < MAX_ROWS, "attempt store row bound")
            require(all(r["effect_key"] != ek or canonical(r["effect_descriptor"]) == effect
                        for r in rows.values()), "effect descriptor binding mismatch")
            conn.execute("INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?)",
                         (ak, action, ek, effect, "PREPARED", None, None, None))
            return _validated(conn, self.store_id)[ak]

    def start(self, action_key):
        require(body_hash(action_key), "invalid action key")
        with self._transaction() as (conn, rows):
            old = rows.get(action_key)
            require(old is not None and old["state"] == "PREPARED", "action not startable")
            require(not any(r["effect_key"] == old["effect_key"] and r["state"] != "PREPARED"
                            for r in rows.values()), "external effect already claimed; never resend")
            changed = conn.execute("UPDATE attempts SET state='STARTED' WHERE action_key=? AND state='PREPARED'",
                                   (action_key,)).rowcount
            require(changed == 1, "atomic START transition failed")
            return _validated(conn, self.store_id)[action_key]

    def mark_unresolved(self, action_key, diagnostic_code):
        require(body_hash(action_key) and ident(diagnostic_code), "invalid unresolved metadata")
        with self._transaction() as (conn, rows):
            old = rows.get(action_key)
            require(old is not None and old["state"] == "STARTED", "invalid UNRESOLVED transition")
            conn.execute("UPDATE attempts SET state='UNRESOLVED',diagnostic_code=? WHERE action_key=?",
                         (diagnostic_code, action_key))
            return _validated(conn, self.store_id)[action_key]

    def mark_verified(self, action_key, receipt_sha256, locator=None):
        require(body_hash(action_key) and body_hash(receipt_sha256), "invalid verified receipt identity")
        locator_text = None if locator is None else _identity_data(locator, MAX_LOCATOR_BYTES)
        with self._transaction() as (conn, rows):
            old = rows.get(action_key)
            require(old is not None and old["state"] in ("STARTED", "UNRESOLVED"), "invalid VERIFIED transition")
            conn.execute("UPDATE attempts SET state='VERIFIED',receipt_sha256=?,locator=? WHERE action_key=?",
                         (receipt_sha256, locator_text, action_key))
            return _validated(conn, self.store_id)[action_key]


def initialize(path, store_id):
    """Explicit provisioning only: never overwrite, migrate or recover a store."""
    store = AttemptStore(path, store_id)
    conn = None
    try:
        fd = os.open(store.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        conn = _connect(store.path)
        conn.execute("BEGIN IMMEDIATE")
        for statement in (META_SQL, ATTEMPTS_SQL, INDEX_SQL):
            conn.execute(statement)
        conn.execute("INSERT INTO store_meta VALUES(1,?,?)", (VERSION, store_id))
        _validated(conn, store_id)
        conn.execute("COMMIT")
    except Conflict:
        raise
    except (sqlite3.Error, OSError, ValueError, TypeError):
        # Leave a failed/incomplete provisioned path for explicit investigation.
        # Never auto-delete/recreate a possibly previously used store.
        raise Conflict("explicit attempt store initialization failed") from None
    finally:
        if conn is not None:
            conn.close()
    return open_store(path, store_id)


def open_store(path, expected_store_id):
    """Runtime open requires existing provisioned store; no implicit creation."""
    store = AttemptStore(path, expected_store_id)
    with store._transaction():
        pass
    return store
