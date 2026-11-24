# NG3 2026-11-24 — frozen 0.1.0 QA isolation review

**Scope:** isolate the already published 0.1.0 release QA from unrelated current-line NG3 changes.

## Verdict

**PASS — frozen release QA now runs only when the frozen release subtree changes.**

## Findings and dispositions

### F1 — historical release validation was coupled to live NG3 sources

**Decision:** accepted.  
**Resolution:** fixed.

The 0.1.0 validator intentionally compares release records with the release project snapshot.
Running that validator after every later change to live NG3 requirements or architecture makes
legitimate post-release development fail historical release QA.

The frozen release snapshot itself is unchanged.

### F2 — release-subtree change detection is sufficient

**Decision:** accepted.  
**Resolution:** fixed.

The existing workflow now performs a full-history checkout only for this job, compares the
event base with HEAD under `release/0.1.0/**`, and runs the historical release validation,
documentation walkthrough and artifact upload only when that subtree changed.

On workflow run `45449667622`, the detection step passed and all three frozen-release QA
steps were skipped; the release job completed successfully.

## Result

Current NG3 development no longer requires rewriting the published 0.1.0 project snapshot.
