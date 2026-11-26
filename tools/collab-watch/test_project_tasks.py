import unittest

from core import Conflict, canonical, digest
from project_tasks import HEADER, comment, immutable, parse_header, stamp


def task_body(kind="RESULT", task="O1", revision=1, attempt=1, commit_sha="a"*40, verdict="ACCEPT"):
    meta = {"kind": kind, "task": task, "revision": revision}
    if kind != "SPEC":
        meta.update(attempt=attempt, commit_sha=commit_sha)
    if kind == "REVIEW":
        meta["verdict"] = verdict
    visible = ("Candidate SHA: " + commit_sha if kind == "RESULT" else
               "GUARD " + verdict + ": " + commit_sha if kind == "REVIEW" else "")
    return HEADER + "\n" + canonical(meta) + "\n-->\n" + (visible + "\n\n" if visible else "") + "Evidence/specification."


def ts(second):
    return f"2026-11-26T20:00:{second:02d}Z"


def row(cid, actor, body, second, updated=None):
    return {"id": cid, "user": {"id": actor}, "body": body, "created_at": ts(second),
            "updated_at": ts(second if updated is None else updated)}


class MaterialTests(unittest.TestCase):
    def test_exact_header_and_visible_identity(self):
        for kind in ("RESULT", "REVIEW", "SPEC"):
            self.assertEqual(parse_header(task_body(kind))["kind"], kind)
        body = task_body("REVIEW")
        for bad in (body.replace("GUARD ACCEPT:", "GUARD REWORK:"),
                    body.replace("GUARD ACCEPT: " + "a"*40, "GUARD ACCEPT: " + "b"*40),
                    body.replace('"revision":1', '"revision":true'),
                    body.replace('"revision":1', '"revision":1,"revision":1'),
                    body.replace("Evidence/specification.", ""),
                    "quoted\n" + body):
            with self.subTest(bad=bad), self.assertRaises(Conflict):
                parse_header(bad)

    def test_timestamp_immutable(self):
        immutable(comment(row(1, 10, "x", 3)))
        for bad in (row(1, 10, "x", 3, 4), row(1, 10, "x", 3, 2)):
            with self.assertRaises(Conflict):
                immutable(comment(bad))
        for bad in ("2026-02-30T00:00:00Z", "2026-01-01T00:00:00+00:00", None):
            with self.assertRaises(Conflict):
                stamp(bad)
