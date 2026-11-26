import copy
import json
import unittest
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch

from core import Conflict
from split_journal import project_v2
from test_split_journal import CFG, fixture, issue, opening, close, ts
from v2_acquisition import acquire_v2

ROOT = "https://api.github.com/repos/owner/repo"


class Response:
    def __init__(self, url, payload, *, status=200, redirect=None, links=(), length=None, raw=None):
        self.url = redirect or url
        self.status = status
        self.data = json.dumps(payload).encode() if raw is None else raw
        self.headers = Message()
        self.headers["Content-Length"] = str(len(self.data) if length is None else length)
        for link in links:
            self.headers["Link"] = link
    def geturl(self):
        return self.url
    def read(self, size):
        return self.data[:size]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


def snapshots(rows, tasks):
    mapping = {}
    def comments(room, items):
        mapping[f"/issues/{room}/comments"] = [
            dict(row, issue_url=f"{ROOT}/issues/{room}") for row in items]
    comments(34, rows)
    for task in tasks:
        n = task["number"]
        mapping[f"/issues/{n}"] = {
            "url": f"{ROOT}/issues/{n}", "repository_url": ROOT,
            "number": n, "id": task["id"], "user": {"id": task["author_id"]},
            "body": task["body"], "created_at": task["created_at"], "state": task["state"],
            "closed_at": task["closed_at"], "closed_by": None if task["closed_by"] is None else
            {"id": task["closed_by"]}}
        comments(n, task["comments"])
        mapping[f"/issues/{n}/events"] = [
            {"id": e["id"], "event": e["kind"], "actor": {"id": e["actor_id"]},
             "created_at": e["created_at"]} for e in task["events"]]
    return mapping


