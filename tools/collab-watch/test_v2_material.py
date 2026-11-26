import copy
import unittest

from core import Conflict, canonical, digest
from split_journal import project_v2
from test_split_journal import (CFG, SHA, OTHER, fixture, issue, opening, control, material,
                                close, ref, row, ts)
from v2_compact import compact_v2
from v2_material import preflight_material, verify_material
from v2_preflight import preflight_control_compact

BUILDER = {"selected_role": "BUILDER", "selected_incarnation": "b"}
GUARD = {"selected_role": "GUARD", "selected_incarnation": "g"}
SPEC = {"selected_role": "SPEC", "selected_incarnation": "s"}


class MaterialTests(unittest.TestCase):
    def case(self, rows, task, outgoing, selected=BUILDER, cfg=CFG, previous=None):
        original = copy.deepcopy(task)
        baseline = compact_v2(cfg, {"34": rows}, {"42": original}, previous)
        actor, body = outgoing["user"]["id"], outgoing["body"]
        args = dict(cfg=cfg, baseline=baseline, task_key="O1", actor=actor, body=body,
                    previous=previous, **selected)
        proof = preflight_material(**args)
        post = copy.deepcopy(original)
        post["comments"].append(outgoing)
        verify = dict(args, expected_preflight_sha256=digest(canonical(proof)),
                      post_control={"34": rows}, post_tasks={"42": post})
        return args, proof, verify

    def result_case(self):
        task = issue()
        return self.case([opening(task)], task, material(1001, "RESULT", 5))

    def test_result_review_and_spec_readback(self):
        rows, task = fixture()
        for n, selected in ((1, BUILDER), (2, GUARD)):
            original = dict(task, comments=task["comments"][:n-1])
            m = task["comments"][n-1]
            args, proof, verify = self.case(rows[:n], original, m, selected)
            self.assertEqual(proof["state"], "CONDITIONAL")
            self.assertNotIn("material_ref", proof)
            receipt = verify_material(**verify)
            self.assertEqual(receipt["state"], "VERIFIED")
            self.assertEqual(receipt["material_ref"], ref(m))
            self.assertEqual(receipt["header"], proof["header"])
            self.assertEqual(receipt["baseline_state_sha256"], receipt["post_state_sha256"])
            self.assertNotEqual(receipt["post_inventory_sha256"], proof["inventory_sha256"])
            self.assertNotIn("ledger", receipt)
            self.assertEqual(receipt["authority"], "material only; no control publication, mutation or retry authorized")
            post = verify["post_tasks"]
            # No control fact yet; the newly verified ref is a later preflight input.
            obs = compact_v2(CFG, {"34": rows[:n]}, post)
            later = preflight_control_compact(CFG, obs, m["user"]["id"], rows[n]["body"], **selected)
            self.assertEqual(later["material"]["comment_id"], m["id"])
            advanced = verify_material(**dict(verify, post_control={"34": rows[:n+1]}))
            self.assertEqual(advanced["material_ref"], receipt["material_ref"])
            self.assertNotEqual(advanced["post_state_sha256"], receipt["post_state_sha256"])

        sup = control("s", "DISPOSITION", 105, 12, open_id="o", previous="v1", disposition="SUPERSEDED")
        m = material(1200, "SPEC", 13, revision=2)
        _, proof, verify = self.case(rows+[sup], task, m, SPEC)
        self.assertEqual(proof["header"]["revision"], 2)
        self.assertEqual(verify_material(**verify)["material_ref"], ref(m))

    def test_material_lifecycle_rejections(self):
        rows, task = fixture()
        for prior, m, selection in (
            (rows[:1], material(1200, "RESULT", 12, revision=2), BUILDER),
            (rows[:1], material(1200, "RESULT", 12, attempt=2), BUILDER),
            (rows[:2], material(1200, "RESULT", 12), BUILDER),
            (rows[:1], material(1200, "REVIEW", 12), GUARD),
            (rows[:2], material(1200, "REVIEW", 12, attempt=2), GUARD),
            (rows[:2], material(1200, "REVIEW", 12, commit_sha=OTHER), GUARD),
            (rows[:2], material(1200, "REVIEW", 12, revision=2), GUARD),
            (rows, material(1200, "SPEC", 12, revision=2), SPEC),
        ):
            with self.subTest(selection=selection, body=m["body"][:150]), self.assertRaises(Conflict):
                self.case(prior, task, m, selection)
        sup = control("s", "DISPOSITION", 105, 12, open_id="o", previous="v1", disposition="SUPERSEDED")
        for rev in (1, 3):
            with self.assertRaises(Conflict):
                self.case(rows+[sup], task, material(1200, "SPEC", 14, revision=rev), SPEC)
        closed = copy.deepcopy(task)
        close(closed)
        with self.assertRaises(Conflict):
            self.case(rows, closed, material(1200, "SPEC", 25, revision=2), SPEC)

    def test_header_selected_role_and_shared_actor(self):
        args, _, _ = self.result_case()
        for changes in ({"selected_role": "GUARD"}, {"selected_incarnation": "wrong"}, {"actor": 10},
                        {"task_key": "other"},
                        {"body": args["body"].replace("Candidate SHA: "+SHA, "Candidate SHA: "+OTHER)},
                        {"body": args["body"].replace('"attempt":1', '"attempt":1,"extra":true')},
                        {"body": args["body"].replace('"task":"O1"', '"task":"O2"')},
                        {"body": "not a material frame"}):
            with self.subTest(changes=changes), self.assertRaises(Conflict):
                preflight_material(**dict(args, **changes))
        cfg = copy.deepcopy(CFG)
        cfg["roles"]["SPEC"]["actor_id"] = 10
        rows, task = fixture()
        task["author_id"] = 10
        rows[0]["user"]["id"] = 10
        original = dict(task, comments=task["comments"][:1])
        m = task["comments"][1]
        args, _, verify = self.case(rows[:2], original, m, GUARD, cfg)
        self.assertEqual(verify_material(**verify)["actor_id"], 10)
        with self.assertRaises(Conflict):
            preflight_material(**dict(args, **SPEC))
        with self.assertRaises(Conflict):
            verify_material(**dict(verify, **SPEC))

    def test_existing_exact_and_different_prose(self):
        args, _, verify = self.result_case()
        post = verify["post_tasks"]
        already = compact_v2(CFG, verify["post_control"], post)
        with self.assertRaises(Conflict):
            preflight_material(**dict(args, baseline=already))
        changed = copy.deepcopy(post)
        changed["42"]["comments"][0]["body"] += " different prose"
        distinct = compact_v2(CFG, verify["post_control"], changed)
        self.assertEqual(preflight_material(**dict(args, baseline=distinct))["state"], "CONDITIONAL")
        with self.assertRaises(Conflict):
            verify_material(**dict(verify, post_tasks=changed))
        edited = copy.deepcopy(post)
        edited["42"]["comments"][0]["updated_at"] = ts(7)
        with self.assertRaises(Conflict):
            preflight_material(**dict(args, baseline=compact_v2(CFG, verify["post_control"], edited)))
        with self.assertRaises(Conflict):
            verify_material(**dict(verify, post_tasks=edited))

    def test_ambiguous_and_exact_occurrence(self):
        _, _, verify = self.result_case()
        missing = copy.deepcopy(verify["post_tasks"])
        missing["42"]["comments"] = []
        with self.assertRaises(Conflict):
            verify_material(**dict(verify, post_tasks=missing))
        original = verify["post_tasks"]["42"]["comments"][0]
        double = copy.deepcopy(verify["post_tasks"])
        duplicate = dict(original, id=2001, created_at=ts(8), updated_at=ts(8))
        double["42"]["comments"].append(duplicate)
        with self.assertRaises(Conflict):
            verify_material(**dict(verify, post_tasks=double))
        for cid in (1001, 2001):
            receipt = verify_material(**dict(verify, post_tasks=double), expected_comment_id=cid)
            self.assertEqual(receipt["material_ref"]["comment_id"], cid)
            self.assertEqual(receipt["matching_occurrences"], 2)
        for cid in (0, 9999, True):
            with self.assertRaises(Conflict):
                verify_material(**verify, expected_comment_id=cid)
        wrong = copy.deepcopy(verify["post_tasks"])
        wrong["42"]["comments"].append(row(2002, 99, original["body"], 7))
        with self.assertRaises(Conflict):
            verify_material(**dict(verify, post_tasks=wrong), expected_comment_id=2002)
        wrong["42"]["comments"][-1]["user"]["id"] = 11
        wrong["42"]["comments"][-1]["body"] += " different"
        with self.assertRaises(Conflict):
            verify_material(**dict(verify, post_tasks=wrong), expected_comment_id=2002)

    def test_chronology_baseline_and_post_inventory(self):
        args, proof, verify = self.result_case()
        for second in (0, 1):
            post = copy.deepcopy(verify["post_tasks"])
            post["42"]["comments"][0]["created_at"] = post["42"]["comments"][0]["updated_at"] = ts(second)
            if second == 0:
                with self.assertRaises(Conflict):
                    verify_material(**dict(verify, post_tasks=post))
            else:
                self.assertEqual(verify_material(**dict(verify, post_tasks=post))["created_at"], ts(1))
        post = copy.deepcopy(verify["post_tasks"])
        post["42"]["comments"].append(row(2000, 99, "ordinary new prose", 7))
        result = verify_material(**verify)
        later = verify_material(**dict(verify, post_tasks=post))
        self.assertEqual(result["material_ref"], later["material_ref"])
        self.assertEqual(result["post_state_sha256"], later["post_state_sha256"])
        self.assertNotEqual(result["post_inventory_sha256"], later["post_inventory_sha256"])
        other_baseline_task = copy.deepcopy(post["42"])
        other_baseline_task["comments"].pop(0)
        altered = compact_v2(CFG, verify["post_control"], {"42": other_baseline_task})
        for changes in ({"baseline": altered}, {"cfg": dict(CFG, signal_room=38)},
                        {"expected_preflight_sha256": "0"*64},
                        {"body": args["body"]+" different", "post_tasks": post}):
            with self.subTest(changes=changes.keys()), self.assertRaises(Conflict):
                verify_material(**dict(verify, **changes))
        rows, task = fixture()
        _, retained = project_v2(CFG, {"34": rows}, {"42": task})
        with self.assertRaises(Conflict):
            verify_material(**dict(verify, previous=retained))
        bad = copy.deepcopy(verify["post_control"])
        bad["34"][0]["id"] = 999
        with self.assertRaises(Conflict):
            verify_material(**dict(verify, post_control=bad))


if __name__ == "__main__":
    unittest.main()
