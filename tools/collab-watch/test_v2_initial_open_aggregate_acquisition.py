"""8c-A: one coherent two-pass acquisition for a prospective initial OPEN."""
import copy
import json
import unittest
from urllib.parse import urlsplit
from unittest.mock import patch

from core import Conflict
from test_split_journal import CFG, issue, opening, ts, close
from test_project_tasks import row
import test_v2_acquisition as acquisition_fixtures
from test_v2_acquisition import Opener, ROOT, snapshots
from v2_acquisition import (InitialOpenAggregateV2, Reader,
                            acquire_aggregate_v2_for_initial_open)


class InitialOpenAggregateTests(unittest.TestCase):
    def setUp(self):
        acquisition_fixtures.AggregateAcquisitionTests.setUp(self)
        self.extra = issue(43, 4003)
        self.extra["comments"] = [row(777, 13, "candidate discussion", 10)]
        self.out = opening(self.extra, task="O2", mid="o2", cid=200)
        self.first.update({k: v for k, v in snapshots([], [self.extra]).items()
                           if k.startswith("/issues/43")})
        self.expected = InitialOpenAggregateV2({"34": self.rows}, {"42": self.task},
                                               self.holder, self.signals, self.extra)

    def acquire(self, opener=None, out=None, actor=13, role="SPEC", inc="s"):
        return acquire_aggregate_v2_for_initial_open(
            CFG, actor, (self.out if out is None else out)["body"],
            selected_role=role, selected_incarnation=inc, token="fake",
            opener=Opener(self.first) if opener is None else opener)

    def paths(self, opener):
        return [urlsplit(u).path.removeprefix("/repos/owner/repo")
                for u, _, _ in opener.calls]

    def test_exact_two_passes_single_reader_and_separate_extra(self):
        opener = Opener(self.first)
        with patch("v2_acquisition.Reader", wraps=Reader) as reader, \
             patch("v2_acquisition.acquire_v2") as task_only, \
             patch("v2_acquisition.acquire_v2_for_initial_open") as old_open, \
             patch("v2_acquisition.acquire_aggregate_v2") as aggregate:
            got = self.acquire(opener)
            self.assertEqual(reader.call_count, 2)
            task_only.assert_not_called()
            old_open.assert_not_called()
            aggregate.assert_not_called()
        self.assertIs(type(got), InitialOpenAggregateV2)
        self.assertEqual(got, self.expected)
        self.assertEqual(set(got.tasks), {"42"})
        self.assertEqual(got.extra_task["number"], 43)
        one = ["/issues/34/comments", "/issues/42", "/issues/42/comments",
               "/issues/42/events", "/issues/35/comments", "/issues/37/comments",
               "/issues/43", "/issues/43/comments", "/issues/43/events"]
        self.assertEqual(self.paths(opener), one * 2)
        self.assertTrue(all(m == "GET" and a == "Bearer fake"
                            for _, m, a in opener.calls))

    def test_whole_pass_budget_includes_candidate_comments_events_and_bytes(self):
        # Add a real normalized lifecycle event to count candidate event rows.
        close(self.extra)
        self.first.update({k: v for k, v in snapshots([], [self.extra]).items()
                           if k.startswith("/issues/43")})
        row_total = sum(len(v) for v in self.first.values() if isinstance(v, list))
        byte_total = sum(len(json.dumps(v).encode()) for v in self.first.values())
        for key, total in (("MAX_OBSERVED_COMMENTS", row_total),
                           ("MAX_LOCAL_BYTES", byte_total)):
            with self.subTest(key=key):
                with patch("v2_acquisition." + key, total):
                    self.acquire()
                for reduction in (1, 2) if key == "MAX_OBSERVED_COMMENTS" else (1,):
                    opener = Opener(self.first)
                    with patch("v2_acquisition." + key, total-reduction), self.assertRaises(Conflict):
                        self.acquire(opener)
                    self.assertEqual(opener.scan, 0)
                    self.assertTrue(self.paths(opener)[-1].startswith("/issues/43/"))

    def test_drift_in_every_partition(self):
        for path in ("/issues/34/comments", "/issues/42/comments",
                     "/issues/35/comments", "/issues/37/comments",
                     "/issues/43/comments", "/issues/43"):
            second = copy.deepcopy(self.first)
            target = second[path]
            (target[0] if isinstance(target, list) else target)["body"] += " drift"
            with self.subTest(path=path), self.assertRaises(Conflict):
                self.acquire(Opener(self.first, second))
        second = copy.deepcopy(self.first)
        second["/issues/43/events"] = [{"id": 999, "event": "closed",
                                        "actor": {"id": 10}, "created_at": ts(20)}]
        with self.assertRaises(Conflict):
            self.acquire(Opener(self.first, second))

    def test_already_admitted_and_alias_fail_before_candidate_reads(self):
        admitted = copy.deepcopy(self.first)
        admitted["/issues/34/comments"].append(dict(self.out, issue_url=ROOT+"/issues/34"))
        for opener, expected_reads in ((Opener(admitted), 0), (Opener(self.first, admitted), 1)):
            with self.assertRaises(Conflict):
                self.acquire(opener)
            self.assertEqual(self.paths(opener).count("/issues/43"), expected_reads)
        for out in (opening(self.extra, task="O1", mid="rebind", cid=200),
                    opening(issue(42, 4003), task="O2", mid="rebind", cid=200),
                    opening(issue(43, 4002), task="O2", mid="rebind", cid=200),
                    opening(self.extra, task="O2", mid="o", cid=200)):
            opener = Opener(self.first)
            with self.assertRaises(Conflict):
                self.acquire(opener, out)
            self.assertEqual(self.paths(opener), ["/issues/34/comments"])

    def test_structural_gate_precedes_network(self):
        for actor, role, inc in ((10, "GUARD", "g"), (13, "SPEC", "wrong")):
            opener = Opener(self.first)
            with self.assertRaises(Conflict):
                self.acquire(opener, actor=actor, role=role, inc=inc)
            self.assertEqual(opener.calls, [])
        opener = Opener(self.first)
        with self.assertRaises(Conflict):
            self.acquire(opener, dict(self.out, body="unframed"))
        self.assertEqual(opener.calls, [])

    def test_candidate_resource_and_transport_fail_closed(self):
        for field, value in (("repository_url", "https://elsewhere"), ("id", 999),
                             ("number", 99), ("pull_request", {}), ("body", None)):
            data = copy.deepcopy(self.first)
            data["/issues/43"][field] = value
            with self.subTest(field=field), self.assertRaises(Conflict):
                self.acquire(Opener(data))
        for path in ("/issues/43", "/issues/43/comments", "/issues/43/events"):
            data = copy.deepcopy(self.first)
            del data[path]
            with self.subTest(path=path), self.assertRaises(Conflict):
                self.acquire(Opener(data))

    def test_normalized_order_and_ignored_events_are_stable(self):
        self.extra["comments"].append(row(778, 13, "another comment", 11))
        self.first.update({k: v for k, v in snapshots([], [self.extra]).items()
                           if k.startswith("/issues/43")})
        second = copy.deepcopy(self.first)
        for path in ("/issues/34/comments", "/issues/42/comments", "/issues/43/comments"):
            second[path].reverse()
        second["/issues/43/events"].append({"id": 999, "event": "unsubscribed"})
        self.assertEqual(self.acquire(Opener(self.first, second)).extra_task, self.extra)


if __name__ == "__main__":
    unittest.main()
