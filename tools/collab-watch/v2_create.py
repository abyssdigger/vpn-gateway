"""Staged single-attempt project Issue creation proof and bounded inventory."""
from __future__ import annotations

from urllib.request import Request, build_opener

from collab_watch import API, MAX_PAGE_BYTES, MAX_LOCAL_BYTES, MAX_PAGES, MAX_OBSERVED_COMMENTS, TIMEOUT, NoRedirect
from core import Conflict, canonical, digest, ident, positive, require, strict_json
from project_tasks import body_hash, shape, stamp
from split_journal import project_v2, validate_v2_config
from v2_acquisition import Reader, _next
from v2_preflight import _baseline, _selected, MAX_CANDIDATE_BYTES
from v2_compact import project_compact_v2

FAMILY = "<!-- vpng-collab-task-create/"
MARKER = FAMILY + "2"
FIELDS = {"repository", "journal_epoch", "task", "revision", "room", "role",
          "incarnation", "actor_id", "title_sha256", "spec_sha256", "effect_sha256"}
PAGE = 100


def effect_for(repository, epoch, task):
    return {"operation": "issue_create", "repository": repository.lower(),
            "journal_epoch": epoch, "task": task}


def _human(title, spec):
    require(isinstance(title, str) and title.strip() and len(title.encode("utf-8")) <= 256
            and "\n" not in title and "\r" not in title
            and isinstance(spec, str) and spec.strip()
            and len(spec.encode("utf-8")) <= MAX_CANDIDATE_BYTES
            and FAMILY not in title and FAMILY not in spec
            and "\x00" not in title and "\x00" not in spec, "invalid human title/spec")


def preflight_create(cfg, observation, actor, request, previous=None, *,
                     selected_role, selected_incarnation):
    validate_v2_config(cfg)
    _selected(cfg, actor, selected_role, selected_incarnation)
    require(selected_role == "SPEC", "creation requires selected SPEC")
    shape(request, {"task", "revision", "room", "title", "spec"}, "creation request")
    task, room = request["task"], request["room"]
    require(ident(task) and not task.startswith("holder:") and positive(request["revision"])
            and request["revision"] == 1 and positive(room) and room in cfg["journal_rooms"],
            "invalid creation task/revision/room")
    title, spec = request["title"], request["spec"]
    _human(title, spec)
    projection, _, proof = _baseline(cfg, observation, previous)
    require(not any(t["task"] == task for t in projection["tasks"]), "task already registered")
    effect = effect_for(cfg["repository"], cfg["journal_epoch"], task)
    meta = dict(repository=effect["repository"], journal_epoch=effect["journal_epoch"],
                task=task, revision=1, room=room, role="SPEC", incarnation=selected_incarnation,
                actor_id=actor, title_sha256=digest(title), spec_sha256=digest(spec),
                effect_sha256=digest(canonical(effect)))
    body = MARKER + "\n" + canonical(meta) + "\n-->\n\n" + spec
    require(len(body.encode("utf-8")) <= MAX_CANDIDATE_BYTES, "creation body bound")
    payload = {"title": title, "body": body}
    return dict(proof, operation="issue_create", selected_role=selected_role,
                selected_incarnation=selected_incarnation, effect=effect, marker=meta,
                request_sha256=digest(canonical(payload)), body_sha256=digest(body),
                postcondition={"actor_id": actor}), payload


def _normalize(repo, raw):
    root = f"{API}/repos/{repo}"
    require(isinstance(raw, dict) and positive(raw.get("number")) and positive(raw.get("id"))
            and isinstance(raw.get("url"), str)
            and raw["url"].lower() == (root+"/issues/"+str(raw["number"])).lower()
            and isinstance(raw.get("repository_url"), str)
            and raw["repository_url"].lower() == root.lower(), "foreign or malformed Issue row")
    require(isinstance(raw.get("user"), dict) and positive(raw["user"].get("id"))
            and isinstance(raw.get("title"), str) and "body" in raw
            and (raw["body"] is None or isinstance(raw["body"], str))
            and raw.get("state") in ("open", "closed"), "incomplete Issue row")
    return {"number": raw["number"], "id": raw["id"], "actor_id": raw["user"]["id"],
            "title": raw["title"], "body": raw["body"], "state": raw["state"],
            "created_at": stamp(raw.get("created_at")), "pr": "pull_request" in raw}


def marker(repo, row):
    title, body = row["title"], row["body"]
    require(FAMILY not in title, "creation marker in title")
    if body is None or FAMILY not in body:
        return None
    lines = body.split("\n", 4)
    require(len(lines) == 5 and lines[0] == MARKER and lines[2] == "-->"
            and lines[3] == "" and len(lines[1].encode("utf-8")) <= 8192,
            "malformed reserved creation marker")
    meta = strict_json(lines[1])
    shape(meta, FIELDS, "creation marker")
    require(canonical(meta) == lines[1] and meta["repository"] == repo.lower()
            and ident(meta["journal_epoch"]) and ident(meta["task"])
            and not meta["task"].startswith("holder:") and positive(meta["revision"])
            and meta["revision"] == 1 and positive(meta["room"]) and meta["role"] == "SPEC"
            and ident(meta["incarnation"]) and positive(meta["actor_id"])
            and meta["actor_id"] == row["actor_id"], "invalid creation marker identity")
    _human(title, lines[4])
    effect = effect_for(repo, meta["journal_epoch"], meta["task"])
    require(meta["title_sha256"] == digest(title) and meta["spec_sha256"] == digest(lines[4])
            and meta["effect_sha256"] == digest(canonical(effect)), "creation marker digest mismatch")
    return meta


