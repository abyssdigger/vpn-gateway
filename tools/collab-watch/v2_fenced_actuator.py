"""Staged owner-fenced composition; never a credential custody or authority policy."""
from __future__ import annotations

from core import require
from v2_actuator import _bound, actuate
from v2_owner import Capability, OwnerBusy, OwnerStore


def _result(state, code):
    return {"state": state, "code": code, "action_key": None}


def actuate_fenced(owner_store, capability, store, original, retention, authorize, *,
                   read_token=None, write_token=None, read_opener=None, reconcile_only=False,
                   runtime_state=None):
    """Bind an exact frozen action to the current owner, then retain its fence.

    Lock order is owner-store -> attempt-store. Neither capability nor
    generation is an input to semantic intent, authority, transport or receipt.
    The trusted caller must pin the stores and prohibit direct credential bypass.
    """
    try:
        _, _, _, _, action, _ = _bound(original)
    except Exception:
        return _result("NO_ATTEMPT", "FROZEN_ACTION_UNBINDABLE")
    try:
        require(type(owner_store) is OwnerStore and type(capability) is Capability,
                "concrete owner store and capability required")
        require(capability.repository == action["repository"].lower()
                and capability.journal_epoch == action["journal_epoch"]
                and capability.transport_role == action["role"]
                and capability.incarnation == action["incarnation"], "owner scope mismatch")
    except Exception:
        return _result("NO_ATTEMPT", "OWNER_CAPABILITY_REJECTED")
    entered = False
    try:
        with owner_store.fence(capability):
            entered = True
            return actuate(store, original, retention, authorize, read_token=read_token,
                           write_token=write_token, read_opener=read_opener,
                           reconcile_only=reconcile_only, runtime_state=runtime_state)
    except Exception as exc:
        # A failure during invocation or fence exit cannot establish no send.
        # BaseException deliberately unwinds both flocks and is not swallowed.
        if entered:
            return _result("EFFECT_UNKNOWN", "FENCED_INVOCATION_UNCONFIRMED")
        if isinstance(exc, OwnerBusy):
            return _result("BUSY", "OWNER_BUSY")
        return _result("NO_ATTEMPT", "OWNER_CAPABILITY_REJECTED")
