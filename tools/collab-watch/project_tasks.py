"""Pure v2 work-plane observation and exact material admission."""
from __future__ import annotations

import re
from datetime import datetime

from core import canonical, digest, ident, positive, read_comment, require, strict_json

STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
SHA = re.compile(r"[0-9a-f]{40}")
HASH = re.compile(r"[0-9a-f]{64}")
HEADER = "<!-- vpng-collab-task-material/2"
MAX_MATERIAL = 2 * 1024 * 1024


def shape(value, fields, label):
    require(isinstance(value, dict) and set(value) == set(fields), "invalid " + label)
    return value


def stamp(value):
    require(isinstance(value, str) and STAMP.fullmatch(value) is not None,
            "invalid UTC timestamp")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        require(False, "invalid UTC timestamp")
    return value


def sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def body_hash(value):
    return isinstance(value, str) and HASH.fullmatch(value) is not None


def comment(row):
    cid, actor, body = read_comment(row)
    require(len(body.encode("utf-8")) <= MAX_MATERIAL, "comment exceeds material bound")
    created, updated = stamp(row.get("created_at")), stamp(row.get("updated_at"))
    require(created <= updated, "comment timestamp order")
    return {"id": cid, "actor_id": actor, "body": body,
            "created_at": created, "updated_at": updated}


def immutable(row):
    require(row["created_at"] == row["updated_at"], "edited semantic comment")
    return row


def fingerprint(row):
    return digest(canonical(row))


def task_identity(ref):
    shape(ref, {"issue_number", "issue_id"}, "task identity")
    require(positive(ref["issue_number"]) and positive(ref["issue_id"]), "invalid task identity")
    return ref


def spec_reference(ref, revision):
    fields = {"kind", "body_sha256"} | ({"comment_id"} if revision > 1 else set())
    shape(ref, fields, "spec ref")
    require(body_hash(ref["body_sha256"]), "invalid spec hash")
    require(ref["kind"] == ("issue_body" if revision == 1 else "issue_comment"), "wrong spec kind")
    if revision > 1:
        require(positive(ref["comment_id"]), "invalid spec comment ID")
    return ref


def material_reference(ref):
    shape(ref, {"comment_id", "body_sha256"}, "material ref")
    require(positive(ref["comment_id"]) and body_hash(ref["body_sha256"]), "invalid material ref")
    return ref


def close_identity(ref):
    shape(ref, {"id", "actor_id", "created_at"}, "close identity")
    require(positive(ref["id"]) and positive(ref["actor_id"]), "invalid close identity")
    stamp(ref["created_at"])
    return ref


def parse_header(body):
    require(isinstance(body, str) and len(body.encode("utf-8")) <= MAX_MATERIAL,
            "invalid task material body")
    lines = body.split("\n", 3)
    require(len(lines) == 4 and lines[0] == HEADER and lines[2] == "-->"
            and len(lines[1].encode("utf-8")) <= 8192 and "-->" not in lines[1],
            "invalid task material header")
    meta = strict_json(lines[1])
    require(isinstance(meta, dict), "material header object required")
    kind = meta.get("kind")
    require(kind in ("SPEC", "RESULT", "REVIEW"), "unknown material kind")
    fields = {"kind", "role", "incarnation", "task", "revision"}
    if kind != "SPEC":
        fields |= {"attempt", "commit_sha"}
    if kind == "REVIEW":
        fields.add("verdict")
    shape(meta, fields, "material header fields")
    require(ident(meta["task"]) and positive(meta["revision"]), "invalid material task/revision")
    owner = {"SPEC": "SPEC", "RESULT": "BUILDER", "REVIEW": "GUARD"}[kind]
    require(meta["role"] == owner and ident(meta["incarnation"]), "invalid material role/incarnation")
    prose = lines[3]
    if kind != "SPEC":
        require(positive(meta["attempt"]) and sha(meta["commit_sha"]), "invalid material candidate")
        if kind == "REVIEW":
            require(meta["verdict"] in ("ACCEPT", "REWORK", "SPEC_REQUIRED"), "invalid review verdict")
            prefix = "GUARD " + meta["verdict"] + ": "
        else:
            prefix = "Candidate SHA: "
        line, sep, rest = prose.partition("\n")
        require(line == prefix + meta["commit_sha"] and sep and rest.strip(),
                "missing exact visible identity or material prose")
    else:
        require(prose.strip(), "empty specification")
    return meta


