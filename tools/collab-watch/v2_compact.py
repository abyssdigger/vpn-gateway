"""V2 compact transport from trusted, complete normalized acquisition.

No network, second lifecycle parser, authority, or provenance claim.
"""
from __future__ import annotations

from dataclasses import dataclass

from collab_watch import MAX_LOCAL_BYTES, MAX_OBSERVED_COMMENTS
from core import Conflict, canonical, digest, positive, require, strict_json
from project_tasks import body_hash, comment, stamp
from split_journal import PREFIX, project_v2, validate_v2_config
from v2_aux import PREFIX as AUX_PREFIX, project_aux

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


def _unpack_rows(rows, retain, opaque_allowed=lambda actor: True):
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
            require(opaque_allowed(actor) and body_hash(data), "invalid opaque digest or partition")
            continue
        require(isinstance(data, str) and retain(actor, data), "invalid raw compact partition")
        raw = {"id": cid, "user": {"id": actor}, "created_at": created,
               "updated_at": updated, "body": data}
        comment(raw)
        semantic.append(raw)
    return semantic


def _views(cfg, value, *, control_retain=None, extra_count=0):
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
    count = extra_count
    if control_retain is None:
        control_retain = lambda a, b: _control_raw(cfg, a, b)
    for key, rows in value["control"].items():
        control[key] = _unpack_rows(rows, control_retain)
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


AGGREGATE_WIRE = "vpng-collab-aggregate-compact-observation/2"


@dataclass(frozen=True, slots=True)
class CompactAggregateV2:
    text: str
    sha256: str
    inventory_sha256: str


def _aggregate_control_raw(cfg, actor, body):
    return (actor in {role["actor_id"] for role in cfg["roles"].values()}
            and body.startswith((PREFIX, AUX_PREFIX)))


def _aggregate_holder_raw(cfg, actor, body):
    return actor == cfg["projectholder"]["actor_id"]


def _all_raw(actor, body):
    return True


def _read_aggregate(cfg, text, expected_sha256):
    validate_v2_config(cfg)
    require(isinstance(text, str) and body_hash(expected_sha256)
            and len(text.encode("utf-8")) <= MAX_LOCAL_BYTES
            and digest(text) == expected_sha256, "aggregate transfer digest/size mismatch")
    value = strict_json(text)
    require(canonical(value) == text and isinstance(value, dict)
            and set(value) == {"protocol", "config_sha256", "control", "tasks", "holder", "signals"},
            "invalid aggregate compact wire")
    require(value["protocol"] == AGGREGATE_WIRE
            and value["config_sha256"] == digest(canonical(cfg)), "aggregate config/protocol mismatch")
    holder = _unpack_rows(value["holder"], lambda a, b: _aggregate_holder_raw(cfg, a, b),
                          lambda a: a != cfg["projectholder"]["actor_id"])
    signals = _unpack_rows(value["signals"], _all_raw, lambda a: False)
    # Reuse accepted task envelope and event validation, not a second task projector.
    task_wire = {key: value[key] for key in ("config_sha256", "control", "tasks")}
    task_wire["protocol"] = WIRE
    control, tasks = _views(cfg, task_wire,
                            control_retain=lambda a, b: _aggregate_control_raw(cfg, a, b),
                            extra_count=len(value["holder"]) + len(value["signals"]))
    inventory = digest(canonical({k: value[k] for k in ("control", "tasks", "holder", "signals")}))
    return (control, tasks, holder, signals), inventory


def compact_aggregate_v2(cfg, control, tasks, holder_rows, signal_rows, previous=None):
    """Prove exact composed projection and retained-state equivalence.

    Input must be trusted, complete normalized aggregate acquisition. Inventory
    digests bind opaque rows but cannot prove honest classification/provenance.
    """
    baseline = project_aux(cfg, control, tasks, holder_rows, signal_rows, previous)
    value = {"protocol": AGGREGATE_WIRE, "config_sha256": digest(canonical(cfg)),
             "control": {key: _pack_rows(rows, lambda a, b: _aggregate_control_raw(cfg, a, b))
                         for key, rows in control.items()},
             "tasks": {key: dict(task, comments=_pack_rows(task["comments"], _task_raw),
                                 events=_pack_events(task["events"]))
                       for key, task in tasks.items()},
             "holder": _pack_rows(holder_rows, lambda a, b: _aggregate_holder_raw(cfg, a, b)),
             "signals": _pack_rows(signal_rows, _all_raw)}
    wire = canonical(value)
    sha = digest(wire)
    partitions, inventory = _read_aggregate(cfg, wire, sha)
    require(project_aux(cfg, *partitions, previous) == baseline,
            "aggregate raw/compact semantic mismatch")
    return CompactAggregateV2(wire, sha, inventory)


def decode_compact_aggregate_v2(cfg, text, expected_sha256, previous=None):
    """Admit exact trusted aggregate bytes; semantic conflicts fail closed."""
    partitions, inventory = _read_aggregate(cfg, text, expected_sha256)
    project_aux(cfg, *partitions, previous)
    return CompactAggregateV2(text, expected_sha256, inventory)


def aggregate_semantic_view(cfg, observation):
    require(type(observation) is CompactAggregateV2, "invalid aggregate compact observation type")
    partitions, inventory = _read_aggregate(cfg, observation.text, observation.sha256)
    require(inventory == observation.inventory_sha256, "aggregate compact inventory mismatch")
    return (*partitions, inventory)


def project_compact_aggregate_v2(cfg, observation, previous=None):
    *partitions, _ = aggregate_semantic_view(cfg, observation)
    return project_aux(cfg, *partitions, previous)


def derive_task_compact(cfg, aggregate):
    """Derive task compact from one admitted aggregate wire, preserving inventory."""
    try:
        require(type(aggregate) is CompactAggregateV2, "exact aggregate compact required")
        admitted = decode_compact_aggregate_v2(cfg, aggregate.text, aggregate.sha256)
        require(admitted == aggregate, "aggregate inventory mismatch")
        value = strict_json(admitted.text)
        control = {}
        for room, rows in value["control"].items():
            control[room] = [
                ["opaque", *row[1:5], digest(row[5])]
                if row[0] == "raw" and not _control_raw(cfg, row[2], row[5])
                else row
                for row in rows
            ]
        wire = canonical({"protocol": WIRE, "config_sha256": value["config_sha256"],
                          "control": control, "tasks": value["tasks"]})
        return decode_compact_v2(cfg, wire, digest(wire))
    except (Conflict, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise Conflict("task compact derivation failed") from None
