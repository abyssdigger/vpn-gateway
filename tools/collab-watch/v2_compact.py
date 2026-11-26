"""V2 compact transport from trusted, complete normalized acquisition.

No network, second lifecycle parser, authority, or provenance claim.
"""
from __future__ import annotations

from dataclasses import dataclass

from collab_watch import MAX_LOCAL_BYTES, MAX_OBSERVED_COMMENTS
from core import canonical, digest, positive, require, strict_json
from project_tasks import body_hash, comment, stamp
from split_journal import PREFIX, project_v2, validate_v2_config

WIRE = "vpng-collab-compact-observation/2"
MATERIAL_PREFIX = "<!-- vpng-collab-task-material/"


@dataclass(frozen=True, slots=True)
class CompactV2:
    text: str
    sha256: str
    inventory_sha256: str


def _control_raw(cfg, actor, body):
    return actor in {role["actor_id"] for role in cfg["roles"].values()} and body.startswith(PREFIX)


def _task_raw(actor, body):
    return body.startswith(MATERIAL_PREFIX)


def _pack_rows(rows, retain):
    """Validate physical identity before dropping any ordinary prose."""
    require(isinstance(rows, list), "invalid comment partition")
    seen = {}
    for raw in rows:
        row = comment(raw)
        cid = row["id"]
        require(cid not in seen or seen[cid] == row, "conflicting physical compact input row")
        seen[cid] = row
    packed = []
    for cid, row in sorted(seen.items()):
        actor, body = row["actor_id"], row["body"]
        keep = retain(actor, body)
        packed.append(["raw" if keep else "opaque", cid, actor,
                       row["created_at"], row["updated_at"], body if keep else digest(body)])
    return packed


def _pack_events(events):
    # The accepted raw projector has already validated event shape/identity.
    unique = {}
    for e in events:
        require(e["id"] not in unique or unique[e["id"]] == e, "conflicting lifecycle event")
        unique[e["id"]] = e
    return [e for _, e in sorted(unique.items())]


def _unpack_rows(rows, retain):
    """Only raw rows reach the canonical projector; opaque rows are inventory."""
    require(isinstance(rows, list), "invalid compact row list")
    semantic = []
    previous_id = 0
    for item in rows:
        require(isinstance(item, list) and len(item) == 6, "invalid compact row")
        kind, cid, actor, created, updated, data = item
        require(kind in ("raw", "opaque") and positive(cid) and positive(actor)
                and cid > previous_id, "invalid/duplicate/unordered physical compact row")
        previous_id = cid
        require(stamp(created) <= stamp(updated), "invalid compact row chronology")
        if kind == "opaque":
            require(body_hash(data), "invalid opaque digest")
            continue
        require(isinstance(data, str) and retain(actor, data), "invalid raw compact partition")
        raw = {"id": cid, "user": {"id": actor}, "created_at": created,
               "updated_at": updated, "body": data}
        comment(raw)
        semantic.append(raw)
    return semantic


def _views(cfg, value):
    """Reconstruct only semantic snapshots, not fabricated opaque bodies."""
    validate_v2_config(cfg)
    require(isinstance(value, dict) and set(value) ==
            {"protocol", "config_sha256", "control", "tasks"}, "invalid compact wire fields")
    require(value["protocol"] == WIRE and value["config_sha256"] == digest(canonical(cfg)),
            "compact config/protocol mismatch")
    require(isinstance(value["control"], dict) and
            set(value["control"]) == {str(r) for r in cfg["journal_rooms"]}, "wrong control partitions")
    require(isinstance(value["tasks"], dict), "invalid task partitions")
    control = {}
    tasks = {}
    count = 0
    for key, rows in value["control"].items():
        control[key] = _unpack_rows(rows, lambda a, b: _control_raw(cfg, a, b))
        count += len(rows)
    for key, task in value["tasks"].items():
        require(isinstance(task, dict) and set(task) ==
                {"repository", "number", "id", "is_pull_request", "author_id", "body",
                 "created_at", "state", "closed_at", "closed_by", "comments", "events"},
                "invalid compact task envelope")
        require(positive(task["number"]) and str(task["number"]) == key,
                "wrong compact task partition key")
        rows = task["comments"]
        raw_rows = _unpack_rows(rows, _task_raw)
        events = task["events"]
        require(isinstance(events, list) and all(isinstance(e, dict) and positive(e.get("id"))
                for e in events), "invalid compact event list")
        ids = [e["id"] for e in events]
        require(ids == sorted(set(ids)), "noncanonical compact lifecycle inventory")
        count += len(rows) + len(events)
        tasks[key] = dict(task, comments=raw_rows)
    require(count <= MAX_OBSERVED_COMMENTS, "compact observation row bound")
    return control, tasks


def _read(cfg, text, expected_sha256):
    require(isinstance(text, str) and body_hash(expected_sha256)
            and len(text.encode("utf-8")) <= MAX_LOCAL_BYTES
            and digest(text) == expected_sha256, "compact transfer digest/size mismatch")
    value = strict_json(text)
    require(canonical(value) == text, "noncanonical compact wire")
    control, tasks = _views(cfg, value)
    inventory = digest(canonical({"control": value["control"], "tasks": value["tasks"]}))
    return control, tasks, inventory


def compact_v2(cfg, control, tasks, previous=None):
    """Prove exact projection/state equivalence before emitting compact bytes.

    Input must already be complete, stable, normalized Unit-2 acquisition.
    Offline fixtures may exercise this seam but do not prove acquisition.
    """
    baseline = project_v2(cfg, control, tasks, previous)
    value = {"protocol": WIRE, "config_sha256": digest(canonical(cfg)),
             "control": {key: _pack_rows(rows, lambda a, b: _control_raw(cfg, a, b))
                         for key, rows in control.items()},
             "tasks": {key: dict(task, comments=_pack_rows(task["comments"], _task_raw),
                                 events=_pack_events(task["events"]))
                       for key, task in tasks.items()}}
    wire = canonical(value)
    sha = digest(wire)
    c, t, inventory = _read(cfg, wire, sha)
    require(project_v2(cfg, c, t, previous) == baseline, "raw/compact semantic mismatch")
    return CompactV2(wire, sha, inventory)


def decode_compact_v2(cfg, text, expected_sha256, previous=None):
    """Admit exact trusted transferred bytes and their canonical projection.

    Digest is not proof of honest classification or GitHub provenance.
    """
    control, tasks, inventory = _read(cfg, text, expected_sha256)
    project_v2(cfg, control, tasks, previous)
    return CompactV2(text, expected_sha256, inventory)


def semantic_view(cfg, observation):
    """Return fresh semantic snapshots and full inventory binding.

    No opaque row is inserted into either semantic snapshot.
    """
    require(isinstance(observation, CompactV2), "invalid compact observation type")
    c, t, inventory = _read(cfg, observation.text, observation.sha256)
    require(inventory == observation.inventory_sha256, "compact inventory mismatch")
    return c, t, inventory


def project_compact_v2(cfg, observation, previous=None):
    control, tasks, _ = semantic_view(cfg, observation)
    return project_v2(cfg, control, tasks, previous)
