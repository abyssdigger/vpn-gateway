"""Conditional existing-task v2 preflight; no synthetic facts or actuator."""
from __future__ import annotations

from core import canonical, digest, positive, require
from journal import framed
from project_tasks import body_hash, inspect_material, normalize_task, shape, sha
from split_journal import MARKER, _registry, advance_relation, physical_ref, project_v2, validate_event
from v2_compact import compact_v2, semantic_view

PROTOCOL = "vpng-collab-preflight/2"
MAX_CANDIDATE_BYTES = 65536
NO_AUTHORITY = "not evaluated; conditional proof only; no mutation or readiness authorized"


def _baseline(cfg, observation, previous):
    control, tasks, inventory = semantic_view(cfg, observation)
    projection, state = project_v2(cfg, control, tasks, previous)
    binding = {"protocol": PROTOCOL, "state": "CONDITIONAL",
               "config_sha256": digest(canonical(cfg)), "journal_epoch": cfg["journal_epoch"],
               "baseline_state_sha256": digest(canonical(state)),
               "inventory_sha256": inventory, "authority": NO_AUTHORITY}
    return projection, tasks, binding


def _task(projection, tasks, name):
    matches = [t for t in projection["tasks"] if t["task"] == name]
    require(len(matches) == 1, "existing registered task required")
    task = matches[0]
    return task, tasks[str(task["issue_number"])]


def _task_binding(task):
    return {k: task[k] for k in ("task", "issue_number", "issue_id", "revision", "state",
                                 "head", "attempt", "accepted_sha")}


def _earliest_fact(projection, event_id):
    matches = [f for f in projection["facts"].values() if f["event"]["event_id"] == event_id]
    require(matches, "current physical predecessor missing")
    return min(matches, key=lambda f: (f["created_at"], f["physical_ref"]))


def _fact_binding(fact):
    return {k: fact[k] for k in ("physical_ref", "body_sha256", "actor_id", "created_at")} | {
        "event_id": fact["event"]["event_id"], "room": fact["event"]["room"]}


def _accept_fact(projection, task, ref):
    shape(ref, {"room", "comment_id", "body_sha256"}, "ACCEPT physical ref")
    require(positive(ref["room"]) and positive(ref["comment_id"]) and body_hash(ref["body_sha256"]),
            "invalid ACCEPT physical ref")
    key = physical_ref(ref["room"], ref["comment_id"])
    fact = projection["facts"].get(key)
    require(fact is not None and fact["body_sha256"] == ref["body_sha256"]
            and fact["event"]["event_id"] == task["head"]
            and fact["event"]["task"] == task["task"]
            and fact["event"]["revision"] == task["revision"]
            and fact["event"]["kind"] == "REVIEW" and fact["event"]["verdict"] == "ACCEPT"
            and fact["event"]["attempt"] == task["attempt"]
            and fact["event"]["commit_sha"] == task["accepted_sha"], "not exact current physical ACCEPT")
    return fact


def _inspect(cfg, task, normalized, event, reference):
    if event["kind"] == "OPEN":
        expected = {"kind": "SPEC", "task": event["task"], "revision": event["revision"],
                    "role": "SPEC", "incarnation": event["incarnation"]}
    else:
        expected = {k: event[k] for k in ("kind", "task", "revision", "attempt", "commit_sha", "incarnation")}
        expected["role"] = event["from"]
        if event["kind"] == "REVIEW":
            expected["verdict"] = event["verdict"]
    actor = cfg["roles"][event["from"]]["actor_id"]
    row = inspect_material(normalized, reference, expected, actor)
    return {"issue_number": task["issue_number"], "issue_id": task["issue_id"],
            "comment_id": row["id"], "actor_id": row["actor_id"], "body_sha256": digest(row["body"]),
            "created_at": row["created_at"], "updated_at": row["updated_at"]}


def _selected(cfg, actor, selected_role, selected_incarnation):
    require(isinstance(selected_role, str) and selected_role in cfg["roles"],
            "explicit selected role required")
    role = cfg["roles"][selected_role]
    require(positive(actor) and role["actor_id"] == actor and
            role["incarnation"] == selected_incarnation, "selected actor/role/incarnation mismatch")
    return {"selected_role": selected_role, "selected_incarnation": selected_incarnation}


def preflight_control(cfg, control, tasks, actor, body, previous=None, *, selected_role, selected_incarnation):
    return preflight_control_compact(cfg, compact_v2(cfg, control, tasks, previous), actor, body, previous,
                                     selected_role=selected_role, selected_incarnation=selected_incarnation)


