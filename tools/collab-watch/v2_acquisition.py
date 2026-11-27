"""Read-only bounded GitHub acquisition for the staged v2 task journal."""
from __future__ import annotations

import re
from typing import NamedTuple
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from collab_watch import (API, PAGE_SIZE, MAX_PAGES, MAX_PAGE_BYTES,
                          MAX_LOCAL_BYTES, MAX_OBSERVED_COMMENTS, TIMEOUT, NoRedirect)
from core import Conflict, canonical, positive, require, strict_json
from project_tasks import comment, normalize_task, stamp
from split_journal import _control, discover_tasks, validate_v2_config
from v2_preflight import initial_open_candidate, prospective_initial_registry


def _next(headers):
    values = headers.get_all("Link", []) if hasattr(headers, "get_all") else (
        [headers["Link"]] if "Link" in headers else [])
    if not values:
        return False
    link = ",".join(values)
    require(len(link) <= 16384 and link.isascii()
            and not re.search(r"[\x00-\x08\x0a-\x1f\x7f]", link), "invalid Link")
    relations = []
    for field in link.split(","):
        match = re.fullmatch(r'\s*<[^<>,\s\x00-\x1f\x7f]+>\s*;\s*rel="(next|last|prev|first)"\s*', field)
        require(match is not None, "invalid Link field")
        relations.append(match[1])
    require(len(set(relations)) == len(relations), "duplicate Link relation")
    return "next" in relations


