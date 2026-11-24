# NG3 2026-11-24 — release scope gate review

**Scope:** review the release-cycle correction that introduces an approved projectholder
release-scope contract before publication preparation.

**Process owner:** `PROJECT-CONVENTIONS.md` §10  
**Release-specific contract:** `release/0.1.0/RELEASE-SCOPE.md`  
**Failed prior attempt record:**
`design/reviews/NG3-0.1.0-2026-11-24-release-cycle-attempt-1-failure.md`

## Verdict

**PASS — the corrected release cycle now has an explicit product-scope gate before release
preparation and can distinguish normative permission from a stronger projectholder choice for a
particular release.**

## Findings and dispositions

### F1 — requirements/constraints alone did not encode the chosen scope of a specific release

**Decision:** accepted.  
**Resolution:** fixed.

A Constraint may permit a weaker release without requiring that weakness. The release process
therefore needs a release-specific projectholder contract rather than modifying the global
Requirement/Constraint tree.

`release/<version>/RELEASE-SCOPE.md` is now that contract.

### F2 — release preparation previously could start before the projectholder scope was recorded

**Decision:** accepted.  
**Resolution:** fixed.

An approved `RELEASE-SCOPE.md` is now a mandatory gate before candidate/publication
preparation, release QA/REQCOV/fulfillment work intended to support publication, or any
release-readiness claim.

The normal sequence is now:

`approved scope -> implementation/evidence closure -> release records/assets -> release branch
-> project snapshot/REQCOV -> QA -> freeze -> fulfillment review -> projectholder release
decision -> publication`.

### F3 — allowed requirement omissions and selected release omissions are different facts

**Decision:** accepted.  
**Resolution:** fixed.

REQCOV must now evaluate the candidate against **requirements + approved release scope**.

A Constraint that allows omission does not make an incomplete feature non-blocking when the
approved release scope explicitly requires that feature.

### F4 — the first 0.1.0 attempt used the wrong effective release frontier

**Decision:** accepted.  
**Resolution:** recorded as failed.

The first attempt treated `VPNG-U004-R5.C1` as sufficient to waive known A.011 partial
materialization. The projectholder had instead selected full Protective mode for Release-1 /
0.1.0.

The old QA/reviews remain historical evidence, but their readiness verdict cannot authorize
publication.

### F5 — the approved 0.1.0 scope is normative only for this release

**Decision:** accepted.

`RELEASE-SCOPE.md` does not globally strengthen or rewrite `VPNG-U004-R5.C1`. It records
that 0.1.0 does **not exercise** the omission permitted by that Constraint.

## Implementation consequence

The next 0.1.0 attempt is blocked until full A.011 / `VPNG-U004-R5*` materialization and
end-to-end evidence are complete.

Known blocking edges entering implementation are:

- `VPNG-U004-R5` — `partial`;
- `VPNG-U004-R5.R1` — `partial`;
- `VPNG-U004-R5.R4` — `partial`.

The existing `full` descendants remain subject to regression review as the missing orchestration
and lifecycle are completed.
