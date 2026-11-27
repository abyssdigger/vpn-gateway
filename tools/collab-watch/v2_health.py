"""Pure, ephemeral communication-health policy over an accepted scheduler view."""
from __future__ import annotations

from core import require

IDLE_MS = 600_000
RESPONSE_MS = 300_000


def _observed(view):
    identity = view["identity"]
    role = identity["transport_role"]
    inventory = view["peer_journal_inventory"]
    evidence = {}
    for peer in sorted(inventory):
        require(peer != role, "selected role cannot be its own peer")
        refs = {}
        for row in inventory[peer]:
            ref = row["physical_ref"]
            require(row["sender"] == peer and ref not in refs,
                    "invalid peer inventory occurrence")
            refs[ref] = row["body_sha256"]
        evidence[peer] = (dict(sorted(refs.items())), {}, {})
    for row in view["health"]["outgoing"]:
        peer, ref = row["recipient"], row["ping_ref"]
        require(row["sender"] == role and peer in evidence,
                "invalid outgoing health role")
        _, outgoing, pending = evidence[peer]
        require(ref not in outgoing and row["state"] in ("pending", "matched"),
                "invalid outgoing health occurrence")
        outgoing[ref] = (row["ping_id"], row["body_sha256"])
        if row["state"] == "pending":
            pending[ref] = row["ping_id"]
    return role, identity["incarnation"], evidence


def _retained(old, current):
    require(all(ref in current and current[ref] == value
                for ref, value in old.items()), "health evidence lost or changed")


def _episode(now_ms, mode="IDLE", *, ping_ref=None, ping_id=None, ambiguous_refs=()):
    return {"mode": mode, "baseline_ms": now_ms, "ping_ref": ping_ref,
            "ping_id": ping_id, "ambiguous_refs": tuple(sorted(ambiguous_refs))}


def _start_response(peer, refs, pending, now_ms, intents):
    refs = sorted(refs)
    if len(refs) > 1:
        intents.append({"kind": "HEALTH_EPISODE_AMBIGUOUS", "peer": peer,
                        "ping_refs": tuple(refs)})
        return _episode(now_ms, "AMBIGUOUS", ambiguous_refs=refs)
    require(len(refs) == 1 and refs[0] in pending, "missing pending PING")
    ref = refs[0]
    return _episode(now_ms, "WAITING_RESPONSE", ping_ref=ref, ping_id=pending[ref])


def advance_health(view, previous, now_ms):
    """Return detached (ephemeral state, intents); never read a clock or send."""
    require(type(now_ms) is int and now_ms >= 0, "invalid monotonic time")
    role, incarnation, evidence = _observed(view)
    if previous is not None:
        require(previous["role"] == role and previous["incarnation"] == incarnation
                and set(previous["peers"]) == set(evidence), "health identity drift")
        require(now_ms >= previous["last_now_ms"], "backwards monotonic time")

    peers, intents = {}, []
    for peer, (refs, outgoing, pending) in evidence.items():
        if previous is None:
            episode = (_start_response(peer, pending, pending, now_ms, intents)
                       if pending else _episode(now_ms))
        else:
            old = previous["peers"][peer]
            _retained(old["peer_refs"], refs)
            _retained(old["outgoing_refs"], outgoing)
            new_pending = set(pending) - set(old["outgoing_refs"])
            episode = dict(old["episode"])
            mode = episode["mode"]
            if set(refs) - set(old["peer_refs"]):
                # New admitted peer evidence wins even exactly at a deadline,
                # or when a new outgoing PING appears in the same observation.
                episode = _episode(now_ms)
            elif new_pending:
                require(mode not in ("UNCONFIRMED", "AMBIGUOUS"),
                        "new PING in suppressed health episode")
                if mode == "WAITING_RESPONSE":
                    active = episode["ping_ref"]
                    require(active in pending, "active PING changed without peer evidence")
                    new_pending.add(active)
                else:
                    require(mode in ("IDLE", "PING_INTENT_EMITTED"),
                            "invalid health episode")
                episode = _start_response(peer, new_pending, pending, now_ms, intents)
            else:
                elapsed = now_ms - episode["baseline_ms"]
                if mode == "IDLE" and elapsed >= IDLE_MS:
                    intents.append({"kind": "PING_DUE", "peer": peer})
                    episode = _episode(now_ms, "PING_INTENT_EMITTED")
                elif mode == "WAITING_RESPONSE":
                    ref = episode["ping_ref"]
                    require(ref in pending and pending[ref] == episode["ping_id"],
                            "active PING changed without peer evidence")
                    if elapsed >= RESPONSE_MS:
                        intents.append({"kind": "COMMUNICATION_UNCONFIRMED", "peer": peer,
                                        "ping_id": episode["ping_id"], "ping_ref": ref})
                        episode = dict(episode, mode="UNCONFIRMED")
                else:
                    require(mode in ("IDLE", "PING_INTENT_EMITTED", "UNCONFIRMED", "AMBIGUOUS"),
                            "invalid health episode")
        peers[peer] = {"peer_refs": refs, "outgoing_refs": dict(sorted(outgoing.items())),
                       "episode": episode}
    return {"role": role, "incarnation": incarnation, "last_now_ms": now_ms,
            "peers": peers}, intents
