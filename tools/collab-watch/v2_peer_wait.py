"""Pure ephemeral budget for one explicit bounded peer-wait invocation."""
from __future__ import annotations

from core import ident, require

WAIT_MS = 120_000
FIELDS = frozenset(("role", "incarnation", "peer", "dependency_key", "wait_token"))


def advance_peer_wait(descriptor, previous, now_ms):
    """Return detached local wait state and at most one expiry intent."""
    require(isinstance(descriptor, dict) and set(descriptor) == FIELDS
            and all(ident(value) for value in descriptor.values())
            and descriptor["role"] != descriptor["peer"], "invalid peer wait descriptor")
    require(type(now_ms) is int and now_ms >= 0, "invalid monotonic time")
    if previous is None:
        baseline, expired = now_ms, False
    else:
        require(previous["descriptor"] == descriptor, "peer wait descriptor drift")
        require(now_ms >= previous["last_now_ms"], "backwards monotonic time")
        baseline, expired = previous["baseline_ms"], previous["expired"]

    intents = []
    if not expired and now_ms - baseline >= WAIT_MS:
        expired = True
        intents.append(dict(descriptor, kind="PEER_WAIT_BUDGET_EXPIRED"))
    return {"descriptor": dict(descriptor), "baseline_ms": baseline,
            "last_now_ms": now_ms, "expired": expired}, intents
