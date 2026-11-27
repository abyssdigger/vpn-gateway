"""Pure v2 auxiliary projection; task lifecycle remains owned by split_journal."""
from __future__ import annotations

from collections import defaultdict

from core import canonical, digest, holder_input, ident, positive, read_comment, require
from journal import framed, is_ref, is_sha, project_signals, receipt_targets
from project_tasks import comment, fingerprint, immutable, shape
from split_journal import MAX_CONTROL_ROWS, physical_ref, project_v2

PROTOCOL = "vpng-collab-aux/2"
PREFIX = "<!-- vpng-collab-aux/"
MARKER = "<!-- " + PROTOCOL + " -->"
COMMON = {"protocol", "journal_epoch", "event_id", "kind", "room", "from", "to",
          "incarnation"}
FIELDS = {"HANDLED": {"handled"}, "PING": {"ping_id"},
          "PONG": {"ping_id", "ping_ref", "ping_sha256"}}


def _event(cfg, row, room):
    e = framed(row["body"], MARKER)
    kind = e.get("kind")
    require(isinstance(kind, str) and kind in FIELDS, "unsupported auxiliary kind")
    shape(e, COMMON | FIELDS[kind], "auxiliary fields")
    require(e["protocol"] == PROTOCOL and e["journal_epoch"] == cfg["journal_epoch"],
            "wrong auxiliary protocol/epoch")
    require(positive(e["room"]) and e["room"] == room and room in cfg["journal_rooms"],
            "wrong auxiliary room")
    require(ident(e["event_id"]) and not e["event_id"].startswith("holder:"),
            "invalid auxiliary event identity")
    sender, to = e["from"], e["to"]
    require(ident(sender) and sender in cfg["roles"] and isinstance(to, list)
            and len(to) == 1 and ident(to[0]) and to[0] in cfg["roles"],
            "invalid auxiliary roles")
    role = cfg["roles"][sender]
    require(row["actor_id"] == role["actor_id"] and e["incarnation"] == role["incarnation"],
            "wrong auxiliary actor/incarnation")
    if kind == "HANDLED":
        require(to == [sender], "HANDLED must be self-addressed")
        receipt_targets(e["handled"])
    else:
        require(to != [sender] and ident(e["ping_id"]), "invalid health relation")
        if kind == "PING":
            require(e["ping_id"] == e["event_id"], "PING identity mismatch")
        else:
            require(is_ref(e["ping_ref"]) and is_sha(e["ping_sha256"]),
                    "invalid PONG physical reference")
    return e


def _fact(row, event, ref):
    return {"event": event, "body_sha256": digest(row["body"]),
            "created_at": row["created_at"], "actor_id": row["actor_id"],
            "physical_ref": ref}


def _holder(cfg, rows, ledger):
    require(isinstance(rows, list) and len(rows) <= MAX_CONTROL_ROWS,
            "invalid holder observation")
    holder = cfg["projectholder"]
    facts, seen = {}, {}
    for raw in rows:
        cid, actor, body = read_comment(raw)
        ref = physical_ref(holder["room"], cid)
        key = canonical([actor, body, raw.get("created_at"), raw.get("updated_at")])
        require(ref not in seen or seen[ref] == key, "conflicting physical holder row")
        if ref in seen:
            continue
        seen[ref] = key
        if actor != holder["actor_id"]:
            continue
        row = comment(raw)
        event = dict(holder_input(cfg, ref, body), event_id=f"holder:{cid}")
        facts[ref] = _fact(row, event, ref)
        ledger["holder:" + ref] = fingerprint(row)
    return facts


def _aux(cfg, control, task_facts, ledger):
    known = {role["actor_id"] for role in cfg["roles"].values()}
    task_ids = {fact["event"]["event_id"] for fact in task_facts.values()}
    logical, facts = {}, {}
    # project_v2 already checked complete control observations and overlapping rows.
    for room in cfg["journal_rooms"]:
        for raw in control[str(room)]:
            cid, actor, body = read_comment(raw)
            if actor not in known or not body.startswith(PREFIX):
                continue
            ref = physical_ref(room, cid)
            if ref in facts:
                continue
            row = immutable(comment(raw))
            event = _event(cfg, row, room)
            mid = event["event_id"]
            require(mid not in task_ids, "task/aux logical identity collision")
            key = canonical([actor, body])
            require(mid not in logical or logical[mid] == key, "conflicting auxiliary identity")
            logical[mid] = key
            facts[ref] = _fact(row, event, ref)
            ledger["aux:" + ref] = fingerprint(row)
    return facts


