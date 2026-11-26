"""Pure v2 readback verification; no network, send, retry, or authority."""
from __future__ import annotations

from core import canonical, digest, positive, require
from journal import framed
from project_tasks import body_hash, normalize_task, shape
from split_journal import MARKER, physical_ref, project_v2
from v2_compact import project_compact_v2
from v2_preflight import (preflight_close_compact, preflight_control_compact,
                          preflight_initial_open_compact)

PROTOCOL = "vpng-collab-readback/2"
NO_AUTHORITY = "verification only; no mutation or retry authorized"


def _post(cfg, baseline, previous, proof, expected_proof_sha256, control, tasks):
    # The caller must independently retain the original preflight digest.
    # Recompute rather than consume externally supplied proof fields.
    require(body_hash(expected_proof_sha256)
            and digest(canonical(proof)) == expected_proof_sha256,
            "original preflight binding mismatch")
    _, baseline_state = project_compact_v2(cfg, baseline, previous)
    require(digest(canonical(baseline_state)) == proof["baseline_state_sha256"],
            "original baseline state mismatch")
    projection, state = project_v2(cfg, control, tasks, baseline_state)
    result = {"protocol": PROTOCOL, "state": "VERIFIED",
              "operation": proof["operation"],
              "proof_sha256": expected_proof_sha256,
              "baseline_state_sha256": proof["baseline_state_sha256"],
              "post_state_sha256": digest(canonical(state)),
              "selected_role": proof["selected_role"],
              "selected_incarnation": proof["selected_incarnation"],
              "authority": NO_AUTHORITY}
    return projection, result


def _exact_occurrence(projection, proof, body, expected_ref):
    event = framed(body, MARKER)
    condition = proof["postcondition"]
    matches = [fact for fact in projection["facts"].values()
               if fact["event"] == event
               and fact["actor_id"] == condition["actor_id"]
               and fact["body_sha256"] == condition["body_sha256"]
               and fact["event"]["room"] == condition["room"]]
    if expected_ref is not None:
        shape(expected_ref, {"room", "comment_id"}, "expected physical ref")
        require(positive(expected_ref["room"]) and positive(expected_ref["comment_id"])
                and expected_ref["room"] == condition["room"], "invalid expected physical ref")
        key = physical_ref(expected_ref["room"], expected_ref["comment_id"])
        selected = [fact for fact in matches if fact["physical_ref"] == key]
        require(len(selected) == 1, "expected physical occurrence not admitted or mismatched")
        resolution = "exact_ref"
    else:
        require(matches, "candidate occurrence not observed; unresolved delivery")
        require(len(matches) == 1, "ambiguous duplicate occurrences; unresolved delivery")
        selected = matches
        resolution = "unique_occurrence"
    fact = selected[0]
    require(fact["created_at"] > condition["created_at_strictly_after"],
            "physical occurrence does not strictly follow preflight lower bound")
    # Canonical replay already proved immutability and relation chronology.
    return {"physical_ref": fact["physical_ref"], "event_id": fact["event"]["event_id"],
            "room": fact["event"]["room"], "actor_id": fact["actor_id"],
            "body_sha256": fact["body_sha256"], "created_at": fact["created_at"],
            "matching_occurrences": len(matches), "resolution": resolution}


def verify_control(cfg, baseline, actor, body, post_control, post_tasks, previous=None, *,
                   selected_role, selected_incarnation, expected_proof_sha256, expected_ref=None):
    """Verify an admitted existing-task control occurrence, not current head."""
    proof = preflight_control_compact(cfg, baseline, actor, body, previous,
                                      selected_role=selected_role,
                                      selected_incarnation=selected_incarnation)
    projection, result = _post(cfg, baseline, previous, proof, expected_proof_sha256,
                               post_control, post_tasks)
    result["occurrence"] = _exact_occurrence(projection, proof, body, expected_ref)
    return result


def verify_initial_open(cfg, baseline, extra_task, actor, body, post_control, post_tasks,
                        previous=None, *, selected_role, selected_incarnation,
                        expected_proof_sha256, expected_ref=None):
    """The prospective extra partition becomes a task only through actual replay."""
    proof = preflight_initial_open_compact(cfg, baseline, extra_task, actor, body, previous,
                                           selected_role=selected_role,
                                           selected_incarnation=selected_incarnation)
    projection, result = _post(cfg, baseline, previous, proof, expected_proof_sha256,
                               post_control, post_tasks)
    result["occurrence"] = _exact_occurrence(projection, proof, body, expected_ref)
    candidate = proof["candidate"]
    ref = candidate["task_ref"]
    matches = [t for t in projection["tasks"] if t["task"] == candidate["task"]]
    require(len(matches) == 1 and matches[0]["issue_number"] == ref["issue_number"]
            and matches[0]["issue_id"] == ref["issue_id"], "real OPEN task binding mismatch")
    normalized = normalize_task(cfg, ref, post_tasks[str(ref["issue_number"])])
    require(normalized["identity"] == proof["prospective_issue"],
            "real OPEN Issue identity differs from preflight")
    result["issue"] = normalized["identity"]
    return result


def verify_close(cfg, baseline, actor, request, post_control, post_tasks, previous=None, *,
                 selected_role, selected_incarnation, expected_proof_sha256):
    """Verify the actual authorized physical close, possibly already disposed."""
    proof = preflight_close_compact(cfg, baseline, actor, request, previous,
                                    selected_role=selected_role,
                                    selected_incarnation=selected_incarnation)
    projection, result = _post(cfg, baseline, previous, proof, expected_proof_sha256,
                               post_control, post_tasks)
    bound = proof["task"]
    matches = [t for t in projection["tasks"] if t["task"] == bound["task"]]
    require(len(matches) == 1, "close task not observed")
    task = matches[0]
    require(all(task[k] == bound[k] for k in
                ("issue_number", "issue_id", "revision", "attempt", "accepted_sha"))
            and task["state"] in ("CLOSE_OBSERVED", "CLOSED"), "exact close not observed")
    normalized = normalize_task(cfg, {"issue_number": task["issue_number"], "issue_id": task["issue_id"]},
                                post_tasks[str(task["issue_number"])])
    condition = proof["postcondition"]
    close = normalized["close"]
    require(normalized["identity"] == proof["open_issue"] and close is not None
            and close["actor_id"] == condition["actor_id"]
            and close["created_at"] > condition["created_at_strictly_after"],
            "physical close identity or strict chronology mismatch")
    # The nominated ACCEPT must itself precede the close, even if the canonical
    # chain has another eligible duplicate or later valid CLOSED disposition.
    accept = proof["accept"]
    fact = projection["facts"].get(accept["physical_ref"])
    require(fact is not None
            and all(fact[k] == accept[k] for k in
                    ("physical_ref", "body_sha256", "actor_id", "created_at"))
            and fact["event"]["event_id"] == accept["event_id"]
            and fact["event"]["room"] == accept["room"]
            and fact["created_at"] < close["created_at"], "nominated pre-close ACCEPT mismatch")
    result.update(issue=normalized["identity"], close_event=close, accept=accept,
                  task_state=task["state"])
    return result
