"""Ephemeral timer policy tested using admitted selected-role observations."""
import copy
import unittest

from core import Conflict
from test_split_journal import CFG, fixture
from test_v2_aux import aux, handled, pong, signal, target
from test_v2_scheduler import B, G, bindings
from v2_health import advance_health, IDLE_MS, RESPONSE_MS
from v2_scheduler import project_scheduler


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(CFG)
        self.rows, task = fixture()
        self.tasks = {"42": task}
        self.p = aux("p", "PING", 301, "GUARD", "BUILDER", ping_id="p")
        self.p2 = aux("p2", "PING", 302, "GUARD", "BUILDER", ping_id="p2")
        self.p3 = aux("p3", "PING", 303, "GUARD", "BUILDER", ping_id="p3")
        self.q = pong("q", 310, self.p)
        self.h = handled("h", 311, "BUILDER", target("p", self.p))
        self.incoming = aux("incoming", "PING", 312, "BUILDER", "GUARD", ping_id="incoming")

    def view(self, extra=(), rows=None, signals=(), role="GUARD", cfg=None):
        control = list(self.rows if rows is None else rows) + list(extra)
        obs = ({"34": control}, self.tasks, [], list(signals))
        return project_scheduler(cfg or self.cfg, obs, None, bindings(),
                                 B if role == "BUILDER" else G, selected_role=role)[0]

    def advance(self, view, prior, now, peer="BUILDER"):
        frozen = copy.deepcopy((view, prior))
        state, intents = advance_health(view, prior, now)
        self.assertEqual((view, prior), frozen)
        return state, [i for i in intents if i["peer"] == peer]

    def mode(self, state, peer="BUILDER"):
        return state["peers"][peer]["episode"]["mode"]

    def test_idle_boundaries_and_proposal_is_not_admission(self):
        view = self.view()
        s, intents = self.advance(view, None, 10_000_000)
        self.assertEqual(intents, [])
        self.assertEqual(self.mode(s), "IDLE")
        s, intents = self.advance(view, s, 10_000_000 + IDLE_MS - 1)
        self.assertEqual(intents, [])
        s, intents = self.advance(view, s, 10_000_000 + IDLE_MS)
        self.assertEqual(intents, [{"kind": "PING_DUE", "peer": "BUILDER"}])
        self.assertEqual(self.mode(s), "PING_INTENT_EMITTED")
        unchanged, intents = self.advance(view, s, s["last_now_ms"])
        self.assertEqual(unchanged, s)
        self.assertEqual(intents, [])
        s, intents = self.advance(view, s, 50_000_000)
        self.assertEqual(intents, [])
        self.assertEqual(self.mode(s), "PING_INTENT_EMITTED")

    def test_admitted_ping_response_boundary_and_latch(self):
        view = self.view()
        s, _ = self.advance(view, None, 0)
        s, _ = self.advance(view, s, IDLE_MS)
        observed = self.view([self.p])
        start = IDLE_MS + 900
        s, intents = self.advance(observed, s, start)
        self.assertEqual(intents, [])
        self.assertEqual(self.mode(s), "WAITING_RESPONSE")
        s, intents = self.advance(observed, s, start + RESPONSE_MS - 1)
        self.assertEqual(intents, [])
        s, intents = self.advance(observed, s, start + RESPONSE_MS)
        self.assertEqual(intents, [{"kind": "COMMUNICATION_UNCONFIRMED", "peer": "BUILDER",
                                    "ping_id": "p", "ping_ref": target("p", self.p)["ref"]}])
        self.assertEqual(self.mode(s), "UNCONFIRMED")
        s2, intents = self.advance(observed, s, s["last_now_ms"])
        self.assertEqual(s2, s)
        self.assertEqual(intents, [])
        s, intents = self.advance(observed, s, 9_000_000)
        self.assertEqual(intents, [])
        self.assertEqual(self.mode(s), "UNCONFIRMED")

    def test_restart_one_pending_and_matched_history(self):
        view = self.view([self.p])
        s, intents = self.advance(view, None, 2_000_000)
        self.assertEqual(intents, [])
        self.assertEqual(self.mode(s), "WAITING_RESPONSE")
        s, intents = self.advance(view, s, 2_299_999)
        self.assertEqual(intents, [])
        _, intents = self.advance(view, s, 2_300_000)
        self.assertEqual(intents[0]["kind"], "COMMUNICATION_UNCONFIRMED")
        s, intents = self.advance(self.view([self.p, self.q]), None, 2_300_000)
        self.assertEqual(intents, [])
        self.assertEqual(self.mode(s), "IDLE")

    def test_restart_ambiguity_and_duplicate_physical_ping(self):
        duplicate = dict(self.p, id=304)
        view = self.view([self.p, duplicate])
        s, intents = self.advance(view, None, 100)
        self.assertEqual(self.mode(s), "AMBIGUOUS")
        self.assertEqual(intents, [{"kind": "HEALTH_EPISODE_AMBIGUOUS", "peer": "BUILDER",
                                    "ping_refs": (target("p", self.p)["ref"],
                                                  target("p", duplicate)["ref"])}])
        s, intents = self.advance(view, s, 10_000_000)
        self.assertEqual(intents, [])
        self.assertEqual(self.mode(s), "AMBIGUOUS")
        with self.assertRaises(Conflict):
            self.advance(self.view([self.p, duplicate, self.p2]), s, 10_000_001)
        s, intents = self.advance(self.view([self.p, duplicate, self.h]), s, 10_000_001)
        self.assertEqual(intents, [])
        self.assertEqual(self.mode(s), "IDLE")

    def test_second_ping_ambiguity_and_suppressed_conflict(self):
        view = self.view([self.p])
        s, _ = self.advance(view, None, 0)
        s, intents = self.advance(self.view([self.p, self.p2]), s, 1)
        self.assertEqual(self.mode(s), "AMBIGUOUS")
        self.assertEqual(intents[0]["ping_refs"],
                         (target("p", self.p)["ref"], target("p2", self.p2)["ref"]))
        with self.assertRaises(Conflict):
            self.advance(self.view([self.p, self.p2, self.p3]), s, 2)
        s, _ = self.advance(view, None, 0)
        s, _ = self.advance(view, s, RESPONSE_MS)
        with self.assertRaises(Conflict):
            self.advance(self.view([self.p, self.p2]), s, RESPONSE_MS + 1)
        s, _ = self.advance(self.view(), None, 0)
        s, intents = self.advance(self.view([self.p, self.p2]), s, 1)
        self.assertEqual(self.mode(s), "AMBIGUOUS")
        self.assertEqual(len(intents), 1)

    def test_peer_task_fact_at_due_boundary_and_unconfirmed_reset(self):
        before = self.view([self.p], rows=self.rows[:1])
        after = self.view([self.p], rows=self.rows[:2])
        s, _ = self.advance(before, None, 0)
        s, intents = self.advance(after, s, RESPONSE_MS)
        self.assertEqual(intents, [])
        self.assertEqual(self.mode(s), "IDLE")
        s, _ = self.advance(before, None, 0)
        s, _ = self.advance(before, s, RESPONSE_MS)
        self.assertEqual(self.mode(s), "UNCONFIRMED")
        s, intents = self.advance(after, s, RESPONSE_MS + 1)
        self.assertEqual(intents, [])
        self.assertEqual(self.mode(s), "IDLE")
        s, intents = self.advance(after, s, RESPONSE_MS + IDLE_MS + 1)
        self.assertEqual(intents, [{"kind": "PING_DUE", "peer": "BUILDER"}])

    def test_each_peer_aux_kind_restores_and_wins_over_new_ping(self):
        for fact in (self.h, self.incoming, self.q):
            with self.subTest(fact=fact["id"]):
                before = self.view([self.p])
                after = self.view([self.p, self.p2, fact])
                s, _ = self.advance(before, None, 0)
                s, intents = self.advance(after, s, RESPONSE_MS)
                self.assertEqual(intents, [])
                self.assertEqual(self.mode(s), "IDLE")
                s, intents = self.advance(after, s, RESPONSE_MS + IDLE_MS - 1)
                self.assertEqual(intents, [])
                s, intents = self.advance(after, s, RESPONSE_MS + IDLE_MS)
                self.assertEqual(intents, [{"kind": "PING_DUE", "peer": "BUILDER"}])
                s, intents = self.advance(self.view([self.p, self.p2, self.p3, fact]), s,
                                          RESPONSE_MS + IDLE_MS + 1)
                self.assertEqual(intents, [])
                self.assertEqual(s["peers"]["BUILDER"]["episode"]["ping_id"], "p3")

    def test_idle_due_peer_fact_wins_and_other_peer_is_independent(self):
        before = self.view(rows=self.rows[:1])
        after = self.view(rows=self.rows[:2])
        s, _ = advance_health(before, None, 0)
        s, intents = advance_health(after, s, IDLE_MS)
        self.assertEqual(intents, [{"kind": "PING_DUE", "peer": "SPEC"}])
        self.assertEqual(self.mode(s), "IDLE")
        self.assertEqual(self.mode(s, "SPEC"), "PING_INTENT_EMITTED")

    def test_signal_only_changes_do_not_refresh(self):
        incoming = self.incoming
        sig = signal(401, "incoming", incoming, "BUILDER", "GUARD")
        before = self.view([incoming])
        after = self.view([incoming], signals=[sig])
        s, _ = self.advance(before, None, 0)
        s, intents = self.advance(after, s, IDLE_MS - 1)
        self.assertEqual(intents, [])
        s, intents = self.advance(before, s, IDLE_MS)
        self.assertEqual(intents, [{"kind": "PING_DUE", "peer": "BUILDER"}])

    def test_observation_loss_digest_drift_identity_and_clock(self):
        view = self.view([self.p])
        s, _ = self.advance(view, None, 100)
        for now in (99, -1, True, 1.0):
            with self.subTest(now=now), self.assertRaises(Conflict):
                self.advance(view, s, now)
        variants = []
        for field, value in (("transport_role", "SPEC"), ("incarnation", "other")):
            bad = copy.deepcopy(view)
            bad["identity"][field] = value
            variants.append(bad)
        bad = copy.deepcopy(view)
        del bad["peer_journal_inventory"]["SPEC"]
        variants.append(bad)
        variants.append(self.view())
        for action in ("remove", "change"):
            bad = copy.deepcopy(view)
            if action == "remove":
                bad["peer_journal_inventory"]["BUILDER"].pop()
            else:
                bad["peer_journal_inventory"]["BUILDER"][0]["body_sha256"] = "0"*64
            variants.append(bad)
        bad = copy.deepcopy(view)
        bad["health"]["outgoing"][0]["body_sha256"] = "0"*64
        variants.append(bad)
        for bad in variants:
            with self.assertRaises(Conflict):
                self.advance(bad, s, 101)

    def test_order_and_shared_actor_no_cross_peer_attribution(self):
        cfg = copy.deepcopy(self.cfg)
        for role in cfg["roles"]:
            cfg["roles"][role]["actor_id"] = 10
        self.tasks["42"]["author_id"] = 10
        for material in self.tasks["42"]["comments"]:
            material["user"] = {"id": 10}
        control = [dict(raw, user={"id": 10}) for raw in self.rows + [self.p]]
        view = self.view(rows=control, cfg=cfg)
        reverse = self.view(rows=list(reversed(control)), cfg=cfg)
        s, intents = advance_health(view, None, 0)
        self.assertEqual((s, intents), advance_health(reverse, None, 0))
        self.assertEqual(set(s["peers"]), {"BUILDER", "SPEC"})
        self.assertEqual(self.mode(s), "WAITING_RESPONSE")
        self.assertEqual(self.mode(s, "SPEC"), "IDLE")
        self.assertEqual(set(s), {"role", "incarnation", "last_now_ms", "peers"})
        self.assertEqual(set(s["peers"]["BUILDER"]), {"peer_refs", "outgoing_refs", "episode"})
        self.assertEqual(set(s["peers"]["BUILDER"]["episode"]),
                         {"mode", "baseline_ms", "ping_ref", "ping_id", "ambiguous_refs"})
        empty = self.view(rows=[])
        s, _ = advance_health(empty, None, 0)
        _, intents = advance_health(empty, s, IDLE_MS)
        self.assertEqual(intents, [{"kind": "PING_DUE", "peer": "BUILDER"},
                                   {"kind": "PING_DUE", "peer": "SPEC"}])
