"""Staged v2 single-attempt transport; no live activation or authority policy."""
from __future__ import annotations

import fcntl
import os
import re
import stat
from urllib.request import Request, build_opener

from collab_watch import API, MAX_PAGE_BYTES, TIMEOUT, NoRedirect
from core import canonical, digest, positive, require, strict_json
from journal import framed
from project_tasks import body_hash, comment
from split_journal import MARKER
from v2_acquisition import (acquire_v2, acquire_v2_for_initial_open, acquire_aggregate_v2,
                            acquire_aggregate_v2_for_initial_open)
from v2_attempts import AttemptStore
from v2_inputs import InputStore, MAX_INPUT_BYTES
from v2_compact import (CompactV2, compact_v2, CompactAggregateV2, compact_aggregate_v2,
                        derive_task_compact)
from v2_aggregate_gate import (gate_aggregate_candidate, gate_initial_open_aggregate,
                               gate_task_state_aggregate, gate_creation_aggregate)
from v2_runtime_state import RuntimeStateStore
from v2_aux_preflight import preflight_aux_compact, preflight_signal_compact
from v2_aux_reconcile import verify_aux, verify_signal
from v2_create import (preflight_create, acquire_creation, verify_creation,
                       acquire_aggregate_v2_for_creation)
from v2_material import preflight_material, verify_material
from v2_preflight import (preflight_control_compact, preflight_close_compact,
                          preflight_initial_open_compact)
from v2_reconcile import verify_control, verify_close, verify_initial_open

AUX_OPERATIONS = {"aux_comment", "signal_comment"}
TASK_STATE_OPERATIONS = {"material_comment", "issue_close"}
AGGREGATE_CONTROL_OPERATIONS = {"control_comment", "aux_comment", "initial_open", "issue_create"} | TASK_STATE_OPERATIONS
OPERATIONS = {"material_comment", "control_comment", "initial_open", "issue_close", "issue_create"} | AUX_OPERATIONS
FIELDS = {"operation", "cfg", "baseline", "actor", "role", "incarnation",
          "proof_sha256", "body", "task_key", "request", "extra_task", "previous"}


def freeze_inputs(operation, cfg, baseline, actor, *, selected_role, selected_incarnation,
                  expected_proof_sha256, body=None, task_key=None, request=None,
                  extra_task=None, previous=None):
    """Detach original proof inputs for a separately durable, trusted input provider.

    The returned bytes contain material, not just metadata. Never put these bytes
    in the attempt ledger, logs, or authority descriptor.
    """
    expected_type = CompactAggregateV2 if operation in AUX_OPERATIONS else CompactV2
    require(isinstance(baseline, expected_type), "invalid original baseline")
    return canonical(dict(operation=operation, cfg=cfg, actor=actor, role=selected_role,
                          incarnation=selected_incarnation, proof_sha256=expected_proof_sha256,
                          baseline={"text": baseline.text, "sha256": baseline.sha256,
                                    "inventory_sha256": baseline.inventory_sha256},
                          body=body, task_key=task_key, request=request,
                          extra_task=extra_task, previous=previous))


def _selection(data):
    return dict(selected_role=data["role"], selected_incarnation=data["incarnation"])


def _proof(data, baseline, extra):
    cfg, actor, previous = data["cfg"], data["actor"], data["previous"]
    kind = data["operation"]
    if kind in AUX_OPERATIONS:
        fn = preflight_aux_compact if kind == "aux_comment" else preflight_signal_compact
        return fn(cfg, baseline, actor, data["body"], previous, **_selection(data))
    if kind == "issue_create":
        return preflight_create(cfg, baseline, actor, data["request"], previous, **_selection(data))[0]
    if kind == "material_comment":
        return preflight_material(cfg, baseline, data["task_key"], actor, data["body"],
                                  previous, **_selection(data))
    if kind == "control_comment":
        return preflight_control_compact(cfg, baseline, actor, data["body"],
                                         previous, **_selection(data))
    if kind == "initial_open":
        return preflight_initial_open_compact(cfg, baseline, extra, actor, data["body"],
                                              previous, **_selection(data))
    return preflight_close_compact(cfg, baseline, actor, data["request"], previous,
                                   **_selection(data))


