# NG3 2026-11-22 — legacy flat architecture retirement review

**Scope:** retire `design/NG3/architecture.md` as a current-content carrier after residual
analysis and transfer of the last architecture-level decision.

## Verdict

**PASS — flat architecture body can be removed from the current tree.**

## Checks

- `design/NG3/architecture-ng.md` remains the sole authoritative current architecture.
- All current architecture component/API/interaction semantics formerly represented by the
  flat report have structured owners.
- The old §15 deliberate-omission decision is now represented in structured §2.9.4.
- Concrete Linux pools, raw JSON/argv facts, internal result names and CI run IDs are confirmed
  as lower implementation/evidence material, not missing architecture.
- Historical S1–S6 scenario prose is explanatory verification history, not an unrepresented
  normative contract.
- Current active documents that mention the old path are limited to the structured
  architecture authority notice and CHANGELOG lineage statement; both are updated for the
  tombstone state. Historical review/research/evidence references are intentionally preserved.
- The last full flat body is preserved by Git history at
  `38607e247f39a87a361a4541e3dace6585c8d52a`.
- The current `design/NG3/architecture.md` path is removed rather than retained as a tombstone.

## Requirement impact

No Requirement/Constraint meaning or closure status changes.

The retirement removes a duplicate/stale documentation surface; it does not change product
behavior or implementation.