class Reader:
    def __init__(self, cfg, token, opener):
        self.repo = cfg["repository"]
        self.root = f"{API}/repos/{self.repo}"
        self.opener = opener
        self.headers = {"Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                        "User-Agent": "vpng-collab-watch/2"}
        if token is not None:
            require(isinstance(token, str) and 0 < len(token) <= 4096
                    and re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token), "invalid bearer credential")
            self.headers["Authorization"] = "Bearer " + token
        self.bytes = self.rows = 0

    def get(self, room, endpoint, page=None):
        # No endpoint or URL is ever taken from response data.
        require(positive(room) and endpoint in ("", "/comments", "/events"), "invalid endpoint")
        url = f"{self.root}/issues/{room}{endpoint}"
        if page is not None:
            url += f"?per_page={PAGE_SIZE}&page={page}"
        try:
            request = Request(url, headers=self.headers, method="GET")
            with self.opener.open(request, timeout=TIMEOUT) as response:
                require(response.status == 200 and response.geturl() == url,
                        "unexpected response status/URL")
                data = response.read(MAX_PAGE_BYTES + 1)
                require(len(data) <= MAX_PAGE_BYTES, "page byte bound")
                length = response.headers.get("Content-Length")
                if length is not None:
                    require(length.isdecimal() and int(length) == len(data), "content length mismatch")
                self.bytes += len(data)
                require(self.bytes <= MAX_LOCAL_BYTES, "scan byte bound")
                try:
                    payload = strict_json(data.decode("utf-8"))
                except (ValueError, UnicodeError, RecursionError):
                    raise Conflict("invalid response JSON") from None
                has_next = _next(response.headers)
                if page is None:
                    require(isinstance(payload, dict) and not has_next, "invalid Issue resource")
                    return payload
                require(isinstance(payload, list) and len(payload) <= PAGE_SIZE, "invalid page list")
                self.rows += len(payload)
                require(self.rows <= MAX_OBSERVED_COMMENTS, "scan row bound")
                return payload, has_next
        except HTTPError as exc:
            raise Conflict(f"GitHub HTTP {exc.code} (Issue {room}, page {page})") from None
        except Conflict:
            raise
        except (URLError, OSError, HTTPException, ValueError, TypeError, AttributeError) as exc:
            raise Conflict(f"GitHub acquisition failed: {type(exc).__name__}") from None

    def comments(self, room):
        def normalize(raw):
            row = comment(raw)
            require(raw.get("issue_url", "").lower() == f"{self.root}/issues/{room}".lower(),
                    "comment Issue identity mismatch")
            return {"id": row["id"], "user": {"id": row["actor_id"]}, "body": row["body"],
                    "created_at": row["created_at"], "updated_at": row["updated_at"]}
        return self.pages(room, "/comments", normalize)

    def events(self, room):
        def normalize(raw):
            kind = raw.get("event")
            require(isinstance(kind, str) and kind, "invalid event kind")
            if kind not in ("closed", "reopened"):
                # Preserve ID and kind for pagination progress, not semantics.
                return {"id": raw["id"], "kind": kind}
            actor = raw.get("actor")
            require(isinstance(actor, dict) and positive(actor.get("id")), "invalid state event actor")
            return {"id": raw["id"], "kind": kind, "actor_id": actor["id"],
                    "created_at": stamp(raw.get("created_at"))}
        rows = self.pages(room, "/events", normalize)
        return [row for row in rows if row["kind"] in ("closed", "reopened")]

    def pages(self, room, endpoint, normalize):
        seen = {}
        for page in range(1, MAX_PAGES + 1):
            items, has_next = self.get(room, endpoint, page)
            before = len(seen)
            for raw in items:
                require(isinstance(raw, dict) and positive(raw.get("id")), "invalid physical row ID")
                row = normalize(raw)
                rid = raw["id"]
                require(rid not in seen or seen[rid] == row, "conflicting overlapping row")
                seen[rid] = row
            require(not items or len(seen) > before, "pagination made no progress")
            require(items or not has_next, "empty page claims continuation")
            # Full page without Link is not evidence of end of collection.
            if not has_next and len(items) < PAGE_SIZE:
                return [seen[rid] for rid in sorted(seen)]
        raise Conflict("pagination page bound")

    def task(self, cfg, ref):
        room = ref["issue_number"]
        raw = self.get(room, "")
        require(isinstance(raw.get("url"), str) and raw["url"].lower() ==
                f"{self.root}/issues/{room}".lower()
                and isinstance(raw.get("repository_url"), str)
                and raw["repository_url"].lower() == self.root.lower(),
                "Issue repository identity mismatch")
        require(positive(raw.get("number")) and raw["number"] == room
                and positive(raw.get("id")) and raw["id"] == ref["issue_id"]
                and "pull_request" not in raw, "Issue identity mismatch or PR")
        author = raw.get("user")
        closed_by = raw.get("closed_by")
        require(isinstance(author, dict) and positive(author.get("id"))
                and (closed_by is None or isinstance(closed_by, dict) and positive(closed_by.get("id"))),
                "invalid Issue author/closer")
        require(all(k in raw for k in ("body", "created_at", "state", "closed_at", "closed_by")),
                "incomplete Issue resource")
        task = {"repository": self.repo, "number": room, "id": raw["id"],
                "is_pull_request": False, "author_id": author["id"], "body": raw["body"],
                "created_at": raw["created_at"], "state": raw["state"], "closed_at": raw["closed_at"],
                "closed_by": None if closed_by is None else closed_by["id"],
                "comments": self.comments(room), "events": self.events(room)}
        normalize_task(cfg, ref, task)
        return task


def _acquire(cfg, token, opener, candidate=None):
    validate_v2_config(cfg)
    if opener is None:
        opener = build_opener(NoRedirect())
    def scan():
        reader = Reader(cfg, token, opener)
        control = {str(room): reader.comments(room) for room in cfg["journal_rooms"]}
        refs = discover_tasks(cfg, control)
        extra_ref = None
        if candidate is not None:
            # The candidate never enters the physical baseline. If it appeared
            # during either scan, stop for reconciliation before any extra GET.
            existing, _, _, _ = _control(cfg, control)
            extra_ref = prospective_initial_registry(cfg, existing, candidate)
        tasks = {key: reader.task(cfg, ref) for key, ref in refs.items()}
        if extra_ref is not None:
            return control, tasks, reader.task(cfg, extra_ref)
        return control, tasks
    first = scan()
    second = scan()
    require(canonical(first) == canonical(second), "dynamic observation changed during acquisition")
    return second