def _bound(original):
    require(type(original) is str and len(original.encode("utf-8")) <= MAX_INPUT_BYTES,
            "invalid retained inputs")
    data = strict_json(original)
    require(isinstance(data, dict) and set(data) == FIELDS and canonical(data) == original,
            "invalid retained input fields")
    kind = data["operation"]
    require(kind in OPERATIONS, "unsupported action")
    require((data["body"] is None) == (kind in ("issue_close", "issue_create"))
            and (data["request"] is not None) == (kind in ("issue_close", "issue_create"))
            and (data["task_key"] is not None) == (kind == "material_comment")
            and (data["extra_task"] is not None) == (kind == "initial_open"),
            "extraneous or missing operation input")
    baseline_type = CompactAggregateV2 if kind in AUX_OPERATIONS else CompactV2
    baseline = baseline_type(**data["baseline"])
    proof = _proof(data, baseline, data["extra_task"])
    require(body_hash(data["proof_sha256"]) and digest(canonical(proof)) == data["proof_sha256"],
            "original proof mismatch")
    cfg, actor = data["cfg"], data["actor"]
    repository = cfg["repository"]
    if kind in AUX_OPERATIONS:
        candidate = proof["candidate"]
        room = proof["postcondition"]["room"]
        target = f"repos/{repository}/issues/{room}/comments"
        request = canonical({"body": data["body"]})
        require(len(request.encode("utf-8")) <= MAX_PAGE_BYTES, "mutation body bound")
        if kind == "aux_comment":
            # Exactly the task-control effect namespace, not a second aux claim.
            effect = {"operation": "control_comment", "repository": repository.lower(),
                      "journal_epoch": cfg["journal_epoch"], "event_id": candidate["event_id"]}
            identity = {k: candidate[k] for k in ("event_id", "kind")}
        else:
            effect = {"operation": "signal_comment", "repository": repository.lower(),
                      "journal_epoch": cfg["journal_epoch"], "signal_id": candidate["signal_id"]}
            identity = {k: candidate[k] for k in ("signal_id", "event_id", "journal_ref",
                                                 "journal_sha256", "to")}
        action = {"operation": kind, "repository": repository, "target": target, "room": room,
                  "method": "POST", "actor_id": actor, "role": data["role"],
                  "incarnation": data["incarnation"], "journal_epoch": cfg["journal_epoch"],
                  "candidate": identity, "proof_sha256": data["proof_sha256"],
                  "inputs_sha256": digest(original), "request_sha256": digest(request),
                  "intent_sha256": digest(request),
                  "config_identity_sha256": digest(canonical(dict(cfg, repository=repository.lower())))}
        return data, baseline, proof, effect, action, request.encode("utf-8")
    if kind == "issue_create":
        _, payload = preflight_create(cfg, baseline, actor, data["request"], data["previous"], **_selection(data))
        effect = proof["effect"]
        target = f"repos/{repository}/issues"
        request = canonical(payload)
        require(len(request.encode("utf-8")) <= MAX_PAGE_BYTES, "mutation body bound")
        action = {"operation": kind, "repository": repository, "target": target,
                  "room": data["request"]["room"], "task": data["request"]["task"], "method": "POST",
                  "actor_id": actor, "role": data["role"], "incarnation": data["incarnation"],
                  "journal_epoch": cfg["journal_epoch"], "candidate": {"revision": 1},
                  "proof_sha256": data["proof_sha256"], "inputs_sha256": digest(original),
                  "request_sha256": digest(request), "intent_sha256": digest(request),
                  "config_identity_sha256": digest(canonical(dict(cfg, repository=repository.lower())))}
        return data, baseline, proof, effect, action, request.encode("utf-8")
    if kind in ("control_comment", "initial_open"):
        candidate = proof["candidate"]
        event = framed(data["body"], MARKER)
        room = candidate["room"]
        task = (proof["task"] if kind == "control_comment" else
                dict(candidate["task_ref"], task=candidate["task"], revision=candidate["revision"]))
        identity = {k: event[k] for k in ("event_id", "kind", "revision")}
        identity.update({k: event[k] for k in ("attempt", "commit_sha") if k in event})
        effect = {"operation": "control_comment", "repository": repository.lower(),
                  "journal_epoch": cfg["journal_epoch"], "event_id": candidate["event_id"]}
    else:
        task = proof["task"]
        room = task["issue_number"]
        effect = {"operation": kind, "repository": repository.lower(), "issue_id": task["issue_id"]}
        if kind == "material_comment":
            effect.update(actor_id=actor, body_sha256=proof["body_sha256"])
            identity = proof["header"]
        else:
            identity = {k: data["request"][k] for k in ("revision", "attempt", "commit_sha")}
    method = "PATCH" if kind == "issue_close" else "POST"
    target = f"repos/{repository}/issues/{room}" + ("/comments" if method == "POST" else "")
    request = canonical({"state": "closed"} if method == "PATCH" else {"body": data["body"]})
    require(len(request.encode("utf-8")) <= MAX_PAGE_BYTES, "mutation body bound")
    action = {"operation": kind, "repository": repository, "target": target,
              "room": room, "issue_number": task["issue_number"], "issue_id": task["issue_id"],
              "task": task["task"], "method": method, "actor_id": actor,
              "role": data["role"], "incarnation": data["incarnation"],
              "journal_epoch": cfg["journal_epoch"], "candidate": identity,
              "proof_sha256": data["proof_sha256"], "inputs_sha256": digest(original),
              "request_sha256": digest(request),
              "intent_sha256": digest(canonical(data["request"])) if kind == "issue_close" else digest(request),
              "config_identity_sha256": digest(canonical(dict(cfg, repository=repository.lower())))}
    return data, baseline, proof, effect, action, request.encode("utf-8")


