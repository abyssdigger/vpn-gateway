import copy
import itertools
import json
import unittest
from unittest.mock import patch

from core import Conflict, canonical, digest
from split_journal import project_v2
from test_split_journal import (CFG, SHA, candidate, close, control, disposition, fixture,
                                issue, material, opening, ref, row, ts)
from v2_compact import (compact_v2, decode_compact_v2, project_compact_v2, semantic_view,
                        compact_aggregate_v2, decode_compact_aggregate_v2,
                        aggregate_semantic_view, project_compact_aggregate_v2)
from v2_aux import project_aux
from test_v2_aux import aux, pong, handled, target, signal


class CompactV2Tests(unittest.TestCase):
    def equivalent(self, rows, task, previous=None):
        c, t = {"34": rows}, {"42": task}
        expected = project_v2(CFG, c, t, previous)
        packed = compact_v2(CFG, c, t, previous)
        decoded = decode_compact_v2(CFG, packed.text, packed.sha256, previous)
        self.assertEqual(decoded, packed)
        self.assertEqual(project_compact_v2(CFG, decoded, previous), expected)
        return packed, expected

    def test_full_lifecycle_and_retained_replay(self):
        rows, task = fixture(True)
        states = ["BUILDER_READY", "GUARD_REVIEW", "BUILDER_READY", "GUARD_REVIEW", "ACCEPTED"]
        previous = None
        for n, state in enumerate(states, 1):
            _, (projection, previous) = self.equivalent(rows[:n], task, previous)
            self.assertEqual(projection["tasks"][0]["state"], state)
        close(task)
        _, (projection, previous) = self.equivalent(rows, task, previous)
        self.assertEqual(projection["tasks"][0]["state"], "CLOSE_OBSERVED")
        rows.append(disposition(rows[-1], previous="v2"))
        packed, (projection, previous) = self.equivalent(rows, task, previous)
        self.assertEqual(projection["tasks"][0]["state"], "CLOSED")
        self.assertEqual(project_compact_v2(CFG, packed, previous)[0], projection)
        self.assertEqual(project_compact_v2(CFG, packed)[0], projection)

    def test_spec_revision(self):
        rows, task = fixture()
        sup = control("s", "DISPOSITION", 105, 12, open_id="o", previous="v1",
                      disposition="SUPERSEDED")
        spec = material(1200, "SPEC", 13, revision=2)
        task["comments"].append(spec)
        o2 = control("o2", "OPEN", 106, 15, revision=2, task_ref={"issue_number": 42, "issue_id": 4002},
                     spec_ref={"kind": "issue_comment", **ref(spec)}, previous="s")
        _, (_, previous) = self.equivalent(rows, task)
        _, (projection, _) = self.equivalent(rows+[sup, o2], task, previous)
        self.assertEqual(projection["tasks"][0]["revision"], 2)
        self.assertEqual(projection["tasks"][0]["state"], "BUILDER_READY")

    def test_multitask_permutation_and_duplicate_identity(self):
        rows, task = fixture()
        other = issue(43, 4003)
        rows += [opening(other, task="O2", mid="o2", cid=200), row(300, 10, "control prose", 19)]
        task["comments"].append(row(301, 11, "task prose", 19))
        baseline = compact_v2(CFG, {"34": rows}, {"42": task, "43": other})
        self.assertEqual(project_compact_v2(CFG, baseline),
                         project_v2(CFG, {"34": rows}, {"42": task, "43": other}))
        for permutation in itertools.permutations(rows):
            rev = dict(task, comments=list(reversed(task["comments"])))
            self.assertEqual(compact_v2(CFG, {"34": list(permutation)}, {"43": other, "42": rev}), baseline)
        duplicates = rows + [copy.deepcopy(rows[-1])]
        dup_task = dict(task, comments=task["comments"] + [copy.deepcopy(task["comments"][-1])])
        self.assertEqual(compact_v2(CFG, {"34": duplicates}, {"42": dup_task, "43": other}), baseline)
        conflict = copy.deepcopy(rows[-1])
        conflict["body"] += " conflict"
        with self.assertRaises(Conflict):
            compact_v2(CFG, {"34": rows+[conflict]}, {"42": task, "43": other})
        conflict = copy.deepcopy(task["comments"][-1])
        conflict["updated_at"] = ts(20)
        with self.assertRaises(Conflict):
            compact_v2(CFG, {"34": rows}, {"42": dict(task, comments=task["comments"]+[conflict]), "43": other})

    def test_keep_unreferenced_and_malformed_material_family(self):
        rows, task = fixture()
        extra = [material(1300, "RESULT", 20, attempt=2),
                 material(1301, "REVIEW", 21, attempt=2),
                 material(1302, "SPEC", 22, revision=2),
                 row(1303, 99, "<!-- vpng-collab-task-material/999\nunknown", 23),
                 row(1304, 99, "<!-- vpng-collab-task-material/2 malformed", 24)]
        task["comments"] += extra
        packed, _ = self.equivalent(rows[:1], task)
        _, semantic, _ = semantic_view(CFG, packed)
        self.assertEqual(semantic["42"]["comments"], task["comments"])
        for bad in ("<!-- vpng-collab-journal/999 -->", "<!-- vpng-collab-journal/2 -->\nbroken"):
            with self.assertRaises(Conflict):
                compact_v2(CFG, {"34": rows+[row(900, 10, bad, 30)]}, {"42": task})

    def test_opaque_inventory_and_no_promotion(self):
        rows, task = fixture()
        plain = row(1800, 11, "untyped result prose not material", 10)
        task["comments"].append(plain)
        control_prose = row(801, 10, "ordinary control discussion", 12)
        rows.append(control_prose)
        foreign = row(802, 99, rows[0]["body"], 13)
        rows.append(foreign)
        packed, expected = self.equivalent(rows, task)
        self.assertNotIn(plain["body"], packed.text)
        self.assertNotIn(control_prose["body"], packed.text)
        c, t, inventory = semantic_view(CFG, packed)
        self.assertEqual(inventory, packed.inventory_sha256)
        self.assertNotIn(1800, {r["id"] for r in t["42"]["comments"]})
        self.assertNotIn(801, {r["id"] for r in c["34"]})
        self.assertNotIn(802, {r["id"] for r in c["34"]})
        bad = control("fake", "RESULT", 901, 14, open_id="o", previous="o",
                      attempt=1, commit_sha=SHA, material_ref=ref(plain))
        # Exact ordinary-prose digest cannot promote it into typed material.
        with self.assertRaises(Conflict):
            project_v2(CFG, {"34": [c["34"][0], bad]}, t)
        for change in ("add", "remove", "body", "timestamp", "actor", "id"):
            rr, tt = copy.deepcopy(rows), copy.deepcopy(task)
            if change == "add":
                rr.append(row(803, 10, "extra ordinary prose", 22))
            elif change == "remove":
                tt["comments"].pop()
            elif change == "body":
                tt["comments"][-1]["body"] += " edited"
            elif change == "timestamp":
                tt["comments"][-1]["updated_at"] = ts(20)
            elif change == "actor":
                tt["comments"][-1]["user"]["id"] = 99
            else:
                tt["comments"][-1]["id"] += 1
            modified, result = self.equivalent(rr, tt)
            self.assertEqual(result, expected)
            self.assertNotEqual(modified.inventory_sha256, packed.inventory_sha256)
            self.assertNotEqual(modified.sha256, packed.sha256)

    def test_wire_integrity_and_partition_config_tamper(self):
        rows, task = fixture()
        task["comments"].append(row(1800, 11, "ordinary prose", 10))
        packed, _ = self.equivalent(rows, task)
        data = json.loads(packed.text)
        def decode_modified(value):
            wire = canonical(value)
            return decode_compact_v2(CFG, wire, digest(wire))
        for key, change in (("control", {}), ("control", dict(data["control"], **{"35": []})),
                            ("tasks", {}), ("tasks", dict(data["tasks"], **{"43": data["tasks"]["42"]}))):
            with self.subTest(key=key), self.assertRaises(Conflict):
                decode_modified(dict(data, **{key: change}))
        for key, value in (("id", 999), ("number", 43), ("repository", "foreign/repo"),
                           ("body", "changed"), ("closed_at", ts(20)),
                           ("events", [{"id": 1, "kind": "closed", "actor_id": 10, "created_at": ts(20)}])):
            damaged = copy.deepcopy(data)
            damaged["tasks"]["42"][key] = value
            with self.subTest(key=key), self.assertRaises(Conflict):
                decode_modified(damaged)
        for cfg_key, cfg_value in (("journal_epoch", "other"), ("repository", "other/repo"),
                                   ("signal_room", 88)):
            cfg = dict(CFG, **{cfg_key: cfg_value})
            with self.assertRaises(Conflict):
                decode_compact_v2(cfg, packed.text, packed.sha256)
        cfg = copy.deepcopy(CFG)
        cfg["roles"]["SPEC"]["incarnation"] = "other"
        with self.assertRaises(Conflict):
            decode_compact_v2(cfg, packed.text, packed.sha256)
        with self.assertRaises(Conflict):
            decode_compact_v2(CFG, packed.text, "0"*64)
        for wire in (packed.text+" ", packed.text.replace('"protocol":', '"protocol":"duplicate","protocol":', 1)):
            with self.assertRaises(Conflict):
                decode_compact_v2(CFG, wire, digest(wire))
        # Even shape-valid opaque alterations are caught by the independently
        # supplied original transfer digest; never claim provenance from rehashing.
        for pos, value in ((1, 1801), (2, 99), (3, ts(9)), (4, ts(11)), (5, "0"*64)):
            damaged = copy.deepcopy(data)
            damaged["tasks"]["42"]["comments"][-1][pos] = value
            with self.assertRaises(Conflict):
                decode_compact_v2(CFG, canonical(damaged), packed.sha256)
        damaged = copy.deepcopy(data)
        damaged["tasks"]["42"]["comments"].append(damaged["tasks"]["42"]["comments"][-1])
        with self.assertRaises(Conflict):
            decode_modified(damaged)
        damaged = copy.deepcopy(data)
        damaged["tasks"]["42"]["comments"][-1][-1] = "not a digest"
        with self.assertRaises(Conflict):
            decode_modified(damaged)

    def test_retained_drift_and_bounds(self):
        rows, task = fixture()
        packed, (_, previous) = self.equivalent(rows, task)
        task["comments"][0]["body"] += " edited"
        with self.assertRaises(Conflict):
            compact_v2(CFG, {"34": rows}, {"42": task}, previous)
        with self.assertRaises(Conflict):
            project_compact_v2(CFG, packed, dict(previous, semantic_config_hash="0"*64))
        with patch("v2_compact.MAX_LOCAL_BYTES", 10), self.assertRaises(Conflict):
            decode_compact_v2(CFG, packed.text, packed.sha256)
        with patch("v2_compact.MAX_OBSERVED_COMMENTS", 1), self.assertRaises(Conflict):
            decode_compact_v2(CFG, packed.text, packed.sha256)



