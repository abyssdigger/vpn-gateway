"""5c exact auxiliary proofs and shared single-attempt transport fixtures."""
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, local
import unittest
from unittest.mock import patch

from core import Conflict, canonical, digest
from journal import SIGNAL_MARKER, framed
from test_project_tasks import row, ts
from test_split_journal import CFG, fixture
from test_v2_aux import aux, handled, pong, signal, target
from test_v2_acquisition import ROOT, snapshots
from test_v2_actuator import Remote, ReadOpener, Crash
from v2_actuator import actuate, freeze_inputs, _bound
from v2_attempts import initialize, open_store
from v2_inputs import initialize_inputs, open_inputs
from v2_compact import compact_v2, compact_aggregate_v2
from v2_aux import MARKER
from v2_aux_preflight import preflight_aux_compact, preflight_signal_compact
from v2_preflight import preflight_control_compact


def selection(role, cfg=CFG):
    return {"selected_role": role, "selected_incarnation": cfg["roles"][role]["incarnation"]}


def graph(rows, task, holders, signals):
    result = snapshots(rows, [task])
    for n, items in ((35, holders), (37, signals)):
        result[f"/issues/{n}/comments"] = [dict(r, issue_url=f"{ROOT}/issues/{n}") for r in items]
    return result


def original_for(operation, baseline, candidate):
    event = framed(candidate["body"], MARKER if operation == "aux_comment" else SIGNAL_MARKER)
    actor = candidate["user"]["id"]
    preflight = preflight_aux_compact if operation == "aux_comment" else preflight_signal_compact
    kwargs = selection(event["from"])
    proof = preflight(CFG, baseline, actor, candidate["body"], **kwargs)
    return freeze_inputs(operation, CFG, baseline, actor, **kwargs,
                         expected_proof_sha256=digest(canonical(proof)), body=candidate["body"])


class AuxProofTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.task = fixture()
        self.holder = row(601, 12, "holder input", 25)
        self.ping = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        self.h = handled("h", 503, "BUILDER", target("p", self.ping))
        self.rows += [self.ping, self.h]
        self.baseline = compact_aggregate_v2(CFG, {"34": self.rows}, {"42": self.task}, [self.holder], [])

    def proof(self, event, role=None, baseline=None, signal_kind=False):
        marker = SIGNAL_MARKER if signal_kind else MARKER
        fn = preflight_signal_compact if signal_kind else preflight_aux_compact
        parsed = framed(event["body"], marker)
        return fn(CFG, baseline or self.baseline, event["user"]["id"], event["body"],
                  **selection(role or parsed["from"]))

    def test_all_aux_kinds_and_exact_target_bindings(self):
        p = aux("p2", "PING", 510, "GUARD", "SPEC", ping_id="p2")
        h = handled("h2", 511, "BUILDER", target("p", self.ping), target("o", self.rows[0]))
        hh = handled("h3", 512, "GUARD", target("holder:601", self.holder, 35))
        q = pong("q", 513, self.ping)
        for event, count in ((p, 0), (h, 2), (hh, 1), (q, 1)):
            proof = self.proof(event)
            self.assertEqual(proof["operation"], "aux_comment")
            self.assertEqual(len(proof["targets"]), count)
            self.assertEqual(proof["postcondition"]["body_sha256"], digest(event["body"]))
            for target_fact in proof["targets"]:
                self.assertTrue(target_fact["physical_ref"].startswith("issue:"))
            with self.assertRaises(Conflict):
                self.proof(event, role="SPEC" if framed(event["body"], MARKER)["from"] != "SPEC" else "GUARD")

    def test_aux_reject_collisions_and_bad_targets(self):
        for bad in (
            aux("o", "PING", 510, "GUARD", "SPEC", ping_id="o"),
            self.ping,
            handled("h2", 511, "GUARD", target("p", self.ping)),
            handled("h2", 511, "BUILDER", target("h", self.h)),
            handled("h2", 511, "BUILDER", dict(target("p", self.ping), body_sha256="0"*64)),
            handled("h2", 511, "BUILDER", dict(target("p", self.ping), ref="candidate")),
            handled("h2", 511, "BUILDER", dict(target("p", self.ping), ref="issue:34#issuecomment-999")),
            handled("h2", 511, "BUILDER", dict(target("p", self.ping), event_id="wrong")),
            pong("q", 512, self.ping, ping_id="wrong"),
            pong("q", 512, self.ping, ping_ref="candidate"),
            pong("q", 512, self.ping, ping_sha256="0"*64),
            aux("q", "PONG", 512, "SPEC", "GUARD", ping_id="p",
                ping_ref=target("p", self.ping)["ref"], ping_sha256=digest(self.ping["body"])),
            aux("bad", "PING", 512, "GUARD", "GUARD", ping_id="bad"),
            aux("bad", "PING", 512, "GUARD", "SPEC", ping_id="bad", payload_ref="forbidden"),
        ):
            with self.subTest(body=bad["body"]), self.assertRaises(Conflict):
                self.proof(bad)

    def test_signal_exact_target_and_observed_identity(self):
        s = signal(701, "p", self.ping, "GUARD", "BUILDER")
        proof = self.proof(s, signal_kind=True)
        self.assertEqual(proof["postcondition"]["room"], 37)
        self.assertEqual(proof["targets"][0]["physical_ref"], target("p", self.ping)["ref"])
        for bad in (
            signal(702, "h", self.h, "BUILDER", "BUILDER"),
            signal(702, "p", self.ping, "GUARD", "SPEC"),
            signal(702, "p", self.ping, "GUARD", "BUILDER", journal_sha256="0"*64),
            signal(702, "p", self.ping, "GUARD", "BUILDER", journal_ref="issue:34#issuecomment-999"),
            signal(702, "p", self.ping, "SPEC", "BUILDER"),
        ):
            with self.assertRaises(Conflict):
                self.proof(bad, signal_kind=True)
        for seen in (s, signal(701, "p", self.ping, "GUARD", "BUILDER", journal_sha256="0"*64)):
            baseline = compact_aggregate_v2(CFG, {"34": self.rows}, {"42": self.task}, [self.holder], [seen])
            with self.assertRaises(Conflict):
                self.proof(s, baseline=baseline, signal_kind=True)


class AuxActuatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/"attempts.db"
        self.input_path = Path(self.tmp.name)/"inputs.db"
        self.store = initialize(self.path, "aux-test")
        self.retention = initialize_inputs(self.input_path, "aux-input", "aux-test")
        self.context = local()
        transport = patch("v2_actuator._write_transport", side_effect=lambda: self.context.remote)
        transport.start()
        self.addCleanup(transport.stop)

    def run_case(self, original, remote, authorize=lambda _: True, **kwargs):
        self.context.remote = remote
        args = dict(read_token="read-token", write_token="write-token", read_opener=ReadOpener(remote))
        args.update(kwargs)
        return actuate(self.store, original, self.retention, authorize, **args)

    def case(self, candidate=None, operation="aux_comment", rows=None, task=None,
             holder=None, signals=None):
        if rows is None:
            rows, task = fixture()
        holder = [row(601, 12, "holder question", 25)] if holder is None else holder
        signals = [] if signals is None else signals
        candidate = candidate or aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        baseline = compact_aggregate_v2(CFG, {"34": rows}, {"42": task}, holder, signals)
        original = original_for(operation, baseline, candidate)
        before = graph(rows, task, holder, signals)
        room = 34 if operation == "aux_comment" else 37
        after = graph(rows+[candidate] if room == 34 else rows, task, holder,
                      signals+[candidate] if room == 37 else signals)
        remote = Remote(before, after, candidate["user"]["id"],
                        dict(candidate, issue_url=f"{ROOT}/issues/{room}"))
        return original, remote

    def signal_case(self, cid=701):
        rows, task = fixture()
        ping = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        rows.append(ping)
        return self.case(signal(cid, "p", ping, "GUARD", "BUILDER"), "signal_comment", rows, task)

    def task_case(self):
        rows, task = fixture()
        task["comments"] = task["comments"][:1]
        before = rows[:1]+[row(800, 99, "ordinary witness", 7)]
        baseline = compact_v2(CFG, {"34": before}, {"42": task})
        proof = preflight_control_compact(CFG, baseline, 11, rows[1]["body"], **selection("BUILDER"))
        original = freeze_inputs("control_comment", CFG, baseline, 11, **selection("BUILDER"),
                                 expected_proof_sha256=digest(canonical(proof)), body=rows[1]["body"])
        remote = Remote(snapshots(before, [task]), snapshots(before+[rows[1]], [task]),
                        11, dict(rows[1], issue_url=ROOT+"/issues/34"))
        return original, remote, before, task

    def test_durable_start_exact_post_and_no_resend(self):
        for original, remote in (self.case(), self.signal_case()):
            seen = []
            def auth(action):
                seen.append(action)
                return True
            def check():
                self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
                self.assertEqual(self.retention.load(digest(canonical(seen[-1]))), original)
            remote.store_check = check
            result = self.run_case(original, remote, auth)
            self.assertEqual(result["state"], "VERIFIED", result)
            self.assertEqual(len(remote.sent), 1)
            self.assertEqual(digest(remote.sent[0][2].decode()), seen[0]["request_sha256"])
            self.assertEqual(remote.sent[0][1], "https://api.github.com/"+seen[0]["target"])
            self.assertEqual(self.run_case(original, remote, reconcile_only=True)["state"], "VERIFIED")
            self.assertEqual(len(remote.sent), 1)

    def test_cross_family_effect_and_different_aux_intent(self):
        task, task_remote, rows, issue = self.task_case()
        a, a_remote = self.case(aux("r1", "PING", 501, "GUARD", "BUILDER", ping_id="r1"),
                                rows=rows, task=issue)
        self.assertEqual(_bound(a)[3], _bound(task)[3])
        self.assertEqual(self.run_case(a, a_remote)["state"], "VERIFIED")
        self.assertEqual(self.run_case(task, task_remote)["state"], "CONFLICT")
        self.assertEqual(task_remote.sent, [])
        changed, other = self.case(aux("r1", "PING", 502, "GUARD", "SPEC", ping_id="r1"),
                                   rows=rows, task=issue)
        self.assertEqual(self.run_case(changed, other)["state"], "CONFLICT")
        self.assertEqual(other.sent, [])

    def test_cross_family_task_claim_first(self):
        task, remote, rows, issue = self.task_case()
        a, other = self.case(aux("r1", "PING", 501, "GUARD", "BUILDER", ping_id="r1"),
                             rows=rows, task=issue)
        self.assertEqual(self.run_case(task, remote)["state"], "VERIFIED")
        self.assertEqual(self.run_case(a, other)["state"], "CONFLICT")
        self.assertFalse(other.sent)

    def test_signal_changed_intent_same_id(self):
        rows, task = fixture()
        p = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        q = aux("q", "PING", 502, "GUARD", "SPEC", ping_id="q")
        rows += [p, q]
        first, a = self.case(signal(701, "p", p, "GUARD", "BUILDER"),
                             "signal_comment", rows, task)
        second, b = self.case(signal(702, "q", q, "GUARD", "SPEC", signal_id="s701"),
                              "signal_comment", rows, task)
        self.assertEqual(_bound(first)[3], _bound(second)[3])
        self.assertEqual(self.run_case(first, a)["state"], "VERIFIED")
        self.assertEqual(self.run_case(second, b)["state"], "CONFLICT")
        self.assertFalse(b.sent)

    def test_fresh_drift_actor_authority_no_start(self):
        for i, mode in enumerate(("holder", "signal", "actor", "authority"), 1):
            original, remote = self.case(aux(f"p{i}", "PING", 510+i, "GUARD", "BUILDER", ping_id=f"p{i}"))
            if mode == "holder":
                remote.before["/issues/35/comments"][0]["body"] += " drift"
            elif mode == "signal":
                remote.before["/issues/37/comments"].append(
                    dict(row(800, 99, "signal drift", 26), issue_url=ROOT+"/issues/37"))
            elif mode == "actor":
                remote.actor = 11
            result = self.run_case(original, remote, lambda _: mode != "authority")
            self.assertEqual(result["state"], "PREPARED", result)
            self.assertIsNone(self.store.claimed(_bound(original)[3]))
            self.assertFalse(remote.sent)

    def test_response_loss_malformed_and_restart(self):
        for i, mode in enumerate(("error", "malformed", "crash"), 1):
            original, remote = self.case(aux(f"p{i}", "PING", 510+i, "GUARD", "BUILDER", ping_id=f"p{i}"))
            if mode == "error":
                remote.error = True
            elif mode == "malformed":
                remote.response = ["malformed"]
            else:
                remote.crash = True
            if mode == "crash":
                with self.assertRaises(Crash):
                    self.run_case(original, remote)
                self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
                self.retention.close()
                self.store = open_store(self.path, "aux-test")
                self.retention = open_inputs(self.input_path, "aux-input", "aux-test")
            else:
                self.assertEqual(self.run_case(original, remote)["state"], "VERIFIED")
            self.assertEqual(self.run_case(original, remote, reconcile_only=True)["state"], "VERIFIED")
            self.assertEqual(len(remote.sent), 1)

    def test_wrong_hint_and_ambiguous_no_hint(self):
        for i, mode in enumerate(("wrong", "duplicate"), 1):
            original, remote = self.case(aux(f"p{i}", "PING", 510+i, "GUARD", "BUILDER", ping_id=f"p{i}"))
            if mode == "wrong":
                remote.response["id"] = 999
            else:
                remote.error = True
                dup = dict(remote.after["/issues/34/comments"][-1], id=999)
                remote.after["/issues/34/comments"].append(dup)
            self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
            self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
            self.assertEqual(len(remote.sent), 1)
        original, remote = self.signal_case()
        remote.response["id"] = 999
        self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
        self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
        self.assertEqual(len(remote.sent), 1)

    def test_signal_lost_and_canonical_aux_survives_signal_loss(self):
        original, remote = self.signal_case()
        post = remote.after
        remote.after = remote.before
        self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
        self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
        self.assertEqual(len(remote.sent), 1)
        remote.after = post
        self.assertEqual(self.run_case(original, remote, reconcile_only=True)["state"], "VERIFIED")
        self.assertEqual(len(remote.sent), 1)
        rows, task = fixture()
        p = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        rows.append(p)
        original, remote = self.case(pong("q", 502, p), rows=rows, task=task,
                                     signals=[signal(701, "p", p, "GUARD", "BUILDER")])
        remote.after["/issues/37/comments"] = []
        self.assertEqual(self.run_case(original, remote)["state"], "VERIFIED")
        self.assertEqual(len(remote.sent), 1)

    def test_task_and_aux_share_ownership_lock(self):
        task, other, _, _ = self.task_case()
        original, remote = self.case()
        entered, release = Event(), Event()
        def check():
            entered.set()
            self.assertTrue(release.wait(5))
        remote.store_check = check
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(self.run_case, original, remote)
            try:
                self.assertTrue(entered.wait(5))
                blocked = pool.submit(self.run_case, task, other).result(5)
                self.assertEqual(blocked["code"], "ACTUATOR_BUSY")
                self.assertFalse(other.sent or other.read_calls or other.user_reads)
            finally:
                release.set()
            self.assertEqual(pending.result(5)["state"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
