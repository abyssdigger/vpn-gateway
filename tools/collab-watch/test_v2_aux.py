import copy
import unittest

from core import Conflict, canonical, digest
from journal import SIGNAL_MARKER, SIGNAL_PROTOCOL
from test_project_tasks import row, ts
from test_split_journal import CFG, fixture
from split_journal import project_v2
from v2_aux import MARKER, PROTOCOL, project_aux

FENCE = chr(96)*3


def frame(marker, e):
    return marker + "\n" + FENCE + "json\n" + canonical(e) + "\n" + FENCE


def aux(mid, kind, cid, sender, recipient, room=34, **fields):
    role = CFG["roles"][sender]
    event = {"protocol": PROTOCOL, "journal_epoch": CFG["journal_epoch"],
             "event_id": mid, "kind": kind, "room": room, "from": sender,
             "to": [recipient], "incarnation": role["incarnation"], **fields}
    return row(cid, role["actor_id"], frame(MARKER, event), 25)


def target(mid, raw, room=34):
    return {"event_id": mid, "ref": f"issue:{room}#issuecomment-{raw['id']}",
            "body_sha256": digest(raw["body"])}


def handled(mid, cid, role, *targets):
    return aux(mid, "HANDLED", cid, role, role, handled=list(targets))


def pong(mid, cid, ping, **overrides):
    fields = {"ping_id": "p", "ping_ref": target("p", ping)["ref"],
              "ping_sha256": digest(ping["body"]), **overrides}
    return aux(mid, "PONG", cid, "BUILDER", "GUARD", **fields)


def signal(cid, mid, raw, sender, recipient, **overrides):
    t = target(mid, raw)
    obj = {"protocol": SIGNAL_PROTOCOL, "journal_epoch": CFG["journal_epoch"],
           "signal_id": f"s{cid}", "event_id": mid, "journal_ref": t["ref"],
           "journal_sha256": t["body_sha256"], "from": sender, "to": recipient,
           "incarnation": CFG["roles"][sender]["incarnation"], **overrides}
    return row(cid, CFG["roles"][sender]["actor_id"], frame(SIGNAL_MARKER, obj), 26)