def _witness(proof, baseline, extra):
    """Deterministic eligibility from the already validated complete inventory.

    Immutable physical comments (including opaque comments) and admitted lifecycle
    events are conservative timestamp witnesses, not predictions of write time.
    """
    lower = proof["postcondition"].get("created_at_strictly_after")
    if lower is None:
        return {"kind": "not_applicable"}
    wire = strict_json(baseline.text)
    candidates = []

    def add_rows(room, rows):
        for row in rows:
            _, cid, actor, created, updated, _ = row
            if created == updated and created > lower:
                candidates.append({"kind": "comment", "room": int(room), "comment_id": cid,
                                   "created_at": created, "row_sha256": digest(canonical(row))})

    for room, rows in wire["control"].items():
        add_rows(room, rows)
    for room, task in wire["tasks"].items():
        add_rows(room, task["comments"])
        for event in task["events"]:
            if event["created_at"] > lower:
                candidates.append({"kind": "lifecycle", "room": int(room), "event_id": event["id"],
                                   "created_at": event["created_at"],
                                   "row_sha256": digest(canonical(event))})
    if extra is not None:
        for raw in extra["comments"]:
            row = comment(raw)
            if row["created_at"] == row["updated_at"] and row["created_at"] > lower:
                candidates.append({"kind": "extra_comment", "room": extra["number"],
                                   "comment_id": row["id"], "created_at": row["created_at"],
                                   "row_sha256": digest(canonical(row))})
    return min(candidates, key=lambda x: (x["created_at"], x["room"], x["kind"],
                                          x.get("comment_id", x.get("event_id")), x["row_sha256"])) if candidates else None


