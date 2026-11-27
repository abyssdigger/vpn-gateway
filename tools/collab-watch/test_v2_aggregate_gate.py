"""Exact one-wire compact derivation and retained aggregate candidate admission."""
import copy
from dataclasses import replace
import unittest

from core import Conflict, canonical, digest, strict_json
from test_split_journal import CFG, fixture, row
from test_v2_aux import aux, signal
from v2_aux import project_aux
from v2_compact import (compact_v2, compact_aggregate_v2, derive_task_compact,
                        project_compact_aggregate_v2, CompactAggregateV2)
from v2_preflight import preflight_control_compact
from v2_aux_preflight import preflight_aux_compact
from v2_aggregate_gate import gate_aggregate_candidate, PROTOCOL, NO_AUTHORITY

BUILDER = dict(selected_role="BUILDER", selected_incarnation="b")
GUARD = dict(selected_role="GUARD", selected_incarnation="g")


class AggregateGateTests(unittest.TestCase):
    def setUp(self):
        rows, task = fixture()
        task["comments"] = task["comments"][:1]
        self.result = rows[1]
        self.tasks = {"42": task}
        self.p = aux("p", "PING", 301, "GUARD", "BUILDER", ping_id="p")
        self.opaque = row(800, 99, "ordinary control witness", 27)
        self.control = {"34": [rows[0], self.p, self.opaque]}
        self.holder = row(801, 12, "holder input", 28)
        self.sig = signal(901, "p", self.p, "GUARD", "BUILDER")
        self.prior = project_aux(CFG, self.control, self.tasks, [], [])[1]
        self.aggregate = self.pack()
        self.task = compact_v2(CFG, self.control, self.tasks, self.prior["task"])
        self.q = aux("q", "PING", 302, "GUARD", "SPEC", ping_id="q")

    def pack(self, control=None, tasks=None, holder=None, signals=None):
        return compact_aggregate_v2(CFG, self.control if control is None else control,
                                    self.tasks if tasks is None else tasks,
                                    [] if holder is None else holder,
                                    [] if signals is None else signals)

    def task_proof(self, compact=None, previous=None, body=None):
        return preflight_control_compact(CFG, self.task if compact is None else compact, 11,
                    self.result["body"] if body is None else body,
                    self.prior["task"] if previous is None else previous, **BUILDER)

    def aux_proof(self, compact=None, previous=None, body=None):
        return preflight_aux_compact(CFG, self.aggregate if compact is None else compact, 10,
                    self.q["body"] if body is None else body,
                    self.prior if previous is None else previous, **GUARD)

    def task_gate(self, **overrides):
        args = dict(cfg=CFG, aggregate=self.aggregate, operation="control_comment", actor=11,
                    body=self.result["body"], frozen_previous=self.prior["task"],
                    composed_previous=self.prior, expected_proof_sha256=digest(canonical(self.task_proof())),
                    **BUILDER)
        args.update(overrides)
        frozen = copy.deepcopy(args)
        output = gate_aggregate_candidate(**args)
        self.assertEqual(args, frozen)
        return output

    def aux_gate(self, **overrides):
        args = dict(cfg=CFG, aggregate=self.aggregate, operation="aux_comment", actor=10,
                    body=self.q["body"], frozen_previous=self.prior, composed_previous=self.prior,
                    expected_proof_sha256=digest(canonical(self.aux_proof())), **GUARD)
        args.update(overrides)
        frozen = copy.deepcopy(args)
        output = gate_aggregate_candidate(**args)
        self.assertEqual(args, frozen)
        return output

    def test_exact_derivation_and_packed_rows(self):
        derived = derive_task_compact(CFG, self.aggregate)
        self.assertEqual(derived, self.task)
        a = strict_json(self.aggregate.text)
        t = strict_json(derived.text)
        self.assertEqual(t["config_sha256"], a["config_sha256"])
        self.assertEqual(t["tasks"], a["tasks"])
        self.assertEqual(t["control"]["34"][0], a["control"]["34"][0])
        self.assertEqual(t["control"]["34"][1],
                         ["opaque", *a["control"]["34"][1][1:5], digest(self.p["body"])])
        self.assertEqual(t["control"]["34"][2], a["control"]["34"][2])
        self.assertNotIn("holder", t)
        self.assertNotIn("signals", t)

    def test_aggregate_only_partitions_and_order(self):
        extra = self.pack(holder=[self.holder], signals=[self.sig])
        self.assertNotEqual(extra.sha256, self.aggregate.sha256)
        self.assertNotEqual(extra.inventory_sha256, self.aggregate.inventory_sha256)
        self.assertEqual(derive_task_compact(CFG, extra), self.task)
        reverse = self.pack(control={"34": list(reversed(self.control["34"]))})
        self.assertEqual(reverse, self.aggregate)
        self.assertEqual(derive_task_compact(CFG, reverse), self.task)
        # Task proof remains exact, while the projected composed frontier advances.
        out = self.task_gate(aggregate=extra)
        self.assertEqual(out["prior_composed_state_sha256"], digest(canonical(self.prior)))
        self.assertNotEqual(out["projected_composed_state_sha256"], out["prior_composed_state_sha256"])
        self.assertEqual(out["projected_composed_state_sha256"],
                         digest(canonical(project_compact_aggregate_v2(CFG, extra, self.prior)[1])))
        with self.assertRaises(Conflict):
            self.aux_gate(aggregate=extra)

    def test_closed_success_and_exact_proofs(self):
        expected_keys = {"protocol", "operation", "aggregate_sha256", "aggregate_inventory_sha256",
                         "prior_composed_state_sha256", "projected_composed_state_sha256",
                         "task_compact_sha256", "task_inventory_sha256", "proof_sha256",
                         "event_id", "selected_role", "selected_incarnation", "authority"}
        for result, operation, mid, proof in (
                (self.task_gate(), "task_control", "r1", self.task_proof()),
                (self.aux_gate(), "aux_control", "q", self.aux_proof())):
            self.assertEqual(set(result), expected_keys)
            self.assertEqual(result["protocol"], PROTOCOL)
            self.assertEqual(result["authority"], NO_AUTHORITY)
            self.assertEqual(result["operation"], operation)
            self.assertEqual(result["event_id"], mid)
            self.assertEqual(result["proof_sha256"], digest(canonical(proof)))
            self.assertEqual(result["aggregate_sha256"], self.aggregate.sha256)
            self.assertEqual(result["aggregate_inventory_sha256"], self.aggregate.inventory_sha256)
            self.assertEqual(result["prior_composed_state_sha256"], digest(canonical(self.prior)))
            self.assertEqual(result["projected_composed_state_sha256"], digest(canonical(self.prior)))
            self.assertEqual(result["task_compact_sha256"], self.task.sha256 if operation == "task_control" else None)
            self.assertEqual(result["task_inventory_sha256"], self.task.inventory_sha256 if operation == "task_control" else None)
            self.assertNotIn(self.result["body"], canonical(result))
        out = self.task_gate()
        out["event_id"] = "mutated"
        self.assertEqual(self.task_gate()["event_id"], "r1")

    def test_task_collision_with_aux_id_not_seen_by_task_proof(self):
        colliding = aux("r1", "PING", 303, "GUARD", "SPEC", ping_id="r1")
        control = {"34": self.control["34"]+[colliding]}
        aggregate = self.pack(control=control)
        task = compact_v2(CFG, control, self.tasks, self.prior["task"])
        proof = self.task_proof(compact=task)
        self.assertEqual(proof["candidate"]["event_id"], "r1")
        with self.assertRaises(Conflict):
            self.task_gate(aggregate=aggregate, expected_proof_sha256=digest(canonical(proof)))

    def test_aux_collision_with_task_id_and_already_observed(self):
        body = aux("r1", "PING", 303, "GUARD", "SPEC", ping_id="r1")["body"]
        proof = self.aux_proof(body=body)
        advanced = self.pack(control={"34": self.control["34"]+[self.result]})
        with self.assertRaises(Conflict):
            self.aux_gate(aggregate=advanced, body=body, expected_proof_sha256=digest(canonical(proof)))
        with self.assertRaises(Conflict):
            self.aux_gate(aggregate=self.pack(control={"34": self.control["34"]+[self.q]}))

    def test_retained_exact_frontier_not_fresh_or_projected(self):
        changed = self.pack(holder=[self.holder])
        new = project_compact_aggregate_v2(CFG, changed, self.prior)[1]
        with self.assertRaises(Conflict):
            self.aux_gate(aggregate=changed, composed_previous=new, frozen_previous=self.prior)
        different = copy.deepcopy(self.prior["task"])
        different["ledger"] = {}
        with self.assertRaises(Conflict):
            self.task_gate(frozen_previous=different)
        for f in (self.task_gate, self.aux_gate):
            for previous in (None, {}, {"task": self.prior["task"]},
                             dict(self.prior, unexpected=True)):
                with self.subTest(previous=previous), self.assertRaises(Conflict):
                    f(composed_previous=previous, frozen_previous=previous)
        bad = copy.deepcopy(self.prior)
        bad["aux"]["ledger"]["bad"] = None
        with self.assertRaises(Conflict):
            self.task_gate(composed_previous=bad)

    def test_bad_hash_selection_and_unsupported_operations(self):
        for f in (self.task_gate, self.aux_gate):
            for kwargs in ({"expected_proof_sha256": "0"*64}, {"expected_proof_sha256": None},
                           {"selected_role": "SPEC"}, {"selected_incarnation": "other"},
                           {"actor": 99}, {"body": "ordinary prose"}):
                with self.subTest(kwargs=kwargs), self.assertRaises(Conflict):
                    f(**kwargs)
        for op in ("material_comment", "signal_comment", "initial_open", "issue_close", "issue_create", None):
            with self.assertRaises(Conflict):
                self.task_gate(operation=op)

    def test_tamper_and_opaque_inventory_binding(self):
        bad = [replace(self.aggregate, sha256="0"*64),
               replace(self.aggregate, inventory_sha256="0"*64),
               replace(self.aggregate, text=self.aggregate.text+" "),
               self.task, None]
        value = strict_json(self.aggregate.text)
        value["control"]["34"][1][5] += "tamper"
        wire = canonical(value)
        bad.append(CompactAggregateV2(wire, digest(wire), self.aggregate.inventory_sha256))
        for a in bad:
            with self.subTest(a=type(a)), self.assertRaises(Conflict):
                derive_task_compact(CFG, a)
            with self.assertRaises(Conflict):
                self.task_gate(aggregate=a)
        changed = copy.deepcopy(self.control)
        changed["34"][-1]["body"] = "changed opaque witness"
        advanced = self.pack(control=changed)
        self.assertNotEqual(derive_task_compact(CFG, advanced), self.task)
        with self.assertRaises(Conflict):
            self.task_gate(aggregate=advanced)
        with self.assertRaises(Conflict):
            self.aux_gate(aggregate=advanced)
        # Recompacting only semantic rows loses the physical witness and cannot
        # reproduce a frozen proof that included it.
        from v2_compact import aggregate_semantic_view
        c, t, _, _, _ = aggregate_semantic_view(CFG, self.aggregate)
        incomplete = compact_v2(CFG, c, t, self.prior["task"])
        self.assertNotEqual(incomplete, self.task)
        self.assertNotEqual(digest(canonical(self.task_proof(compact=incomplete))),
                            digest(canonical(self.task_proof())))
