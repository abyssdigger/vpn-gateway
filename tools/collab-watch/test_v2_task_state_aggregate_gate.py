"""8d-A: exact retained aggregate gate for material and Issue close."""
import copy
from dataclasses import replace
import unittest
from unittest.mock import patch

from core import Conflict, canonical, digest
from test_split_journal import CFG, SHA, OTHER, fixture, issue, opening, material, row, ref, close
from test_v2_aux import aux, signal
from v2_aux import project_aux
from v2_compact import (compact_aggregate_v2, derive_task_compact,
                        project_compact_aggregate_v2)
from v2_material import preflight_material
from v2_preflight import preflight_close_compact
from v2_aggregate_gate import gate_task_state_aggregate, PROTOCOL, NO_AUTHORITY

OPS = ("material_comment", "issue_close")


class TaskStateAggregateGateTests(unittest.TestCase):
    def case(self, operation):
        if operation == "material_comment":
            task = issue()
            rows = [opening(task)]
            args = dict(task_key="O1", body=material(1001, "RESULT", 5)["body"],
                        actor=11, selected_role="BUILDER", selected_incarnation="b")
        else:
            rows, task = fixture()
            args = dict(request=dict(task="O1", issue_number=42, issue_id=4002,
                                     revision=1, attempt=1, commit_sha=SHA,
                                     accept_ref={"room": 34, **ref(rows[2])}),
                        actor=10, selected_role="GUARD", selected_incarnation="g")
        ping = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        control = {"34": rows + [ping, row(800, 99, "opaque witness", 27)]}
        tasks = {"42": task}
        prior = project_aux(CFG, control, tasks, [], [])[1]
        aggregate = compact_aggregate_v2(CFG, control, tasks, [], [], prior)
        args.update(cfg=CFG, aggregate=aggregate, operation=operation,
                    frozen_task_previous=prior["task"], composed_previous=prior)
        args["expected_proof_sha256"] = digest(canonical(self.proof(args)))
        return args, control, tasks, ping

    def proof(self, args):
        task = derive_task_compact(CFG, args["aggregate"])
        selection = dict(selected_role=args["selected_role"],
                         selected_incarnation=args["selected_incarnation"])
        if args["operation"] == "material_comment":
            return preflight_material(CFG, task, args["task_key"], args["actor"],
                                      args["body"], args["frozen_task_previous"], **selection)
        return preflight_close_compact(CFG, task, args["actor"], args["request"],
                                       args["frozen_task_previous"], **selection)

    def gate(self, args, **overrides):
        data = dict(args, **overrides)
        before = copy.deepcopy(data)
        try:
            return gate_task_state_aggregate(**data)
        finally:
            self.assertEqual(data, before)

    def pack(self, args, control, tasks, holder=None, signals=None):
        return compact_aggregate_v2(CFG, control, tasks, holder or [], signals or [],
                                    args["composed_previous"])

    def test_closed_bindings_and_exact_preflight(self):
        for op in OPS:
            args, _, _, _ = self.case(op)
            agg = args["aggregate"]
            task = derive_task_compact(CFG, agg)
            prior = args["composed_previous"]
            expected = dict(protocol=PROTOCOL, operation=op,
                            aggregate_sha256=agg.sha256,
                            aggregate_inventory_sha256=agg.inventory_sha256,
                            task_compact_sha256=task.sha256,
                            task_inventory_sha256=task.inventory_sha256,
                            prior_composed_state_sha256=digest(canonical(prior)),
                            projected_composed_state_sha256=digest(canonical(
                                project_compact_aggregate_v2(CFG, agg, prior)[1])),
                            proof_sha256=args["expected_proof_sha256"],
                            selected_role=args["selected_role"],
                            selected_incarnation=args["selected_incarnation"], authority=NO_AUTHORITY)
            fn = preflight_material if op == "material_comment" else preflight_close_compact
            name = fn.__name__
            with patch("v2_aggregate_gate."+name, wraps=fn) as preflight, \
                 patch("v2_aggregate_gate.derive_task_compact", wraps=derive_task_compact) as derive, \
                 patch("v2_acquisition.Reader") as reader:
                result = self.gate(args)
                preflight.assert_called_once()
                derive.assert_called_once_with(CFG, agg)
                reader.assert_not_called()
            self.assertEqual(result, expected)
            self.assertNotIn("event_id", result)
            self.assertNotIn("Initial specification", canonical(result))
            material = args.get("body") or canonical(args["request"])
            self.assertNotIn(material, canonical(result))
            result["operation"] = "changed"
            self.assertEqual(self.gate(args), expected)

    def test_exact_type_retained_shape_and_frozen_frontier(self):
        for op in OPS:
            args, _, _, _ = self.case(op)
            agg = args["aggregate"]
            prior = args["composed_previous"]
            for bad in (None, dict(text=agg.text, sha256=agg.sha256),
                        derive_task_compact(CFG, agg),
                        replace(agg, inventory_sha256="0"*64)):
                with self.subTest(op=op, bad=type(bad)), self.assertRaises(Conflict):
                    self.gate(args, aggregate=bad)
            for bad in (None, {}, {"task": prior["task"]}, dict(prior, extra=True)):
                with self.subTest(op=op), self.assertRaises(Conflict):
                    self.gate(args, composed_previous=bad)
            bad = copy.deepcopy(prior)
            bad["aux"]["ledger"]["bad"] = None
            with self.assertRaises(Conflict):
                self.gate(args, composed_previous=bad)
            frozen = copy.deepcopy(prior["task"])
            frozen["ledger"] = {}
            for bad in (None, prior, frozen):
                with self.assertRaises(Conflict):
                    self.gate(args, frozen_task_previous=bad)

    def test_closed_operation_shape_proof_and_selection(self):
        for op in OPS:
            args, _, _, _ = self.case(op)
            variants = [{"operation": "initial_open"}, {"expected_proof_sha256": "0"*64},
                        {"expected_proof_sha256": None}, {"actor": 99},
                        {"selected_role": "SPEC"}, {"selected_incarnation": "wrong"}]
            variants += ([{"task_key": None}, {"body": None}, {"request": {}}]
                         if op == "material_comment" else
                         [{"request": None}, {"task_key": "O1"}, {"body": "unexpected"}])
            for change in variants:
                with self.subTest(op=op, change=change), self.assertRaises(Conflict):
                    self.gate(args, **change)

    def test_material_task_header_and_already_observed(self):
        args, control, tasks, _ = self.case("material_comment")
        for change in ({"task_key": "O2"}, {"body": "unframed"},
                       {"body": material(1001, "RESULT", 5, revision=2)["body"]},
                       {"body": material(1001, "RESULT", 5, attempt=2)["body"]},
                       {"body": material(1001, "REVIEW", 5)["body"]}):
            with self.subTest(change=change), self.assertRaises(Conflict):
                self.gate(args, **change)
        observed = copy.deepcopy(tasks)
        observed["42"]["comments"].append(material(1001, "RESULT", 5))
        agg = self.pack(args, control, observed)
        with self.assertRaises(Conflict):
            self.gate(args, aggregate=agg)
        rows, task = fixture()
        advanced = self.pack(args, {"34": control["34"]+rows[1:]}, {"42": task})
        with self.assertRaises(Conflict):
            self.gate(args, aggregate=advanced)

    def test_close_exact_accept_and_open_issue(self):
        args, control, tasks, _ = self.case("issue_close")
        for changes in ({"task": "O2"}, {"revision": 2}, {"attempt": 2},
                        {"commit_sha": OTHER}, {"accept_ref": {"room": 34, "comment_id": 999,
                                                               "body_sha256": "0"*64}}):
            with self.subTest(changes=changes), self.assertRaises(Conflict):
                self.gate(args, request=dict(args["request"], **changes))
        closed = copy.deepcopy(tasks)
        close(closed["42"])
        with self.assertRaises(Conflict):
            self.gate(args, aggregate=self.pack(args, control, closed))
        rows, task = fixture(rework=True)
        # A proof for an accepted current task cannot silently bind to a
        # different lifecycle; use a fresh valid alternate composed frontier.
        other_control = {"34": rows}
        other_tasks = {"42": task}
        prior = project_aux(CFG, other_control, other_tasks, [], [])[1]
        other = compact_aggregate_v2(CFG, other_control, other_tasks, [], [], prior)
        with self.assertRaises(Conflict):
            self.gate(args, aggregate=other, frozen_task_previous=prior["task"],
                      composed_previous=prior)

    def test_holder_signal_preserve_task_proof_and_bind_aggregate(self):
        for op in OPS:
            args, control, tasks, ping = self.case(op)
            baseline = self.gate(args)
            for holder, signals in (([row(601, 12, "holder input", 25)], []),
                                    ([], [signal(701, "p", ping, "GUARD", "BUILDER")])):
                aggregate = self.pack(args, control, tasks, holder, signals)
                got = self.gate(args, aggregate=aggregate)
                for key in ("aggregate_sha256", "aggregate_inventory_sha256"):
                    self.assertNotEqual(got[key], baseline[key])
                for key in ("task_compact_sha256", "task_inventory_sha256", "proof_sha256",
                            "prior_composed_state_sha256"):
                    self.assertEqual(got[key], baseline[key])
                self.assertEqual(got["projected_composed_state_sha256"],
                                 digest(canonical(project_compact_aggregate_v2(
                                     CFG, aggregate, args["composed_previous"])[1])))

    def test_opaque_aux_task_inventory_drift_is_bound(self):
        for op in OPS:
            args, control, tasks, _ = self.case(op)
            baseline = self.gate(args)
            opaque = copy.deepcopy(control)
            opaque["34"][-1]["body"] += " changed"
            added_aux = {"34": control["34"]+[aux("q", "PING", 502, "GUARD", "SPEC", ping_id="q")]}
            extra_task = copy.deepcopy(tasks)
            extra_task["42"]["comments"].append(row(901, 99, "ordinary task prose", 30))
            for c, t in ((opaque, tasks), (added_aux, tasks), (control, extra_task)):
                aggregate = self.pack(args, c, t)
                with self.assertRaises(Conflict):
                    self.gate(args, aggregate=aggregate)
                proof = self.proof(dict(args, aggregate=aggregate))
                got = self.gate(args, aggregate=aggregate,
                                expected_proof_sha256=digest(canonical(proof)))
                for key in ("aggregate_inventory_sha256", "task_inventory_sha256", "proof_sha256"):
                    self.assertNotEqual(got[key], baseline[key])


if __name__ == "__main__":
    unittest.main()
