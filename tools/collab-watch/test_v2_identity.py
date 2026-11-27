"""Staged v2 binding fixture; root migration is deliberately a later gate."""
import copy
import json
from pathlib import Path
import unittest

from core import Conflict
from v2_identity import IdentityConflict, SCHEMA, select_identity, validate_bindings

GUARD = "GPT-5.6 Sol"
BUILDER = "GPT-6.2"
G = {"transport_role": "GUARD", "incarnation": "guard-gpt56-sol-current"}
S = {"transport_role": "SPEC", "incarnation": "spec-gpt56-sol-v2"}
B = {"transport_role": "BUILDER", "incarnation": "builder-gpt62-current"}
PROPOSED = {"schema": SCHEMA, "bindings": [
    {"model": GUARD, "status": "admitted", "transport_pairs": [G, S],
     "additional_responsibilities": {"GUARD": ["SPEC"]}},
    {"model": BUILDER, "status": "admitted", "transport_pairs": [B],
     "additional_responsibilities": {}}
]}
V1 = json.loads((Path(__file__).resolve().parent/"pilot-config-m1.json").read_text())["roles"]
V2 = dict(V1, SPEC={"actor_id": V1["GUARD"]["actor_id"], "incarnation": S["incarnation"]})


class IdentityTests(unittest.TestCase):
    def test_staged_schema_and_current_v1(self):
        self.assertEqual(validate_bindings(PROPOSED), PROPOSED)
        self.assertEqual(select_identity(PROPOSED, GUARD, V1), {"model": GUARD, **G})
        self.assertEqual(select_identity(PROPOSED, GUARD, V1, selected_role="GUARD"), {"model": GUARD, **G})
        with self.assertRaisesRegex(IdentityConflict, "IDENTITY_CONFLICT"):
            select_identity(PROPOSED, GUARD, V1, selected_role="SPEC")

    def test_v2_explicit_selection_and_role_switch(self):
        with self.assertRaises(IdentityConflict):
            select_identity(PROPOSED, GUARD, V2)
        a = select_identity(PROPOSED, GUARD, V2, selected_role="GUARD")
        b = select_identity(PROPOSED, GUARD, V2, selected_role="SPEC")
        self.assertEqual(a, {"model": GUARD, **G})
        self.assertEqual(b, {"model": GUARD, **S})
        self.assertNotEqual(a["incarnation"], b["incarnation"])
        self.assertEqual(select_identity(PROPOSED, GUARD, V2, selected_role="GUARD"), a)
        # Output is detached, not active state or an authority token.
        a["incarnation"] = "modified"
        self.assertEqual(select_identity(PROPOSED, GUARD, V2, selected_role="GUARD"), {"model": GUARD, **G})
        self.assertEqual(set(b), {"model", "transport_role", "incarnation"})

    def test_builder_exact_and_no_cross_role(self):
        for active in (V1, V2):
            self.assertEqual(select_identity(PROPOSED, BUILDER, active), {"model": BUILDER, **B})
            for role in ("GUARD", "SPEC"):
                with self.assertRaises(IdentityConflict):
                    select_identity(PROPOSED, BUILDER, active, selected_role=role)
        for model in ("GPT-6.2 ", "gpt-6.2", "GPT-other", "", None, 6.2):
            with self.assertRaises(IdentityConflict):
                select_identity(PROPOSED, model, V2)

    def test_stale_missing_disabled_and_wrong_role_map(self):
        active = copy.deepcopy(V1)
        active["GUARD"]["incarnation"] = "stale"
        with self.assertRaises(IdentityConflict):
            select_identity(PROPOSED, GUARD, active)
        active = copy.deepcopy(V2)
        active["SPEC"]["incarnation"] = "stale"
        with self.assertRaises(IdentityConflict):
            select_identity(PROPOSED, GUARD, active, selected_role="SPEC")
        doc = copy.deepcopy(PROPOSED)
        doc["bindings"][0]["status"] = "disabled"
        with self.assertRaises(IdentityConflict):
            select_identity(doc, GUARD, V2, selected_role="GUARD")
        for roles in ({}, {"OTHER": {"actor_id": 10, "incarnation": "x"}},
                      {"GUARD": {"actor_id": True, "incarnation": G["incarnation"]}},
                      {"GUARD": {"actor_id": 10, "incarnation": G["incarnation"], "extra": 1}},
                      dict(V1, SPEC={"actor_id": 10, "incarnation": G["incarnation"]})):
            with self.assertRaises(IdentityConflict):
                select_identity(PROPOSED, GUARD, roles)
        for role in ("OTHER", "", ["SPEC"], {"transport_role": "SPEC"}):
            with self.assertRaises(IdentityConflict):
                select_identity(PROPOSED, GUARD, V2, selected_role=role)

    def test_whole_closed_binding_schema_rejects_malformed(self):
        cases = []
        def changed(fn):
            d = copy.deepcopy(PROPOSED)
            fn(d)
            cases.append(d)
        changed(lambda d: d.update(schema="vpng-collab-role-bindings/1"))
        changed(lambda d: d.update(epoch="forbidden"))
        changed(lambda d: d.update(bindings=[]))
        changed(lambda d: d["bindings"].append(copy.deepcopy(d["bindings"][0])))
        changed(lambda d: d["bindings"][1].update(model=" GPT-6.2"))
        changed(lambda d: d["bindings"][1].update(status="active"))
        changed(lambda d: d["bindings"][1].update(status=[]))
        changed(lambda d: d["bindings"][1].update(unknown=True))
        changed(lambda d: d["bindings"][1].update(transport_pairs=[]))
        changed(lambda d: d["bindings"][1]["transport_pairs"].append(dict(G)))
        changed(lambda d: d["bindings"][0]["transport_pairs"].append(dict(G, incarnation="second-guard")))
        changed(lambda d: d["bindings"][1]["transport_pairs"][0].update(incarnation=G["incarnation"]))
        changed(lambda d: d["bindings"][1]["transport_pairs"][0].update(transport_role="OTHER"))
        changed(lambda d: d["bindings"][1]["transport_pairs"][0].update(transport_role=[]))
        changed(lambda d: d["bindings"][1]["transport_pairs"][0].update(active=True))
        changed(lambda d: d["bindings"][1]["transport_pairs"][0].update(incarnation="bad space"))
        changed(lambda d: d["bindings"][0].update(additional_responsibilities={"BUILDER": ["SPEC"]}))
        changed(lambda d: d["bindings"][0].update(additional_responsibilities={"GUARD": ["OTHER"]}))
        changed(lambda d: d["bindings"][0].update(additional_responsibilities={"GUARD": ["SPEC","SPEC"]}))
        changed(lambda d: d["bindings"][0].update(additional_responsibilities={"GUARD": [[]]}))
        changed(lambda d: d["bindings"][0].update(status="disabled", transport_pairs=[]))
        for bad in cases:
            with self.subTest(bad=bad), self.assertRaises(IdentityConflict):
                # Even selecting GUARD must validate unrelated model rows.
                select_identity(bad, GUARD, V1, selected_role="GUARD")

    def test_additional_responsibility_is_not_transport_capability(self):
        doc = copy.deepcopy(PROPOSED)
        doc["bindings"][0]["transport_pairs"] = [G]
        self.assertEqual(select_identity(doc, GUARD, V2), {"model": GUARD, **G})
        with self.assertRaises(Conflict):
            select_identity(doc, GUARD, V2, selected_role="SPEC")

    def test_no_caller_supplied_incarnation_or_recovered_context(self):
        with self.assertRaises(TypeError):
            select_identity(PROPOSED, GUARD, V2, selected_role="SPEC", incarnation=S["incarnation"])
        with self.assertRaises(TypeError):
            select_identity(PROPOSED, GUARD, V2, recovered_context={"role": "SPEC"})
        active = copy.deepcopy(V2)
        active["SPEC"]["incarnation"] = "arbitrary"
        with self.assertRaises(IdentityConflict):
            select_identity(PROPOSED, GUARD, active, selected_role="SPEC")


if __name__ == "__main__":
    unittest.main()
