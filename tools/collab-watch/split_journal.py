"""Pure staged COLLAB v2 task journal. No network, writes, or authority."""
from __future__ import annotations

from collections import defaultdict

from core import canonical, digest, ident, positive, read_comment, require, validate_config
from journal import framed
from project_tasks import (body_hash, bind_material, close_identity, comment, fingerprint,
                           immutable, material_reference, normalize_task, shape, sha,
                           spec_reference, task_identity)

PROTOCOL = "vpng-collab/2"
MARKER = "<!-- vpng-collab-journal/2 -->"
PREFIX = "<!-- vpng-collab-journal/"
MAX_TASKS = 128
MAX_CONTROL_ROWS = 10000
COMMON = {"protocol", "journal_epoch", "event_id", "kind", "room", "from", "to",
          "incarnation", "task", "revision"}
LINK = {"open_id", "previous"}
CANDIDATE = LINK | {"attempt", "commit_sha", "material_ref"}


def validate_v2_config(cfg):
    shape(cfg, {"protocol", "repository", "journal_rooms", "signal_room", "journal_epoch",
                "roles", "projectholder", "command_registry"}, "v2 config")
    require(cfg["protocol"] == PROTOCOL and ident(cfg["journal_epoch"]), "invalid v2 config identity")
    common = {k: cfg[k] for k in ("repository", "roles", "projectholder", "command_registry")}
    validate_config(dict(common, event_room=cfg["signal_room"], task_rooms=cfg["journal_rooms"],
                         legacy_comments=[]))
    require(set(cfg["roles"]) == {"SPEC", "BUILDER", "GUARD"}, "pilot role set mismatch")
    require(len({r["incarnation"] for r in cfg["roles"].values()}) == 3, "role incarnation collision")
    return cfg


def physical_ref(room, cid):
    return f"issue:{room}#issuecomment-{cid}"


def validate_event(cfg, event, room, actor):
    require(isinstance(event, dict) and COMMON <= set(event), "missing v2 control fields")
    require(event["protocol"] == PROTOCOL and event["journal_epoch"] == cfg["journal_epoch"],
            "wrong v2 protocol/epoch")
    require(positive(event["room"]) and event["room"] == room and room in cfg["journal_rooms"],
            "wrong physical control room")
    require(ident(event["event_id"]) and not event["event_id"].startswith("holder:")
            and ident(event["task"]) and positive(event["revision"]), "invalid task event identity")
    kind = event["kind"]
    require(kind in ("OPEN", "RESULT", "REVIEW", "DISPOSITION"), "unsupported v2 task event kind")
    if kind == "OPEN" or (kind == "DISPOSITION" and event.get("disposition") == "SUPERSEDED"):
        sender, recipient = "SPEC", "BUILDER"
    elif kind == "RESULT":
        sender, recipient = "BUILDER", "GUARD"
    elif kind == "REVIEW" and event.get("verdict") == "SPEC_REQUIRED":
        sender, recipient = "GUARD", "SPEC"
    else:
        sender, recipient = "GUARD", "BUILDER"
    role = cfg["roles"][sender]
    require(event["from"] == sender and event["to"] == [recipient]
            and positive(actor) and actor == role["actor_id"]
            and event["incarnation"] == role["incarnation"], "wrong role/actor/incarnation")
    if kind == "OPEN":
        shape(event, COMMON | {"task_ref", "spec_ref", "previous"}, "OPEN fields")
        task_identity(event["task_ref"])
        spec_reference(event["spec_ref"], event["revision"])
        require((event["previous"] is None if event["revision"] == 1 else ident(event["previous"])),
                "invalid OPEN predecessor")
    elif kind in ("RESULT", "REVIEW"):
        shape(event, COMMON | CANDIDATE | ({"verdict"} if kind == "REVIEW" else set()),
              "candidate relation fields")
        require(positive(event["attempt"]) and sha(event["commit_sha"]), "invalid candidate")
        material_reference(event["material_ref"])
        if kind == "REVIEW":
            require(event["verdict"] in ("REWORK", "ACCEPT", "SPEC_REQUIRED"), "invalid review verdict")
    else:
        require(event.get("disposition") in ("SUPERSEDED", "CLOSED"), "invalid disposition")
        fields = COMMON | LINK | {"disposition"}
        if event["disposition"] == "CLOSED":
            fields |= {"accept_ref", "close_event"}
        shape(event, fields, "DISPOSITION fields")
        if event["disposition"] == "CLOSED":
            ref = shape(event["accept_ref"], {"room", "comment_id", "body_sha256"}, "accept ref")
            require(positive(ref["room"]) and ref["room"] == room and positive(ref["comment_id"])
                    and body_hash(ref["body_sha256"]), "invalid physical ACCEPT ref")
            close_identity(event["close_event"])
    if kind != "OPEN":
        require(ident(event["open_id"]) and ident(event["previous"]), "invalid relation link")
    require(event["previous"] != event["event_id"], "self predecessor")
    return event