def _fresh(data, read_token, read_opener, *, before):
    if data["operation"] in AUX_OPERATIONS:
        c, t, h, s = acquire_aggregate_v2(data["cfg"], token=read_token, opener=read_opener)
        return c, t, (h, s)
    if before and data["operation"] == "initial_open":
        return acquire_v2_for_initial_open(data["cfg"], data["actor"], data["body"],
                                            **_selection(data), token=read_token, opener=read_opener)
    control, tasks = acquire_v2(data["cfg"], token=read_token, opener=read_opener)
    return control, tasks, None


def _write_headers(token):
    require(type(token) is str and 0 < len(token) <= 4096
            and re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token), "invalid write credential")
    return {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "vpng-collab-actuator/2",
            "Content-Type": "application/json"}


def _write_transport():
    """Closed production transport; tests patch a private seam, not caller inputs."""
    return build_opener(NoRedirect())


def _http(opener, headers, url, method, request, expected_status):
    # Exactly one call, no redirect following with the production opener.
    with opener.open(Request(url, data=request, headers=headers, method=method),
                     timeout=TIMEOUT) as response:
        require(response.status == expected_status and response.geturl() == url,
                "unexpected response status or URL")
        raw = response.read(MAX_PAGE_BYTES + 1)
        require(len(raw) <= MAX_PAGE_BYTES, "response byte bound")
        length = response.headers.get("Content-Length")
        require(length is None or length.isdecimal() and int(length) == len(raw),
                "response length mismatch")
        value = strict_json(raw.decode("utf-8"))
        require(isinstance(value, dict), "response object required")
        return value


def _send(opener, headers, action, request):
    """One physical mutation only. Any returned locator is an unverified hint."""
    if action["operation"] == "issue_create":
        value = _http(opener, headers, API + "/" + action["target"], "POST", request, 201)
        number, iid = value.get("number"), value.get("id")
        root = f"{API}/repos/{action['repository']}"
        require(positive(number) and positive(iid) and "pull_request" not in value
                and isinstance(value.get("url"), str) and value["url"].lower() == (root+"/issues/"+str(number)).lower()
                and isinstance(value.get("repository_url"), str) and value["repository_url"].lower() == root.lower(),
                "invalid creation response locator")
        return {"issue_number": number, "issue_id": iid}
    root = f"{API}/repos/{action['repository']}/issues/{action['room']}"
    value = _http(opener, headers, API + "/" + action["target"], action["method"],
                  request, 200 if action["method"] == "PATCH" else 201)
    if action["method"] == "PATCH":
        require(positive(value.get("id")) and value["id"] == action["issue_id"]
                and positive(value.get("number")) and value["number"] == action["issue_number"]
                and value.get("state") == "closed" and value.get("url", "").lower() == root.lower(),
                "invalid close response")
        # The Issue response has no immutable close-event ID.
        return None
    require(positive(value.get("id")) and isinstance(value.get("issue_url"), str)
            and value["issue_url"].lower() == root.lower(), "invalid comment response locator")
    # Bind the exact physical ref even if its body/actor subsequently fail readback.
    return {"room": action["room"], "comment_id": value["id"]}


def _receipt(data, baseline, control, tasks, hint):
    cfg, actor, previous = data["cfg"], data["actor"], data["previous"]
    kind = data["operation"]
    common = _selection(data)
    if kind == "material_comment":
        receipt = verify_material(cfg, baseline, data["task_key"], actor, data["body"],
                                  control, tasks, previous, **common,
                                  expected_preflight_sha256=data["proof_sha256"],
                                  expected_comment_id=None if hint is None else hint["comment_id"])
        locator = {"room": receipt["issue"]["number"], "comment_id": receipt["material_ref"]["comment_id"]}
    elif kind in ("control_comment", "initial_open"):
        fn = verify_initial_open if kind == "initial_open" else verify_control
        extra = [data["extra_task"]] if kind == "initial_open" else []
        receipt = fn(cfg, baseline, *extra, actor, data["body"], control, tasks, previous,
                     **common, expected_proof_sha256=data["proof_sha256"], expected_ref=hint)
        locator = {"room": receipt["occurrence"]["room"], "physical_ref": receipt["occurrence"]["physical_ref"]}
    else:
        receipt = verify_close(cfg, baseline, actor, data["request"], control, tasks, previous,
                               **common, expected_proof_sha256=data["proof_sha256"])
        locator = {"room": receipt["issue"]["number"], "issue_id": receipt["issue"]["id"],
                   "event_id": receipt["close_event"]["id"]}
    return digest(canonical(receipt)), locator


