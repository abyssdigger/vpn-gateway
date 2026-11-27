"""9c-A directed pure contract checks; supplied observations are not live proof."""
import copy
import hashlib
import unittest

from core import Conflict, canonical
from test_split_journal import CFG
from v2_deployment_manifest import (FIELDS, PIN, STORES, PATHS, PREDICATES, SCHEMA,
                                    COMMON, NEW, MAX_BYTES, inspect_contract)


def wire(value):
    return canonical(value).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture():
    # All values fictitious, no secrets or actual deployment parameters.
    m = {k: {f: None for f in spec} for k, spec in FIELDS.items()}
    m.update(schema=SCHEMA, mode="deployment", revision="r1")
    for k, spec in FIELDS.items():
        for f in spec:
            m[k][f] = "a"*64 if f.endswith("sha256") else k+"-"+f
    registry = {p: dict(observer="observer", adapter_sha256="b"*64,
                        anchor_sha256="c"*64) for p in PREDICATES}
    m["trust"].update(manifest_path="/trusted/manifest", evidence_registry_sha256=digest(wire(registry)))
    bindings = {"schema": "vpng-collab-role-bindings/2", "bindings": [
        dict(model="model-"+r, status="admitted",
             transport_pairs=[dict(transport_role=r, incarnation=v["incarnation"])],
             additional_responsibilities={}) for r, v in CFG["roles"].items()]}
    m["identity"].update(repository=CFG["repository"], epoch=CFG["journal_epoch"],
                         config_json=canonical(CFG), bindings_json=canonical(bindings))
    m["installation"].update(commit="a"*40, protocol=CFG["protocol"],
                             config_sha256=digest(wire(CFG)))
    m["isolation"].update(worker_uid=1001, worker_gid=1001, trusted_uid=1002,
                          trusted_gid=1002, worker_groups=[], trusted_groups=[])
    m["authority"]["lifetime"] = "maintained_fence"
    m["transport"]["kind"] = "reviewed_external"
    m["stores"] = {s: dict(store_id=s, path="/trusted/"+s, device=1, inode=i+1,
                           owner_uid=1002, mode="0600", kind="regular-single-link")
                   for i, s in enumerate(STORES)}
    m["targets"] = [dict(role="BUILDER", incarnation="b", actor_id=11,
                         operation="material_comment", room=42)]
    m["alternate_paths"] = {p: "excluded" for p in PATHS}
    m["evidence"] = {p: "ref-"+p for p in PREDICATES}
    return m, registry


def inputs(m, registry):
    raw = wire(m)
    root = dict(deployment_root=m["trust"]["deployment_root"],
                manifest_path=m["trust"]["manifest_path"], revision=m["revision"],
                manifest_sha256=digest(raw), registry=registry)
    obs = [dict(predicate=p, ref=m["evidence"][p], manifest_sha256=digest(raw),
                **registry[p], method="fixture", observation_sha256="d"*64,
                not_before=1, not_after=10, status="PASS") for p in sorted(PREDICATES)]
    return raw, wire(root), obs


def report(m, registry, *, omit=(), fail=(), now=2):
    raw, root, obs = inputs(m, registry)
    for o in obs:
        if o["predicate"] in fail:
            o["status"] = "FAIL"
    return inspect_contract(raw, expected_root=root,
                            observations=wire([o for o in obs if o["predicate"] not in omit]), now=now)


