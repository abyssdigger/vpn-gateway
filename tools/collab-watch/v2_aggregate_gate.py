"""Pure retained-only aggregate admission for canonical control candidates."""
from __future__ import annotations

from core import Conflict, canonical, digest, require
from project_tasks import body_hash
from split_journal import PROTOCOL as TASK_PROTOCOL
from v2_aux import PROTOCOL as AUX_PROTOCOL
from v2_acquisition import InitialOpenAggregateV2
from v2_compact import (CompactAggregateV2, compact_aggregate_v2, derive_task_compact,
                        project_compact_aggregate_v2)
from v2_preflight import (preflight_control_compact, preflight_initial_open_compact,
                          preflight_close_compact)
from v2_material import preflight_material
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


def gate_initial_open_aggregate(cfg, coherent, actor, body, frozen_task_previous,
                                composed_previous, expected_proof_sha256, *,
                                selected_role, selected_incarnation):
    """Bind one trusted coherent prospective observation to retained history.

    The exact observation type is a structural seam, not an authentication or
    remote atomicity proof. Acquisition provenance remains a caller obligation.
    """
    try:
        require(type(coherent) is InitialOpenAggregateV2,
                "exact coherent initial OPEN observation required")
        _retained_shape(composed_previous)
        require(canonical(frozen_task_previous) == canonical(composed_previous["task"]),
                "frozen retained task frontier mismatch")
        require(body_hash(expected_proof_sha256), "invalid expected proof SHA")
        aggregate = compact_aggregate_v2(
            cfg, coherent.control, coherent.tasks, coherent.holder_rows,
            coherent.signal_rows, composed_previous)
        projection, projected = project_compact_aggregate_v2(
            cfg, aggregate, composed_previous)
        derived = derive_task_compact(cfg, aggregate)
        proof = preflight_initial_open_compact(
            cfg, derived, coherent.extra_task, actor, body, frozen_task_previous,
            selected_role=selected_role, selected_incarnation=selected_incarnation)
        proof_sha = digest(canonical(proof))
        require(proof_sha == expected_proof_sha256, "frozen candidate proof mismatch")
        require(proof["operation"] == "initial_open"
                and proof["selected_role"] == selected_role
                and proof["selected_incarnation"] == selected_incarnation,
                "candidate selection mismatch")
        mid = proof["candidate"]["event_id"]
        require(all(f["event"]["event_id"] != mid
                    for facts in (projection["task"]["facts"], projection["aux_facts"])
                    for f in facts.values()), "candidate global logical ID already observed")
        return {"protocol": PROTOCOL, "operation": "initial_open",
                "aggregate_sha256": aggregate.sha256,
                "aggregate_inventory_sha256": aggregate.inventory_sha256,
                "prior_composed_state_sha256": digest(canonical(composed_previous)),
                "projected_composed_state_sha256": digest(canonical(projected)),
                "task_compact_sha256": derived.sha256,
                "task_inventory_sha256": derived.inventory_sha256,
                "extra_observation_sha256": proof["extra_observation_sha256"],
                "proof_sha256": proof_sha, "event_id": mid,
                "selected_role": selected_role, "selected_incarnation": selected_incarnation,
                "authority": NO_AUTHORITY}
    except (Conflict, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise Conflict("initial OPEN aggregate candidate gate failed") from None


def gate_task_state_aggregate(cfg, aggregate, operation, actor, frozen_task_previous,
                              composed_previous, expected_proof_sha256, *,
                              selected_role, selected_incarnation,
                              task_key=None, body=None, request=None):
    """Conditional task-state admission for physical material/close effects."""
    try:
        require(type(aggregate) is CompactAggregateV2, "exact aggregate compact required")
        material = operation == "material_comment"
        require(material or operation == "issue_close", "unsupported task-state operation")
        require((type(task_key) is str and type(body) is str and request is None)
                if material else (type(request) is dict and task_key is None and body is None),
                "invalid task-state operation inputs")
        _retained_shape(composed_previous)
        require(canonical(frozen_task_previous) == canonical(composed_previous["task"]),
                "frozen retained task frontier mismatch")
        require(body_hash(expected_proof_sha256), "invalid expected proof SHA")
        _, projected = project_compact_aggregate_v2(cfg, aggregate, composed_previous)
        derived = derive_task_compact(cfg, aggregate)
        selection = dict(selected_role=selected_role, selected_incarnation=selected_incarnation)
        if material:
            proof = preflight_material(cfg, derived, task_key, actor, body,
                                       frozen_task_previous, **selection)
        else:
            proof = preflight_close_compact(cfg, derived, actor, request,
                                            frozen_task_previous, **selection)
        proof_sha = digest(canonical(proof))
        require(proof_sha == expected_proof_sha256, "frozen task-state proof mismatch")
        require(proof["operation"] == operation and proof["selected_role"] == selected_role
                and proof["selected_incarnation"] == selected_incarnation,
                "task-state selection mismatch")
        return {"protocol": PROTOCOL, "operation": operation,
                "aggregate_sha256": aggregate.sha256,
                "aggregate_inventory_sha256": aggregate.inventory_sha256,
                "prior_composed_state_sha256": digest(canonical(composed_previous)),
                "projected_composed_state_sha256": digest(canonical(projected)),
                "task_compact_sha256": derived.sha256,
                "task_inventory_sha256": derived.inventory_sha256,
                "proof_sha256": proof_sha, "selected_role": selected_role,
                "selected_incarnation": selected_incarnation, "authority": NO_AUTHORITY}
    except (Conflict, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise Conflict("task-state aggregate gate failed") from None