def normalize_task(cfg, ref, raw):
    """Normalize the deliberately narrow semantic Issue observation.

    The acquisition layer is responsible for API identity and completeness.
    """
    task_identity(ref)
    shape(raw, {"repository", "number", "id", "is_pull_request", "author_id", "body",
                "created_at", "state", "closed_at", "closed_by", "comments", "events"},
          "task observation")
    require(raw["repository"] == cfg["repository"] and positive(raw["number"])
            and positive(raw["id"]) and raw["number"] == ref["issue_number"]
            and raw["id"] == ref["issue_id"] and raw["is_pull_request"] is False,
            "wrong repository/Issue identity or PR")
    guard = cfg["roles"]["GUARD"]["actor_id"]
    spec_actor = cfg["roles"]["SPEC"]["actor_id"]
    require(positive(raw["author_id"]) and raw["author_id"] == spec_actor,
            "initial specification author mismatch")
    require(isinstance(raw["body"], str) and raw["body"].strip()
            and len(raw["body"].encode("utf-8")) <= MAX_MATERIAL, "invalid Issue body")
    stamp(raw["created_at"])
    require(isinstance(raw["comments"], list) and isinstance(raw["events"], list)
            and len(raw["comments"]) <= 10000 and len(raw["events"]) <= 10000,
            "invalid task observation lists")
    comments = {}
    for item in raw["comments"]:
        row = comment(item)
        cid = row["id"]
        require(cid not in comments or comments[cid] == row, "conflicting physical task comment")
        comments[cid] = row
    events = {}
    for row in raw["events"]:
        shape(row, {"id", "kind", "actor_id", "created_at"}, "state event")
        require(row["kind"] in ("closed", "reopened"), "invalid state event kind")
        close_identity({k: row[k] for k in ("id", "actor_id", "created_at")})
        require(row["id"] not in events or events[row["id"]] == row, "conflicting state event")
        events[row["id"]] = row
    require(not any(x["kind"] == "reopened" for x in events.values()), "pilot forbids reopen")
    require(len(events) <= 1, "multiple close events")
    require(raw["state"] in ("open", "closed"), "invalid Issue state")
    close = None
    if raw["state"] == "closed":
        require(len(events) == 1, "closed Issue without exact close event")
        row = next(iter(events.values()))
        close = {k: row[k] for k in ("id", "actor_id", "created_at")}
        require(positive(raw["closed_by"]) and raw["closed_by"] == close["actor_id"] == guard
                and raw["closed_at"] == close["created_at"]
                and raw["created_at"] < close["created_at"], "inconsistent or unauthorized close")
    else:
        require(not events and raw["closed_at"] is None and raw["closed_by"] is None,
                "open Issue with close evidence")
    identity = {k: raw[k] for k in ("repository", "number", "id", "author_id", "created_at")}
    identity["body_sha256"] = digest(raw["body"])
    return {"identity": identity, "comments": comments, "close": close}


def inspect_material(task, ref, expected, actor):
    """Validate exact existing material, independent of a future control timestamp."""
    row = task["comments"].get(ref["comment_id"])
    require(row is not None, "referenced task material missing")
    immutable(row)
    require(row["actor_id"] == actor and digest(row["body"]) == ref["body_sha256"],
            "task material actor/digest mismatch")
    require(task["identity"]["created_at"] <= row["created_at"], "task material chronology unproved")
    require(parse_header(row["body"]) == expected, "task material header mismatch")
    return row


def bind_material(task, ref, expected, actor, before, ledger):
    """Resolve exactly one same-task referenced comment, never arbitrary text/URL."""
    row = inspect_material(task, ref, expected, actor)
    require(row["created_at"] < before, "task material chronology unproved")
    key = "task:" + str(task["identity"]["id"]) + ":comment:" + str(row["id"])
    ledger[key] = fingerprint(row)
    return row
