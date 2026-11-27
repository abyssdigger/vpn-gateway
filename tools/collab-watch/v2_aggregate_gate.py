"""Pure retained-only aggregate admission for canonical task/aux control candidates."""
from __future__ import annotations

from core import Conflict, canonical, digest, require
from project_tasks import body_hash
from split_journal import PROTOCOL as TASK_PROTOCOL
from v2_aux import PROTOCOL as AUX_PROTOCOL
from v2_compact import derive_task_compact, project_compact_aggregate_v2
from v2_preflight import preflight_control_compact
from v2_aux_preflight import preflight_aux_compact

PROTOCOL = "vpng-collab-aggregate-candidate-gate/2"
NO_AUTHORITY = "not evaluated; conditional aggregate gate only"


def _retained_shape(state):
    # Local closed storage-compatible shape, not a second semantic replay.
    require(type(state) is dict and set(state) == {"task", "aux"},
            "retained composed state required")
    for family, protocol in (("task", TASK_PROTOCOL), ("aux", AUX_PROTOCOL)):
        part = state[family]
        require(type(part) is dict and set(part) == {"protocol", "semantic_config_hash", "ledger"}
                and part["protocol"] == protocol and body_hash(part["semantic_config_hash"])
                and type(part["ledger"]) is dict
                and all(type(k) is str and k and body_hash(v)
                        for k, v in part["ledger"].items()), "invalid retained family shape")
    require(state["task"]["semantic_config_hash"] == state["aux"]["semantic_config_hash"],
            "retained config identity mismatch")


def gate_aggregate_candidate(cfg, aggregate, operation, actor, body, frozen_previous,
                             composed_previous, expected_proof_sha256, *,
                             selected_role, selected_incarnation):
    """Validate against exactly the supplied prior and aggregate; no fresh fallback."""
    try:
        require(operation in ("control_comment", "aux_comment"), "unsupported aggregate operation")
        _retained_shape(composed_previous)
        task_control = operation == "control_comment"
        required_previous = composed_previous["task"] if task_control else composed_previous
        require(canonical(frozen_previous) == canonical(required_previous),
                "frozen retained frontier mismatch")
        require(body_hash(expected_proof_sha256), "invalid expected proof SHA")
        projection, projected = project_compact_aggregate_v2(cfg, aggregate, composed_previous)
        derived = derive_task_compact(cfg, aggregate) if task_control else None
        fn = preflight_control_compact if task_control else preflight_aux_compact
        proof = fn(cfg, derived if task_control else aggregate, actor, body, required_previous,
                   selected_role=selected_role, selected_incarnation=selected_incarnation)
        proof_sha = digest(canonical(proof))
        require(proof_sha == expected_proof_sha256, "frozen candidate proof mismatch")
        require(proof["operation"] == operation and proof["selected_role"] == selected_role
                and proof["selected_incarnation"] == selected_incarnation,
                "candidate selection mismatch")
        mid = proof["candidate"]["event_id"]
        require(all(f["event"]["event_id"] != mid
                    for facts in (projection["task"]["facts"], projection["aux_facts"])
                    for f in facts.values()), "candidate global logical ID already observed")
        return {"protocol": PROTOCOL, "operation": "task_control" if task_control else "aux_control",
                "aggregate_sha256": aggregate.sha256,
                "aggregate_inventory_sha256": aggregate.inventory_sha256,
                "prior_composed_state_sha256": digest(canonical(composed_previous)),
                "projected_composed_state_sha256": digest(canonical(projected)),
                "task_compact_sha256": derived.sha256 if task_control else None,
                "task_inventory_sha256": derived.inventory_sha256 if task_control else None,
                "proof_sha256": proof_sha, "event_id": mid,
                "selected_role": selected_role, "selected_incarnation": selected_incarnation,
                "authority": NO_AUTHORITY}
    except (Conflict, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise Conflict("aggregate candidate gate failed") from None
