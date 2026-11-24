# NG3 2026-11-23 — release artifact model review

**Scope:** review the project release-methodology refinement introduced from the first
Release-1 / 0.1.0 preparation experience.

**Governing requirement:** `VPNG-D001-R3*`  
**Process owner:** `PROJECT-CONVENTIONS.md` §10  
**Reviewed process head:** `2c1ccd401dcc8ef979375842968710aa17660df7`

## Verdict

**PASS — the refined release artifact model is consistent with the existing release-development
requirements and may govern 0.1.0 finalization.**

No product requirement semantics need to change. `VPNG-D001-R3.R1/R2/R3` already require a
release identity, source-state binding, aggregate implementation-fulfillment check, and a
separate release decision; the new rules make the project records/assets needed to perform those
obligations reproducibly explicit.

## Findings and dispositions

### F1 — the previous model preserved the reviewed source identity but not a complete release snapshot

**Decision:** accepted.  
**Resolution:** fixed.

The previous §10 required `VERSION`, exact SHA, fulfillment review, release tag and release
record, but did not require a full per-release requirements coverage artifact, a QA report, or a
snapshot of the project documents used for the decision.

The refined model requires:

- product bundle + checksum;
- `QA-REPORT.md`;
- full `REQUIREMENTS-COVERAGE.md`;
- project snapshot containing current requirements, architecture and changelog;
- project-snapshot archive + checksum;
- required deployment documentation.

### F2 — anomaly review and full release coverage have different purposes

**Decision:** accepted.  
**Resolution:** fixed.

The `anomalies` fulfillment policy remains useful as a compact release gate, but it does not
show the disposition of every current normative R/C.

The new `REQUIREMENTS-COVERAGE.md` therefore covers every normative requirement/constraint
independently of the anomaly policy and distinguishes at least:

- `covered` for accepted `closed` scope;
- `excluded-postponed` for scope outside the current release frontier;
- `conformance-applicable` for `permanent` obligations;
- explicit release treatment for any open/pending/rejected state if one exists.

This does not create a second requirement-status model.

### F3 — release-branch staging must not become release identity

**Decision:** accepted.  
**Resolution:** fixed.

`release/<version>` is a staging/record branch. The immutable release identity remains
`v<version>` on the exact reviewed candidate SHA plus the release record/assets.

The release branch may therefore be removed after publication without losing release identity.

### F4 — fulfillment review must not create a self-referential candidate SHA

**Decision:** accepted.  
**Resolution:** fixed.

The first draft of the refinement still allowed an ambiguous interpretation where committing
the fulfillment-review artifact onto the release branch would move the SHA being reviewed.

The corrected model freezes `release/<version>` before fulfillment review. The review is then
recorded separately in project history without moving that branch. A positive release decision
causes `v<version>` to point to the frozen reviewed SHA.

### F5 — Git authorization remains owned by AGENTS.md

**Decision:** accepted.  
**Resolution:** fixed.

The release methodology describes branch/artifact lifecycle but explicitly delegates permission
to create/delete/move refs to `AGENTS.md`. It does not create a parallel Git authorization
path.

## Disposition

Use the refined §10 model for finalization of `0.1.0`.

The previous 0.1.0 candidate QA and fulfillment records remain historical evidence. Final
release preparation must create the complete release branch/artifact set, full requirements
coverage and project snapshot, then perform/apply the required QA and a new fulfillment review
against the frozen final release candidate.