class AuxTests(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(CFG)
        self.rows, issue = fixture()
        self.tasks = {"42": issue}
        self.holder = row(201, 12, "Ordinary holder request", 23)
        self.command = row(202, 12, "!COLLAB STOP cycle=test", 23)
        self.lookalike = row(203, 12, "!COLLAB STOP cycle=other", 23)
        self.p = aux("p", "PING", 301, "GUARD", "BUILDER", ping_id="p")
        self.q = pong("q", 302, self.p)

    def run_aux(self, extra=(), holders=(), signals=(), previous=None, cfg=None):
        return project_aux(cfg or self.cfg, {"34": self.rows + list(extra)},
                           self.tasks, list(holders), list(signals), previous)

    def test_task_equivalence_and_holder_classification(self):
        extra = [self.p, self.q]
        p, state = self.run_aux(extra, [self.holder, self.command, self.lookalike,
                                        row(204, 10, "worker", 23)])
        expected, expected_state = project_v2(self.cfg, {"34": self.rows + extra}, self.tasks)
        self.assertEqual(p["task"], expected)
        self.assertEqual(state["task"], expected_state)
        self.assertEqual(p["task"], self.run_aux()[0]["task"])
        self.assertEqual(p["holder_mailboxes"]["BUILDER"], ["issue:35#issuecomment-202"])
        self.assertEqual(p["holder_mailboxes"]["SPEC"], ["issue:35#issuecomment-202"])
        self.assertEqual(len(p["holder_mailboxes"]["GUARD"]), 3)
        self.assertEqual(p["holder_inputs"]["issue:35#issuecomment-202"]["event"]["command"]["id"], "STOP")
        self.assertIn("command_diagnostic", p["holder_inputs"]["issue:35#issuecomment-203"]["event"])
        self.assertEqual(p["authority"], "not evaluated; auxiliary coordination only")

    def test_holder_receipt_only_clears_one_role(self):
        h = handled("h", 310, "GUARD", target("holder:202", self.command, 35))
        p, _ = self.run_aux([h], [self.command])
        self.assertEqual(p["holder_mailboxes"]["GUARD"], [])
        self.assertEqual(p["holder_mailboxes"]["BUILDER"], ["issue:35#issuecomment-202"])
        self.assertEqual(p["holder_mailboxes"]["SPEC"], ["issue:35#issuecomment-202"])

    def test_exact_receipts_and_task_delivery(self):
        t = target("o", self.rows[0])
        h = handled("h", 310, "BUILDER", t)
        p, _ = self.run_aux([h])
        self.assertEqual(p["task"], self.run_aux()[0]["task"])
        self.assertEqual(len(p["handled"]), 1)
        for bad in (dict(t, event_id="wrong"), dict(t, ref="issue:34#issuecomment-999"),
                    dict(t, body_sha256="a"*64)):
            with self.subTest(bad=bad), self.assertRaises(Conflict):
                self.run_aux([handled("h", 310, "BUILDER", bad)])
        with self.assertRaises(Conflict):
            self.run_aux([handled("h", 310, "GUARD", t)])
        with self.assertRaises(Conflict):
            self.run_aux([h, handled("h2", 311, "BUILDER", target("h", h))])
        dup = dict(self.rows[0], id=199)
        self.rows.append(dup)
        s = signal(400, "o", dup, "SPEC", "BUILDER")
        self.assertEqual(self.run_aux([h], signals=[s])[0]["gc_candidates"], [])

    def test_health_exact_occurrence_and_no_mailbox_effect(self):
        duplicate = dict(self.p, id=303)
        p, _ = self.run_aux([self.p, duplicate, self.q], [self.command])
        self.assertEqual([x["state"] for x in p["health"]], ["matched", "pending"])
        self.assertEqual(p["holder_mailboxes"], self.run_aux(holders=[self.command])[0]["holder_mailboxes"])
        for bad in (pong("q", 302, self.p, ping_id="absent"),
                    pong("q", 302, self.p, ping_sha256="a"*64),
                    pong("q", 302, self.p, ping_ref="issue:99#issuecomment-301"),
                    aux("q", "PONG", 302, "SPEC", "GUARD", ping_id="p",
                        ping_ref=target("p", self.p)["ref"], ping_sha256=digest(self.p["body"]))):
            with self.assertRaises(Conflict):
                self.run_aux([self.p, bad])
        with self.assertRaises(Conflict):
            self.run_aux([self.q])
        h = handled("h", 310, "BUILDER", target("p", self.p))
        self.assertEqual(self.run_aux([self.p, self.q, h])[0]["health"],
                         self.run_aux([self.p, self.q])[0]["health"])
        cfg = dict(self.cfg, journal_rooms=[34, 36])
        cross = aux("q", "PONG", 302, "BUILDER", "GUARD", room=36, ping_id="p",
                    ping_ref=target("p", self.p)["ref"], ping_sha256=digest(self.p["body"]))
        with self.assertRaises(Conflict):
            project_aux(cfg, {"34": self.rows+[self.p], "36": [cross]}, self.tasks, [], [])

    def test_signal_task_aux_gc_and_quarantine(self):
        a = signal(400, "o", self.rows[0], "SPEC", "BUILDER")
        b = signal(401, "p", self.p, "GUARD", "BUILDER")
        h = handled("h", 310, "BUILDER", target("o", self.rows[0]), target("p", self.p))
        p, st = self.run_aux([self.p, h], signals=[a, b])
        self.assertEqual(len(p["gc_candidates"]), 2)
        self.assertEqual(len(self.run_aux([self.p], signals=[a, b])[0]["signal_status"]["valid"]), 2)
        bads = [signal(410, "p", self.p, "GUARD", "BUILDER", **kw)
                for kw in ({"journal_sha256": "a"*64}, {"to": "SPEC"},
                           {"journal_ref": "issue:34#issuecomment-999"}, {"incarnation": "bad"})]
        bads += [row(411, 10, "not framed", 26), signal(412, "h", h, "BUILDER", "BUILDER")]
        for bad in bads:
            q, st2 = self.run_aux([self.p, h], signals=[a, b, bad], previous=st)
            self.assertEqual(st2, st)
            self.assertEqual(q["task"], p["task"])
            self.assertEqual(len(q["signal_status"]["conflicts"]), 1)
            self.assertEqual(len(q["gc_candidates"]), 2)
        collision = signal(420, "o", self.rows[0], "SPEC", "BUILDER", signal_id="s401")
        q, _ = self.run_aux([self.p, h], signals=[b, collision])
        self.assertEqual(len(q["signal_status"]["conflicts"]), 2)
        self.assertEqual(q["gc_candidates"], [])
        q, st2 = self.run_aux([self.p, h], signals=[row(423, 999, "unknown", 26)], previous=st)
        self.assertEqual(st2, st)
        self.assertEqual(q["signal_status"]["ignored_external"], ["issue:37#issuecomment-423"])
        rotated = dict(self.cfg, signal_room=38)
        q, st2 = self.run_aux([self.p, h], previous=st, cfg=rotated)
        self.assertEqual(st2, st)
        self.assertEqual(q["task"], p["task"])
        self.assertEqual(q["health"], p["health"])
        self.assertEqual(q["gc_candidates"], [])

    def test_retained_identity_and_configuration(self):
        _, st = self.run_aux([self.p], [self.holder])
        for extra, holders in (([], [self.holder]), ([self.p], []),
                               ([dict(self.p, created_at=ts(26), updated_at=ts(26))], [self.holder]),
                               ([self.p], [dict(self.holder, body="edited", updated_at=ts(27))]),
                               ([dict(self.p, id=399)], [self.holder]),
                               ([self.p], [dict(self.holder, id=299)])):
            with self.assertRaises(Conflict):
                self.run_aux(extra, holders, previous=st)
        edited = dict(self.p, updated_at=ts(26))
        with self.assertRaises(Conflict):
            self.run_aux([edited])
        cfg = copy.deepcopy(self.cfg)
        cfg["projectholder"]["route_to"] = ["SPEC"]
        with self.assertRaises(Conflict):
            self.run_aux([self.p], [self.holder], previous=st, cfg=cfg)

    def test_aux_closed_wire_and_identity(self):
        for bad in (aux("o", "PING", 310, "GUARD", "BUILDER", ping_id="o"),
                    aux("holder:201", "PING", 310, "GUARD", "BUILDER", ping_id="holder:201"),
                    aux("p2", "PING", 310, "GUARD", "BUILDER", ping_id="p"),
                    aux("x", "PING", 310, "GUARD", "BUILDER", ping_id="x", payload_ref="x"),
                    aux("x", "DORMANT", 310, "GUARD", "BUILDER"),
                    aux("x", "PING", 310, "GUARD", "GUARD", ping_id="x"),
                    aux("p", "PING", 310, "BUILDER", "GUARD", ping_id="p"),
                    dict(self.p, body=self.p["body"].replace("/2 -->", "/3 -->")),
                    dict(self.p, user={"id": 11})):
            with self.subTest(bad=bad), self.assertRaises(Conflict):
                self.run_aux([self.p, bad])
        p, _ = self.run_aux([self.p, dict(self.p, id=399)])
        self.assertEqual(len(p["aux_facts"]), 2)
        self.assertEqual(self.run_aux([dict(self.p, user={"id": 999})])[0]["aux_facts"], {})
