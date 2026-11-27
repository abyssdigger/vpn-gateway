"""8e-B: exact coherent graph/inventory and retained creation proof."""
import copy
import unittest
from unittest.mock import patch

from core import Conflict, canonical, digest
from test_split_journal import CFG, fixture, row, issue, opening
from test_v2_aux import aux, signal
from test_v2_create import REQ, SPEC, resource
from v2_aux import project_aux
from v2_compact import compact_aggregate_v2, derive_task_compact, project_compact_aggregate_v2
from v2_create import CreationAggregateV2, _normalize, preflight_create, marker
from v2_aggregate_gate import gate_creation_aggregate, PROTOCOL, NO_AUTHORITY


class CreationAggregateGateTests(unittest.TestCase):
    def setUp(self):
        rows, task = fixture()
        self.ping = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        self.control = {"34": rows + [self.ping, row(800, 99, "opaque", 27)]}
        self.tasks = {"42": task}
        self.prior = project_aux(CFG, self.control, self.tasks, [], [])[1]
        self.other = _normalize(CFG["repository"], resource({"title": "unrelated", "body": None}, 44, 4004))
        self.coherent = CreationAggregateV2(self.control, self.tasks, [], [], [self.other])
        self.aggregate = self.pack(self.coherent)
        self.proof, self.payload = self.preflight(self.coherent)
        self.args = dict(cfg=CFG, coherent=self.coherent, actor=13, request=REQ,
                         frozen_task_previous=self.prior["task"], composed_previous=self.prior,
                         expected_proof_sha256=digest(canonical(self.proof)), **SPEC)

    def pack(self, coherent):
        return compact_aggregate_v2(CFG, coherent.control, coherent.tasks,
                                    coherent.holder_rows, coherent.signal_rows, self.prior)

    def preflight(self, coherent, request=REQ):
        return preflight_create(CFG, derive_task_compact(CFG, self.pack(coherent)), 13,
                                request, self.prior["task"], **SPEC)

    def gate(self, **overrides):
        args = dict(self.args, **overrides)
        before = copy.deepcopy(args)
        try:
            return gate_creation_aggregate(**args)
        finally:
            self.assertEqual(args, before)

    def candidate(self, number=43, iid=4003, pr=False, payload=None):
        raw = resource(self.payload if payload is None else payload, number, iid)
        if pr:
            raw["pull_request"] = {}
        return _normalize(CFG["repository"], raw)

    def test_exact_bindings_one_compaction_and_no_io(self):
        task = derive_task_compact(CFG, self.aggregate)
        expected = dict(protocol=PROTOCOL, operation="issue_create",
                        aggregate_sha256=self.aggregate.sha256,
                        aggregate_inventory_sha256=self.aggregate.inventory_sha256,
                        task_compact_sha256=task.sha256, task_inventory_sha256=task.inventory_sha256,
                        creation_inventory_sha256=digest(canonical(self.coherent.inventory)),
                        prior_composed_state_sha256=digest(canonical(self.prior)),
                        projected_composed_state_sha256=digest(canonical(
                            project_compact_aggregate_v2(CFG, self.aggregate, self.prior)[1])),
                        proof_sha256=digest(canonical(self.proof)),
                        effect_sha256=digest(canonical(self.proof["effect"])), **SPEC,
                        authority=NO_AUTHORITY)
        with patch("v2_aggregate_gate.compact_aggregate_v2", wraps=compact_aggregate_v2) as pack, \
             patch("v2_aggregate_gate.preflight_create", wraps=preflight_create) as preflight, \
             patch("v2_create.CreationReader") as reader, \
             patch("v2_aggregate_gate.marker", wraps=marker) as check:
            got = self.gate()
            pack.assert_called_once()
            preflight.assert_called_once()
            reader.assert_not_called()
            check.assert_called_once_with(CFG["repository"], self.other)
        self.assertEqual(got, expected)
        for raw in (REQ["title"], REQ["spec"], self.payload["body"]):
            self.assertNotIn(raw, canonical(got))

    def test_exact_type_retained_and_proof(self):
        for obj in (None, tuple(self.coherent), self.coherent._asdict(), self.aggregate):
            with self.subTest(obj=type(obj)), self.assertRaises(Conflict):
                self.gate(coherent=obj)
        for prior in (None, {}, {"task": self.prior["task"]}, dict(self.prior, extra=True)):
            with self.subTest(prior=prior), self.assertRaises(Conflict):
                self.gate(composed_previous=prior)
        bad = copy.deepcopy(self.prior)
        bad["aux"]["ledger"]["bad"] = None
        with self.assertRaises(Conflict):
            self.gate(composed_previous=bad)
        for prev in (None, {}, self.prior):
            with self.assertRaises(Conflict):
                self.gate(frozen_task_previous=prev)
        for sha in (None, "0"*64):
            with self.assertRaises(Conflict):
                self.gate(expected_proof_sha256=sha)

    def test_create_request_and_selection(self):
        for kwargs in ({"actor": 10}, {"selected_role": "GUARD", "selected_incarnation": "g"},
                       {"selected_incarnation": "wrong"}, {"request": None},
                       {"request": dict(REQ, revision=2)}, {"request": dict(REQ, task="O1")},
                       {"request": dict(REQ, title="changed")}, {"request": dict(REQ, spec="changed")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(Conflict):
                self.gate(**kwargs)

    def test_matching_marker_pr_and_duplicate_effect(self):
        for inventory in ([self.candidate()], [self.candidate(pr=True)],
                          [self.candidate(), self.candidate(45, 4005)],
                          [self.candidate(), self.candidate(45, 4005, pr=True)]):
            with self.subTest(inventory=inventory), self.assertRaises(Conflict):
                self.gate(coherent=self.coherent._replace(inventory=inventory))

    def test_unrelated_marker_and_nonmarker_are_bound(self):
        _, payload = self.preflight(self.coherent, dict(REQ, task="O9"))
        unrelated = self.candidate(payload=payload)
        before = self.gate()
        inventory = [unrelated, self.other]
        got = self.gate(coherent=self.coherent._replace(inventory=inventory))
        self.assertEqual(got["creation_inventory_sha256"], digest(canonical(inventory)))
        self.assertEqual(set(k for k in got if got[k] != before[k]), {"creation_inventory_sha256"})
        changed = [dict(self.other, title="unrelated drift")]
        self.assertNotEqual(self.gate(coherent=self.coherent._replace(inventory=changed))[
            "creation_inventory_sha256"], before["creation_inventory_sha256"])
        # 8e-A normalizes by ascending ID: reject caller-reordered objects.
        with self.assertRaises(Conflict):
            self.gate(coherent=self.coherent._replace(inventory=list(reversed(inventory))))

    def test_forged_malformed_inventory_is_closed(self):
        for row_ in (dict(self.other, extra=True), dict(self.other, number=True),
                     dict(self.other, id=0), dict(self.other, actor_id="13"),
                     dict(self.other, pr=0), dict(self.other, state="unknown"),
                     dict(self.other, title=None), dict(self.other, body=[]),
                     dict(self.other, created_at="not a stamp"),
                     dict(self.other, body="<!-- vpng-collab-task-create/1 broken"),
                     dict(self.candidate(), title="modified")):
            with self.subTest(row=row_), self.assertRaises(Conflict):
                self.gate(coherent=self.coherent._replace(inventory=[row_]))
        for inventory in (None, {}, tuple(self.coherent.inventory),
                          [self.other, self.other], [self.other, dict(self.other, id=5000)],
                          [self.other, dict(self.other, number=99)]):
            with self.subTest(inventory=inventory), self.assertRaises(Conflict):
                self.gate(coherent=self.coherent._replace(inventory=inventory))

    def test_holder_signal_preserve_proof_but_bind_graph(self):
        before = self.gate()
        for kwargs in ({"holder_rows": [row(601, 12, "holder input", 25)]},
                       {"signal_rows": [signal(701, "p", self.ping, "GUARD", "BUILDER")]}):
            got = self.gate(coherent=self.coherent._replace(**kwargs))
            for k in ("aggregate_sha256", "aggregate_inventory_sha256"):
                self.assertNotEqual(got[k], before[k])
            for k in ("proof_sha256", "task_compact_sha256", "task_inventory_sha256",
                      "creation_inventory_sha256", "prior_composed_state_sha256"):
                self.assertEqual(got[k], before[k])

    def test_task_control_aux_and_opaque_drift_bound(self):
        opaque = copy.deepcopy(self.control)
        opaque["34"][-1]["body"] += " changed"
        added_aux = {"34": self.control["34"] + [
            aux("q", "PING", 502, "GUARD", "SPEC", ping_id="q")]}
        tasks = copy.deepcopy(self.tasks)
        tasks["42"]["comments"].append(row(901, 99, "ordinary task prose", 30))
        before = self.gate()
        for coherent in (self.coherent._replace(control=opaque),
                         self.coherent._replace(control=added_aux),
                         self.coherent._replace(tasks=tasks)):
            with self.assertRaises(Conflict):
                self.gate(coherent=coherent)
            proof, _ = self.preflight(coherent)
            got = self.gate(coherent=coherent, expected_proof_sha256=digest(canonical(proof)))
            for k in ("aggregate_inventory_sha256", "task_inventory_sha256", "proof_sha256"):
                self.assertNotEqual(got[k], before[k])
        new = issue(43, 4003)
        registered = self.coherent._replace(
            control={"34": self.control["34"] + [opening(new, task="O2", mid="new", cid=999)]},
            tasks=dict(self.tasks, **{"43": new}))
        with self.assertRaises(Conflict):
            self.gate(coherent=registered)


if __name__ == "__main__":
    unittest.main()