class DeploymentContractTests(unittest.TestCase):
    def test_complete_supplied_claims_are_only_contract_consistency(self):
        m, registry = fixture()
        r = report(m, registry)
        self.assertEqual(r.new_effect_blockers, ())
        self.assertEqual(r.recovery_only_blockers, ())
        self.assertFalse(hasattr(r, "live_admissible"))
        r = inspect_contract(wire(m))
        self.assertIn("external_root_missing", r.recovery_only_blockers)
        self.assertTrue(all("evidence:"+p in r.new_effect_blockers for p in PREDICATES))

    def test_design_unresolved_and_deployment_fail_closed(self):
        m, registry = fixture()
        m["mode"] = "design"
        m["environment"]["runtime_id"] = None
        r = inspect_contract(wire(m))
        self.assertIn("environment.runtime_id", r.unresolved)
        self.assertIn("design_only", r.new_effect_blockers)
        self.assertIn("unresolved_bindings", r.recovery_only_blockers)
        m["mode"] = "deployment"
        with self.assertRaises(Conflict):
            inspect_contract(wire(m))

    def test_all_alternate_path_counterexamples(self):
        for p in PATHS:
            with self.subTest(path=p):
                m, registry = fixture()
                m["alternate_paths"][p] = "present"
                r = report(m, registry)
                self.assertIn("alternate_path:"+p, r.new_effect_blockers)
                if p in ("read_credential", "mutable_bootstrap"):
                    self.assertIn("alternate_path:"+p, r.recovery_only_blockers)
                m["alternate_paths"][p] = "excluded"
                self.assertIn("evidence:"+p, report(m, registry, fail=(p,)).new_effect_blockers)
        m, registry = fixture()
        for p in ("aggregate_containment", "pair_mediation", "write_custody"):
            self.assertIn("evidence:"+p, report(m, registry, omit=(p,)).new_effect_blockers)

    def test_separate_recovery_contract_and_lifetime(self):
        m, registry = fixture()
        m["authority"]["lifetime"] = "point_in_time_revocable"
        r = report(m, registry, omit=NEW)
        self.assertIn("authority_lifetime", r.new_effect_blockers)
        self.assertEqual(r.recovery_only_blockers, ())
        r = report(m, registry, omit=("read_only_provider", "store_continuity"))
        self.assertIn("evidence:read_only_provider", r.recovery_only_blockers)
        self.assertIn("evidence:store_continuity", r.recovery_only_blockers)
        m["authority"]["lifetime"] = "bounded_irrevocable"
        self.assertEqual(report(m, registry).new_effect_blockers, ())

    def test_root_substitution_and_untrusted_observer(self):
        m, registry = fixture()
        raw, root, obs = inputs(m, registry)
        changed = copy.deepcopy(m)
        changed["revision"] = "r2"
        other_raw, _, other_obs = inputs(changed, registry)
        r = inspect_contract(other_raw, expected_root=root, observations=wire(other_obs), now=2)
        self.assertIn("external_root_mismatch", r.new_effect_blockers)
        obs[0]["anchor_sha256"] = "e"*64
        r = inspect_contract(raw, expected_root=root, observations=wire(obs), now=2)
        self.assertIn("evidence:"+obs[0]["predicate"], r.new_effect_blockers)
        changed_registry = copy.deepcopy(registry)
        changed_registry[obs[0]["predicate"]]["observer"] = "other"
        _, other_root, _ = inputs(m, changed_registry)
        self.assertIn("external_root_mismatch", inspect_contract(raw, expected_root=other_root).new_effect_blockers)

    def test_evidence_ref_not_pass_stale_or_wrong_manifest(self):
        m, registry = fixture()
        raw, root, obs = inputs(m, registry)
        obs[0]["manifest_sha256"] = "f"*64
        self.assertIn("evidence:"+obs[0]["predicate"], inspect_contract(
            raw, expected_root=root, observations=wire(obs), now=2).new_effect_blockers)
        self.assertTrue(all("evidence:"+p in report(m, registry, now=10).new_effect_blockers
                            for p in PREDICATES))

    def test_unknown_fields_types_duplicates_and_aliases(self):
        for edit in (
            lambda m: m.update(extra=True),
            lambda m: m["environment"].update(runtime_id=[]),
            lambda m: m["isolation"].update(worker_uid=True),
            lambda m: m["isolation"].update(worker_uid=m["isolation"]["trusted_uid"]),
            lambda m: m["credentials"].update(read_source=m["credentials"]["write_source"]),
            lambda m: m["stores"]["input"].update(inode=m["stores"]["attempt"]["inode"]),
            lambda m: m["targets"].append(copy.deepcopy(m["targets"][0])),
            lambda m: m["targets"][0].update(actor_id=999),
            lambda m: m["alternate_paths"].update(model_tools="maybe"),
            lambda m: m["evidence"].update(model_tools=m["evidence"]["brokers"]),
        ):
            m, registry = fixture()
            edit(m)
            with self.assertRaises(Conflict):
                inspect_contract(wire(m))
        for raw in (b'{"schema":1,"schema":2}', b'{} ', b'x'*(MAX_BYTES+1), b'\xff'):
            with self.assertRaises(Conflict):
                inspect_contract(raw)
        m, registry = fixture()
        raw, root, obs = inputs(m, registry)
        with self.assertRaises(Conflict):
            inspect_contract(raw, expected_root=root, observations=wire(obs+[obs[0]]), now=2)

    def test_synthetic_never_production_contract(self):
        m, registry = fixture()
        m["transport"]["kind"] = "synthetic"
        self.assertIn("synthetic_or_unbound_transport", report(m, registry).new_effect_blockers)


if __name__ == "__main__":
    unittest.main()
