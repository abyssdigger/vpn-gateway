"""Staged 9b-C-A admission spool. No delegate, credentials, scheduler or authority."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import sqlite3
import stat

from core import Conflict, canonical, ident, positive, require, strict_json
from project_tasks import body_hash
from split_journal import validate_v2_config
from v2_actuator import FIELDS, _bound
from v2_attempts import MAX_ROWS as MAX_ATTEMPTS
from v2_identity import select_identity, validate_bindings
from v2_inputs import MAX_INPUT_BYTES, MAX_ROWS as MAX_INPUTS, MAX_TOTAL_BYTES
from v2_trusted_writer import (NEW_OPERATIONS, RECONCILE_OPERATIONS,
                               _closed_result, _rejected, _unknown)
from v2_writer_ipc import MAX_RESPONSE_BYTES, SessionBinding

VERSION = 1
MAX_RECORDS = 10000
MAX_ORIGINAL_BYTES = 512 * 1024 * 1024
MAX_CONFIG_BYTES = 256 * 1024
MAX_PIN_BYTES = 4096
META_RESERVE = 4096
RESULT_RESERVE = MAX_RESPONSE_BYTES
MAX_DB_BYTES = 1024 * 1024 * 1024  # local rejection bound, not disk headroom
MAX_VERSION = 2**63 - 1
BUSY_MS = 2000
INITIAL = "INITIAL"
FORCED = "FORCED_RECOVERY"
READY = "READY"
MARKED = "DELEGATION_MARKED"
RESULT = "RESULT"
TV = "TERMINAL_VERIFIED"
TN = "TERMINAL_NO_EFFECT"
RR = "RECOVERY_REQUIRED"
NC = "NO_CLAIM_REARM_CANDIDATE"
RN = "RETAINED_NONTERMINAL"
CLASSES = (TV, TN, RR, NC, RN)

META_SQL = ("CREATE TABLE spool_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
            "version INTEGER NOT NULL, pin BLOB NOT NULL, config BLOB NOT NULL)")
ROWS_SQL = (
    "CREATE TABLE spool_records (request_id TEXT PRIMARY KEY NOT NULL, "
    "original BLOB NOT NULL, original_sha256 TEXT NOT NULL, original_bytes INTEGER NOT NULL, "
    "reconcile_only INTEGER NOT NULL, role TEXT NOT NULL, incarnation TEXT NOT NULL, "
    "actor INTEGER NOT NULL, operation TEXT NOT NULL, policy_id TEXT NOT NULL, "
    "policy_sha256 TEXT NOT NULL, first_session TEXT NOT NULL, first_generation INTEGER NOT NULL, "
    "attempt_charge INTEGER NOT NULL, input_charge INTEGER NOT NULL, "
    "input_bytes_charge INTEGER NOT NULL, meta_charge INTEGER NOT NULL, result_charge INTEGER NOT NULL, "
    "state TEXT NOT NULL, version INTEGER NOT NULL, execution TEXT, uncertain INTEGER NOT NULL, "
    "classification TEXT, diagnostic TEXT, result BLOB)"
)
SCHEMA = {("table", "spool_meta", META_SQL), ("table", "spool_records", ROWS_SQL)}
COLS = ("request_id", "original", "original_sha256", "original_bytes", "reconcile_only",
        "role", "incarnation", "actor", "operation", "policy_id", "policy_sha256",
        "first_session", "first_generation", "attempt_charge", "input_charge",
        "input_bytes_charge", "meta_charge", "result_charge", "state", "version",
        "execution", "uncertain", "classification", "diagnostic", "result")
META_COLS = tuple(x for x in COLS if x not in ("original", "result"))
QUOTA_NAMES = ("records", "original_bytes", "metadata_bytes", "result_bytes",
               "attempt_rows", "input_rows", "input_bytes")
QUOTA_MAX = (MAX_RECORDS, MAX_ORIGINAL_BYTES, MAX_RECORDS * META_RESERVE,
             MAX_RECORDS * RESULT_RESERVE, MAX_ATTEMPTS, MAX_INPUTS, MAX_TOTAL_BYTES)


@dataclass(frozen=True, slots=True)
class Quotas:
    records: int
    original_bytes: int
    metadata_bytes: int
    result_bytes: int
    attempt_rows: int
    input_rows: int
    input_bytes: int

    def __post_init__(self):
        require(all(type(v) is int and 0 <= v <= limit
                    for v, limit in zip(self.values(), QUOTA_MAX)), "invalid spool quotas")

    def values(self):
        return tuple(getattr(self, k) for k in QUOTA_NAMES)


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    """Opaque trusted policy identity, not its contents or a worker-selected limit."""
    policy_id: str
    sha256: str

    def __post_init__(self):
        require(type(self.policy_id) is str and ident(self.policy_id)
                and type(self.sha256) is str and body_hash(self.sha256),
                "invalid resource policy identity")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encode(value):
    return canonical(value).encode("utf-8")


def _shape(value, keys):
    return type(value) is dict and all(type(k) is str for k in value) and set(value) == keys


def _strict_copy(value, bound):
    raw = _encode(value)
    require(0 < len(raw) <= bound, "bounded metadata required")
    return raw, strict_json(raw.decode("utf-8"))


def _checked_original(request, cfg_bytes, role, incarnation, actor):
    """Pure admission; rerun for each selected durable original before marking."""
    try:
        require(_shape(request, {"original", "reconcile_only"}), "invalid request shape")
        original, mode = request["original"], request["reconcile_only"]
        require(type(original) is str and type(mode) is bool
                and 0 < len(original) <= MAX_INPUT_BYTES, "invalid original")
        raw = original.encode("utf-8")
        require(0 < len(raw) <= MAX_INPUT_BYTES, "invalid original byte bound")
        data = strict_json(original)
        require(_shape(data, FIELDS) and _encode(data) == raw
                and _encode(data["cfg"]) == cfg_bytes
                and type(data["role"]) is str and data["role"] == role
                and type(data["incarnation"]) is str and data["incarnation"] == incarnation
                and positive(data["actor"]) and data["actor"] == actor,
                "original scope mismatch")
        op = data["operation"]
        require(type(op) is str and op in (RECONCILE_OPERATIONS if mode else NEW_OPERATIONS),
                "unsupported operation")
        _bound(original)
        return raw, mode, op
    except Exception:
        raise Conflict("spool pure admission rejected") from None


class ProvenanceError(Conflict):
    """Structurally closed but impossible from the accepted source path."""


def classify_result(value, operation, original_mode, execution):
    """Validate the full operation-specific 9a union and canonical IPC envelope.

    Returns detached bytes and classification. No-claim is an observation, not
    authority to send. A forced result can resolve earlier uncertainty only by
    a verified receipt or the exact no-claim triple.
    """
    require(type(operation) is str and operation in RECONCILE_OPERATIONS
            and type(original_mode) is bool and execution in (INITIAL, FORCED)
            and (original_mode or operation in NEW_OPERATIONS), "invalid execution provenance")
    try:
        clean = None
        for special in (_rejected(), _unknown()):
            if _shape(value, set(special)) and all(type(value[k]) is type(v) and value[k] == v
                                                   for k, v in special.items()):
                clean = special
                break
        if clean is None:
            clean = _closed_result(value, operation)
        envelope = _encode({"state": RESULT, "result": clean})
        require(0 < len(envelope) <= RESULT_RESERVE, "result envelope too large")
    except Exception:
        raise Conflict("spool closed result rejected") from None
    state, code, key = clean["state"], clean["code"], clean["action_key"]
    reconcile = original_mode or execution == FORCED
    if ((state == "NO_ATTEMPT" and key is not None)
            or (state == "EFFECT_UNKNOWN" and
                ((key is None) != (code in ("FENCED_INVOCATION_UNCONFIRMED",
                                            "TRUSTED_RESULT_INVALID"))))
            or (reconcile and (state == "PREPARED" or code in
                               ("START_NOT_CONFIRMED", "START_OR_FENCE_EXIT_UNCONFIRMED")))
            or (not reconcile and code == "NO_CLAIMED_EFFECT")):
        raise ProvenanceError("spool result provenance rejected")
    if state == "VERIFIED":
        classification = TV
    elif code == "NO_CLAIMED_EFFECT":
        classification = TN if original_mode else NC
    elif execution == FORCED or state in ("UNRESOLVED", "EFFECT_UNKNOWN"):
        classification = RR
    else:
        classification = RN
    return envelope, classification


def _path(path):
    require(os.fspath(path) not in ("", ":memory:"), "durable spool path required")
    return Path(path).absolute()


def _identity(info):
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
            and info.st_size <= MAX_DB_BYTES,
            "invalid spool file")
    return info.st_dev, info.st_ino


def _pin(path):
    fd = os.open(path, os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        identity = _identity(os.fstat(fd))
        require(_identity(os.lstat(path)) == identity, "spool path changed")
        return fd, identity
    except BaseException:
        os.close(fd)
        raise


def _connect(path, identity):
    require(_identity(os.lstat(path)) == identity, "spool path changed")
    db = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True,
                         timeout=BUSY_MS / 1000, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=" + str(BUSY_MS))
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA cache_size=-2048")
        require(db.execute("PRAGMA synchronous").fetchone() == (2,)
                and db.execute("PRAGMA journal_mode").fetchone() == ("delete",),
                "invalid spool durability settings")
        return db
    except BaseException:
        db.close()
        raise


# The aggregate scan uses only SQL metadata and length/type operations on BLOBs.
# No original or result BLOB is returned to Python by this scan.
def _invalid_sql():
    checks = []
    for col in ("request_id", "original_sha256", "policy_sha256"):
        checks += [f"typeof({col})!='text'", f"length(CAST({col} AS BLOB))!=64", f"instr({col},char(0))!=0",
                   f"{col} GLOB '*[^0-9a-f]*'"]
    for col in ("role", "incarnation", "policy_id", "first_session", "operation", "state"):
        checks += [f"typeof({col})!='text'", f"length(CAST({col} AS BLOB)) NOT BETWEEN 1 AND 128",
                   f"instr({col},char(0))!=0"]
    for col in ("original_bytes", "reconcile_only", "actor", "first_generation",
                "attempt_charge", "input_charge", "input_bytes_charge", "meta_charge",
                "result_charge", "version", "uncertain"):
        checks.append(f"typeof({col})!='integer'")
    checks += [
        "typeof(original)!='blob'", f"original_bytes NOT BETWEEN 1 AND {MAX_INPUT_BYTES}",
        "length(original)!=original_bytes", "reconcile_only NOT IN (0,1)",
        "actor<=0", "first_generation<=0", "version<=0", "uncertain NOT IN (0,1)",
        "attempt_charge!=CASE reconcile_only WHEN 0 THEN 2 ELSE 0 END",
        "input_charge!=CASE reconcile_only WHEN 0 THEN 1 ELSE 0 END",
        "input_bytes_charge!=CASE reconcile_only WHEN 0 THEN original_bytes ELSE 0 END",
        f"meta_charge!={META_RESERVE}", f"result_charge!={RESULT_RESERVE}",
        "role NOT IN ('SPEC','GUARD','BUILDER')",
        "operation NOT IN (" + ",".join("'" + op + "'" for op in sorted(RECONCILE_OPERATIONS)) + ")",
        "(reconcile_only=0 AND operation='signal_comment')",
        # CASE prevents SQL NULL/unknown from escaping a required conjunction.
        "CASE state "
        "WHEN 'READY' THEN NOT (version=1 AND execution IS NULL AND uncertain=0 "
        "AND classification IS NULL AND diagnostic IS NULL AND result IS NULL) "
        "WHEN 'DELEGATION_MARKED' THEN CASE WHEN version>=2 AND execution IN ('INITIAL','FORCED_RECOVERY') "
        "AND uncertain=1 AND classification='RECOVERY_REQUIRED' AND result IS NULL "
        "AND (diagnostic IS NULL OR diagnostic IN ('PROVENANCE_INVALID','RESULT_INVALID')) "
        "THEN 0 ELSE 1 END "
        "WHEN 'RESULT' THEN CASE WHEN version>=3 AND execution IN ('INITIAL','FORCED_RECOVERY') "
        "AND classification IN (" + ",".join("'" + c + "'" for c in CLASSES) + ") "
        "AND uncertain=CASE classification WHEN 'RECOVERY_REQUIRED' THEN 1 ELSE 0 END "
        "AND (execution!='FORCED_RECOVERY' OR classification!='RETAINED_NONTERMINAL') "
        "AND (classification!='NO_CLAIM_REARM_CANDIDATE' OR (execution='FORCED_RECOVERY' AND reconcile_only=0)) "
        "AND (classification!='TERMINAL_NO_EFFECT' OR reconcile_only=1) "
        "AND diagnostic IS NULL AND typeof(result)='blob' "
        f"AND length(result) BETWEEN 1 AND {RESULT_RESERVE} THEN 0 ELSE 1 END ELSE 1 END"
    ]
    return " OR ".join("(" + x + ")" for x in checks)


AGGREGATE = ("SELECT count(*), coalesce(sum(original_bytes),0), coalesce(sum(meta_charge),0), "
             "coalesce(sum(result_charge),0), coalesce(sum(attempt_charge),0), "
             "coalesce(sum(input_charge),0), coalesce(sum(input_bytes_charge),0), "
             "coalesce(sum(CASE WHEN " + _invalid_sql() + " THEN 1 ELSE 0 END),0) FROM spool_records")


class Spool:
    """One trusted role/session/policy view of a shared pair-wide admission DB.

    The caller must establish one authoritative physical budget per exact pair,
    trusted installation/path ownership, and continuity. C-A cannot prove
    historical occupancy, rollback resistance, or serialize actual delegation.
    """
    __slots__ = ("_path", "_fd", "_inode", "_cfg", "_pin_bytes", "_quotas",
                 "_scope", "_role", "_incarnation", "_actor", "_session", "_policy")

    def __init__(self, path, *, cfg, bindings, runtime_model, session, spool_id,
                 attempt_store_id, input_store_id, quotas, resource_policy):
        self._fd = None
        try:
            self._path = _path(path)
            require(type(quotas) is Quotas and type(resource_policy) is ResourcePolicy
                    and type(session) is SessionBinding, "trusted spool bootstrap required")
            ids = (spool_id, attempt_store_id, input_store_id)
            require(all(type(x) is str and ident(x) for x in ids) and len(set(ids)) == 3,
                    "invalid distinct spool identities")
            validate_v2_config(cfg)
            validate_bindings(bindings)
            self._cfg, config = _strict_copy(cfg, MAX_CONFIG_BYTES)
            validate_v2_config(config)
            _, detached_bindings = _strict_copy(bindings, MAX_CONFIG_BYTES)
            validate_bindings(detached_bindings)
            selected = select_identity(detached_bindings, runtime_model, config["roles"],
                                       selected_role=session.role)
            self._role, self._incarnation = selected["transport_role"], selected["incarnation"]
            require(self._incarnation == session.incarnation, "session identity mismatch")
            self._actor = config["roles"][self._role]["actor_id"]
            require(positive(self._actor) and self._actor <= MAX_VERSION, "actor bound")
            self._session = SessionBinding(session.role, session.incarnation,
                                           session.owner_generation, session.session_id)
            self._policy = ResourcePolicy(resource_policy.policy_id, resource_policy.sha256)
            self._quotas = Quotas(*quotas.values())
            self._scope = (spool_id, attempt_store_id, input_store_id,
                           config["repository"].lower(), config["journal_epoch"])
            self._pin_bytes = _encode({"scope": self._scope, "quotas": self._quotas.values()})
            require(len(self._pin_bytes) <= MAX_PIN_BYTES, "spool pin bound")
        except Exception:
            raise Conflict("spool bootstrap rejected") from None

    @classmethod
    def provision(cls, path, *, verified_empty_pair, **trusted):
        require(verified_empty_pair is True, "verified empty exact pair required")
        obj = cls(path, **trusted)
        fd = db = None
        try:
            fd = os.open(obj._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                         os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
            os.fchmod(fd, 0o600)
            expected = _identity(os.fstat(fd))
            obj._fd, obj._inode = _pin(obj._path)
            require(obj._inode == expected, "spool file changed")
            os.close(fd)
            fd = None
            db = _connect(obj._path, obj._inode)
            db.execute("BEGIN IMMEDIATE")
            for sql in (META_SQL, ROWS_SQL):
                db.execute(sql)
            db.execute("INSERT INTO spool_meta VALUES(1,?,?,?)",
                       (VERSION, obj._pin_bytes, obj._cfg))
            obj._validate(db)
            db.execute("COMMIT")
            parent = os.open(obj._path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
            obj._check_pin()
            return obj
        except BaseException as exc:
            obj.close()
            if isinstance(exc, Exception):
                raise Conflict("spool provisioning failed") from None
            raise
        finally:
            if db is not None:
                db.close()
            if fd is not None:
                os.close(fd)

    @classmethod
    def open(cls, path, *, expected_inode, **trusted):
        """Existing only; expected physical pin comes from trusted caller."""
        obj = cls(path, **trusted)
        try:
            require(type(expected_inode) is tuple and len(expected_inode) == 2
                    and all(type(x) is int and x >= 0 for x in expected_inode),
                    "trusted physical pin required")
            obj._fd, obj._inode = _pin(obj._path)
            require(obj._inode == expected_inode, "spool physical identity changed")
            with obj._transaction(integrity=True):
                pass
            return obj
        except BaseException as exc:
            obj.close()
            if isinstance(exc, Exception):
                raise Conflict("spool open rejected") from None
            raise

    @property
    def inode(self):
        self._check_pin()
        return self._inode

    def close(self):
        fd = self._fd
        self._fd = None
        if fd is not None:
            os.close(fd)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _check_pin(self):
        require(self._fd is not None and _identity(os.fstat(self._fd)) == self._inode
                and _identity(os.lstat(self._path)) == self._inode, "spool pin changed")

    def _validate(self, db):
        require(set(db.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL"))
                == SCHEMA, "spool schema mismatch")
        require(db.execute("SELECT count(*) FROM spool_meta").fetchone() == (1,)
                and db.execute("SELECT count(*) FROM spool_meta WHERE singleton=1 "
                               "AND typeof(version)='integer' AND version=? "
                               "AND typeof(pin)='blob' AND length(pin)=? AND pin=? "
                               "AND typeof(config)='blob' AND length(config)=? AND config=?",
                               (VERSION, len(self._pin_bytes), self._pin_bytes,
                                len(self._cfg), self._cfg)).fetchone() == (1,),
                "spool pin mismatch")
        values = db.execute(AGGREGATE).fetchone()
        require(len(values) == 8 and values[-1] == 0
                and all(type(v) is int and 0 <= v <= limit
                        for v, limit in zip(values[:-1], self._quotas.values())),
                "spool capacity or metadata integrity rejected")
        return values[:-1]

    @contextmanager
    def _transaction(self, *, integrity=False):
        db = None
        try:
            self._check_pin()
            db = _connect(self._path, self._inode)
            db.execute("BEGIN IMMEDIATE")
            self._check_pin()
            totals = self._validate(db)
            if integrity:
                require(db.execute("PRAGMA quick_check(1)").fetchall() == [("ok",)],
                        "spool database integrity failure")
            yield db, totals
            db.execute("COMMIT")
            self._check_pin()
        except Exception:
            raise Conflict("spool transaction rejected") from None
        finally:
            if db is not None:
                if db.in_transaction:
                    try:
                        db.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                db.close()

    def _request_id(self, mode, sha):
        return _sha(_encode([self._scope, self._role, self._incarnation,
                             self._actor, mode, sha]))

    def _pure(self, request):
        return _checked_original(request, self._cfg, self._role, self._incarnation, self._actor)

    @staticmethod
    def _charges(mode, size):
        return (0, 0, 0, META_RESERVE, RESULT_RESERVE) if mode else (
            2, 1, size, META_RESERVE, RESULT_RESERVE)

    def status(self):
        with self._transaction() as (_, totals):
            return dict(zip(QUOTA_NAMES, totals))

    def list_metadata(self):
        """Bounded pair-wide inventory; no retained payload/result BLOB loaded."""
        with self._transaction() as (db, _):
            roles = strict_json(self._cfg.decode("utf-8"))["roles"]
            rows = []
            for raw in db.execute("SELECT " + ",".join(META_COLS) +
                                  " FROM spool_records ORDER BY request_id"):
                row = dict(zip(META_COLS, raw))
                role = row["role"]
                require(role in roles and row["incarnation"] == roles[role]["incarnation"]
                        and row["actor"] == roles[role]["actor_id"]
                        and ident(row["policy_id"]) and ident(row["first_session"]),
                        "stored inventory scope mismatch")
                expected = _sha(_encode([self._scope, role, row["incarnation"],
                                         row["actor"], bool(row["reconcile_only"]),
                                         row["original_sha256"]]))
                require(expected == row["request_id"], "stored inventory identity mismatch")
                rows.append(row)
            return rows

    def _selected(self, db, request_id):
        require(type(request_id) is str and body_hash(request_id), "invalid request id")
        # _validate ran under the same transaction, so lengths/types are bounded.
        row = db.execute("SELECT " + ",".join(COLS) + " FROM spool_records WHERE request_id=?",
                         (request_id,)).fetchone()
        require(row is not None, "spool request missing")
        r = dict(zip(COLS, row))
        require(r["role"] == self._role and r["incarnation"] == self._incarnation
                and r["actor"] == self._actor and r["policy_id"] == self._policy.policy_id
                and r["policy_sha256"] == self._policy.sha256
                and ident(r["first_session"]) and type(r["original"]) is bytes
                and _sha(r["original"]) == r["original_sha256"], "stored request scope mismatch")
        mode = bool(r["reconcile_only"])
        raw, _, operation = self._pure({"original": r["original"].decode("utf-8"),
                                       "reconcile_only": mode})
        require(raw == r["original"] and len(raw) == r["original_bytes"]
                and operation == r["operation"]
                and request_id == self._request_id(mode, r["original_sha256"])
                and tuple(r[k] for k in ("attempt_charge", "input_charge", "input_bytes_charge",
                                        "meta_charge", "result_charge")) == self._charges(mode, len(raw)),
                "stored immutable request mismatch")
        if r["state"] == RESULT:
            envelope = strict_json(r["result"].decode("utf-8"))
            require(_shape(envelope, {"state", "result"}) and envelope["state"] == RESULT,
                    "stored result envelope mismatch")
            checked, classification = classify_result(envelope["result"], operation, mode, r["execution"])
            require(checked == r["result"] and classification == r["classification"],
                    "stored result provenance mismatch")
        return r

    def load(self, request_id):
        with self._transaction() as (db, _):
            return self._selected(db, request_id)

    def admit(self, request):
        raw, mode, operation = self._pure(request)
        sha = _sha(raw)
        request_id = self._request_id(mode, sha)
        charges = self._charges(mode, len(raw))
        with self._transaction() as (db, totals):
            if db.execute("SELECT 1 FROM spool_records WHERE request_id=?", (request_id,)).fetchone():
                old = self._selected(db, request_id)
                require(old["original"] == raw and old["reconcile_only"] == int(mode)
                        and old["operation"] == operation, "immutable request conflict")
                return request_id
            a, i, b, m, r = charges
            additions = (1, len(raw), m, r, a, i, b)
            require(all(v + delta <= limit for v, delta, limit
                        in zip(totals, additions, self._quotas.values())), "spool quota exhausted")
            values = (request_id, raw, sha, len(raw), int(mode), self._role, self._incarnation,
                      self._actor, operation, self._policy.policy_id, self._policy.sha256,
                      self._session.session_id, self._session.owner_generation, *charges,
                      READY, 1, None, 0, None, None, None)
            db.execute("INSERT INTO spool_records VALUES(" + ",".join("?" for _ in COLS) + ")", values)
            return request_id

    @staticmethod
    def _expect(r, expected_version):
        require(type(expected_version) is int and 0 < expected_version < MAX_VERSION
                and r["version"] == expected_version, "stale or exhausted spool version")

    def _mark(self, request_id, expected_version, execution):
        with self._transaction() as (db, _):
            r = self._selected(db, request_id)
            self._expect(r, expected_version)
            require((execution == INITIAL and r["state"] == READY)
                    or (execution == FORCED and (r["state"] == MARKED or
                        (r["state"] == RESULT and r["classification"] == RR))),
                    "invalid spool delegation transition")
            changed = db.execute(
                "UPDATE spool_records SET state=?,version=version+1,execution=?,uncertain=1,"
                "classification=?,diagnostic=NULL,result=NULL WHERE request_id=? AND version=? AND state=?",
                (MARKED, execution, RR, request_id, expected_version, r["state"])).rowcount
            require(changed == 1, "spool delegation CAS failed")
            return dict(original=r["original"].decode("utf-8"),
                        reconcile_only=bool(r["reconcile_only"]) or execution == FORCED)

    def mark_initial(self, request_id, expected_version):
        return self._mark(request_id, expected_version, INITIAL)

    def mark_recovery(self, request_id, expected_version):
        return self._mark(request_id, expected_version, FORCED)

    def persist_result(self, request_id, expected_version, execution, value):
        """Commit one bounded result or preserve the marker with a fixed diagnostic."""
        with self._transaction() as (db, _):
            r = self._selected(db, request_id)
            self._expect(r, expected_version)
            require(r["state"] == MARKED and execution == r["execution"],
                    "result does not match delegation")
            try:
                raw, classification = classify_result(value, r["operation"],
                                                       bool(r["reconcile_only"]), execution)
            except Conflict as exc:
                diagnostic = "PROVENANCE_INVALID" if isinstance(exc, ProvenanceError) else "RESULT_INVALID"
                changed = db.execute("UPDATE spool_records SET version=version+1,diagnostic=? "
                                     "WHERE request_id=? AND version=? AND state=?",
                                     (diagnostic, request_id, expected_version, MARKED)).rowcount
                require(changed == 1, "spool diagnostic CAS failed")
                return RR
            changed = db.execute("UPDATE spool_records SET state=?,version=version+1,uncertain=?,"
                                 "classification=?,diagnostic=NULL,result=? WHERE request_id=? "
                                 "AND version=? AND state=?",
                                 (RESULT, int(classification == RR), classification, raw,
                                  request_id, expected_version, MARKED)).rowcount
            require(changed == 1, "spool result CAS failed")
            return classification
