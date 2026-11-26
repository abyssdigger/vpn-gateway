import copy
import itertools
import unittest

from core import Conflict, canonical, digest
from split_journal import MARKER, PROTOCOL, discover_tasks, project_v2
from test_project_tasks import row, task_body, ts

SHA = "a"*40
OTHER = "b"*40
FENCE = chr(96)*3
CFG = {"protocol": PROTOCOL, "repository": "owner/repo", "journal_rooms": [34],
       "signal_room": 37, "journal_epoch": "v2-test",
       "roles": {"GUARD": {"actor_id": 10, "incarnation": "g"},
                 "BUILDER": {"actor_id": 11, "incarnation": "b"},
                 "SPEC": {"actor_id": 13, "incarnation": "s"}},
       "projectholder": {"actor_id": 12, "room": 35, "route_to": ["GUARD"]},
       "command_registry": {"cycle": "test", "capability_scopes": {}, "condition_keys": [],
                            "utc_keys": [], "model_scopes": {}}}


def control(mid, kind, cid, second, revision=1, task="O1", **fields):
    if kind == "OPEN" or (kind == "DISPOSITION" and fields.get("disposition") == "SUPERSEDED"):
        sender, target, actor, inc = "SPEC", "BUILDER", 13, "s"
    elif kind == "RESULT":
        sender, target, actor, inc = "BUILDER", "GUARD", 11, "b"
    elif kind == "REVIEW" and fields.get("verdict") == "SPEC_REQUIRED":
        sender, target, actor, inc = "GUARD", "SPEC", 10, "g"
    else:
        sender, target, actor, inc = "GUARD", "BUILDER", 10, "g"
    event = {"protocol": PROTOCOL, "journal_epoch": "v2-test", "event_id": mid,
             "kind": kind, "room": 34, "from": sender, "to": [target], "incarnation": inc,
             "task": task, "revision": revision, **fields}
    return row(cid, actor, MARKER + "\n" + FENCE + "json\n" + canonical(event) + "\n" + FENCE, second)


def material(cid, kind, second, revision=1, attempt=1, commit_sha=SHA, verdict="ACCEPT", task="O1"):
    actor = 11 if kind == "RESULT" else 13 if kind == "SPEC" else 10
    return row(cid, actor, task_body(kind, task, revision, attempt, commit_sha, verdict), second)


def ref(m):
    return {"comment_id": m["id"], "body_sha256": digest(m["body"])}


def issue(number=42, iid=4002, body="Initial specification"):
    return {"repository": "owner/repo", "number": number, "id": iid, "is_pull_request": False,
            "author_id": 13, "body": body, "created_at": ts(1), "state": "open",
            "closed_at": None, "closed_by": None, "comments": [], "events": []}


def opening(task_issue, task="O1", mid="o", cid=100, second=3):
    return control(mid, "OPEN", cid, second, task=task,
                   task_ref={"issue_number": task_issue["number"], "issue_id": task_issue["id"]},
                   spec_ref={"kind": "issue_body", "body_sha256": digest(task_issue["body"])},
                   previous=None)


def candidate(task_issue, mid, kind, cid, second, previous, attempt=1, sha=SHA,
              verdict="ACCEPT", revision=1, open_id="o"):
    m = material(cid+1000, kind, second-1, revision, attempt, sha, verdict)
    task_issue["comments"].append(m)
    fields = dict(open_id=open_id, previous=previous, attempt=attempt, commit_sha=sha, material_ref=ref(m))
    if kind == "REVIEW":
        fields["verdict"] = verdict
    return control(mid, kind, cid, second, revision=revision, **fields)


def fixture(rework=False):
    i = issue()
    rows = [opening(i), candidate(i, "r1", "RESULT", 101, 6, "o"),
            candidate(i, "v1", "REVIEW", 102, 9, "r1", verdict="REWORK" if rework else "ACCEPT")]
    if rework:
        rows += [candidate(i, "r2", "RESULT", 103, 12, "v1", 2, OTHER),
                 candidate(i, "v2", "REVIEW", 104, 15, "r2", 2, OTHER)]
    return rows, i


def close(i, second=20):
    i.update(state="closed", closed_at=ts(second), closed_by=10,
             events=[{"id": 900, "kind": "closed", "actor_id": 10, "created_at": ts(second)}])


def disposition(accept, previous="v1", second=24, close_id=900):
    return control("d", "DISPOSITION", 108, second, open_id="o", previous=previous,
                   disposition="CLOSED", accept_ref={"room": 34, **ref(accept)},
                   close_event={"id": close_id, "actor_id": 10, "created_at": ts(20)})


