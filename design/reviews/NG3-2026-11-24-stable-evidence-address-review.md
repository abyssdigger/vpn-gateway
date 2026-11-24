# NG3 2026-11-24 — stable architecture evidence-address review

**Scope:** replace direct experiment references in stable NG3 architecture with stable evidence
addresses.

## Verdict

**PASS — stable architecture now references executable/review evidence only through EV IDs.**

## Findings and dispositions

### F1 — direct experiment references violated architecture §2.9.1

**Decision:** accepted.  
**Resolution:** fixed.

All direct `EXP-*` references were removed from `design/NG3/architecture-ng.md`. Three
stable evidence entries now cover the distinct facts:

- `EV-00020` — private-peer observation versus transport provenance;
- `EV-00030` — protective containment selection;
- `EV-00040` — aggressive routing authority and escape protection.

The concrete experiment identities remain inside `design/NG3/evidence-index.md` and its
linked reviews.

### F2 — the invariant is mechanically enforced

**Decision:** accepted.  
**Resolution:** fixed.

`test_architecture_traceability.py` now rejects any `EXP-<number>` token in the stable
architecture. Unit/traceability on commit `f1d9a2855d46dd3756b19878be376e0ad44b0773`
passes in NG3 Python run `45450326677`.

The frozen 0.1.0 release job also completes successfully under the separately fixed release-QA
scope detection.

## Result

No unresolved finding remains in this review unit.