def _control(cfg, snapshots):
    validate_v2_config(cfg)
    require(isinstance(snapshots, dict) and set(snapshots) == {str(x) for x in cfg["journal_rooms"]},
            "incomplete control observation")
    require(all(isinstance(x, list) for x in snapshots.values())
            and sum(map(len, snapshots.values())) <= MAX_CONTROL_ROWS, "invalid control rows")
    known = {r["actor_id"] for r in cfg["roles"].values()}
    events, occurrences, facts, ledger, seen = {}, defaultdict(list), {}, {}, {}
    raw_keys = {}
    for room in cfg["journal_rooms"]:
        for raw in snapshots[str(room)]:
            cid, actor, body = read_comment(raw)
            ref = physical_ref(room, cid)
            key = canonical([actor, body, raw.get("created_at"), raw.get("updated_at")])
            require(ref not in seen or seen[ref] == key, "conflicting physical control comment")
            if ref in seen:
                continue
            seen[ref] = key
            if actor not in known or not body.startswith(PREFIX):
                continue
            row = immutable(comment(raw))
            event = validate_event(cfg, framed(body, MARKER), room, actor)
            mid = event["event_id"]
            raw_key = canonical([actor, body])
            require(mid not in raw_keys or raw_keys[mid] == raw_key, "conflicting logical event")
            raw_keys[mid] = raw_key
            events[mid] = event
            fact = {"event": event, "body_sha256": digest(body), "created_at": row["created_at"],
                    "actor_id": actor, "physical_ref": ref}
            facts[ref] = fact
            occurrences[mid].append(fact)
            ledger["control:" + ref] = fingerprint(row)
    for rows in occurrences.values():
        rows.sort(key=lambda x: (x["created_at"], x["physical_ref"]))
    return events, occurrences, facts, ledger


def _registry(cfg, events):
    reserved = {*cfg["journal_rooms"], cfg["signal_room"], cfg["projectholder"]["room"]}
    tasks, by_number, by_id, opens = {}, {}, {}, {}
    for e in events.values():
        if e["kind"] != "OPEN":
            continue
        task, ref = e["task"], e["task_ref"]
        number, iid = ref["issue_number"], ref["issue_id"]
        require(number not in reserved, "task overlaps control/holder/signal room")
        binding = (e["room"], number, iid)
        require(task not in tasks or tasks[task] == binding, "task identity rebind")
        require(number not in by_number or by_number[number] == task, "Issue number rebind")
        require(iid not in by_id or by_id[iid] == task, "Issue ID rebind")
        key = (task, e["revision"])
        require(key not in opens, "multiple OPENs for task revision")
        tasks[task], by_number[number], by_id[iid], opens[key] = binding, task, task, e
    require(len(tasks) <= MAX_TASKS, "task discovery bound exceeded")
    revs = defaultdict(list)
    for (task, rev) in opens:
        revs[task].append(rev)
    for values in revs.values():
        require(sorted(values) == list(range(1, len(values) + 1)), "revision gap")
    for e in events.values():
        if e["kind"] == "OPEN":
            if e["revision"] > 1:
                previous = events.get(e["previous"])
                old = opens[(e["task"], e["revision"] - 1)]
                require(previous is not None and previous["kind"] == "DISPOSITION"
                        and previous["disposition"] == "SUPERSEDED"
                        and previous["open_id"] == old["event_id"]
                        and previous["task"] == e["task"]
                        and previous["revision"] == old["revision"]
                        and previous["room"] == e["room"], "OPEN lacks exact prior supersession")
            continue
        opened = opens.get((e["task"], e["revision"]))
        require(opened is not None and opened["event_id"] == e["open_id"]
                and opened["room"] == e["room"], "unregistered task or stale OPEN reference")
    return tasks, opens


