"""Pure task material publication preflight and actual readback; no authority."""
from __future__ import annotations

from core import canonical, digest, positive, require
from project_tasks import body_hash, immutable, normalize_task, parse_header
from split_journal import project_v2
from v2_compact import compact_v2, project_compact_v2, semantic_view
from v2_preflight import _selected, _task, _task_binding

PROTOCOL = "vpng-collab-material/2"
NO_AUTHORITY = "material only; no control publication, mutation or retry authorized"


def _normalized(cfg, task, raw):
    return normalize_task(cfg, {"issue_number": task["issue_number"],
                                "issue_id": task["issue_id"]}, raw)


def preflight_material(cfg, baseline, task_key, actor, body, previous=None, *,
                       selected_role, selected_incarnation):
    """Conditional material proof, not a material_ref or semantic transition."""
    control, tasks, inventory = semantic_view(cfg, baseline)
    projection, state = project_v2(cfg, control, tasks, previous)
    selected = _selected(cfg, actor, selected_role, selected_incarnation)
    task, raw = _task(projection, tasks, task_key)
    normalized = _normalized(cfg, task, raw)
    require(raw["state"] == "open" and normalized["close"] is None,
            "material requires physically open task Issue")
    header = parse_header(body)
    require(header["role"] == selected_role and header["incarnation"] == selected_incarnation
            and header["task"] == task_key, "material task/selected role/incarnation mismatch")
    kind = header["kind"]
    if kind == "RESULT":
        require(task["state"] == "BUILDER_READY" and header["revision"] == task["revision"]
                and header["attempt"] == task["attempt"] + 1,
                "RESULT material requires exact ready revision/next attempt")
    elif kind == "REVIEW":
        heads = [f["event"] for f in projection["facts"].values()
                 if f["event"]["event_id"] == task["head"]]
        require(task["state"] == "GUARD_REVIEW" and header["revision"] == task["revision"]
                and header["attempt"] == task["attempt"] and heads
                and all(e["kind"] == "RESULT" and e["commit_sha"] == header["commit_sha"] for e in heads),
                "REVIEW material requires exact current RESULT revision/attempt/SHA")
    else:
        require(task["state"] == "SUPERSEDED" and header["revision"] == task["revision"] + 1
                and header["revision"] > 1, "SPEC material requires exact next superseded revision")
    for row in normalized["comments"].values():
        if row["actor_id"] == actor and row["body"] == body:
            immutable(row)  # An edited matching row is also a conflict, never a retry permit.
            require(False, "exact material already observed; reconcile or reuse")
    identity = normalized["identity"]
    return {"protocol": PROTOCOL, "state": "CONDITIONAL", "operation": "material_comment",
            "config_sha256": digest(canonical(cfg)), "journal_epoch": cfg["journal_epoch"],
            **selected, "actor_id": actor, "task": _task_binding(task), "issue": identity,
            "header": header, "body_sha256": digest(body),
            "baseline_state_sha256": digest(canonical(state)), "inventory_sha256": inventory,
            "postcondition": {"issue_number": task["issue_number"], "issue_id": task["issue_id"],
                              "actor_id": actor, "body_sha256": digest(body), "header": header,
                              "immutable": True, "created_at_at_least": identity["created_at"]},
            "authority": NO_AUTHORITY}


def verify_material(cfg, baseline, task_key, actor, body, post_control, post_tasks, previous=None, *,
                    selected_role, selected_incarnation, expected_preflight_sha256,
                    expected_comment_id=None):
    """Verify one actual physical material occurrence; it is not a control fact."""
    proof = preflight_material(cfg, baseline, task_key, actor, body, previous,
                               selected_role=selected_role, selected_incarnation=selected_incarnation)
    require(body_hash(expected_preflight_sha256)
            and digest(canonical(proof)) == expected_preflight_sha256, "original material preflight mismatch")
    _, baseline_state = project_compact_v2(cfg, baseline, previous)
    require(digest(canonical(baseline_state)) == proof["baseline_state_sha256"],
            "original material baseline state mismatch")
    post = compact_v2(cfg, post_control, post_tasks, baseline_state)
    projection, state = project_compact_v2(cfg, post, baseline_state)
    task, raw = _task(projection, post_tasks, task_key)
    normalized = _normalized(cfg, task, raw)
    require(normalized["identity"] == proof["issue"], "material post-read Issue identity mismatch")
    matches = [r for r in normalized["comments"].values()
               if r["actor_id"] == actor and r["body"] == body]
    # Only actual exact immutable occurrences are eligible; edited exact
    # duplicates are a conflict, rather than evidence for another send.
    for row in matches:
        immutable(row)
        require(parse_header(row["body"]) == proof["header"]
                and row["created_at"] >= proof["postcondition"]["created_at_at_least"],
                "material readback header/Issue chronology mismatch")
    if expected_comment_id is not None:
        require(positive(expected_comment_id), "invalid expected material comment ID")
        selected = [r for r in matches if r["id"] == expected_comment_id]
        require(len(selected) == 1, "expected material occurrence not observed or mismatched")
        resolution = "exact_ref"
    else:
        require(matches, "material occurrence not observed; unresolved delivery")
        require(len(matches) == 1, "ambiguous duplicate material; unresolved delivery")
        selected = matches
        resolution = "unique_occurrence"
    row = selected[0]
    return {"protocol": PROTOCOL, "state": "VERIFIED", "operation": "material_comment",
            "preflight_sha256": expected_preflight_sha256,
            "baseline_state_sha256": proof["baseline_state_sha256"],
            "post_state_sha256": digest(canonical(state)), "post_inventory_sha256": post.inventory_sha256,
            "selected_role": selected_role, "selected_incarnation": selected_incarnation,
            "issue": normalized["identity"], "header": proof["header"], "actor_id": actor,
            "created_at": row["created_at"], "material_ref": {"comment_id": row["id"], "body_sha256": digest(body)},
            "matching_occurrences": len(matches), "resolution": resolution, "authority": NO_AUTHORITY}