class AggregateCompactTests(unittest.TestCase):
    def setUp(self):
        rows, task = fixture()
        self.ping = aux("p", "PING", 501, "GUARD", "BUILDER", ping_id="p")
        self.pong = pong("q", 502, self.ping)
        self.h = handled("h", 503, "BUILDER", target("p", self.ping))
        self.control = {"34": rows + [self.ping, self.pong, self.h, row(510, 10, "opaque control", 25)]}
        self.tasks = {"42": task}
        self.holder = [row(601, 12, "!COLLAB STOP cycle=test", 25),
                       row(602, 99, "opaque holder", 26)]
        self.signals = [signal(701, "p", self.ping, "GUARD", "BUILDER"),
                        row(702, 10, "quarantined signal prose", 26),
                        row(703, 99, "ignored external signal", 26)]

    def equivalent(self, control=None, tasks=None, holder=None, signals=None, previous=None, cfg=CFG):
        parts = (self.control if control is None else control,
                 self.tasks if tasks is None else tasks,
                 self.holder if holder is None else holder,
                 self.signals if signals is None else signals)
        expected = project_aux(cfg, *parts, previous)
        packed = compact_aggregate_v2(cfg, *parts, previous)
        self.assertEqual(decode_compact_aggregate_v2(cfg, packed.text, packed.sha256, previous), packed)
        self.assertEqual(project_compact_aggregate_v2(cfg, packed, previous), expected)
        return packed, expected

    def test_exact_round_trip_retained_and_diagnostics(self):
        packed, (p, previous) = self.equivalent()
        self.assertEqual(self.equivalent(previous=previous)[1], (p, previous))
        c, t, h, s, inventory = aggregate_semantic_view(CFG, packed)
        self.assertEqual(inventory, packed.inventory_sha256)
        self.assertEqual(h, self.holder[:1])
        self.assertEqual(s, self.signals)
        self.assertEqual(len(p["gc_candidates"]), 1)
        self.assertEqual(len(p["signal_status"]["conflicts"]), 1)
        self.assertEqual(len(p["signal_status"]["ignored_external"]), 1)
        self.assertIn(self.ping, c["34"])
        self.assertNotIn("opaque control", packed.text)
        self.assertNotIn("opaque holder", packed.text)
        self.assertEqual(t, self.tasks)
        self.assertEqual(self.equivalent(signals=[] , previous=previous)[1][1], previous)

    def test_rotation_and_config_transfer_binding(self):
        packed, (p, previous) = self.equivalent()
        cfg = dict(CFG, signal_room=38)
        rotated, (p2, state) = self.equivalent(signals=[], previous=previous, cfg=cfg)
        self.assertEqual(state, previous)
        self.assertEqual(p2["task"], p["task"])
        self.assertNotEqual(rotated.sha256, packed.sha256)
        with self.assertRaises(Conflict):
            decode_compact_aggregate_v2(cfg, packed.text, packed.sha256, previous)

    def test_opaque_inventory_identity(self):
        packed, expected = self.equivalent()
        for change in ("add", "remove", "body", "timestamp", "actor", "id"):
            holder = copy.deepcopy(self.holder)
            if change == "add":
                holder.append(row(603, 99, "extra opaque", 27))
            elif change == "remove":
                holder.pop()
            elif change == "body":
                holder[-1]["body"] += " changed"
            elif change == "timestamp":
                holder[-1]["updated_at"] = ts(27)
            elif change == "actor":
                holder[-1]["user"]["id"] = 98
            else:
                holder[-1]["id"] += 2
            new, actual = self.equivalent(holder=holder)
            self.assertEqual(actual, expected)
            self.assertNotEqual(new.inventory_sha256, packed.inventory_sha256)
            self.assertNotEqual(new.sha256, packed.sha256)

    def test_malformed_reserved_control_families_fail_both_paths(self):
        packed, _ = self.equivalent()
        for body in ("<!-- vpng-collab-journal/999 -->", "<!-- vpng-collab-aux/999 -->",
                     "<!-- vpng-collab-aux/2 -->\\nbroken"):
            bad = row(999, 10, body, 30)
            control = {"34": self.control["34"]+[bad]}
            with self.assertRaises(Conflict):
                project_aux(CFG, control, self.tasks, self.holder, self.signals)
            with self.assertRaises(Conflict):
                self.equivalent(control=control)
            obj = json.loads(packed.text)
            obj["control"]["34"].append(["raw", 999, 10, ts(30), ts(30), body])
            wire = canonical(obj)
            with self.assertRaises(Conflict):
                decode_compact_aggregate_v2(CFG, wire, digest(wire))

    def test_wire_bounds_and_closed_raw_partitions(self):
        packed, (_, previous) = self.equivalent()
        def decode(value):
            wire = canonical(value)
            return decode_compact_aggregate_v2(CFG, wire, digest(wire))
        for partition in ("holder", "signals"):
            value = json.loads(packed.text)
            value[partition][0][0] = "opaque"
            value[partition][0][-1] = digest(value[partition][0][-1])
            with self.assertRaises(Conflict):
                decode(value)
        for key in ("control", "tasks", "holder", "signals"):
            value = json.loads(packed.text)
            del value[key]
            with self.assertRaises(Conflict):
                decode(value)
        for n in (len(self.control["34"])+sum(len(t["comments"])+len(t["events"]) for t in self.tasks.values()),
                  len(self.control["34"])+sum(len(t["comments"])+len(t["events"]) for t in self.tasks.values())+len(self.holder)):
            with patch("v2_compact.MAX_OBSERVED_COMMENTS", n), self.assertRaises(Conflict):
                decode_compact_aggregate_v2(CFG, packed.text, packed.sha256)
        with patch("v2_compact.MAX_LOCAL_BYTES", len(packed.text.encode())-1), self.assertRaises(Conflict):
            decode_compact_aggregate_v2(CFG, packed.text, packed.sha256)
        with self.assertRaises(Conflict):
            decode_compact_aggregate_v2(CFG, packed.text, "0"*64)
        with self.assertRaises(Conflict):
            self.equivalent(holder=self.holder[1:], previous=previous)

    def test_old_wire_byte_compatibility_and_type_separation(self):
        old = compact_v2(CFG, self.control, self.tasks)
        # Existing task-only format remains exactly its original canonical shape.
        obj = json.loads(old.text)
        self.assertEqual(set(obj), {"protocol", "config_sha256", "control", "tasks"})
        self.assertEqual(obj["protocol"], "vpng-collab-compact-observation/2")
        self.assertEqual(next(r[0] for r in obj["control"]["34"] if r[1] == 501), "opaque")
        new, _ = self.equivalent()
        self.assertEqual(compact_v2(CFG, self.control, self.tasks), old)
        with self.assertRaises(Conflict):
            decode_compact_v2(CFG, new.text, new.sha256)
        with self.assertRaises(Conflict):
            decode_compact_aggregate_v2(CFG, old.text, old.sha256)
        with self.assertRaises(Conflict):
            project_compact_aggregate_v2(CFG, old)
        with self.assertRaises(Conflict):
            project_compact_v2(CFG, new)


if __name__ == "__main__":
    unittest.main()