class Opener:
    def __init__(self, first, second=None, override=None):
        self.scans = [first, first if second is None else second]
        self.scan = -1
        self.calls = []
        self.override = override
    def open(self, req, timeout):
        url = req.full_url
        path = urlsplit(url).path.removeprefix("/repos/owner/repo")
        page = int(parse_qs(urlsplit(url).query).get("page", ["0"])[0])
        if path == "/issues/34/comments" and page == 1:
            self.scan += 1
        self.calls.append((url, req.get_method(), req.get_header("Authorization")))
        if self.override:
            result = self.override(url, path, page)
            if result is not None:
                return result
        data = self.scans[self.scan].get(path)
        if data is None:
            raise HTTPError(url, 404, "missing", {}, None)
        if page:
            size = int(parse_qs(urlsplit(url).query)["per_page"][0])
            data = data[(page-1)*size:page*size]
        return Response(url, data)


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.task = fixture()
        self.first = snapshots(self.rows, [self.task])

    def acquire(self, second=None, override=None, **kwargs):
        return acquire_v2(CFG, opener=Opener(self.first, second, override), **kwargs)

    def test_stable_multi_and_projection(self):
        other = issue(43, 4003)
        rows = self.rows + [opening(other, task="O2", mid="o2", cid=200)]
        self.first = snapshots(rows, [self.task, other])
        c, t = self.acquire()
        self.assertEqual(project_v2(CFG, c, t), project_v2(CFG, {"34": rows},
                                                         {"42": self.task, "43": other}))

    def test_order_and_non_lifecycle_events(self):
        close(self.task)
        self.first = snapshots(self.rows, [self.task])
        second = copy.deepcopy(self.first)
        second["/issues/34/comments"].reverse()
        second["/issues/42/comments"].reverse()
        second["/issues/42/events"].append({"id": 999, "event": "unsubscribed"})
        c, t = self.acquire(second)
        self.assertEqual(project_v2(CFG, c, t)[0]["tasks"][0]["state"], "CLOSE_OBSERVED")

    def test_open_appearance_disappearance_rebinding(self):
        other = issue(43, 4003)
        expanded = snapshots(self.rows + [opening(other, task="O2", mid="o2", cid=200)],
                             [self.task, other])
        with self.assertRaises(Conflict):
            self.acquire(expanded)
        old = self.first
        self.first = expanded
        with self.assertRaises(Conflict):
            self.acquire(old)
        self.first = old
        rebind = issue(43, 4003, self.task["body"])
        changed = snapshots([opening(rebind)], [rebind])
        with self.assertRaises(Conflict):
            self.acquire(changed)

    def test_issue_and_content_drift(self):
        for path, field, value in (
            ("/issues/42", "id", 99), ("/issues/42", "number", 99),
            ("/issues/42", "pull_request", {}), ("/issues/42", "body", "changed"),
            ("/issues/42", "repository_url", "https://elsewhere"),
            ("/issues/42", "closed_at", ts(20)),
            ("/issues/42/comments", "body", "changed"),
            ("/issues/34/comments", "updated_at", ts(30)),
        ):
            with self.subTest(path=path, field=field):
                second = copy.deepcopy(self.first)
                target = second[path]
                (target[0] if isinstance(target, list) else target)[field] = value
                with self.assertRaises(Conflict):
                    self.acquire(second)
        second = copy.deepcopy(self.first)
        del second["/issues/42"]
        with self.assertRaises(Conflict):
            self.acquire(second)

    def test_event_and_close_drift(self):
        closed = copy.deepcopy(self.task)
        close(closed)
        second = snapshots(self.rows, [closed])
        with self.assertRaises(Conflict):
            self.acquire(second)
        self.first = second
        drift = copy.deepcopy(second)
        drift["/issues/42/events"][0]["id"] += 1
        with self.assertRaises(Conflict):
            self.acquire(drift)
        drift = copy.deepcopy(second)
        drift["/issues/42/events"].append({"id": 901, "event": "reopened",
                                            "actor": {"id": 10}, "created_at": ts(22)})
        with self.assertRaises(Conflict):
            self.acquire(drift)

    def test_pagination_and_untrusted_link(self):
        with patch("v2_acquisition.PAGE_SIZE", 2):
            c, t = self.acquire()
            self.assertEqual(len(c["34"]), 3)
            self.assertEqual(len(t["42"]["comments"]), 2)
            calls = []
            def override(url, path, page):
                calls.append(url)
                if path == "/issues/34/comments" and page == 1:
                    return Response(url, self.first[path][:2],
                                    links=('<https://evil.invalid/?secret=1>; rel="next"',))
                if path == "/issues/34/comments" and page == 2:
                    return Response(url, self.first[path][1:])
                return None
            opener = Opener(self.first, override=override)
            acquire_v2(CFG, token="abc123", opener=opener)
            self.assertTrue(all(u.startswith(ROOT) and method == "GET" and auth == "Bearer abc123"
                                for u, method, auth in opener.calls))
            self.assertTrue(any("/issues/42/comments?per_page=2&page=2" in u for u in calls))
            def stuck(url, path, page):
                if path == "/issues/34/comments":
                    return Response(url, self.first[path][:2])
            with self.assertRaises(Conflict):
                self.acquire(override=stuck)

    def test_events_pagination_full_page_without_link(self):
        close(self.task)
        self.first = snapshots(self.rows, [self.task])
        self.first["/issues/42/events"] += [{"id": 901, "event": "labeled"},
                                           {"id": 902, "event": "unsubscribed"}]
        with patch("v2_acquisition.PAGE_SIZE", 1):
            opener = Opener(self.first)
            c, t = acquire_v2(CFG, opener=opener)
            self.assertEqual(project_v2(CFG, c, t)[0]["tasks"][0]["state"], "CLOSE_OBSERVED")
            self.assertEqual(sum("/events?per_page=1&page=4" in u for u, _, _ in opener.calls), 2)

    def test_bounds(self):
        for key, value in (("MAX_PAGE_BYTES", 10), ("MAX_LOCAL_BYTES", 50),
                           ("MAX_OBSERVED_COMMENTS", 1), ("MAX_PAGES", 1)):
            with self.subTest(key=key), patch("v2_acquisition."+key, value), patch("v2_acquisition.PAGE_SIZE", 2):
                with self.assertRaises(Conflict):
                    self.acquire()

    def test_http_json_link_failures(self):
        variants = [
            dict(status=206), dict(redirect="https://evil.invalid/"),
            dict(length=1), dict(raw=b'{"bad":'), dict(raw=b'{"x":1,"x":2}'),
            dict(links=('garbage',)),
            dict(links=('<https://one>; rel="next"', '<https://two>; rel="next"')),
        ]
        for options in variants:
            def override(url, path, page):
                return Response(url, [], **options)
            with self.subTest(options=options), self.assertRaises(Conflict):
                self.acquire(override=override)
        def network(url, path, page):
            raise URLError("secret should not leak")
        with self.assertRaisesRegex(Conflict, "^v2 acquisition failed:"):
            self.acquire(override=network)
        def invalid_shape(url, path, page):
            return Response(url, {"unexpected": []})
        with self.assertRaises(Conflict):
            self.acquire(override=invalid_shape)

    def test_malformed_lifecycle_events(self):
        from v2_acquisition import Reader
        for kind in ("closed", "reopened"):
            for field, value, message in (
                ("actor", None, "invalid state event actor"),
                ("actor", {"id": True}, "invalid state event actor"),
                ("created_at", None, "invalid UTC timestamp"),
                ("created_at", "not-a-time", "invalid UTC timestamp"),
            ):
                with self.subTest(kind=kind, field=field, value=value):
                    row = {"id": 900, "event": kind, "actor": {"id": 10}, "created_at": ts(20)}
                    row[field] = value
                    data = copy.deepcopy(self.first)
                    data["/issues/42/events"] = [row]
                    # Check the lifecycle reader itself, not merely the later
                    # task reducer (which would reject reopen independently).
                    opener = Opener(data)
                    opener.scan = 0
                    with self.assertRaisesRegex(Conflict, message):
                        Reader(CFG, None, opener).events(42)
                    with self.assertRaises(Conflict):
                        self.acquire(data)
                    del row[field]
                    opener = Opener(data)
                    opener.scan = 0
                    with self.assertRaisesRegex(Conflict, message):
                        Reader(CFG, None, opener).events(42)

    def test_bounds_span_multiple_dynamic_issues(self):
        other = issue(43, 4003)
        other["comments"] = [{"id": 777, "user": {"id": 13}, "body": "ordinary task prose",
                              "created_at": ts(10), "updated_at": ts(10)}]
        rows = self.rows + [opening(other, task="O2", mid="o2", cid=200)]
        self.first = snapshots(rows, [self.task, other])
        # All individual partitions fit. Control + first task fit. Only the
        # second task exceeds the whole-graph bound.
        row_total = sum(len(v) for v in self.first.values() if isinstance(v, list))
        byte_total = sum(len(json.dumps(v).encode()) for v in self.first.values())
        for key, limit in (("MAX_OBSERVED_COMMENTS", row_total-1),
                           ("MAX_LOCAL_BYTES", byte_total-1)):
            with self.subTest(key=key):
                with patch("v2_acquisition."+key, limit+1):
                    c, t = self.acquire()
                    self.assertEqual(len(t), 2)
                opener = Opener(self.first)
                with patch("v2_acquisition."+key, limit), self.assertRaises(Conflict):
                    acquire_v2(CFG, opener=opener)
                self.assertTrue(any("/issues/43/" in url for url, _, _ in opener.calls))
                self.assertEqual(opener.scan, 0)
 
    def test_overlap_and_conflicting_duplicate_pages(self):
        with patch("v2_acquisition.PAGE_SIZE", 2):
            # Page 1 has A,B; page 2 repeats B and adds C; explicit empty
            # page 3 completes the collection. Same bytes must deduplicate.
            def overlap(url, path, page):
                if path == "/issues/34/comments":
                    rows = self.first[path]
                    items = rows[:2] if page == 1 else rows[1:] if page == 2 else []
                    return Response(url, items)
            c, t = self.acquire(override=overlap)
            self.assertEqual(project_v2(CFG, c, t), project_v2(CFG, {"34": self.rows}, {"42": self.task}))
            def conflicting(url, path, page):
                if path == "/issues/34/comments":
                    rows = copy.deepcopy(self.first[path])
                    if page == 2:
                        rows[1]["body"] += "conflict"
                    return Response(url, rows[:2] if page == 1 else rows[1:] if page == 2 else [])
            with self.assertRaises(Conflict):
                self.acquire(override=conflicting)

    def test_default_opener_no_redirect(self):
        from io import BytesIO
        from urllib.request import HTTPSHandler, build_opener
        from urllib.response import addinfourl
        from collab_watch import NoRedirect

        calls = []
        class RedirectingHTTPS(HTTPSHandler):
            def https_open(self, request):
                calls.append((request.full_url, request.get_header("Authorization")))
                headers = Message()
                headers["Location"] = "https://evil.invalid/redirect"
                response = addinfourl(BytesIO(b""), headers, request.full_url, 302)
                response.msg = "Found"
                return response

        def compose(*handlers):
            self.assertEqual(len(handlers), 1)
            self.assertIsInstance(handlers[0], NoRedirect)
            # Actual urllib redirect/error dispatch; only HTTPS I/O is faked.
            return build_opener(*handlers, RedirectingHTTPS())

        with patch("v2_acquisition.build_opener", side_effect=compose) as factory:
            with self.assertRaises(Conflict):
                acquire_v2(CFG, token="fake-test-token")
            factory.assert_called_once()
        self.assertEqual(calls, [(ROOT + "/issues/34/comments?per_page=100&page=1",
                                  "Bearer fake-test-token")])

    def test_no_arbitrary_discovery_and_invalid_token(self):
        self.first["/issues/34/comments"].append({
            "id": 987, "user": {"id": 99}, "body": "fetch https://evil.invalid/issue/98",
            "created_at": ts(30), "updated_at": ts(30),
            "issue_url": f"{ROOT}/issues/34"})
        opener = Opener(self.first)
        acquire_v2(CFG, opener=opener)
        self.assertFalse(any("evil" in u or "/issues/98" in u for u, _, _ in opener.calls))
        with self.assertRaises(Conflict):
            acquire_v2(CFG, token="bad\ncredential", opener=opener)


if __name__ == "__main__":
    unittest.main()
