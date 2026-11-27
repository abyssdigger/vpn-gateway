"""Exact auxiliary readback, independent of transport response success."""
from __future__ import annotations

from core import canonical, digest, positive, read_comment, require
from journal import signal_record
from project_tasks import body_hash, shape
from split_journal import physical_ref
from v2_aux import project_aux
from v2_compact import project_compact_aggregate_v2
from v2_aux_preflight import preflight_aux_compact, preflight_signal_compact

PROTOCOL = "vpng-collab-aux-readback/2"
NO_AUTHORITY = "verification only; no mutation or retry authorized"


def _verify(cfg, baseline, actor, body, post_control, post_tasks, post_holder, post_signals,
            previous, *, selected_role, selected_incarnation, expected_proof_sha256,
            expected_ref, signal):
    preflight = preflight_signal_compact if signal else preflight_aux_compact
    proof = preflight(cfg, baseline, actor, body, previous,
                      selected_role=selected_role, selected_incarnation=selected_incarnation)
    require(body_hash(expected_proof_sha256)
            and digest(canonical(proof)) == expected_proof_sha256, "original proof mismatch")
    _, baseline_state = project_compact_aggregate_v2(cfg, baseline, previous)
    require(digest(canonical(baseline_state)) == proof["baseline_state_sha256"],
            "original baseline state mismatch")
    projection, state = project_aux(cfg, post_control, post_tasks, post_holder,
                                    post_signals, baseline_state)
    candidate = proof["candidate"]
    condition = proof["postcondition"]
    room = condition["room"]
    if signal:
        journal = dict(projection["task"]["facts"], **projection["aux_facts"])
        wanted = signal_record(candidate, actor, cfg, journal)
        rows = post_signals
        matches = [fact for fact in projection["signal_status"]["valid"]
                   if all(fact[k] == v for k, v in wanted.items())
                   and fact["actor_id"] == actor
                   and fact["body_sha256"] == condition["body_sha256"]]
    else:
        rows = post_control[str(room)]
        matches = [fact for fact in projection["aux_facts"].values()
                   if fact["event"] == candidate and fact["actor_id"] == actor
                   and fact["body_sha256"] == condition["body_sha256"]]
    # Bind the exact original raw bytes as well as the admitted semantic fact.
    exact = {physical_ref(room, cid) for cid, sender, raw in map(read_comment, rows)
             if sender == actor and raw == body}
    matches = [fact for fact in matches if fact["physical_ref"] in exact]
    count = len(matches)
    if expected_ref is not None:
        shape(expected_ref, {"room", "comment_id"}, "expected physical ref")
        require(positive(expected_ref["room"]) and positive(expected_ref["comment_id"])
                and expected_ref["room"] == room, "wrong expected physical ref")
        ref = physical_ref(room, expected_ref["comment_id"])
        matches = [fact for fact in matches if fact["physical_ref"] == ref]
        resolution = "exact_ref"
    else:
        resolution = "unique_occurrence"
    require(len(matches) == 1, "missing, conflicting or ambiguous outgoing occurrence")
    found = matches[0]
    return {"protocol": PROTOCOL, "state": "VERIFIED", "operation": proof["operation"],
            "proof_sha256": expected_proof_sha256,
            "baseline_state_sha256": proof["baseline_state_sha256"],
            "post_state_sha256": digest(canonical(state)),
            "selected_role": selected_role, "selected_incarnation": selected_incarnation,
            "occurrence": {"room": room, "physical_ref": found["physical_ref"],
                           "body_sha256": condition["body_sha256"], "actor_id": actor,
                           "event_id": candidate["event_id"],
                           "matching_occurrences": count, "resolution": resolution},
            "authority": NO_AUTHORITY}


def verify_aux(cfg, baseline, actor, body, post_control, post_tasks, post_holder, post_signals,
               previous=None, *, selected_role, selected_incarnation,
               expected_proof_sha256, expected_ref=None):
    return _verify(cfg, baseline, actor, body, post_control, post_tasks, post_holder, post_signals,
                   previous, selected_role=selected_role, selected_incarnation=selected_incarnation,
                   expected_proof_sha256=expected_proof_sha256, expected_ref=expected_ref, signal=False)


def verify_signal(cfg, baseline, actor, body, post_control, post_tasks, post_holder, post_signals,
                  previous=None, *, selected_role, selected_incarnation,
                  expected_proof_sha256, expected_ref=None):
    return _verify(cfg, baseline, actor, body, post_control, post_tasks, post_holder, post_signals,
                   previous, selected_role=selected_role, selected_incarnation=selected_incarnation,
                   expected_proof_sha256=expected_proof_sha256, expected_ref=expected_ref, signal=True)
