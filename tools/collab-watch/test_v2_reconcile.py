import copy
import unittest

from core import Conflict, canonical, digest
from test_split_journal import (CFG, SHA, OTHER, candidate, close, control, disposition,
                                fixture, issue, material, opening, ref, row, ts)
from split_journal import project_v2
from v2_compact import compact_v2
from v2_preflight import (preflight_close_compact, preflight_control_compact,
                          preflight_initial_open_compact)
from v2_reconcile import verify_close, verify_control, verify_initial_open

GUARD = dict(selected_role="GUARD", selected_incarnation="g")
BUILDER = dict(selected_role="BUILDER", selected_incarnation="b")
SPEC = dict(selected_role="SPEC", selected_incarnation="s")


def binding(actor):
    return {10: GUARD, 11: BUILDER, 13: SPEC}[actor]


def proof_hash(proof):
    return digest(canonical(proof))


class ReconcileTests(unittest.TestCase):
    def control_case(self, prior, task, outgoing, post, *, cfg=CFG, post_task=None, previous=None):
        actor = outgoing["user"]["id"]
        chosen = binding(actor)
        baseline = compact_v2(cfg, {"34": prior}, {"42": task}, previous)
        proof = preflight_control_compact(cfg, baseline, actor, outgoing["body"], previous, **chosen)
        params = dict(cfg=cfg, baseline=baseline, actor=actor, body=outgoing["body"],
                      post_control={"34": post}, post_tasks={"42": post_task or task},
                      previous=previous, expected_proof_sha256=proof_hash(proof), **chosen)
        return params, proof

    def test_all_existing_control_relations(self):
        rows, task = fixture(True)
        for n in range(1, len(rows)):
            with self.subTest(n=n):
                params, proof = self.control_case(rows[:n], task, rows[n], rows)
                result = verify_control(**params, expected_ref={"room": 34, "comment_id": rows[n]["id"]})
                self.assertEqual(result["state"], "VERIFIED")
                self.assertEqual(result["occurrence"]["body_sha256"], digest(rows[n]["body"]))
                self.assertEqual(result["occurrence"]["resolution"], "exact_ref")
                self.assertEqual(result["proof_sha256"], proof_hash(proof))
                self.assertNotIn("ledger", result)
                self.assertNotIn("projection", result)
                self.assertEqual(result["authority"], "verification only; no mutation or retry authorized")
                _, baseline_state = project_v2(CFG, {"34": rows[:n]}, {"42": task})
                _, post_state = project_v2(CFG, {"34": rows}, {"42": task}, baseline_state)
                self.assertEqual(result["post_state_sha256"], proof_hash(post_state))
                reordered = dict(params, post_control={"34": list(reversed(rows))})
                self.assertEqual(verify_control(**reordered, expected_ref={"room": 34, "comment_id": rows[n]["id"]}), result)

        rows, task = fixture()
        sup = control("s", "DISPOSITION", 105, 12, open_id="o", previous="v1", disposition="SUPERSEDED")
        spec = material(1200, "SPEC", 13, revision=2)
        task["comments"].append(spec)
        o2 = control("o2", "OPEN", 106, 15, revision=2, task_ref={"issue_number": 42, "issue_id": 4002},
                     spec_ref={"kind": "issue_comment", **ref(spec)}, previous="s")
        for prior, outgoing in ((rows, sup), (rows+[sup], o2)):
            params, _ = self.control_case(prior, task, outgoing, rows+[sup, o2])
            self.assertEqual(verify_control(**params)["occurrence"]["event_id"],
                             "s" if outgoing is sup else "o2")
        rows, task = fixture()
        close(task)
        out = disposition(rows[-1])
        params, _ = self.control_case(rows, task, out, rows+[out])
        self.assertEqual(verify_control(**params)["occurrence"]["event_id"], "d")

    def test_unresolved_duplicates_and_expected_ref(self):
        rows, task = fixture()
        params, _ = self.control_case(rows[:1], task, rows[1], rows[:1])
        with self.assertRaises(Conflict):
            verify_control(**params)
        unique = dict(params, post_control={"34": rows[:2]})
        self.assertEqual(verify_control(**unique)["occurrence"]["resolution"], "unique_occurrence")
        duplicate = copy.deepcopy(rows[1])
        duplicate.update(id=999, created_at=ts(10), updated_at=ts(10))
        double = dict(params, post_control={"34": rows[:2]+[duplicate]})
        with self.assertRaises(Conflict):
            verify_control(**double)
        for cid in (101, 999):
            occurrence = verify_control(**double, expected_ref={"room": 34, "comment_id": cid})["occurrence"]
            self.assertEqual(occurrence["physical_ref"], "issue:34#issuecomment-"+str(cid))
            self.assertEqual(occurrence["matching_occurrences"], 2)
        for expected in ({"room": 35, "comment_id": 101}, {"room": 34, "comment_id": 102},
                         {"room": 34, "comment_id": 0}, {"room": 34, "comment_id": 101, "x": 1}):
            with self.assertRaises(Conflict):
                verify_control(**double, expected_ref=expected)
        wrong = row(999, 99, rows[1]["body"], 10)
        with self.assertRaises(Conflict):
            verify_control(**dict(params, post_control={"34": rows[:2]+[wrong]}),
                           expected_ref={"room": 34, "comment_id": 999})

    def test_wrong_bytes_actor_time_and_prior_ledger(self):
        rows, task = fixture()
        params, proof = self.control_case(rows[:1], task, rows[1], rows[:2])
        for mutation in ("body", "actor", "time", "edited"):
            wrong = copy.deepcopy(rows[1])
            if mutation == "body":
                # Same parsed JSON, different exact bytes.
                wrong["body"] = wrong["body"].replace('"attempt":1', '"attempt": 1')
            elif mutation == "actor":
                wrong["user"]["id"] = 10
            elif mutation == "time":
                wrong["created_at"] = wrong["updated_at"] = proof["postcondition"]["created_at_strictly_after"]
            else:
                wrong["updated_at"] = ts(10)
            with self.subTest(mutation=mutation), self.assertRaises(Conflict):
                verify_control(**dict(params, post_control={"34": rows[:1]+[wrong]}))
        missing = copy.deepcopy(rows[:2])
        missing[0]["id"] = 800
        with self.assertRaises(Conflict):
            verify_control(**dict(params, post_control={"34": missing}))
        _, retained = project_v2(CFG, {"34": rows}, {"42": task})
        with self.assertRaises(Conflict):
            verify_control(**dict(params, previous=retained))

    def test_original_proof_binds_candidate_inventory_role_and_config(self):
        rows, task = fixture()
        params, _ = self.control_case(rows[:1], task, rows[1], rows[:2])
        alternative = copy.deepcopy(rows[1])
        alternative["body"] = alternative["body"].replace('"event_id":"r1"', '"event_id":"different"')
        # Both candidate and post-read are internally consistent, but not the original preflight.
        with self.assertRaises(Conflict):
            verify_control(**dict(params, body=alternative["body"], post_control={"34": rows[:1]+[alternative]}))
        drift = copy.deepcopy(task)
        drift["comments"].append(row(1800, 11, "ordinary prose", 4))
        changed = compact_v2(CFG, {"34": rows[:1]}, {"42": drift})
        for changes in ({"baseline": changed}, {"selected_incarnation": "wrong"},
                        {"selected_role": "GUARD"}, {"expected_proof_sha256": "0"*64},
                        {"cfg": dict(CFG, signal_room=38)}):
            with self.subTest(changes=changes.keys()), self.assertRaises(Conflict):
                verify_control(**dict(params, **changes))
        # Unrelated post-preflight activity is not a baseline replacement.
        self.assertEqual(verify_control(**dict(params, post_tasks={"42": drift}))["state"], "VERIFIED")

    def initial_case(self):
        rows, task = fixture()
        extra = issue(43, 4003)
        out = opening(extra, task="O2", mid="o2", cid=200)
        baseline = compact_v2(CFG, {"34": rows}, {"42": task})
        proof = preflight_initial_open_compact(CFG, baseline, extra, 13, out["body"], **SPEC)
        params = dict(cfg=CFG, baseline=baseline, extra_task=extra, actor=13, body=out["body"],
                      post_control={"34": rows+[out]}, post_tasks={"42": task, "43": extra},
                      expected_proof_sha256=proof_hash(proof), **SPEC)
        return rows, task, extra, out, params

    def test_initial_open_physical_registration_and_drift(self):
        rows, task, extra, out, params = self.initial_case()
        result = verify_initial_open(**params)
        self.assertEqual(result["issue"]["number"], 43)
        self.assertEqual(result["issue"]["id"], 4003)
        self.assertEqual(result["occurrence"]["physical_ref"], "issue:34#issuecomment-200")
        self.assertEqual(result["issue"]["body_sha256"], digest(extra["body"]))
        _, original_state = project_v2(CFG, {"34": rows}, {"42": task})
        self.assertNotIn("task:4003:identity", original_state["ledger"])
        with self.assertRaises(Conflict):
            verify_initial_open(**dict(params, post_control={"34": rows}, post_tasks={"42": task}))
        for k, value in (("body", "changed"), ("id", 999), ("created_at", ts(2))):
            changed = dict(extra, **{k: value})
            with self.assertRaises(Conflict):
                verify_initial_open(**dict(params, post_tasks={"42": task, "43": changed}))
        changed = copy.deepcopy(extra)
        changed["comments"].append(row(1800, 13, "legitimate ordinary post comment", 8))
        self.assertEqual(verify_initial_open(**dict(params, post_tasks={"42": task, "43": changed})), result)
        with self.assertRaises(Conflict):
            verify_initial_open(**dict(params, extra_task=changed))
        dup = copy.deepcopy(out)
        dup.update(id=201, created_at=ts(5), updated_at=ts(5))
        double = dict(params, post_control={"34": rows+[out, dup]})
        with self.assertRaises(Conflict):
            verify_initial_open(**double)
        self.assertEqual(verify_initial_open(**double, expected_ref={"room": 34, "comment_id": 201})
                         ["occurrence"]["matching_occurrences"], 2)

    def close_case(self, rows, task, accept):
        baseline = compact_v2(CFG, {"34": rows}, {"42": task})
        request = {"task": "O1", "issue_number": 42, "issue_id": 4002, "revision": 1,
                   "attempt": 1, "commit_sha": SHA, "accept_ref": {"room": 34, **ref(accept)}}
        proof = preflight_close_compact(CFG, baseline, 10, request, **GUARD)
        return dict(cfg=CFG, baseline=baseline, actor=10, request=request,
                    post_control={"34": rows}, post_tasks={"42": task},
                    expected_proof_sha256=proof_hash(proof), **GUARD)

    def test_close_and_already_disposed(self):
        rows, task = fixture()
        params = self.close_case(rows, task, rows[-1])
        with self.assertRaises(Conflict):
            verify_close(**params)
        closed = copy.deepcopy(task)
        close(closed)
        params["post_tasks"] = {"42": closed}
        result = verify_close(**params)
        self.assertEqual(result["task_state"], "CLOSE_OBSERVED")
        self.assertEqual(result["close_event"], {"id": 900, "actor_id": 10, "created_at": ts(20)})
        self.assertEqual(result["accept"]["physical_ref"], "issue:34#issuecomment-102")
        done = dict(params, post_control={"34": rows+[disposition(rows[-1])]})
        self.assertEqual(verify_close(**done)["task_state"], "CLOSED")
        for key, value in (("revision", 2), ("attempt", 2), ("commit_sha", OTHER),
                           ("issue_id", 999), ("accept_ref", {"room": 34, **ref(rows[1])})):
            with self.assertRaises(Conflict):
                verify_close(**dict(params, request=dict(params["request"], **{key: value})))
        for mutation in ("actor", "metadata", "reopen", "multiple", "time"):
            wrong = copy.deepcopy(closed)
            if mutation == "actor":
                wrong["closed_by"] = wrong["events"][0]["actor_id"] = 13
            elif mutation == "metadata":
                wrong["closed_at"] = ts(21)
            elif mutation in ("reopen", "multiple"):
                wrong["events"].append({"id": 901, "actor_id": 10,
                                        "kind": "reopened" if mutation == "reopen" else "closed",
                                        "created_at": ts(22)})
            else:
                close(wrong, 9)
            with self.subTest(mutation=mutation), self.assertRaises(Conflict):
                verify_close(**dict(params, post_tasks={"42": wrong}))

    def test_close_exact_nominated_duplicate_and_later_disposition(self):
        rows, task = fixture()
        accept = rows[-1]
        duplicate = copy.deepcopy(accept)
        duplicate.update(id=999, created_at=ts(11), updated_at=ts(11))
        rows.append(duplicate)
        params = self.close_case(rows, task, duplicate)
        closed = copy.deepcopy(task)
        close(closed, 11)
        # Canonical close is valid against earlier ACCEPT, but not nominated occurrence.
        self.assertEqual(project_v2(CFG, {"34": rows}, {"42": closed})[0]["tasks"][0]["state"], "CLOSE_OBSERVED")
        with self.assertRaises(Conflict):
            verify_close(**dict(params, post_tasks={"42": closed}))
        close(closed)
        params["post_tasks"] = {"42": closed}
        self.assertEqual(verify_close(**params)["accept"]["physical_ref"], "issue:34#issuecomment-999")
        # PATCH does not encode an ACCEPT ref. A valid later disposition may cite
        # another eligible occurrence, without erasing the nominated predecessor.
        done = dict(params, post_control={"34": rows+[disposition(accept)]})
        self.assertEqual(verify_close(**done)["task_state"], "CLOSED")
        with self.assertRaises(Conflict):
            verify_close(**dict(params, post_control={"34": rows[:-1]}))


if __name__ == "__main__":
    unittest.main()
