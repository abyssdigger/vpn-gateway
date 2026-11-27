"""Conditional auxiliary publication proofs over the accepted aggregate observation."""
from __future__ import annotations

from core import Conflict, canonical, digest, read_comment, require
from journal import SIGNAL_MARKER, framed, signal_record
from v2_aux import MARKER, _event, _relations
from v2_compact import aggregate_semantic_view
from v2_aux import project_aux
from v2_preflight import _selected

PROTOCOL = "vpng-collab-aux-preflight/2"
NO_AUTHORITY = "not evaluated; conditional proof only; no mutation or readiness authorized"


def _baseline(cfg, observation, actor, selected_role, selected_incarnation, previous):
    control, tasks, holder, signals, inventory = aggregate_semantic_view(cfg, observation)
    projection, state = project_aux(cfg, control, tasks, holder, signals, previous)
    proof = {"protocol": PROTOCOL, "state": "CONDITIONAL",
             "config_sha256": digest(canonical(cfg)),
             "journal_epoch": cfg["journal_epoch"],
             "baseline_state_sha256": digest(canonical(state)),
             "inventory_sha256": inventory, "authority": NO_AUTHORITY}
    proof.update(_selected(cfg, actor, selected_role, selected_incarnation))
    journal = dict(projection["task"]["facts"], **projection["aux_facts"])
    return projection, journal, signals, proof


def _finish(proof, operation, candidate, actor, body, room, targets):
    proof.update(operation=operation, candidate=candidate, targets=targets,
                 postcondition={"room": room, "actor_id": actor,
                                "body_sha256": digest(body)})
    return proof


def preflight_aux_compact(cfg, observation, actor, body, previous=None, *,
                          selected_role, selected_incarnation):
    projection, journal, _, proof = _baseline(
        cfg, observation, actor, selected_role, selected_incarnation, previous)
    event = _event(cfg, {"actor_id": actor, "body": body}, framed(body, MARKER).get("room"))
    require(event["from"] == selected_role and event["incarnation"] == selected_incarnation,
            "candidate does not match selected role/incarnation")
    require(all(f["event"]["event_id"] != event["event_id"] for f in journal.values()),
            "outgoing logical event already observed; reconcile")
    targets = dict(journal, **projection["holder_inputs"])
    # Reuse the accepted relation checks. This key is deliberately NOT a
    # physical ref, never enters the target map, and cannot be named by a
    # wire receipt/PONG. Discard every derived receipt/health output.
    prospective = dict(projection["aux_facts"], candidate={"event": event})
    _relations(prospective, targets)
    refs = ([t["ref"] for t in event["handled"]] if event["kind"] == "HANDLED"
            else [event["ping_ref"]] if event["kind"] == "PONG" else [])
    return _finish(proof, "aux_comment", event, actor, body, event["room"],
                   [targets[ref] for ref in refs])


def preflight_signal_compact(cfg, observation, actor, body, previous=None, *,
                             selected_role, selected_incarnation):
    _, journal, signals, proof = _baseline(
        cfg, observation, actor, selected_role, selected_incarnation, previous)
    event = framed(body, SIGNAL_MARKER)
    signal_record(event, actor, cfg, journal)
    require(event["from"] == selected_role and event["incarnation"] == selected_incarnation,
            "candidate does not match selected role/incarnation")
    known = {role["actor_id"] for role in cfg["roles"].values()}
    for row in signals:
        _, sender, raw = read_comment(row)
        if sender not in known:
            continue
        try:
            observed = framed(raw, SIGNAL_MARKER)
        except Conflict:
            continue
        # Includes schema-invalid known-worker claims with parseable ID.
        require(observed.get("signal_id") != event["signal_id"],
                "outgoing signal identity already observed; reconcile")
    return _finish(proof, "signal_comment", event, actor, body, cfg["signal_room"],
                   [journal[event["journal_ref"]]])
