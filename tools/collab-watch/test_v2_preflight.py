import copy
import unittest

from core import Conflict, digest
from split_journal import project_v2
from test_split_journal import (CFG, SHA, OTHER, candidate, close, control, disposition,
                                fixture, issue, material, opening, ref, row, ts)
from v2_compact import compact_v2
from v2_preflight import (preflight_close, preflight_close_compact, preflight_control,
                          preflight_control_compact)


class PreflightV2Tests(unittest.TestCase):
    def control(self, rows, task, outgoing, previous=None, cfg=CFG):
        c, t = {"34": rows}, {"42": task}
        before = copy.deepcopy((c, t, previous))
        proof = preflight_control(cfg, c, t, outgoing["user"]["id"], outgoing["body"], previous)
        packed = compact_v2(cfg, c, t, previous)
        self.assertEqual(preflight_control_compact(cfg, packed, outgoing["user"]["id"],
                                                   outgoing["body"], previous), proof)
        self.assertEqual((c, t, previous), before)
        self.assertEqual(proof["state"], "CONDITIONAL")
        self.assertEqual(proof["candidate"]["body_sha256"], digest(outgoing["body"]))
        self.assertNotIn("ledger", proof)
        self.assertNotIn("projection", proof)
        self.assertNotIn("comment_id", proof["candidate"])
        self.assertNotIn("created_at", proof["candidate"])
        self.assertNotIn("created_at", proof["postcondition"])
        return proof

    def test_result_review_rework_accept_and_strict_time(self):
        rows, task = fixture(True)
        states = ["BUILDER_READY", "GUARD_REVIEW", "BUILDER_READY", "GUARD_REVIEW"]
        for n, expected in enumerate(states, 1):
            p, previous = project_v2(CFG, {"34": rows[:n]}, {"42": task})
            proof = self.control(rows[:n], task, rows[n], previous)
            self.assertEqual(p["tasks"][0]["state"], expected)
            self.assertEqual(proof["task"]["state"], expected)
            self.assertEqual(proof["postcondition"]["created_at_strictly_after"],
                             task["comments"][n-1]["created_at"])
            same_second = copy.deepcopy(rows[n])
            same_second["created_at"] = same_second["updated_at"] = proof["postcondition"]["created_at_strictly_after"]
            # Preflight does not invent timestamps and cannot admit equality.
            with self.assertRaises(Conflict):
                project_v2(CFG, {"34": rows[:n]+[same_second]}, {"42": task}, previous)
            after, _ = project_v2(CFG, {"34": rows[:n+1]}, {"42": task}, previous)
            self.assertNotEqual(after["tasks"][0]["state"], expected)
        self.assertEqual(project_v2(CFG, {"34": rows[:-1]}, {"42": task})[0]["tasks"][0]["state"], "GUARD_REVIEW")

    def test_wrong_result_material_or_attempt(self):
        rows, task = fixture()
        valid = rows[1]
        for transform in (
            lambda s: s.replace('"attempt":1', '"attempt":2'),
            lambda s: s.replace('"previous":"o"', '"previous":"stale"'),
            lambda s: s.replace(SHA, OTHER),
            lambda s: s.replace(ref(task["comments"][0])["body_sha256"], "0"*64),
            lambda s: s.replace('"incarnation":"b"', '"incarnation":"wrong"'),
        ):
            with self.assertRaises(Conflict):
                preflight_control(CFG, {"34": rows[:1]}, {"42": task}, 11, transform(valid["body"]))
        for field, value in (("user", {"id": 10}), ("updated_at", ts(7)),
                             ("body", task["comments"][0]["body"].replace('"incarnation":"b"', '"incarnation":"bad"'))):
            damaged = copy.deepcopy(task)
            damaged["comments"][0][field] = value
            # Bind exact modified digest so malformed header/owner must fail, not just stale digest.
            body = valid["body"].replace(ref(task["comments"][0])["body_sha256"],
                                         digest(damaged["comments"][0]["body"]))
            with self.assertRaises(Conflict):
                preflight_control(CFG, {"34": rows[:1]}, {"42": damaged}, 11, body)
        late = candidate(task, "late", "RESULT", 109, 15, "v1", 2)
        with self.assertRaises(Conflict):
            self.control(rows, task, late)

    def test_review_wrong_state_candidate_or_role(self):
        rows, task = fixture()
        for prior in (rows[:1], rows):
            with self.assertRaises(Conflict):
                self.control(prior, task, rows[2])
        for body in (rows[2]["body"].replace(SHA, OTHER),
                     rows[2]["body"].replace('"attempt":1', '"attempt":2'),
                     rows[2]["body"].replace('"previous":"r1"', '"previous":"o"'),
                     rows[2]["body"].replace('"verdict":"ACCEPT"', '"verdict":"SPEC_REQUIRED"')):
            with self.assertRaises(Conflict):
                preflight_control(CFG, {"34": rows[:2]}, {"42": task}, 10, body)
        with self.assertRaises(Conflict):
            preflight_control(CFG, {"34": rows[:2]}, {"42": task}, 13, rows[2]["body"])

    def test_spec_required_supersede_revision_and_roles(self):
        task = issue()
        rows = [opening(task), candidate(task, "r1", "RESULT", 101, 6, "o"),
                candidate(task, "v1", "REVIEW", 102, 9, "r1", verdict="SPEC_REQUIRED")]
        self.control(rows[:2], task, rows[2])
        sup = control("s", "DISPOSITION", 105, 12, open_id="o", previous="v1", disposition="SUPERSEDED")
        spec = material(1200, "SPEC", 13, revision=2)
        task["comments"].append(spec)
        o2 = control("o2", "OPEN", 106, 15, revision=2, task_ref={"issue_number": 42, "issue_id": 4002},
                     spec_ref={"kind": "issue_comment", **ref(spec)}, previous="s")
        self.control(rows, task, sup)
        p = self.control(rows+[sup], task, o2)
        self.assertEqual(p["material"]["comment_id"], 1200)
        self.assertEqual(p["postcondition"]["created_at_strictly_after"], ts(13))
        for prior, out, actor in ((rows, o2, 13), (rows, sup, 10), (rows+[sup], o2, 10)):
            with self.assertRaises(Conflict):
                preflight_control(CFG, {"34": prior}, {"42": task}, actor, out["body"])
        with self.assertRaises(Conflict):
            preflight_control(CFG, {"34": rows+[sup]}, {"42": task}, 13,
                              o2["body"].replace('"revision":2', '"revision":3'))
        with self.assertRaises(Conflict):
            self.control([], task, rows[0])
        with self.assertRaises(Conflict):
            preflight_control(CFG, {"34": []}, {}, 13, rows[0]["body"])

    def close_request(self, accept):
        return {"task": "O1", "issue_number": 42, "issue_id": 4002, "revision": 1,
                "attempt": 1, "commit_sha": SHA, "accept_ref": {"room": 34, **ref(accept)}}

    def test_close_preflight_exact_physical_accept(self):
        rows, task = fixture()
        request = self.close_request(rows[-1])
        c, t = {"34": rows}, {"42": task}
        proof = preflight_close(CFG, c, t, 10, request)
        self.assertEqual(proof, preflight_close_compact(CFG, compact_v2(CFG, c, t), 10, request))
        self.assertEqual(proof["task"]["state"], "ACCEPTED")
        self.assertEqual(proof["postcondition"]["created_at_strictly_after"], ts(9))
        self.assertNotIn("close_event", proof)
        self.assertNotIn("id", proof["postcondition"])
        for key, val in (("task", "other"), ("issue_id", 999), ("issue_number", 43),
                         ("revision", 2), ("attempt", 2), ("commit_sha", OTHER)):
            with self.assertRaises(Conflict):
                preflight_close(CFG, c, t, 10, dict(request, **{key: val}))
        for val in (dict(request["accept_ref"], comment_id=101),
                    dict(request["accept_ref"], body_sha256="0"*64),
                    dict(request["accept_ref"], comment_id=999)):
            with self.assertRaises(Conflict):
                preflight_close(CFG, c, t, 10, dict(request, accept_ref=val))
        with self.assertRaises(Conflict):
            preflight_close(CFG, c, t, 13, request)
        with self.assertRaises(Conflict):
            preflight_close(CFG, {"34": rows[:2]}, t, 10, request)
        duplicate = copy.deepcopy(rows[-1])
        duplicate.update(id=999, created_at=ts(11), updated_at=ts(11))
        request2 = self.close_request(duplicate)
        p = preflight_close(CFG, {"34": rows+[duplicate]}, t, 10, request2)
        self.assertEqual(p["postcondition"]["created_at_strictly_after"], ts(11))
        close(task)
        with self.assertRaises(Conflict):
            preflight_close(CFG, c, t, 10, request)

    def test_closed_requires_actual_close_and_eligible_accept(self):
        rows, task = fixture()
        out = disposition(rows[-1])
        with self.assertRaises(Conflict):
            self.control(rows, task, out)
        close(task)
        proof = self.control(rows, task, out)
        self.assertEqual(proof["observed_close"]["id"], 900)
        self.assertEqual(proof["postcondition"]["created_at_strictly_after"], ts(20))
        with self.assertRaises(Conflict):
            self.control(rows, task, disposition(rows[-1], close_id=901))
        late = copy.deepcopy(rows[-1])
        late.update(id=999, created_at=ts(22), updated_at=ts(22))
        with self.assertRaises(Conflict):
            self.control(rows+[late], task, disposition(late))
        sup = control("s", "DISPOSITION", 105, 23, open_id="o", previous="v1", disposition="SUPERSEDED")
        with self.assertRaises(Conflict):
            self.control(rows, task, sup)

    def test_duplicate_inventory_opaque_config_retained(self):
        rows, task = fixture()
        with self.assertRaises(Conflict):
            self.control(rows[:2], task, rows[1])
        p = self.control(rows[:1], task, rows[1])
        prose = row(1800, 11, "ordinary untyped result", 4)
        task["comments"].append(prose)
        q = self.control(rows[:1], task, rows[1])
        self.assertNotEqual(p["inventory_sha256"], q["inventory_sha256"])
        self.assertEqual(p["baseline_state_sha256"], q["baseline_state_sha256"])
        task["comments"][-1]["body"] += " changed"
        r = self.control(rows[:1], task, rows[1])
        self.assertNotEqual(q["inventory_sha256"], r["inventory_sha256"])
        task["comments"].pop()
        self.assertEqual(self.control(rows[:1], task, rows[1]), p)
        task["comments"].append(prose)
        out = control("fake", "RESULT", 999, 6, open_id="o", previous="o", attempt=1,
                      commit_sha=SHA, material_ref=ref(prose))
        with self.assertRaises(Conflict):
            self.control(rows[:1], task, out)
        packed = compact_v2(CFG, {"34": rows[:1]}, {"42": task})
        cfg = copy.deepcopy(CFG)
        cfg["roles"]["BUILDER"]["incarnation"] = "other"
        with self.assertRaises(Conflict):
            preflight_control_compact(cfg, packed, 11, rows[1]["body"])
        with self.assertRaises(Conflict):
            preflight_control(cfg, {"34": rows[:1]}, {"42": task}, 11, rows[1]["body"])
        _, retained = project_v2(CFG, {"34": rows[:2]}, {"42": task})
        with self.assertRaises(Conflict):
            self.control(rows[:1], task, rows[1], retained)


if __name__ == "__main__":
    unittest.main()
