"""Staged closed writer composition, not a same-process or OS isolation boundary."""
from __future__ import annotations

from core import COMMENT_REF, Conflict, canonical, positive, require, strict_json
from project_tasks import body_hash
from split_journal import validate_v2_config
from v2_actuator import FIELDS
from v2_attempts import AttemptStore
from v2_fenced_actuator import actuate_fenced
from v2_identity import select_identity, validate_bindings
from v2_inputs import InputStore, MAX_INPUT_BYTES
from v2_owner import Capability, OwnerStore
from v2_runtime_state import RuntimeStateStore

NEW_OPERATIONS = frozenset({"material_comment", "control_comment", "aux_comment",
                            "initial_open", "issue_close", "issue_create"})
RECONCILE_OPERATIONS = NEW_OPERATIONS | {"signal_comment"}
RESULT_CODES = {
    "NO_ATTEMPT": frozenset({"OWNERSHIP_UNAVAILABLE", "INPUT_PROVIDER_UNAVAILABLE",
                             "NO_CLAIMED_EFFECT", "INPUT_OR_STORE_UNAVAILABLE",
                             "FROZEN_ACTION_UNBINDABLE", "OWNER_CAPABILITY_REJECTED"}),
    "BUSY": frozenset({"ACTUATOR_BUSY", "OWNER_BUSY"}),
    "PREPARED": frozenset({"CHECKPOINT_UNAVAILABLE_OR_STALE", "CHRONOLOGY_INELIGIBLE",
                           "FRESH_PROOF_OR_INPUT_RETENTION_FAILED", "WRITE_ACTOR_UNVERIFIED",
                           "AUTHORITY_DENIED", "INPUT_PROVIDER_UNAVAILABLE",
                           "AGGREGATE_ADMISSION_FAILED", "CHECKPOINT_FENCE_OR_INPUT_FAILED"}),
    "CONFLICT": frozenset({"EFFECT_CLAIM_CONFLICT"}),
    "UNRESOLVED": frozenset({"READBACK_UNRESOLVED"}),
    "EFFECT_UNKNOWN": frozenset({"RETAINED_INPUT_UNAVAILABLE", "STORE_FAILURE_AFTER_START",
                                 "INPUT_PROVIDER_UNAVAILABLE", "START_OR_FENCE_EXIT_UNCONFIRMED",
                                 "START_NOT_CONFIRMED", "FENCED_INVOCATION_UNCONFIRMED"}),
    "VERIFIED": frozenset({"CANONICAL_RECEIPT_RECORDED"}),
}
RESULT_FIELDS = frozenset({"state", "code", "action_key"})
LOCATOR_FIELDS = {
    "issue_create": {"issue_number", "issue_id"},
    "material_comment": {"room", "comment_id"},
    "control_comment": {"room", "physical_ref"},
    "initial_open": {"room", "physical_ref"},
    "aux_comment": {"room", "physical_ref"},
    "signal_comment": {"room", "physical_ref"},
    "issue_close": {"room", "issue_id", "event_id"},
}


def _shape(value, fields):
    return (type(value) is dict and all(type(k) is str for k in value)
            and set(value) == fields)


def _hash(value):
    return type(value) is str and body_hash(value)


def _closed_result(result, operation):
    require(type(result) is dict and all(type(k) is str for k in result),
            "invalid delegate result")
    state, code, key = result.get("state"), result.get("code"), result.get("action_key")
    require(type(state) is str and type(code) is str
            and code in RESULT_CODES.get(state, ())
            and (key is None or _hash(key)), "invalid delegate outcome")
    require(key is not None or state not in {"PREPARED", "CONFLICT", "UNRESOLVED", "VERIFIED"},
            "missing action identity")
    require(state != "BUSY" or key is None, "invalid busy action identity")
    fields = RESULT_FIELDS | ({"receipt_sha256", "locator"} if state == "VERIFIED" else set())
    require(_shape(result, fields), "invalid delegate result fields")
    out = {"state": state, "code": code, "action_key": key}
    if state == "VERIFIED":
        receipt, locator = result["receipt_sha256"], result["locator"]
        require(_hash(receipt) and _shape(locator, LOCATOR_FIELDS[operation]),
                "invalid receipt identity")
        for k, v in locator.items():
            if k != "physical_ref":
                require(positive(v), "invalid physical locator")
        if "physical_ref" in locator:
            ref = locator["physical_ref"]
            match = COMMENT_REF.fullmatch(ref) if type(ref) is str and len(ref) <= 1024 else None
            require(match is not None and match.group(1) == str(locator["room"]),
                    "invalid physical reference")
        out.update(receipt_sha256=receipt, locator=dict(locator))
    return out


def _rejected():
    return dict(state="NO_ATTEMPT", code="TRUSTED_INGRESS_REJECTED", action_key=None)


