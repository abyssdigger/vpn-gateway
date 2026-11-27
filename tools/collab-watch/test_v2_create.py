import copy
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from core import Conflict, canonical, digest
from test_split_journal import CFG, fixture, issue, opening
from test_v2_acquisition import ROOT, Response
from v2_compact import compact_v2
from v2_create import preflight_create, acquire_creation, verify_creation, marker, _normalize
from v2_preflight import preflight_initial_open_compact
from split_journal import project_v2

SPEC = {"selected_role": "SPEC", "selected_incarnation": "s"}
REQ = {"task": "O2", "revision": 1, "room": 34, "title": "Fresh task", "spec": "## Specification\n\nHuman prose"}


def resource(payload, number=43, iid=4003, actor=13):
    return dict(payload, number=number, id=iid, user={"id": actor}, state="open",
                url=ROOT+"/issues/"+str(number), repository_url=ROOT,
                created_at="2026-01-01T00:00:01Z", closed_at=None, closed_by=None)


class Inventory:
    def __init__(self, first, second=None, fixed=None, override=None):
        self.scans = [first, first if second is None else second]
        self.scan = -1
        self.fixed = fixed
        self.override = override
        self.calls = []

    def open(self, req, timeout):
        url = req.full_url
        self.calls.append(url)
        q = parse_qs(urlsplit(url).query)
        if q:
            page = int(q["page"][0])
            size = int(q["per_page"][0])
            if page == 1:
                self.scan += 1
            data = self.scans[self.scan][(page-1)*size:page*size]
            if self.override:
                return self.override(url, page, data)
            return Response(url, data)
        return Response(url, self.fixed if self.fixed is not None else self.scans[-1][0])


class CreationTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.task = fixture()
        self.control, self.tasks = {"34": self.rows}, {"42": self.task}
        self.baseline = compact_v2(CFG, self.control, self.tasks)
        self.proof, self.payload = preflight_create(CFG, self.baseline, 13, REQ, **SPEC)
        self.raw = resource(self.payload)
        self.effect = self.proof["effect"]

    def preflight(self, request=REQ, **kw):
        return preflight_create(CFG, self.baseline, kw.pop("actor", 13), request,
                                **dict(SPEC, **kw))

    def verify(self, physical=None, control=None, tasks=None, hint=None):
        return verify_creation(CFG, self.baseline, 13, REQ,
                               self.control if control is None else control,
                               self.tasks if tasks is None else tasks,
                               _normalize(CFG["repository"], self.raw) if physical is None else physical,
                               **SPEC, expected_proof_sha256=digest(canonical(self.proof)), hint=hint)

    def test_prospective_and_epoch_scoped_effect(self):
        p, payload = self.preflight(dict(REQ, title="Changed", spec="New prose"))
        self.assertEqual(p["effect"], self.effect)
        self.assertNotEqual(payload, self.payload)
        cfg = dict(CFG, journal_epoch="next-epoch")
        b = compact_v2(cfg, {"34": []}, {})
        p, _ = preflight_create(cfg, b, 13, REQ, **SPEC)
        self.assertNotEqual(p["effect"], self.effect)
        self.assertEqual(self.proof["body_sha256"], digest(self.payload["body"]))
        self.assertNotIn("issue_number", self.proof)
        for changed in (dict(REQ, task="O1"), dict(REQ, revision=2),
                        dict(REQ, room=37), dict(REQ, task="bad task"),
                        dict(REQ, title=""), dict(REQ, spec=""), dict(REQ, revision=True)):
            with self.assertRaises(Conflict):
                self.preflight(changed)
        for kw in ({"selected_role":"GUARD","selected_incarnation":"g","actor":10},
                   {"selected_incarnation":"wrong"}, {"actor":10}):
            with self.assertRaises(Conflict):
                self.preflight(**kw)

    def test_marker_and_identity_fail_closed(self):
        for changed in (dict(REQ, title="<!-- vpng-collab-task-create/1"),
                        dict(REQ, spec="text <!-- vpng-collab-task-create/2")):
            with self.assertRaises(Conflict):
                self.preflight(changed)
        for change in ({"body":"<!-- vpng-collab-task-create/1 broken"},
                       {"title":"changed"}, {"body": self.payload["body"]+" changed"},
                       {"user":{"id":10}}, {"pull_request":{}},
                       {"repository_url":"https://foreign.invalid"}):
            with self.subTest(change=change), self.assertRaises(Conflict):
                acquire_creation(CFG, self.effect, opener=Inventory([dict(self.raw, **change)]))

    def test_inventory_absence_unique_and_fixed(self):
        self.assertIsNone(acquire_creation(CFG, self.effect, opener=Inventory([]), expect_absent=True))
        p = acquire_creation(CFG, self.effect, opener=Inventory([self.raw]))
        self.assertEqual(p, _normalize(CFG["repository"], self.raw))
        for rows in ([], [self.raw, resource(self.payload,44,4004)],
                     [self.raw, dict(self.raw,id=999)], [self.raw, dict(self.raw,number=44)]):
            with self.assertRaises(Conflict):
                acquire_creation(CFG, self.effect, opener=Inventory(rows))
        with self.assertRaises(Conflict):
            acquire_creation(CFG,self.effect,opener=Inventory([self.raw]),expect_absent=True)
        with self.assertRaises(Conflict):
            acquire_creation(CFG,self.effect,opener=Inventory([self.raw],fixed=dict(self.raw,title="changed")))
        with self.assertRaises(Conflict):
            acquire_creation(CFG,self.effect,opener=Inventory([], [self.raw]))

    def test_full_page_bounds_and_links(self):
        other = resource({"title":"unrelated","body":None},44,4004)
        with patch("v2_create.PAGE",1):
            op = Inventory([self.raw,other])
            acquire_creation(CFG,self.effect,opener=op)
            self.assertEqual(sum("page=3" in url for url in op.calls),2)
            for key, val in (("MAX_PAGES",1),("MAX_PAGE_BYTES",10),
                             ("MAX_LOCAL_BYTES",10),("MAX_OBSERVED_COMMENTS",1)):
                with patch("v2_create."+key,val), self.assertRaises(Conflict):
                    acquire_creation(CFG,self.effect,opener=Inventory([self.raw,other]))
            def stuck(url,page,data):
                return Response(url,[self.raw])
            with self.assertRaises(Conflict):
                acquire_creation(CFG,self.effect,opener=Inventory([self.raw],override=stuck))
            def badlink(url,page,data):
                return Response(url,data,links=("broken",))
            with self.assertRaises(Conflict):
                acquire_creation(CFG,self.effect,opener=Inventory([self.raw],override=badlink))

    def test_receipt_and_initial_open_composition(self):
        result = self.verify(hint={"issue_number":43,"issue_id":4003})
        self.assertEqual(result["issue"], {"issue_number":43,"issue_id":4003})
        self.assertEqual(result["body_sha256"], digest(self.payload["body"]))
        self.assertEqual(len(project_v2(CFG,self.control,self.tasks)[0]["tasks"]),1)
        extra = issue(43,4003,self.payload["body"])
        extra["created_at"] = self.raw["created_at"]
        op = opening(extra,task="O2",mid="o2",cid=200,second=20)
        p = preflight_initial_open_compact(CFG,self.baseline,extra,13,op["body"],**SPEC)
        self.assertEqual(p["candidate"]["task_ref"],result["issue"])
        post = {"34":self.rows+[op]}
        self.verify(control=post,tasks=dict(self.tasks,**{"43":extra}))
        other = issue(44,4004,self.payload["body"])
        with self.assertRaises(Conflict):
            self.verify(control={"34":self.rows+[opening(other,task="O2",mid="o2",cid=200,second=20)]},
                        tasks=dict(self.tasks,**{"44":other}))
        with self.assertRaises(Conflict):
            self.verify(hint={"issue_number":44,"issue_id":4004})