class CreationReader(Reader):
    """Separate fixed-endpoint inventory; inherited header construction only."""
    def _read(self, number=None, page=None):
        require((positive(number) and page is None) or (number is None and positive(page)),
                "invalid inventory endpoint")
        url = self.root + (f"/issues/{number}" if number is not None else
            f"/issues?state=all&sort=created&direction=asc&per_page={PAGE}&page={page}")
        with self.opener.open(Request(url, headers=self.headers, method="GET"), timeout=TIMEOUT) as response:
            require(response.status == 200 and response.geturl() == url, "inventory status/URL")
            data = response.read(MAX_PAGE_BYTES+1)
            require(len(data) <= MAX_PAGE_BYTES, "inventory page bytes")
            length = response.headers.get("Content-Length")
            require(length is None or length.isdecimal() and int(length) == len(data), "inventory length")
            self.bytes += len(data)
            require(self.bytes <= MAX_LOCAL_BYTES, "inventory total bytes")
            value = strict_json(data.decode("utf-8"))
            has_next = _next(response.headers)
            if number is not None:
                require(isinstance(value, dict) and not has_next, "invalid fixed Issue response")
                return _normalize(self.repo, value)
            require(isinstance(value, list) and len(value) <= PAGE, "invalid inventory page")
            self.rows += len(value)
            require(self.rows <= MAX_OBSERVED_COMMENTS, "inventory row bound")
            return value, has_next

    def scan(self):
        ids, numbers = {}, {}
        for page in range(1, MAX_PAGES+1):
            items, more = self._read(page=page)
            before = len(ids)
            for raw in items:
                row = _normalize(self.repo, raw)
                rid, num = row["id"], row["number"]
                require(rid not in ids or ids[rid] == row, "conflicting Issue ID")
                require(num not in numbers or numbers[num] == rid, "conflicting Issue number")
                ids[rid], numbers[num] = row, rid
                marker(self.repo, row)
            require(not items or len(ids) > before, "inventory pagination no progress")
            require(items or not more, "empty continuation")
            if not more and len(items) < PAGE:
                return [ids[k] for k in sorted(ids)]
        raise Conflict("inventory page bound")


def acquire_creation(cfg, effect, token=None, opener=None, *, expect_absent=False):
    """Two complete equal scans; unique candidate additionally fixed-resource checked."""
    try:
        validate_v2_config(cfg)
        require(effect == effect_for(cfg["repository"], cfg["journal_epoch"], effect["task"]),
                "creation effect mismatch")
        if opener is None:
            opener = build_opener(NoRedirect())
        a = CreationReader(cfg, token, opener).scan()
        reader = CreationReader(cfg, token, opener)
        b = reader.scan()
        require(a == b, "unstable creation inventory")
        key = digest(canonical(effect))
        candidates = [r for r in b if (marker(cfg["repository"], r) or {}).get("effect_sha256") == key]
        if expect_absent:
            require(not candidates, "creation effect already physically present")
            return None
        require(len(candidates) == 1, "missing or ambiguous creation effect")
        result = candidates[0]
        require(not result["pr"] and reader._read(number=result["number"]) == result,
                "candidate fixed resource mismatch or PR")
        return result
    except Exception:
        raise Conflict("creation inventory incomplete, conflicting or unavailable") from None


def verify_creation(cfg, baseline, actor, request, control, tasks, physical, previous=None, *,
                    selected_role, selected_incarnation, expected_proof_sha256, hint=None):
    proof, payload = preflight_create(cfg, baseline, actor, request, previous,
                                     selected_role=selected_role, selected_incarnation=selected_incarnation)
    require(body_hash(expected_proof_sha256) and digest(canonical(proof)) == expected_proof_sha256,
            "creation proof mismatch")
    require(marker(cfg["repository"], physical) == proof["marker"] and physical["pr"] is False
            and physical["actor_id"] == actor and physical["title"] == payload["title"]
            and physical["body"] == payload["body"], "created physical content mismatch")
    ref = {"issue_number": physical["number"], "issue_id": physical["id"]}
    require(all(positive(v) for v in ref.values()) and ref["issue_number"] not in
            {*cfg["journal_rooms"], cfg["signal_room"], cfg["projectholder"]["room"]}, "reserved Issue")
    require(hint is None or hint == ref, "creation hint mismatch")
    _, state = project_compact_v2(cfg, baseline, previous)
    projection, post = project_v2(cfg, control, tasks, state)
    matches = [t for t in projection["tasks"] if t["task"] == request["task"]]
    aliases = [t for t in projection["tasks"] if t["issue_number"] == ref["issue_number"]
               or t["issue_id"] == ref["issue_id"]]
    if matches:
        require(len(matches) == 1 and aliases == matches
                and all(matches[0][k] == v for k, v in ref.items()), "registered creation mismatch")
        opened = [f["event"] for f in projection["facts"].values() if f["event"]["kind"] == "OPEN"
                  and f["event"]["task"] == request["task"] and f["event"]["revision"] == 1]
        require(opened and all(e["room"] == request["room"] and e["task_ref"] == ref
                and e["spec_ref"] == {"kind": "issue_body", "body_sha256": proof["body_sha256"]}
                for e in opened), "initial OPEN corroboration mismatch")
        task = tasks[str(ref["issue_number"])]
        require(task["created_at"] == physical["created_at"] and task["state"] == physical["state"],
                "physical/canonical Issue state mismatch")
    else:
        require(not aliases and physical["state"] == "open", "unexpected orphan state or alias")
    return {"operation": "issue_create", "proof_sha256": expected_proof_sha256,
            "post_state_sha256": digest(canonical(post)), "issue": ref,
            "body_sha256": proof["body_sha256"], "title_sha256": digest(payload["title"]),
            "actor_id": actor, "created_at": physical["created_at"],
            "authority": "verification only; no registration or mutation authorized"}