def _unknown():
    # No independent lookup of a trustworthy existing key at this boundary.
    return dict(state="EFFECT_UNKNOWN", code="TRUSTED_RESULT_INVALID", action_key=None)


class TrustedWriter:
    """Trusted bootstrap only. The public data interface is invoke(request).

    Configuration pin is detached, exact canonical parsed JSON, including the
    transport room. The accepted delegate owns proof, current-owner fencing,
    runtime authority, checkpoint, STARTED and reconciliation. This class
    cannot authenticate arbitrary code in its own process or storage continuity.
    """
    __slots__ = ("_config_pin", "_repository", "_epoch", "_role", "_incarnation", "_actor",
                 "_owner", "_capability", "_store", "_retention", "_runtime_state",
                 "_authorize", "_read_token", "_write_token", "_read_opener")

    def __init__(self, cfg, bindings, runtime_model, *, selected_role=None,
                 owner_store, capability, store, retention, runtime_state,
                 authorize, read_token=None, write_token=None, read_opener=None):
        try:
            validate_v2_config(cfg)
            validate_bindings(bindings)
            detached_cfg = strict_json(canonical(cfg))
            detached_bindings = strict_json(canonical(bindings))
            validate_v2_config(detached_cfg)
            selected = select_identity(detached_bindings, runtime_model, detached_cfg["roles"],
                                       selected_role=selected_role)
            role, incarnation = selected["transport_role"], selected["incarnation"]
            self._config_pin = canonical(detached_cfg)
            self._repository, self._epoch = detached_cfg["repository"].lower(), detached_cfg["journal_epoch"]
            self._role, self._incarnation = role, incarnation
            self._actor = detached_cfg["roles"][role]["actor_id"]
            require(type(owner_store) is OwnerStore and type(capability) is Capability
                    and type(store) is AttemptStore and type(retention) is InputStore
                    and callable(authorize), "invalid trusted composition")
            self._owner, self._capability = owner_store, capability
            self._check_scope()
            retention.validate_pair(store.store_id)
            if runtime_state is not None:
                require(type(runtime_state) is RuntimeStateStore
                        and runtime_state._repository == self._repository
                        and runtime_state._epoch == self._epoch, "invalid checkpoint scope")
            self._store, self._retention, self._runtime_state = store, retention, runtime_state
            self._authorize = authorize
            self._read_token, self._write_token, self._read_opener = read_token, write_token, read_opener
        except Exception:
            raise Conflict("trusted writer bootstrap rejected") from None

    def _check_scope(self):
        cap = self._capability
        require(type(self._owner) is OwnerStore and type(cap) is Capability,
                "invalid trusted owner objects")
        scope = self._owner._scope()
        require(scope["repository"] == self._repository and scope["journal_epoch"] == self._epoch
                and cap.store_id == scope["store_id"] and cap.repository == self._repository
                and cap.journal_epoch == self._epoch and cap.transport_role == self._role
                and cap.incarnation == self._incarnation, "owner scope mismatch")
        # No generation/status lookup outside the accepted owner fence.

    def _admit(self, request):
        require(_shape(request, {"original", "reconcile_only"}), "invalid request shape")
        original, reconcile = request["original"], request["reconcile_only"]
        require(type(original) is str and type(reconcile) is bool
                and len(original) <= MAX_INPUT_BYTES
                and len(original.encode("utf-8")) <= MAX_INPUT_BYTES, "invalid frozen input")
        data = strict_json(original)
        require(_shape(data, FIELDS) and canonical(data) == original, "invalid frozen fields")
        require(canonical(data["cfg"]) == self._config_pin
                and data["role"] == self._role and data["incarnation"] == self._incarnation
                and positive(data["actor"]) and data["actor"] == self._actor,
                "trusted config or identity mismatch")
        self._check_scope()
        operation = data["operation"]
        require(type(operation) is str and operation in
                (RECONCILE_OPERATIONS if reconcile else NEW_OPERATIONS), "operation not admitted")
        return original, reconcile, operation

    def invoke(self, request):
        """No worker-supplied bootstrap override, no retries or independent claimed lookup."""
        try:
            original, reconcile, operation = self._admit(request)
        except Exception:
            return _rejected()
        try:
            result = actuate_fenced(self._owner, self._capability, self._store, original,
                                    self._retention, self._authorize,
                                    read_token=self._read_token, write_token=self._write_token,
                                    read_opener=self._read_opener, reconcile_only=reconcile,
                                    runtime_state=self._runtime_state)
            return _closed_result(result, operation)
        except Exception:
            # After delegation, failure to observe/validate a result is not no-send.
            # Process termination/BaseException remains a lost-response recovery case.
            return _unknown()