def _result(state, code, key=None):
    return {"state": state, "code": code, "action_key": key}


def _verified(row):
    return dict(_result("VERIFIED", "CANONICAL_RECEIPT_RECORDED", row["action_key"]),
                receipt_sha256=row["receipt_sha256"], locator=row["locator"])


def _reconcile(store, row, retention, read_token, read_opener, *, persist=True):
    """Read-only remote recovery. Never calls _send or store.start."""
    key = row["action_key"]
    try:
        _provider_pair(store, retention)
        original = retention.load(key)
        data, baseline, proof, effect, action, _ = _bound(original)
        witness = _witness(proof, baseline, data["extra_task"])
        require(witness is not None and dict(action, witness=witness) == row["action_descriptor"]
                and effect == row["effect_descriptor"], "retained action mismatch")
    except Exception:
        return _result("EFFECT_UNKNOWN", "RETAINED_INPUT_UNAVAILABLE", key)
    if row["state"] == "VERIFIED":
        return _verified(row)
    try:
        hint = row["response_hint"]
        if hint is not None and action["operation"] == "issue_create":
            require(set(hint) == {"issue_number", "issue_id"} and all(positive(v) for v in hint.values()),
                    "creation hint binding mismatch")
        elif hint is not None:
            require(set(hint) == {"room", "comment_id"} and hint["room"] == action["room"]
                    and positive(hint["comment_id"]) and action["method"] == "POST", "hint binding mismatch")
        control, tasks, extra = _fresh(data, read_token, read_opener, before=False)
        if action["operation"] == "issue_create":
            physical = acquire_creation(data["cfg"], effect, read_token, read_opener)
            verified = verify_creation(data["cfg"], baseline, data["actor"], data["request"],
                                       control, tasks, physical, data["previous"], **_selection(data),
                                       expected_proof_sha256=data["proof_sha256"], hint=hint)
            receipt, locator = digest(canonical(verified)), verified["issue"]
        elif action["operation"] in AUX_OPERATIONS:
            verify = verify_aux if action["operation"] == "aux_comment" else verify_signal
            verified = verify(data["cfg"], baseline, data["actor"], data["body"], control, tasks,
                              *extra, data["previous"], **_selection(data),
                              expected_proof_sha256=data["proof_sha256"], expected_ref=hint)
            occurrence = verified["occurrence"]
            receipt = digest(canonical(verified))
            locator = {"room": occurrence["room"], "physical_ref": occurrence["physical_ref"]}
        else:
            receipt, locator = _receipt(data, baseline, control, tasks, hint)
    except Exception:
        if not persist:
            return _result("EFFECT_UNKNOWN", "STORE_FAILURE_AFTER_START", key)
        try:
            if row["state"] == "STARTED":
                store.mark_unresolved(key, "READBACK_UNRESOLVED")
            return _result("UNRESOLVED", "READBACK_UNRESOLVED", key)
        except Exception:
            return _result("EFFECT_UNKNOWN", "STORE_FAILURE_AFTER_START", key)
    if not persist:
        return _result("EFFECT_UNKNOWN", "STORE_FAILURE_AFTER_START", key)
    try:
        _provider_pair(store, retention)
        # The first exact bytes were already bound to this claimed action and
        # effect above. Equality after a fresh validated load confirms that
        # same canonical binding, not a refreshed or substituted original.
        require(retention.load(key) == original, "retained input changed during readback")
    except Exception:
        return _result("EFFECT_UNKNOWN", "RETAINED_INPUT_UNAVAILABLE", key)
    try:
        return _verified(store.mark_verified(key, receipt, locator))
    except Exception:
        return _result("EFFECT_UNKNOWN", "STORE_FAILURE_AFTER_START", key)