def acquire_v2(cfg, token=None, opener=None):
    """Return (control, tasks) only after two equal complete dynamic scans.

    Not an atomic GitHub snapshot. No holder/signal, compact, state persistence,
    projection authority, CLI dispatch or write actuator in this unit.
    """
    try:
        return _acquire(cfg, token, opener)
    except (Conflict, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        # Some legacy validators include untrusted JSON keys in their messages.
        # Keep the public acquisition diagnostic independent of remote strings.
        raise Conflict("v2 acquisition failed: invalid, incomplete, unstable or inaccessible observation") from None


def acquire_v2_for_initial_open(cfg, actor, body, *, selected_role, selected_incarnation,
                                token=None, opener=None):
    """Acquire baseline plus one separately held, structurally nominated Issue.

    Both complete scans use the same aggregate bounds and prospective registry
    checks. An actually admitted candidate requires reconciliation, not replay
    as an outgoing candidate. The returned extra is not a canonical task.
    """
    try:
        candidate = initial_open_candidate(cfg, actor, body, selected_role=selected_role,
                                           selected_incarnation=selected_incarnation)
        return _acquire(cfg, token, opener, candidate)
    except (Conflict, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise Conflict("v2 initial OPEN acquisition failed: invalid, incomplete, unstable or already observed") from None


class AggregateV2(NamedTuple):
    """Complete normalized partitions from one twice-observed graph."""
    control: dict
    tasks: dict
    holder_rows: list
    signal_rows: list


def acquire_aggregate_v2(cfg, token=None, opener=None):
    """Two equal whole-graph scans; one Reader and aggregate budget per scan.

    No projection, network writes or authority evaluation. Equality is an
    observation contract, not a claim of an atomic GitHub snapshot.
    """
    try:
        validate_v2_config(cfg)
        if opener is None:
            opener = build_opener(NoRedirect())

        def scan():
            reader = Reader(cfg, token, opener)
            control = {str(room): reader.comments(room) for room in cfg["journal_rooms"]}
            refs = discover_tasks(cfg, control)
            tasks = {key: reader.task(cfg, ref) for key, ref in refs.items()}
            holder = reader.comments(cfg["projectholder"]["room"])
            signals = reader.comments(cfg["signal_room"])
            return AggregateV2(control, tasks, holder, signals)

        first = scan()
        second = scan()
        require(canonical(first) == canonical(second), "aggregate observation changed")
        return second
    except (Conflict, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise Conflict("v2 aggregate acquisition failed: invalid, incomplete, unstable or inaccessible observation") from None



class InitialOpenAggregateV2(NamedTuple):
    """One coherent aggregate graph with a separate prospective task Issue."""
    control: dict
    tasks: dict
    holder_rows: list
    signal_rows: list
    extra_task: dict


def acquire_aggregate_v2_for_initial_open(cfg, actor, body, *, selected_role,
                                          selected_incarnation, token=None, opener=None):
    """Observe the entire aggregate plus prospective Issue twice.

    One Reader and one shared budget per pass. No independently stabilized
    subgraph, projection, state mutation, authority or atomic snapshot claim.
    """
    try:
        validate_v2_config(cfg)
        candidate = initial_open_candidate(cfg, actor, body, selected_role=selected_role,
                                           selected_incarnation=selected_incarnation)
        if opener is None:
            opener = build_opener(NoRedirect())

        def scan():
            reader = Reader(cfg, token, opener)
            control = {str(room): reader.comments(room) for room in cfg["journal_rooms"]}
            refs = discover_tasks(cfg, control)
            existing, _, _, _ = _control(cfg, control)
            extra_ref = prospective_initial_registry(cfg, existing, candidate)
            tasks = {key: reader.task(cfg, ref) for key, ref in refs.items()}
            holder = reader.comments(cfg["projectholder"]["room"])
            signals = reader.comments(cfg["signal_room"])
            extra = reader.task(cfg, extra_ref)
            return InitialOpenAggregateV2(control, tasks, holder, signals, extra)

        first = scan()
        second = scan()
        require(canonical(first) == canonical(second), "initial OPEN aggregate observation changed")
        return second
    except (Conflict, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise Conflict("v2 initial OPEN aggregate acquisition failed: invalid, incomplete, unstable or already observed") from None