def preflight_control_compact(cfg, observation, actor, body, previous=None, *, selected_role, selected_incarnation):
    projection, tasks, proof = _baseline(cfg, observation, previous)
    proof.update(_selected(cfg, actor, selected_role, selected_incarnation))
    require(isinstance(body, str) and 0 < len(body.encode("utf-8")) <= MAX_CANDIDATE_BYTES,
            "invalid outgoing candidate size")
    event = framed(body, MARKER)
    require(isinstance(event, dict), "invalid outgoing control candidate")
    validate_event(cfg, event, event.get("room"), actor)
    require(event["from"] == selected_role and event["incarnation"] == selected_incarnation,
            "candidate does not match explicit selected role/incarnation")
    existing = {f["event"]["event_id"]: f["event"] for f in projection["facts"].values()}
    require(event["event_id"] not in existing, "outgoing event already observed; reconcile delivery")
    task, raw = _task(projection, tasks, event["task"])
    require(event["kind"] != "OPEN" or event["revision"] > 1, "initial OPEN not supported here")
    # Validate prospective registry/role/ref constraints without adding a physical fact.
    _registry(cfg, dict(existing, **{event["event_id"]: event}))
    normalized = normalize_task(cfg, {"issue_number": task["issue_number"], "issue_id": task["issue_id"]}, raw)
    require(event["previous"] == task["head"], "candidate predecessor is not current head")
    head_fact = _earliest_fact(projection, task["head"])
    head = head_fact["event"]
    lower = head_fact["created_at"]
    material, accept, observed_close = None, None, None
    if event["kind"] == "OPEN":
        require(task["state"] == "SUPERSEDED" and normalized["close"] is None
                and event["revision"] == task["revision"] + 1, "revision OPEN requires current superseded open task")
        material = _inspect(cfg, task, normalized, event, event["spec_ref"])
    else:
        require(event["revision"] == task["revision"] and event["open_id"] == task["revisions"][-1]["open_id"],
                "stale candidate revision/open ref")
        current_state = task["state"]
        accepted = head if current_state in ("ACCEPTED", "CLOSE_OBSERVED") else None
        if event["kind"] == "DISPOSITION" and event["disposition"] == "CLOSED":
            require(current_state == "CLOSE_OBSERVED" and normalized["close"] is not None
                    and event["close_event"] == normalized["close"], "exact actual close required")
            accept_fact = _accept_fact(projection, task, event["accept_ref"])
            require(accept_fact["physical_ref"] in task["eligible_accept_refs"], "ineligible pre-close ACCEPT")
            accept = _fact_binding(accept_fact)
            observed_close = normalized["close"]
            lower = max(lower, observed_close["created_at"])
            current_state = "ACCEPTED"  # Physical CLOSE_OBSERVED overlays logical ACCEPTED.
        else:
            require(normalized["close"] is None, "candidate cannot modify physically closed task")
        advance_relation(current_state, head, task["attempt"], accepted, event)
        if event["kind"] in ("RESULT", "REVIEW"):
            material = _inspect(cfg, task, normalized, event, event["material_ref"])
    if material is not None:
        lower = max(lower, material["created_at"])
    proof.update(operation="control_comment", task=_task_binding(task),
                 candidate={k: event[k] for k in ("event_id", "kind", "task", "revision", "room",
                                                   "from", "incarnation", "previous")},
                 predecessor=_fact_binding(head_fact), material=material, accept=accept,
                 observed_close=observed_close)
    proof["candidate"].update(actor_id=actor, body_sha256=digest(body))
    proof["postcondition"] = {"actor_id": actor, "body_sha256": digest(body),
                              "event_id": event["event_id"], "room": event["room"],
                              "immutable": True, "created_at_strictly_after": lower}
    return proof


def preflight_close(cfg, control, tasks, actor, request, previous=None, *, selected_role, selected_incarnation):
    return preflight_close_compact(cfg, compact_v2(cfg, control, tasks, previous), actor, request, previous,
                                   selected_role=selected_role, selected_incarnation=selected_incarnation)


def preflight_close_compact(cfg, observation, actor, request, previous=None, *, selected_role, selected_incarnation):
    projection, tasks, proof = _baseline(cfg, observation, previous)
    proof.update(_selected(cfg, actor, selected_role, selected_incarnation))
    shape(request, {"task", "issue_number", "issue_id", "revision", "attempt", "commit_sha", "accept_ref"},
          "close request")
    require(selected_role == "GUARD", "close selected role must be GUARD")
    require(all(positive(request[k]) for k in ("issue_number", "issue_id", "revision", "attempt"))
            and sha(request["commit_sha"]), "invalid close request identity")
    task, raw = _task(projection, tasks, request["task"])
    require(task["state"] == "ACCEPTED" and raw["state"] == "open"
            and all(task[k] == request[k] for k in ("issue_number", "issue_id", "revision", "attempt"))
            and task["accepted_sha"] == request["commit_sha"], "close requires exact current accepted open task")
    normalized = normalize_task(cfg, {"issue_number": task["issue_number"], "issue_id": task["issue_id"]}, raw)
    fact = _accept_fact(projection, task, request["accept_ref"])
    proof.update(operation="issue_close", task=_task_binding(task), actor_id=actor,
                 role="GUARD", incarnation=cfg["roles"]["GUARD"]["incarnation"],
                 accept=_fact_binding(fact), open_issue=normalized["identity"],
                 request_sha256=digest(canonical(request)))
    proof["postcondition"] = {"event_kind": "closed", "actor_id": actor,
                              "issue_number": task["issue_number"], "issue_id": task["issue_id"],
                              "created_at_strictly_after": fact["created_at"]}
    return proof