def run(rows, i, previous=None):
    return project_v2(CFG, {"34": rows}, {"42": i}, previous)


class JournalTests(unittest.TestCase):
    def test_lifecycle_and_permutations(self):
        rows, i = fixture(True)
        expected = ["BUILDER_READY", "GUARD_REVIEW", "BUILDER_READY", "GUARD_REVIEW", "ACCEPTED"]
        for n, state in enumerate(expected, 1):
            baseline = run(rows[:n], i)
            self.assertEqual(baseline[0]["tasks"][0]["state"], state)
            for p in itertools.permutations(rows[:n]):
                self.assertEqual(run(list(p), i), baseline)
        self.assertEqual(run(rows, i)[0]["tasks"][0]["accepted_sha"], OTHER)

    def test_close_and_physical_retry(self):
        rows, i = fixture()
        close(i)
        duplicate = copy.deepcopy(rows[-1])
        duplicate.update(id=999, created_at=ts(22), updated_at=ts(22))
        rows.append(duplicate)
        p, _ = run(rows, i)
        self.assertEqual(p["tasks"][0]["state"], "CLOSE_OBSERVED")
        self.assertEqual(p["tasks"][0]["eligible_accept_refs"], ["issue:34#issuecomment-102"])
        terminal = disposition(rows[2])
        p, state = run(rows+[terminal], i)
        self.assertEqual(p["tasks"][0]["state"], "CLOSED")
        self.assertEqual(p["roles"]["BUILDER"]["state"], "WAITING")
        self.assertEqual(p["roles"]["GUARD"]["state"], "WAITING")
        self.assertEqual(run(rows+[terminal], i, state)[0], p)
        for bad in (rows[:2]+[duplicate, terminal], rows+[disposition(duplicate)],
                    rows+[disposition(rows[2], close_id=901)],
                    rows+[disposition(rows[2], second=20)]):
            with self.assertRaises(Conflict):
                run(bad, i)

    def test_premature_reopen_same_second(self):
        rows, i = fixture()
        close(i, 9)
        with self.assertRaises(Conflict):
            run(rows, i)
        close(i, 20)
        with self.assertRaises(Conflict):
            run(rows[:2], i)
        i["events"].append({"id": 901, "kind": "reopened", "actor_id": 10, "created_at": ts(23)})
        with self.assertRaises(Conflict):
            run(rows, i)

    def test_material_and_ledger_drift(self):
        rows, i = fixture()
        _, state = run(rows, i)
        for mutation in ("body", "material", "edited_material", "edited_control", "missing"):
            r, x = copy.deepcopy(rows), copy.deepcopy(i)
            if mutation == "body":
                x["body"] += "!"
            elif mutation == "material":
                x["comments"][0]["body"] += "!"
            elif mutation == "edited_material":
                x["comments"][0]["updated_at"] = ts(7)
            elif mutation == "edited_control":
                r[0]["updated_at"] = ts(4)
            else:
                x["comments"].pop()
            with self.subTest(mutation=mutation), self.assertRaises(Conflict):
                run(r, x)
        with self.assertRaises(Conflict):
            run(rows[:1], i, state)

    def test_bad_attempts_and_duplicate(self):
        rows, i = fixture()
        r = candidate(i, "fork", "RESULT", 111, 12, "o")
        after = candidate(i, "after", "RESULT", 112, 15, "v1", 2)
        wrong = candidate(i, "wrong", "REVIEW", 113, 15, "r1", sha=OTHER)
        unlinked = candidate(i, "unlinked", "RESULT", 114, 15, "missing", 2)
        for bad in (rows+[r], rows+[after], rows[:2]+[wrong], rows+[unlinked],
                    rows+[control("r1", "RESULT", 115, 16, open_id="o", previous="o",
                                  attempt=2, commit_sha=SHA, material_ref=ref(i["comments"][0]))]):
            with self.assertRaises(Conflict):
                run(bad, i)
        duplicate = copy.deepcopy(rows[1])
        duplicate.update(id=999, created_at=ts(17), updated_at=ts(17))
        self.assertEqual(run(rows+[duplicate], i)[0]["tasks"][0]["state"], "ACCEPTED")

    def test_revision_and_fresh_replay(self):
        rows, i = fixture()
        supersede = control("s", "DISPOSITION", 105, 12, open_id="o", previous="v1", disposition="SUPERSEDED")
        spec = material(1200, "SPEC", 13, revision=2)
        i["comments"].append(spec)
        o2 = control("o2", "OPEN", 106, 15, revision=2,
                     task_ref={"issue_number": 42, "issue_id": 4002},
                     spec_ref={"kind": "issue_comment", **ref(spec)}, previous="s")
        p, _ = run(rows+[supersede, o2], i)
        self.assertEqual(p["tasks"][0]["revision"], 2)
        self.assertEqual(p["tasks"][0]["state"], "BUILDER_READY")
        self.assertIsNone(p["tasks"][0]["accepted_sha"])
        self.assertEqual(p["tasks"][0]["revisions"][0]["state"], "SUPERSEDED")
        with self.assertRaises(Conflict):
            run(rows+[o2], i)
        with self.assertRaises(Conflict):
            run(rows+[supersede, o2, candidate(i, "stale", "RESULT", 107, 18, "v1", 2)], i)
        i["comments"][-1]["body"] += " changed"
        # The stale candidate is the last row; modify actual SPEC to prove binding on fresh replay.
        spec["body"] += " changed"
        with self.assertRaises(Conflict):
            run(rows+[supersede, o2], i)

    def test_dynamic_registry_and_identity(self):
        rows, i = fixture()
        other = issue(43, 4003)
        second = opening(other, task="O2", mid="other", cid=150)
        control_rows = {"34": rows+[second]}
        self.assertEqual(set(discover_tasks(CFG, control_rows)), {"42", "43"})
        p, _ = project_v2(CFG, control_rows, {"42": i, "43": other})
        self.assertEqual(len(p["tasks"]), 2)
        with self.assertRaises(Conflict):
            project_v2(CFG, control_rows, {"42": i})
        with self.assertRaises(Conflict):
            project_v2(CFG, {"34": rows}, {"42": i, "43": other})
        for key, value in (("repository", "foreign/repo"), ("is_pull_request", True), ("id", 9)):
            x = copy.deepcopy(i)
            x[key] = value
            with self.assertRaises(Conflict):
                run(rows, x)
        for bad in (opening(other, task="O1", mid="rebind", cid=151),
                    opening(i, task="O2", mid="alias", cid=152),
                    opening(issue(35, 99), task="O3", mid="reserved", cid=153)):
            with self.assertRaises(Conflict):
                discover_tasks(CFG, {"34": rows+[bad]})

    def test_stale_role_and_foreign_prose(self):
        rows, i = fixture()
        unknown = row(999, 99, rows[0]["body"], 4)
        self.assertEqual(run(rows+[unknown], i), run(rows, i))
        bad = copy.deepcopy(rows[0])
        bad["body"] = bad["body"].replace('"incarnation":"s"', '"incarnation":"stale"')
        with self.assertRaises(Conflict):
            run([bad]+rows[1:], i)
        self.assertEqual(discover_tasks(CFG, {"34": [row(100, 10, "ordinary issue:999", 3)]}), {})


    def test_three_roles_and_same_actor(self):
        i = issue()
        opened = opening(i)
        for change in ("missing", "collision"):
            cfg = copy.deepcopy(CFG)
            if change == "missing":
                del cfg["roles"]["SPEC"]
            else:
                cfg["roles"]["SPEC"]["incarnation"] = "g"
            with self.assertRaises(Conflict):
                project_v2(cfg, {"34": [opened]}, {"42": i})
        cfg = copy.deepcopy(CFG)
        cfg["roles"]["SPEC"]["actor_id"] = 10
        i["author_id"] = 10
        opened["user"]["id"] = 10
        p, _ = project_v2(cfg, {"34": [opened]}, {"42": i})
        self.assertEqual(p["roles"]["BUILDER"]["state"], "READY")
        self.assertEqual(p["roles"]["SPEC"]["state"], "WAITING")
        bad = copy.deepcopy(opened)
        bad["body"] = bad["body"].replace('"from":"SPEC"', '"from":"GUARD"').replace('"incarnation":"s"', '"incarnation":"g"')
        with self.assertRaises(Conflict):
            project_v2(cfg, {"34": [bad]}, {"42": i})

    def test_spec_required_and_role_specific_readiness(self):
        i = issue()
        rows = [opening(i), candidate(i, "r1", "RESULT", 101, 6, "o"),
                candidate(i, "v1", "REVIEW", 102, 9, "r1", verdict="SPEC_REQUIRED")]
        p, _ = run(rows, i)
        self.assertEqual(p["tasks"][0]["state"], "SPEC_REQUIRED")
        self.assertEqual(p["roles"]["SPEC"]["state"], "READY")
        self.assertEqual(p["roles"]["BUILDER"]["state"], "WAITING")
        self.assertEqual(p["roles"]["GUARD"]["state"], "WAITING")
        supersede = control("s", "DISPOSITION", 105, 12, open_id="o", previous="v1", disposition="SUPERSEDED")
        self.assertEqual(run(rows+[supersede], i)[0]["roles"]["SPEC"]["state"], "READY")
        spec = material(1200, "SPEC", 13, revision=2)
        i["comments"].append(spec)
        o2 = control("o2", "OPEN", 106, 15, revision=2,
                     task_ref={"issue_number": 42, "issue_id": 4002},
                     spec_ref={"kind": "issue_comment", **ref(spec)}, previous="s")
        p, _ = run(rows+[supersede, o2], i)
        self.assertEqual(p["tasks"][0]["state"], "BUILDER_READY")
        self.assertEqual(p["roles"]["SPEC"]["state"], "WAITING")
        self.assertEqual(p["roles"]["BUILDER"]["state"], "READY")
        bad = copy.deepcopy(supersede)
        bad["user"]["id"] = 10
        bad["body"] = bad["body"].replace('"from":"SPEC"', '"from":"GUARD"').replace('"incarnation":"s"', '"incarnation":"g"')
        with self.assertRaises(Conflict):
            run(rows+[bad], i)
        for p_rows in itertools.permutations(rows+[supersede, o2]):
            self.assertEqual(run(list(p_rows), i)[0], p)

    def test_spec_direct_amendment_and_postclose_forbidden(self):
        i = issue()
        opened = opening(i)
        s = control("s", "DISPOSITION", 105, 5, open_id="o", previous="o", disposition="SUPERSEDED")
        spec = material(1200, "SPEC", 6, revision=2)
        i["comments"].append(spec)
        o2 = control("o2", "OPEN", 106, 8, revision=2,
                     task_ref={"issue_number": 42, "issue_id": 4002},
                     spec_ref={"kind": "issue_comment", **ref(spec)}, previous="s")
        self.assertEqual(run([opened, s, o2], i)[0]["tasks"][0]["state"], "BUILDER_READY")
        rows, i = fixture()
        close(i)
        s = control("s", "DISPOSITION", 105, 22, open_id="o", previous="v1", disposition="SUPERSEDED")
        with self.assertRaises(Conflict):
            run(rows+[s], i)

    def test_wrong_material_owner_incarnation_and_wrong_review_role(self):
        rows, i = fixture()
        for role, incarnation in (("SPEC", "s"), ("GUARD", "stale")):
            x = copy.deepcopy(i)
            m = x["comments"][1]
            m["body"] = task_body("REVIEW", role=role, incarnation=incarnation)
            modified = control("v1", "REVIEW", 102, 9, open_id="o", previous="r1",
                               attempt=1, commit_sha=SHA, material_ref=ref(m), verdict="ACCEPT")
            with self.assertRaises(Conflict):
                run(rows[:2]+[modified], x)
        bad = copy.deepcopy(rows[-1])
        bad["user"]["id"] = 13
        bad["body"] = bad["body"].replace('"from":"GUARD"', '"from":"SPEC"').replace('"incarnation":"g"', '"incarnation":"s"')
        with self.assertRaises(Conflict):
            run(rows[:2]+[bad], i)
        close(i)
        bad = disposition(rows[2])
        bad["user"]["id"] = 13
        bad["body"] = bad["body"].replace('"from":"GUARD"', '"from":"SPEC"').replace('"incarnation":"g"', '"incarnation":"s"')
        with self.assertRaises(Conflict):
            run(rows+[bad], i)

    def test_spec_revision_material_actor_and_incarnation(self):
        rows, i = fixture()
        s = control("s", "DISPOSITION", 105, 12, open_id="o", previous="v1", disposition="SUPERSEDED")
        for actor, inc in ((10, "s"), (13, "stale")):
            x = copy.deepcopy(i)
            spec = row(1200, actor, task_body("SPEC", revision=2, incarnation=inc), 13)
            x["comments"].append(spec)
            o2 = control("o2", "OPEN", 106, 15, revision=2,
                         task_ref={"issue_number": 42, "issue_id": 4002},
                         spec_ref={"kind": "issue_comment", **ref(spec)}, previous="s")
            with self.assertRaises(Conflict):
                run(rows+[s, o2], x)