def _provider_pair(store, retention):
    require(type(retention) is InputStore, "concrete durable input provider required")
    retention.validate_pair(store.store_id)


def _stable_intent(action):
    # Every identity field is significant unless explicitly refreshable.
    stable = {k: v for k, v in action.items()
              if k not in {"proof_sha256", "inputs_sha256", "witness", "config_identity_sha256"}}
    stable["repository"] = stable["repository"].lower()
    stable["target"] = stable["target"].lower()
    return stable


def _claimed_result(store, claimed, action, retention, read_token, read_opener):
    if _stable_intent(claimed["action_descriptor"]) != _stable_intent(action):
        return _result("CONFLICT", "EFFECT_CLAIM_CONFLICT", claimed["action_key"])
    return _reconcile(store, claimed, retention, read_token, read_opener)


def _ownership_fd(store):
    """Lock the existing authoritative ledger inode; never create a lock file.

    SQLite POSIX record locks and Linux flock are independent. Every actuator
    invocation, including reconcile-only, uses this same exclusive flock.
    The deployment must preserve the authoritative local inode while in use.
    """
    require(type(store) is AttemptStore, "authoritative attempt store required")
    fd = os.open(store.path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        held = os.fstat(fd)
        require(stat.S_ISREG(held.st_mode), "regular attempt store required")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        actual = os.stat(store.path, follow_symlinks=False)
        require((held.st_dev, held.st_ino) == (actual.st_dev, actual.st_ino),
                "attempt store inode changed")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _checkpoint_for_control(data, runtime_state):
    cfg = data["cfg"]
    require(type(runtime_state) is RuntimeStateStore
            and runtime_state._repository == cfg["repository"].lower()
            and runtime_state._epoch == cfg["journal_epoch"], "checkpoint scope mismatch")
    checkpoint = runtime_state.load()
    require(checkpoint is not None, "retained checkpoint required")
    state = checkpoint["state"]
    prior = state if data["operation"] == "aux_comment" else state["task"]
    require(canonical(prior) == canonical(data["previous"]), "frozen checkpoint frontier mismatch")
    require(digest(canonical(state)) == checkpoint["state_sha256"], "checkpoint digest mismatch")
    return checkpoint


def _admit_control(data, proof, witness, checkpoint, read_token, read_opener):
    cfg = data["cfg"]
    previous = checkpoint["state"]
    kind = data["operation"]
    extra = None
    if kind == "initial_open":
        coherent = acquire_aggregate_v2_for_initial_open(
            cfg, data["actor"], data["body"], **_selection(data),
            token=read_token, opener=read_opener)
        gate = gate_initial_open_aggregate(
            cfg, coherent, data["actor"], data["body"], data["previous"], previous,
            data["proof_sha256"], **_selection(data))
        # Reconstruct the witness locally from exactly the same observation.
        # No separate task/candidate scan or second network acquisition.
        aggregate = compact_aggregate_v2(cfg, coherent.control, coherent.tasks,
                                         coherent.holder_rows, coherent.signal_rows, previous)
        extra = coherent.extra_task
        require(gate["extra_observation_sha256"] == proof["extra_observation_sha256"],
                "extra observation binding mismatch")
    elif kind == "issue_create":
        coherent = acquire_aggregate_v2_for_creation(cfg, token=read_token, opener=read_opener)
        gate = gate_creation_aggregate(
            cfg, coherent, data["actor"], data["request"], data["previous"], previous,
            data["proof_sha256"], **_selection(data))
        aggregate = compact_aggregate_v2(cfg, coherent.control, coherent.tasks,
                                         coherent.holder_rows, coherent.signal_rows, previous)
        require(gate["creation_inventory_sha256"] == digest(canonical(coherent.inventory))
                and gate["effect_sha256"] == digest(canonical(proof["effect"])),
                "creation inventory/effect binding mismatch")
    else:
        graph = acquire_aggregate_v2(cfg, token=read_token, opener=read_opener)
        aggregate = compact_aggregate_v2(cfg, *graph, previous)
        if kind in TASK_STATE_OPERATIONS:
            gate = gate_task_state_aggregate(
                cfg, aggregate, kind, data["actor"], data["previous"], previous,
                data["proof_sha256"], task_key=data["task_key"], body=data["body"],
                request=data["request"], **_selection(data))
        else:
            gate = gate_aggregate_candidate(cfg, aggregate, kind, data["actor"],
                                            data["body"], data["previous"], previous,
                                            data["proof_sha256"], **_selection(data))
    require(gate["prior_composed_state_sha256"] == checkpoint["state_sha256"]
            and gate["proof_sha256"] == data["proof_sha256"]
            and gate["aggregate_sha256"] == aggregate.sha256
            and gate["aggregate_inventory_sha256"] == aggregate.inventory_sha256,
            "aggregate gate binding mismatch")
    if kind in ("control_comment", "initial_open", "issue_create") or kind in TASK_STATE_OPERATIONS:
        task = derive_task_compact(cfg, aggregate)
        require(task.sha256 == gate["task_compact_sha256"]
                and task.inventory_sha256 == gate["task_inventory_sha256"]
                and _witness(proof, task, extra) == witness, "aggregate witness mismatch")


def actuate(store, original, retention, authorize, *, read_token=None, write_token=None,
            read_opener=None, reconcile_only=False, runtime_state=None):
    """Single local owner across sender, response hint and recovery.

    A concurrent caller never observes/finalizes an in-flight STARTED attempt.
    The OS releases ownership on close/process exit. No fork while active;
    all users of the ledger must use this interface, not direct state mutation.
    """
    try:
        fd = _ownership_fd(store)
    except BlockingIOError:
        return _result("BUSY", "ACTUATOR_BUSY")
    except Exception:
        return _result("NO_ATTEMPT", "OWNERSHIP_UNAVAILABLE")
    try:
        return _actuate(store, original, retention, authorize, read_token=read_token,
                        write_token=write_token, read_opener=read_opener,
                        reconcile_only=reconcile_only, runtime_state=runtime_state)
    finally:
        os.close(fd)


def _actuate(store, original, retention, authorize, *, read_token=None, write_token=None,
             read_opener=None, reconcile_only=False, runtime_state=None):
    """Compose accepted preflight, acquisition, durable attempt and readback.

    Only the concrete, externally pinned durable InputStore is accepted.
    The caller owns real runtime authority.
    """
    key = None
    try:
        data, baseline, proof, effect, action, request = _bound(original)
        claimed = store.claimed(effect)
        try:
            _provider_pair(store, retention)
        except Exception:
            return _result("EFFECT_UNKNOWN" if claimed else "NO_ATTEMPT",
                           "INPUT_PROVIDER_UNAVAILABLE", claimed["action_key"] if claimed else None)
        if claimed is not None:
            return _claimed_result(store, claimed, action, retention, read_token, read_opener)
        if reconcile_only:
            return _result("NO_ATTEMPT", "NO_CLAIMED_EFFECT")
        provisional = {"kind": "not_applicable"} if data["operation"] in ({"material_comment", "issue_create"} | AUX_OPERATIONS) else {"kind": "pending"}
        key = store.prepare(dict(action, witness=provisional), effect)["action_key"]
    except Exception:
        return _result("NO_ATTEMPT", "INPUT_OR_STORE_UNAVAILABLE", key)
    aggregate_control = data["operation"] in AGGREGATE_CONTROL_OPERATIONS
    checkpoint = None
    if aggregate_control:
        try:
            checkpoint = _checkpoint_for_control(data, runtime_state)
        except Exception:
            return _result("PREPARED", "CHECKPOINT_UNAVAILABLE_OR_STALE", key)
    try:
        if aggregate_control:
            # Frozen witness; final aggregate admission follows actor/authority.
            witness = _witness(proof, baseline, data["extra_task"])
        else:
            control, tasks, extra = _fresh(data, read_token, read_opener, before=True)
            fresh = (compact_aggregate_v2(data["cfg"], control, tasks, *extra, data["previous"])
                     if data["operation"] in AUX_OPERATIONS else
                     compact_v2(data["cfg"], control, tasks, data["previous"]))
            require(digest(canonical(_proof(data, fresh, extra))) == data["proof_sha256"],
                    "fresh preflight mismatch")
            witness = _witness(proof, fresh, extra)
            require(witness == _witness(proof, baseline, data["extra_task"]), "witness binding mismatch")
        if witness is None:
            return _result("PREPARED", "CHRONOLOGY_INELIGIBLE", key)
        exact = dict(action, witness=witness)
        key = store.prepare(exact, effect)["action_key"]
        retention.save(key, original)
        require(retention.load(key) == original, "durable input provider mismatch")
    except Exception:
        return _result("PREPARED", "FRESH_PROOF_OR_INPUT_RETENTION_FAILED", key)
    try:
        headers = _write_headers(write_token)
        opener = _write_transport()
        actor = _http(opener, headers, API + "/user", "GET", None, 200)
        require(positive(actor.get("id")) and actor["id"] == action["actor_id"], "write actor mismatch")
    except Exception:
        return _result("PREPARED", "WRITE_ACTOR_UNVERIFIED", key)
    try:
        descriptor = strict_json(canonical(exact))
        require(authorize(descriptor) is True and canonical(descriptor) == canonical(exact),
                "exact runtime authority denied or descriptor changed")
    except Exception:
        return _result("PREPARED", "AUTHORITY_DENIED", key)
    try:
        _provider_pair(store, retention)
        require(retention.load(key) == original, "durable input provider mismatch")
    except Exception:
        return _result("PREPARED", "INPUT_PROVIDER_UNAVAILABLE", key)
    if aggregate_control:
        try:
            _admit_control(data, proof, witness, checkpoint, read_token, read_opener)
        except Exception:
            return _result("PREPARED", "AGGREGATE_ADMISSION_FAILED", key)
        start_entered = False
        try:
            with runtime_state.fence(checkpoint["generation"], checkpoint["state_sha256"]):
                _provider_pair(store, retention)
                require(retention.load(key) == original, "durable input provider mismatch")
                start_entered = True
                started = store.start(key)
        except Exception:
            if not start_entered:
                return _result("PREPARED", "CHECKPOINT_FENCE_OR_INPUT_FAILED", key)
            # STARTED may be durable. Never send on uncertainty.
            try:
                claimed = store.claimed(effect)
                if claimed is not None:
                    key = claimed["action_key"]
            except Exception:
                pass
            return _result("EFFECT_UNKNOWN", "START_OR_FENCE_EXIT_UNCONFIRMED", key)
    else:
        try:
            started = store.start(key)  # Durable before any external write.
        except Exception:
            try:
                claimed = store.claimed(effect)
                if claimed is not None:
                    return _claimed_result(store, claimed, action, retention, read_token, read_opener)
            except Exception:
                pass
            return _result("EFFECT_UNKNOWN", "START_NOT_CONFIRMED", key)
    # No path from this point returns to send eligibility.
    try:
        hint = _send(opener, headers, action, request)
    except Exception:
        hint = None
    if hint is not None:
        try:
            started = store.record_response_hint(key, hint)
        except Exception:
            # Read back, but do not claim VERIFIED after a store failure.
            return _reconcile(store, dict(started, response_hint=hint), retention,
                              read_token, read_opener, persist=False)
    return _reconcile(store, started, retention, read_token, read_opener)
