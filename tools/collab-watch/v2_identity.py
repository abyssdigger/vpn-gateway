"""Pure proposed v2 model/role binding validation, not authority or ownership."""
from __future__ import annotations

import re

from core import Conflict, ident, positive

SCHEMA = "vpng-collab-role-bindings/2"
TRANSPORT_ROLES = frozenset({"SPEC", "GUARD", "BUILDER"})
PROCESS_RESPONSIBILITIES = frozenset({"SPEC", "ARCHITECTURE"})
STATUSES = frozenset({"admitted", "disabled"})
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:+-]{0,127}")


class IdentityConflict(Conflict):
    """Selection is not established; role-attributed actions must fail closed."""


def _check(condition, reason):
    if not condition:
        raise IdentityConflict("IDENTITY_CONFLICT: " + reason)


def _shape(value, fields, name):
    _check(type(value) is dict and set(value) == fields, "invalid " + name)


def _model(value):
    return type(value) is str and MODEL.fullmatch(value) is not None and value == value.strip()


def _role(value):
    return type(value) is str and value in TRANSPORT_ROLES


def validate_bindings(document):
    """Validate the entire closed capability document, including disabled rows.

    No role is selected by validation. The active journal/config is a distinct
    input, not a field in this document.
    """
    _shape(document, {"schema", "bindings"}, "binding document")
    _check(document["schema"] == SCHEMA, "unknown binding schema")
    entries = document["bindings"]
    _check(type(entries) is list and 0 < len(entries) <= 64, "invalid binding entries")
    models, pairs, incarnations = set(), set(), set()
    for item in entries:
        _shape(item, {"model", "status", "transport_pairs", "additional_responsibilities"},
               "model binding")
        model, status = item["model"], item["status"]
        _check(_model(model) and model not in models, "invalid or duplicate model")
        models.add(model)
        _check(type(status) is str and status in STATUSES, "unknown admission status")
        allowed = item["transport_pairs"]
        _check(type(allowed) is list and 0 < len(allowed) <= len(TRANSPORT_ROLES),
               "invalid transport pair set")
        roles = set()
        for pair in allowed:
            _shape(pair, {"transport_role", "incarnation"}, "transport pair")
            role, incarnation = pair["transport_role"], pair["incarnation"]
            _check(_role(role) and ident(incarnation), "invalid transport pair")
            _check(role not in roles, "duplicate role within model")
            _check((role, incarnation) not in pairs and incarnation not in incarnations,
                   "duplicate pair or incarnation")
            roles.add(role)
            pairs.add((role, incarnation))
            incarnations.add(incarnation)
        extra = item["additional_responsibilities"]
        _check(type(extra) is dict and set(extra) <= roles, "invalid process-responsibility owners")
        for role, responsibilities in extra.items():
            _check(type(responsibilities) is list and 0 < len(responsibilities) <= len(PROCESS_RESPONSIBILITIES),
                   "invalid process responsibility list")
            _check(all(type(x) is str and x in PROCESS_RESPONSIBILITIES and x != role
                       for x in responsibilities)
                   and len(set(responsibilities)) == len(responsibilities),
                   "unknown or duplicate process responsibility")
    return document


def _active_pairs(roles):
    _check(type(roles) is dict and 0 < len(roles) <= len(TRANSPORT_ROLES),
           "active role map required")
    result, incarnations = {}, set()
    for role, row in roles.items():
        _check(_role(role), "unknown active transport role")
        _shape(row, {"actor_id", "incarnation"}, "active role declaration")
        inc = row["incarnation"]
        _check(positive(row["actor_id"]) and ident(inc) and inc not in incarnations,
               "invalid or duplicate active incarnation/actor")
        result[role] = inc
        incarnations.add(inc)
    return result


def select_identity(document, runtime_model, active_roles, *, selected_role=None):
    """Select only the exact root/config intersection for the trusted model.

    The caller must obtain runtime_model and active_roles independently of
    recovered/project-shared context. This pure function cannot authenticate
    their provenance, establish live-session uniqueness, or grant authority.
    """
    validate_bindings(document)
    active = _active_pairs(active_roles)
    _check(_model(runtime_model), "actual runtime model required")
    _check(selected_role is None or _role(selected_role), "invalid selected role")
    entries = [item for item in document["bindings"]
               if item["model"] == runtime_model and item["status"] == "admitted"]
    _check(len(entries) == 1, "runtime model not admitted")
    matches = [pair for pair in entries[0]["transport_pairs"]
               if active.get(pair["transport_role"]) == pair["incarnation"]
               and (selected_role is None or pair["transport_role"] == selected_role)]
    _check(len(matches) == 1, "missing, stale or ambiguous selected transport pair")
    return {"model": runtime_model, **matches[0]}