def _target(facts, ref, mid, sha):
    fact = facts.get(ref)
    require(fact is not None and fact["event"]["event_id"] == mid
            and fact["body_sha256"] == sha, "unadmitted or changed physical target")
    return fact["event"]


def _relations(aux, targets):
    receipts, matched = defaultdict(set), defaultdict(set)
    for ref, fact in aux.items():
        e = fact["event"]
        if e["kind"] == "HANDLED":
            for item in e["handled"]:
                target = _target(targets, item["ref"], item["event_id"], item["body_sha256"])
                require(target["kind"] != "HANDLED" and e["from"] in target["to"],
                        "ineligible receipt target/recipient")
                receipts[(item["ref"], e["from"])].add(ref)
        elif e["kind"] == "PONG":
            target = _target(aux, e["ping_ref"], e["ping_id"], e["ping_sha256"])
            require(target["kind"] == "PING" and target["room"] == e["room"]
                    and target["to"] == [e["from"]] and e["to"] == [target["from"]],
                    "PONG does not reverse exact same-room PING")
            matched[e["ping_ref"]].add(ref)
    health = [{"ping_ref": ref, "ping_id": fact["event"]["event_id"],
               "state": "matched" if matched.get(ref) else "pending",
               "pong_refs": sorted(matched.get(ref, ()))}
              for ref, fact in sorted(aux.items()) if fact["event"]["kind"] == "PING"]
    handled = [{"ref": ref, "recipient": role, "receipt_refs": sorted(refs)}
               for (ref, role), refs in sorted(receipts.items())]
    return receipts, health, handled


def project_aux(cfg, control, tasks, holder_rows, signal_rows, previous=None):
    """Return (composed projection, derivative state); inputs are complete observations.

    No task filtering, network access, clock, command execution or mutation.
    A canonical conflict raises Conflict without returning a new state.
    """
    if previous is not None:
        shape(previous, {"task", "aux"}, "composed retained state")
        shape(previous["aux"], {"protocol", "semantic_config_hash", "ledger"},
              "auxiliary retained state")
        require(previous["aux"]["protocol"] == PROTOCOL
                and isinstance(previous["aux"]["ledger"], dict)
                and isinstance(previous["task"], dict), "invalid retained auxiliary state")
    task_projection, task_state = project_v2(
        cfg, control, tasks, previous["task"] if previous is not None else None)
    config_hash = task_state["semantic_config_hash"]
    ledger = {}
    holder = _holder(cfg, holder_rows, ledger)
    aux = _aux(cfg, control, task_projection["facts"], ledger)
    journal = dict(task_projection["facts"], **aux)
    targets = dict(journal, **holder)
    receipts, health, handled = _relations(aux, targets)
    if previous is not None:
        prior = previous["aux"]
        require(prior["semantic_config_hash"] == config_hash, "auxiliary config changed")
        for key, old in prior["ledger"].items():
            require(ledger.get(key) == old, "prior holder/aux observation missing or changed")
    mailboxes = {role: [ref for ref, fact in sorted(holder.items())
                        if role in fact["event"]["to"] and (ref, role) not in receipts]
                 for role in sorted(cfg["roles"])}
    require(isinstance(signal_rows, list) and len(signal_rows) <= MAX_CONTROL_ROWS,
            "invalid signal observation")
    signals, gc = project_signals(cfg, signal_rows, journal, receipts)
    projection = {"task": task_projection, "holder_inputs": holder,
                  "holder_mailboxes": mailboxes, "aux_facts": aux, "handled": handled,
                  "health": health, "signal_status": signals, "gc_candidates": gc,
                  "authority": "not evaluated; auxiliary coordination only"}
    state = {"task": task_state, "aux": {"protocol": PROTOCOL,
             "semantic_config_hash": config_hash, "ledger": ledger}}
    return projection, state
