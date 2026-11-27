"""Selected-role composition over accepted v2 semantics, not a second reducer."""
import copy
import unittest
from unittest.mock import patch

from core import Conflict
from test_project_tasks import row
from test_split_journal import CFG, fixture
from test_v2_aux import aux, handled, pong, signal, target
from v2_aux import project_aux
from v2_identity import SCHEMA, IdentityConflict
from v2_scheduler import project_scheduler

G, B = "GPT-5.6 Sol", "GPT-6.2"


def bindings():
    def pair(role):
        return dict(transport_role=role, incarnation=CFG["roles"][role]["incarnation"])
    return {"schema": SCHEMA, "bindings": [
        dict(model=G, status="admitted", transport_pairs=[pair("GUARD"), pair("SPEC")],
             additional_responsibilities={"GUARD": ["SPEC"]}),
        dict(model=B, status="admitted", transport_pairs=[pair("BUILDER")],
             additional_responsibilities={})]}


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(CFG)
        self.rows, task = fixture()
        self.tasks = {"42": task}
        self.holder = row(201, 12, "ordinary request", 23)
        self.command = row(202, 12, "!COLLAB STOP cycle=test", 23)
        self.lookalike = row(203, 12, "!COLLAB STOP cycle=other", 23)
        self.holders = [self.holder, self.command, self.lookalike]
        self.p = aux("p", "PING", 301, "GUARD", "BUILDER", ping_id="p")
        self.q = pong("q", 302, self.p)
        self.s = signal(401, "p", self.p, "GUARD", "BUILDER")

    def obs(self, extra=(), signals=(), holders=None):
        return ({"34": self.rows + list(extra)}, self.tasks,
                self.holders if holders is None else holders, list(signals))

    def run_view(self, role, observation=None, previous=None, cfg=None):
        return project_scheduler(cfg or self.cfg, observation or self.obs(), previous,
                                 bindings(), B if role == "BUILDER" else G,
                                 selected_role=role)

    def test_exact_selection_and_role_projection(self):
        obs = self.obs()
        full, expected = project_aux(self.cfg, *obs)
        with self.assertRaises(IdentityConflict):
            project_scheduler(self.cfg, obs, None, bindings(), G)
        v, _ = project_scheduler(self.cfg, obs, None, bindings(), B)
        self.assertEqual(v["identity"]["transport_role"], "BUILDER")
        for role in ("BUILDER", "GUARD", "SPEC"):
            view, state = self.run_view(role)
            self.assertEqual(view["identity"], dict(model=B if role == "BUILDER" else G,
                                 transport_role=role, incarnation=self.cfg["roles"][role]["incarnation"]))
            self.assertEqual(view["work"]["task"], full["task"]["roles"][role])
            refs = full["holder_mailboxes"][role]
            self.assertEqual(view["work"]["holder_mailbox"], refs)
            self.assertEqual(view["work"]["holder_inputs"],
                             {ref: full["holder_inputs"][ref] for ref in refs})
            self.assertEqual(state, expected)

    def test_holder_commands_are_data_not_execution(self):
        guard, _ = self.run_view("GUARD")
        items = guard["work"]["holder_inputs"]
        self.assertEqual(items["issue:35#issuecomment-201"]["event"]["outcome"], "PRODUCT_MANAGER")
        self.assertEqual(items["issue:35#issuecomment-202"]["event"]["outcome"], "HOLDER_COMMAND")
        self.assertEqual(items["issue:35#issuecomment-202"]["event"]["command"]["id"], "STOP")
        self.assertEqual(items["issue:35#issuecomment-203"]["event"]["outcome"], "PRODUCT_MANAGER")
        self.assertEqual(guard["authority"], "not evaluated; observation only")
        self.assertEqual(guard["work"]["task"], self.run_view("GUARD", self.obs(holders=[]))[0]["work"]["task"])

    def test_handled_clears_only_exact_recipient(self):
        receipt = handled("h", 310, "GUARD", target("holder:202", self.command, 35))
        obs = self.obs([receipt])
        for role in ("GUARD", "SPEC", "BUILDER"):
            old, _ = self.run_view(role)
            new, _ = self.run_view(role, obs)
            refs = old["work"]["holder_mailbox"]
            if role == "GUARD":
                refs = [ref for ref in refs if ref != "issue:35#issuecomment-202"]
            self.assertEqual(new["work"]["holder_mailbox"], refs)
            self.assertEqual(new["work"]["task"], old["work"]["task"])

    def test_health_exact_physical_and_no_work_effect(self):
        for role, side in (("GUARD", "outgoing"), ("BUILDER", "incoming")):
            initial, _ = self.run_view(role)
            pending, _ = self.run_view(role, self.obs([self.p]))
            matched, _ = self.run_view(role, self.obs([self.p, self.q, dict(self.p, id=303)]))
            self.assertEqual(initial["work"], pending["work"])
            self.assertEqual(initial["work"], matched["work"])
            self.assertEqual(pending["health"][side][0]["state"], "pending")
            self.assertEqual([x["state"] for x in matched["health"][side]], ["matched", "pending"])
            self.assertEqual(matched["health"][side][0]["sender"], "GUARD")
            self.assertEqual(matched["health"][side][0]["ping_id"], "p")
            self.assertEqual(matched["health"][side][0]["ping_ref"], "issue:34#issuecomment-301")
        spec, _ = self.run_view("SPEC", self.obs([self.p, self.q]))
        self.assertEqual(spec["health"], {"incoming": [], "outgoing": []})

    def test_signal_gc_and_rotation_no_canonical_effect(self):
        receipt = handled("h", 310, "BUILDER", target("p", self.p))
        extra = [self.p, receipt]
        obs = self.obs(extra, [self.s])
        builder, state = self.run_view("BUILDER", obs)
        guard, _ = self.run_view("GUARD", obs)
        self.assertEqual(len(builder["signal_diagnostics"]["incoming"]), 1)
        self.assertEqual(len(guard["signal_diagnostics"]["outgoing"]), 1)
        self.assertEqual(builder["gc_evidence"], builder["signal_diagnostics"]["incoming"])
        self.assertFalse(guard["gc_evidence"])
        self.assertEqual(self.run_view("SPEC", obs)[0]["signal_diagnostics"]["incoming"], [])
        rotated, new_state = self.run_view("BUILDER", self.obs(extra), state,
                                          dict(self.cfg, signal_room=38))
        self.assertEqual(new_state, state)
        self.assertEqual(rotated["work"], builder["work"])
        self.assertEqual(rotated["health"], builder["health"])
        self.assertFalse(rotated["gc_evidence"])
        self.assertFalse(rotated["signal_diagnostics"]["incoming"])
        self.assertEqual(obs, self.obs(extra, [self.s]))  # no deletion

    def test_quarantine_is_actor_scoped_and_never_work(self):
        malformed = row(410, self.cfg["roles"]["GUARD"]["actor_id"], "not framed", 26)
        other = row(411, self.cfg["roles"]["SPEC"]["actor_id"], "not framed", 26)
        obs = self.obs([self.p], [self.s, malformed, other, row(412, 999, "unknown", 26)])
        plain, state = self.run_view("GUARD", self.obs([self.p]))
        guard, new_state = self.run_view("GUARD", obs, state)
        self.assertEqual(state, new_state)
        self.assertEqual(plain["work"], guard["work"])
        self.assertEqual([x["physical_ref"] for x in guard["signal_diagnostics"]["actor_scoped_quarantine"]],
                         ["issue:37#issuecomment-410"])
        builder, _ = self.run_view("BUILDER", obs)
        self.assertFalse(builder["signal_diagnostics"]["actor_scoped_quarantine"])
        self.assertEqual(len(builder["signal_diagnostics"]["incoming"]), 1)

    def test_previous_exact_and_conflict_propagates(self):
        obs = self.obs([self.p])
        _, previous = self.run_view("GUARD", obs)
        frozen = copy.deepcopy(previous)
        with patch("v2_scheduler.project_aux", wraps=project_aux) as project:
            _, returned = self.run_view("GUARD", obs, previous)
            self.assertIs(project.call_args.args[-1], previous)
            self.assertEqual(returned, project_aux(self.cfg, *obs, previous)[1])
        with self.assertRaises(Conflict):
            self.run_view("GUARD", self.obs(), previous)
        self.assertEqual(previous, frozen)

    def test_empty_work_not_stop_and_no_invented_fields(self):
        view, _ = self.run_view("SPEC", self.obs(holders=[]))
        self.assertEqual(set(view), {"identity", "work", "health", "signal_diagnostics",
                                     "gc_evidence", "authority"})
        self.assertEqual(set(view["work"]), {"task", "holder_mailbox", "holder_inputs"})
        self.assertFalse(view["work"]["holder_mailbox"])
        self.assertEqual(view["work"]["task"]["state"], "WAITING")