def discover_tasks(cfg, control):
    """Only strict control facts can discover bounded same-repo task identities."""
    events, _, _, _ = _control(cfg, control)
    tasks, _ = _registry(cfg, events)
    return {str(number): {"issue_number": number, "issue_id": iid}
            for _, number, iid in sorted(tasks.values())}


def _earliest(occurrences, event):
    return occurrences[event["event_id"]][0]["created_at"]


def _reduce_revision(cfg, task, opened, relations, occurrences, ledger):
    """One causally linked attempt chain, independent of observation order."""
    spec_actor, guard, builder = (cfg["roles"][name]["actor_id"] for name in ("SPEC", "GUARD", "BUILDER"))
    earliest = lambda e: _earliest(occurrences, e)
    spec = opened["spec_ref"]
    if opened["revision"] == 1:
        require(task["identity"]["body_sha256"] == spec["body_sha256"]
                and task["identity"]["created_at"] < earliest(opened), "initial spec digest/chronology mismatch")
    else:
        bind_material(task, spec, {"kind": "SPEC", "task": opened["task"],
                                  "revision": opened["revision"], "role": "SPEC",
                                  "incarnation": opened["incarnation"]},
                      spec_actor, earliest(opened), ledger)
    successors = {}
    for e in relations:
        require(e["previous"] not in successors, "forked attempt or disposition")
        successors[e["previous"]] = e
        if e["kind"] in ("RESULT", "REVIEW"):
            expected = {k: e[k] for k in ("kind", "task", "revision", "attempt", "commit_sha", "incarnation")}
            expected["role"] = e["from"]
            if e["kind"] == "REVIEW":
                expected["verdict"] = e["verdict"]
            bind_material(task, e["material_ref"], expected,
                          builder if e["kind"] == "RESULT" else guard, earliest(e), ledger)
    current, visited, attempt, accepted = opened, set(), 0, None
    state = "BUILDER_READY"
    while current["event_id"] in successors:
        e = successors[current["event_id"]]
        mid = e["event_id"]
        require(mid not in visited and earliest(current) < earliest(e), "cyclic or unproved relation chronology")
        visited.add(mid)
        if e["kind"] == "RESULT":
            require(state == "BUILDER_READY" and e["attempt"] == attempt + 1,
                    "unlinked, stale or post-ACCEPT result")
            attempt = e["attempt"]
            state = "GUARD_REVIEW"
        elif e["kind"] == "REVIEW":
            require(state == "GUARD_REVIEW" and current["kind"] == "RESULT"
                    and e["attempt"] == attempt and e["commit_sha"] == current["commit_sha"],
                    "review does not match exact current result")
            if e["verdict"] == "ACCEPT":
                accepted = e
                state = "ACCEPTED"
            elif e["verdict"] == "SPEC_REQUIRED":
                state = "SPEC_REQUIRED"
            else:
                state = "BUILDER_READY"
        else:
            require(state not in ("SUPERSEDED", "CLOSED"), "relation after disposition")
            if e["disposition"] == "SUPERSEDED":
                state = "SUPERSEDED"
            else:
                require(state == "ACCEPTED", "CLOSED disposition without ACCEPT")
                state = "CLOSED"
        current = e
    require(len(visited) == len(relations), "disconnected task relation")
    return {"state": state, "head": current, "accepted": accepted, "attempt": attempt}


