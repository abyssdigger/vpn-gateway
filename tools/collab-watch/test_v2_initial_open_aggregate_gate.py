"""8c-B retained-only initial OPEN admission over the coherent 8c-A graph."""
import copy
import unittest
from unittest.mock import patch

from core import Conflict, canonical, digest
from test_split_journal import CFG, fixture, issue, opening
from test_project_tasks import row
from test_v2_aux import aux, signal
from v2_acquisition import InitialOpenAggregateV2
from v2_aux import project_aux
from v2_compact import (compact_aggregate_v2, derive_task_compact,
                        project_compact_aggregate_v2)
from v2_preflight import preflight_initial_open_compact
from v2_aggregate_gate import gate_initial_open_aggregate, PROTOCOL, NO_AUTHORITY

SPEC = dict(selected_role="SPEC", selected_incarnation="s")


class InitialOpenAggregateGateTests(unittest.TestCase):
    def setUp(self):
        rows, task = fixture()
        self.ping = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        self.opaque = row(800, 99, "ordinary control witness", 27)
        self.control = {"34": rows + [self.ping, self.opaque]}
        self.tasks = {"42": task}
        self.extra = issue(43, 4003, "private candidate specification")
        self.extra["comments"] = [row(777, 13, "private candidate discussion", 10)]
        self.out = opening(self.extra, task="O2", mid="o2", cid=200)
        self.holder = row(601, 12, "holder input", 25)
        self.signal = signal(701, "p", self.ping, "GUARD", "BUILDER")
        self.coherent = InitialOpenAggregateV2(self.control, self.tasks, [], [], self.extra)
        self.prior = project_aux(CFG, self.control, self.tasks, [], [])[1]

    def packed(self, graph=None, prior=None):
        graph = self.coherent if graph is None else graph
        prior = self.prior if prior is None else prior
        return compact_aggregate_v2(CFG, graph.control, graph.tasks, graph.holder_rows,
                                    graph.signal_rows, prior)

    def proof(self, graph=None, body=None):
        graph = self.coherent if graph is None else graph
        derived = derive_task_compact(CFG, self.packed(graph))
        return preflight_initial_open_compact(
            CFG, derived, graph.extra_task, 13, self.out["body"] if body is None else body,
            self.prior["task"], **SPEC)

    def gate(self, **overrides):
        args = dict(cfg=CFG, coherent=self.coherent, actor=13, body=self.out["body"],
                    frozen_task_previous=self.prior["task"], composed_previous=self.prior,
                    expected_proof_sha256=digest(canonical(self.proof())), **SPEC)
        args.update(overrides)
        before = copy.deepcopy(args)
        try:
            return gate_initial_open_aggregate(**args)
        finally:
            self.assertEqual(args, before)

    def test_closed_exact_bindings_and_single_compaction(self):
        aggregate = self.packed()
        derived = derive_task_compact(CFG, aggregate)
        proof = self.proof()
        expected = dict(protocol=PROTOCOL, operation="initial_open",
                        aggregate_sha256=aggregate.sha256,
                        aggregate_inventory_sha256=aggregate.inventory_sha256,
                        prior_composed_state_sha256=digest(canonical(self.prior)),
                        projected_composed_state_sha256=digest(canonical(
                            project_compact_aggregate_v2(CFG, aggregate, self.prior)[1])),
                        task_compact_sha256=derived.sha256,
                        task_inventory_sha256=derived.inventory_sha256,
                        extra_observation_sha256=proof["extra_observation_sha256"],
                        proof_sha256=digest(canonical(proof)), event_id="o2",
                        selected_role="SPEC", selected_incarnation="s", authority=NO_AUTHORITY)
        # Direct call avoids counting the test's independent frozen proof preparation.
        with patch("v2_aggregate_gate.compact_aggregate_v2", wraps=compact_aggregate_v2) as compact, \
             patch("v2_acquisition.Reader") as reader, \
             patch("v2_acquisition.acquire_aggregate_v2_for_initial_open") as acquire:
            got = gate_initial_open_aggregate(
                CFG, self.coherent, 13, self.out["body"], self.prior["task"],
                self.prior, expected["proof_sha256"], **SPEC)
            compact.assert_called_once_with(CFG, self.control, self.tasks, [], [], self.prior)
            reader.assert_not_called()
            acquire.assert_not_called()
        self.assertEqual(got, expected)
        self.assertEqual(self.gate(), expected)
        for material in (self.out["body"], self.extra["body"], self.extra["comments"][0]["body"]):
            self.assertNotIn(material, canonical(got))
        got["event_id"] = "mutated"
        self.assertEqual(self.gate(), expected)

    def test_exact_coherent_type_and_retained_shape(self):
        class Lookalike(InitialOpenAggregateV2):
            pass
        for graph in (None, tuple(self.coherent), self.coherent._asdict(), self.packed(),
                      Lookalike(*self.coherent)):
            with self.subTest(type=type(graph)), self.assertRaises(Conflict):
                self.gate(coherent=graph)
        for prior in (None, {}, {"task": self.prior["task"]},
                      dict(self.prior, unexpected=True)):
            with self.subTest(prior=prior), self.assertRaises(Conflict):
                self.gate(composed_previous=prior)
        bad = copy.deepcopy(self.prior)
        bad["aux"]["ledger"]["bad"] = None
        with self.assertRaises(Conflict):
            self.gate(composed_previous=bad)
        wrong = copy.deepcopy(self.prior["task"])
        wrong["ledger"] = {}
        for frozen in (None, wrong, self.prior):
            with self.subTest(frozen=frozen), self.assertRaises(Conflict):
                self.gate(frozen_task_previous=frozen)

    def test_wrong_proof_actor_role_incarnation_body(self):
        for kwargs in ({"expected_proof_sha256": "0"*64}, {"expected_proof_sha256": None},
                       {"actor": 10}, {"selected_role": "GUARD"},
                       {"selected_incarnation": "wrong"}, {"body": "unframed"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(Conflict):
                self.gate(**kwargs)

    def test_global_aux_collision_after_exact_task_preflight(self):
        collision = aux("o2", "PING", 502, "GUARD", "BUILDER", ping_id="o2")
        graph = self.coherent._replace(control={"34": self.control["34"] + [collision]})
        accepted = self.proof(graph)
        self.assertEqual(accepted["candidate"]["event_id"], "o2")
        # Prove the accepted preflight really succeeded inside the gate with
        # the matching frozen proof, so global collision is the rejection.
        with patch("v2_aggregate_gate.preflight_initial_open_compact",
                   wraps=preflight_initial_open_compact) as check:
            with self.assertRaises(Conflict):
                self.gate(coherent=graph, expected_proof_sha256=digest(canonical(accepted)))
            check.assert_called_once()
            self.assertEqual(check.call_args.args[1], derive_task_compact(CFG, self.packed(graph)))

    def test_task_collision_or_candidate_already_observed(self):
        conflicting = opening(self.extra, task="O2", mid="o", cid=200)
        with self.assertRaises(Conflict):
            self.gate(body=conflicting["body"])
        admitted = self.coherent._replace(
            control={"34": self.control["34"] + [self.out]},
            tasks=dict(self.tasks, **{"43": self.extra}))
        with self.assertRaises(Conflict):
            self.gate(coherent=admitted)
        alias = opening(issue(42, 4003), task="O2", mid="alias", cid=200)
        with self.assertRaises(Conflict):
            self.gate(body=alias["body"])

    def test_extra_partition_content_binding_and_normalization(self):
        changed = copy.deepcopy(self.extra)
        changed["comments"][0]["body"] += " drift"
        graph = self.coherent._replace(extra_task=changed)
        before = self.gate()
        with self.assertRaises(Conflict):
            self.gate(coherent=graph)
        new = self.gate(coherent=graph, expected_proof_sha256=digest(canonical(self.proof(graph))))
        self.assertNotEqual(new["extra_observation_sha256"], before["extra_observation_sha256"])
        self.assertEqual(new["aggregate_sha256"], before["aggregate_sha256"])
        other = self.coherent._replace(extra_task=issue(44, 4004))
        with self.assertRaises(Conflict):
            self.gate(coherent=other)
        normalized = copy.deepcopy(self.extra)
        normalized["comments"] += normalized["comments"]
        self.assertEqual(self.gate(coherent=self.coherent._replace(extra_task=normalized)), before)

    def test_holder_and_signal_transport_bindings(self):
        baseline = self.gate()
        for graph in (self.coherent._replace(holder_rows=[self.holder]),
                      self.coherent._replace(signal_rows=[self.signal])):
            with self.subTest(graph=graph):
                got = self.gate(coherent=graph)
                for key in ("aggregate_sha256", "aggregate_inventory_sha256"):
                    self.assertNotEqual(got[key], baseline[key])
                for key in ("task_compact_sha256", "task_inventory_sha256", "proof_sha256",
                            "extra_observation_sha256", "prior_composed_state_sha256"):
                    self.assertEqual(got[key], baseline[key])
                self.assertEqual(got["projected_composed_state_sha256"],
                                 digest(canonical(project_compact_aggregate_v2(
                                     CFG, self.packed(graph), self.prior)[1])))

    def test_opaque_control_and_task_inventory_drift(self):
        baseline = self.gate()
        graph = copy.deepcopy(self.coherent)
        graph.control["34"][-1]["body"] += " changed"
        for changed in (graph, self.coherent._replace(tasks={"42": dict(
                self.tasks["42"], comments=self.tasks["42"]["comments"] +
                [row(901, 99, "new task prose", 29)])})):
            with self.subTest(graph=changed), self.assertRaises(Conflict):
                self.gate(coherent=changed)
        new = self.gate(coherent=graph, expected_proof_sha256=digest(canonical(self.proof(graph))))
        self.assertNotEqual(new["aggregate_inventory_sha256"], baseline["aggregate_inventory_sha256"])
        self.assertNotEqual(new["task_inventory_sha256"], baseline["task_inventory_sha256"])
        self.assertNotEqual(new["proof_sha256"], baseline["proof_sha256"])


if __name__ == "__main__":
    unittest.main()
