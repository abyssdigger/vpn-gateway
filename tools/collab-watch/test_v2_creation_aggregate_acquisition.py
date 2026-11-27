import copy
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from core import Conflict
from test_split_journal import CFG, fixture, issue, opening, close, ts
from test_v2_acquisition import ROOT, Response, Opener, snapshots
from test_v2_aux import aux, signal
from test_project_tasks import row
from test_v2_create import REQ, SPEC, resource
from v2_compact import compact_v2
from v2_create import (
    CreationAggregateV2, CreationReader, _normalize,
    acquire_aggregate_v2_for_creation, acquire_creation, preflight_create,
)


class CreationAggregateAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.task = fixture()
        self.ping = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        self.rows.append(self.ping)
        self.holder = [row(601, 12, "holder question", 25)]
        self.signals = [signal(701, "p", self.ping, "GUARD", "BUILDER")]
        self.first = snapshots(self.rows, [self.task])
        for n, rows in ((35, self.holder), (37, self.signals)):
            self.first[f"/issues/{n}/comments"] = [
                dict(r, issue_url=f"{ROOT}/issues/{n}") for r in rows]
        baseline = compact_v2(CFG, {"34": self.rows}, {"42": self.task})
        self.proof, payload = preflight_create(CFG, baseline, 13, REQ, **SPEC)
        self.candidate = resource(payload)
        self.other = resource({"title": "unrelated", "body": None}, 44, 4004)
        self.first["/issues"] = [self.other, self.candidate]

    def acquire(self, second=None, override=None):
        return acquire_aggregate_v2_for_creation(
            CFG, opener=Opener(self.first, second, override))

    def test_whole_graph_order_and_exact_type(self):
        opener = Opener(self.first)
        with patch("v2_create.CreationReader", wraps=CreationReader) as reader:
            got = acquire_aggregate_v2_for_creation(CFG, token="fake", opener=opener)
            self.assertEqual(reader.call_count, 2)
        self.assertIs(type(got), CreationAggregateV2)
        self.assertEqual(got, CreationAggregateV2(
            {"34": self.rows}, {"42": self.task}, self.holder, self.signals,
            [_normalize(CFG["repository"], x) for x in (self.candidate, self.other)]))
        paths = [urlsplit(u).path.removeprefix("/repos/owner/repo") for u, _, _ in opener.calls]
        one = ["/issues/34/comments", "/issues/42", "/issues/42/comments",
               "/issues/42/events", "/issues/35/comments", "/issues/37/comments", "/issues"]
        self.assertEqual(paths, one * 2)
        self.assertTrue(all(m == "GET" and a == "Bearer fake" for _, m, a in opener.calls))
        self.assertTrue(all("state=all&sort=created&direction=asc" in u
                            for u, _, _ in opener.calls if urlsplit(u).path.endswith("/issues")))

    def test_drift_any_partition(self):
        for path in ("/issues/34/comments", "/issues/42/comments",
                     "/issues/35/comments", "/issues/37/comments"):
            second = copy.deepcopy(self.first)
            second[path][0]["body"] += " drift"
            with self.subTest(path=path), self.assertRaises(Conflict):
                self.acquire(second)
        for path, field, value in (
            ("/issues/42", "body", "different task"),
            ("/issues/42/events", None, [{"id": 999, "event": "closed",
                    "actor": {"id": 10}, "created_at": ts(20)}]),
            ("/issues", None, [self.other]),
        ):
            second = copy.deepcopy(self.first)
            if field is None:
                second[path] = value
            else:
                second[path][field] = value
            with self.subTest(path=path), self.assertRaises(Conflict):
                self.acquire(second)
        second = copy.deepcopy(self.first)
        second["/issues"][0]["title"] = "different unrelated title"
        with self.assertRaises(Conflict):
            self.acquire(second)

    def test_registry_discovery_is_from_each_pass(self):
        other = issue(45, 4005)
        expanded = snapshots(self.rows + [opening(other, task="O3", mid="o3", cid=202)],
                             [self.task, other])
        expanded.update({k: self.first[k] for k in
                         ("/issues/35/comments", "/issues/37/comments", "/issues")})
        opener = Opener(self.first, expanded)
        with self.assertRaises(Conflict):
            acquire_aggregate_v2_for_creation(CFG, opener=opener)
        self.assertTrue(any(u.endswith("/issues/45") for u, _, _ in opener.calls))

    def test_normalized_order_is_stable(self):
        second = copy.deepcopy(self.first)
        for path in ("/issues/34/comments", "/issues/42/comments", "/issues"):
            second[path].reverse()
        self.assertEqual(self.acquire(second), self.acquire())

    def test_shared_row_and_byte_budgets(self):
        row_total = sum(len(v) for v in self.first.values() if isinstance(v, list))
        byte_total = sum(len(json.dumps(v).encode()) for v in self.first.values())
        for key, total in (("MAX_OBSERVED_COMMENTS", row_total), ("MAX_LOCAL_BYTES", byte_total)):
            with self.subTest(key=key), patch("v2_acquisition."+key, total), patch("v2_create."+key, total):
                self.acquire()
            opener = Opener(self.first)
            with patch("v2_acquisition."+key, total-1), patch("v2_create."+key, total-1), self.assertRaises(Conflict):
                acquire_aggregate_v2_for_creation(CFG, opener=opener)
            self.assertEqual(opener.scan, 0)
            self.assertEqual(urlsplit(opener.calls[-1][0]).path, "/repos/owner/repo/issues")

    def test_marker_presence_including_pr_is_observation_not_admission(self):
        for pr in (False, True):
            self.first["/issues"] = [dict(self.candidate, **({"pull_request": {}} if pr else {}))]
            got = self.acquire()
            self.assertEqual(got.inventory[0]["pr"], pr)
            self.assertEqual(got.inventory[0]["body"], self.candidate["body"])
        # Legacy expect_absent remains rejecting physical presence.
        from test_v2_create import Inventory
        with self.assertRaises(Conflict):
            acquire_creation(CFG, self.proof["effect"], opener=Inventory([self.candidate]),
                             expect_absent=True)

    def test_inventory_identity_marker_and_bounds(self):
        for rows in (
            [dict(self.candidate, body="<!-- vpng-collab-task-create/1 broken")],
            [dict(self.candidate, title="changed")],
            [dict(self.candidate, repository_url="https://foreign.invalid")],
            [dict(self.candidate, number=True)],
            [self.candidate, dict(self.candidate, title="conflicting")],
            [self.candidate, dict(self.other, number=43, url=ROOT+"/issues/43")],
            [self.candidate, dict(self.other, id=self.candidate["id"])],
        ):
            with self.subTest(rows=rows), self.assertRaises(Conflict):
                self.first["/issues"] = rows
                self.acquire()
        self.first["/issues"] = [self.candidate, self.other]
        with patch("v2_create.PAGE", 1):
            opener = Opener(self.first)
            acquire_aggregate_v2_for_creation(CFG, opener=opener)
            self.assertEqual(sum("state=all" in u and "page=3" in u for u, _, _ in opener.calls), 2)
            with patch("v2_create.MAX_PAGES", 1), self.assertRaises(Conflict):
                self.acquire()
            def stuck(url, path, page):
                if path == "/issues":
                    return Response(url, [self.candidate])
            with self.assertRaises(Conflict):
                self.acquire(override=stuck)

    def test_inventory_transport_and_invalid_config_fail_closed(self):
        for options in (dict(status=206), dict(redirect="https://evil.invalid/"),
                        dict(length=1), dict(raw=b'{"x":1,"x":2}'),
                        dict(links=("broken",))):
            def override(url, path, page):
                if path == "/issues":
                    return Response(url, [], **options)
            with self.subTest(options=options), self.assertRaises(Conflict):
                self.acquire(override=override)
        opener = Opener(self.first)
        with self.assertRaises(Conflict):
            acquire_aggregate_v2_for_creation(dict(CFG, journal_rooms=[]), opener=opener)
        self.assertEqual(opener.calls, [])


if __name__ == "__main__":
    unittest.main()