def _terminal(task, result, occurrences, facts):
    state, accept, head = result["state"], result["accepted"], result["head"]
    close = task["close"]
    if close is None:
        require(state != "CLOSED", "CLOSED disposition without observed close")
        return state, []
    require(state in ("ACCEPTED", "CLOSED") and accept is not None, "premature or stale physical close")
    eligible = [f for f in occurrences[accept["event_id"]] if f["created_at"] < close["created_at"]]
    require(eligible, "no immutable pre-close ACCEPT occurrence")
    if state == "ACCEPTED":
        return "CLOSE_OBSERVED", [f["physical_ref"] for f in eligible]
    ref = head["accept_ref"]
    physical = physical_ref(ref["room"], ref["comment_id"])
    fact = facts.get(physical)
    require(fact is not None and fact in eligible and fact["body_sha256"] == ref["body_sha256"],
            "missing or ineligible exact physical ACCEPT")
    require(head["close_event"] == close and close["created_at"] < _earliest(occurrences, head),
            "CLOSED disposition close identity/chronology mismatch")
    return "CLOSED", [physical]


def project_v2(cfg, control, tasks, previous=None):
    """Return pure task projection and derivative immutable ledger."""
    events, occurrences, facts, ledger = _control(cfg, control)
    registry, opens = _registry(cfg, events)
    require(isinstance(tasks, dict) and set(tasks) == {str(x[1]) for x in registry.values()},
            "missing or unregistered task observation")
    config_hash = digest(canonical({k: v for k, v in cfg.items() if k != "signal_room"}))
    if previous is not None:
        shape(previous, {"protocol", "semantic_config_hash", "ledger"}, "retained state")
        require(previous["protocol"] == PROTOCOL and previous["semantic_config_hash"] == config_hash
                and isinstance(previous["ledger"], dict), "retained state/config mismatch")
    groups = defaultdict(list)
    for e in events.values():
        if e["kind"] != "OPEN":
            groups[(e["task"], e["revision"])].append(e)
    projected, roles = [], {"SPEC": [], "BUILDER": [], "GUARD": []}
    for name, (_, number, iid) in sorted(registry.items()):
        task = normalize_task(cfg, {"issue_number": number, "issue_id": iid}, tasks[str(number)])
        key = f"task:{iid}"
        ledger[key + ":identity"] = fingerprint(task["identity"])
        if task["close"] is not None:
            ledger[key + ":close"] = fingerprint(task["close"])
        revisions = sorted(rev for (t, rev) in opens if t == name)
        historical = []
        prior = None
        for rev in revisions:
            opened = opens[(name, rev)]
            if prior is not None:
                require(prior["state"] == "SUPERSEDED"
                        and opened["previous"] == prior["head"]["event_id"]
                        and _earliest(occurrences, prior["head"]) < _earliest(occurrences, opened),
                        "invalid specification supersession relation")
            result = _reduce_revision(cfg, task, opened, groups[(name, rev)], occurrences, ledger)
            prior = result
            historical.append({"revision": rev, "open_id": opened["event_id"],
                               "state": result["state"], "head": result["head"]["event_id"]})
        state, eligible = _terminal(task, result, occurrences, facts)
        historical[-1]["state"] = state
        accepted = result["accepted"]
        item = {"task": name, "issue_number": number, "issue_id": iid, "revision": revisions[-1],
                "state": state, "attempt": result["attempt"], "head": result["head"]["event_id"],
                "accepted_sha": accepted["commit_sha"] if accepted and state != "SUPERSEDED" else None,
                "eligible_accept_refs": eligible, "revisions": historical}
        projected.append(item)
        role = ("BUILDER" if state == "BUILDER_READY" else
                "SPEC" if state in ("SPEC_REQUIRED", "SUPERSEDED") else
                None if state == "CLOSED" else "GUARD")
        if role:
            roles[role].append({"task": name, "revision": revisions[-1], "state": state})
    if previous is not None:
        for key, old in previous["ledger"].items():
            require(ledger.get(key) == old, "prior immutable observation missing or changed")
    state = {"protocol": PROTOCOL, "semantic_config_hash": config_hash, "ledger": ledger}
    projection = {"protocol": PROTOCOL, "journal_epoch": cfg["journal_epoch"], "tasks": projected,
                  "roles": {r: {"state": "READY" if reasons else "WAITING", "reasons": reasons}
                            for r, reasons in roles.items()},
                  "facts": facts, "authority": "not evaluated; task coordination only"}
    return projection, state
