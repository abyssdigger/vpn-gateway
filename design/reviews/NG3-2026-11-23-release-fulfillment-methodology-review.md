# NG3 2026-11-23 — release model and implementation-fulfillment acceptance review

**Scope:** accept the new release-based development requirement branch, release methodology,
per-requirement component materialization status, and strengthened traceability guards.

**Requirements:** `VPNG-D001-R3*`  
**Architecture:** `design/NG3/architecture-ng.md`  
**Process:** `PROJECT-CONVENTIONS.md` §10  
**Implementation trace:** `design/NG3/implementation-traceability.md`  
**Reviewed head:** `5f65bcfc1886514d42793056d27a2f938c6db3b4`

## Verdict

**PASS — the release-development and implementation-fulfillment model is sufficient
architecture/process closure for `VPNG-D001-R3*`.**

The six new nodes may move from `pending_closure` to `closed`. This verdict closes the
method/process design. It does not claim that the first product release is being prepared now:
`VPNG-D001-R3.C1` explicitly keeps the current pre-first-release development state outside
mandatory release-candidate discipline.

## Findings and dispositions

### F1 — the new branch has a valid causal path from D001

**Decision:** accepted.  
**Resolution:** fixed.

`VPNG-D001-R3` no longer starts from versioning, release authority or evidence mechanics.
Its Purpose derives directly from D001's accepted need to keep product change and maintenance
safe and controllable in cost and result. The Statement introduces the release model itself.
Only descendants then introduce release numbering, prerelease fulfillment checking and the
separate release decision.

The touched D001/R1/R1.R1 wording was also made product-neutral where no VPN-GATE-specific
meaning exists.

### F2 — release identity, accounting and publication have one project methodology

**Decision:** accepted.  
**Resolution:** fixed.

`PROJECT-CONVENTIONS.md` §10 defines:

- Semantic Versioning 2.0.0 for actual release versions;
- root `VERSION` as the single canonical source once a concrete release is prepared;
- exact commit SHA as the reviewed source state;
- `v<version>` Git tag plus the project release record for publication/accounting;
- a required runtime/current-status version check before release;
- an explicit distinction between product-scope labels such as `Release-1` and actual
  release version numbers.

No `VERSION` file is created by this CDC because no actual release candidate is being
prepared; that is intentionally allowed by `VPNG-D001-R3.C1`.

### F3 — prerelease fulfillment review is a snapshot, not a second source of truth

**Decision:** accepted.  
**Resolution:** fixed.

The release review is tied to an exact candidate version and commit SHA, runs before the
separate release decision, and may send the candidate back to development. A source-state
change capable of affecting reviewed release properties requires a new review.

The current NG3 policy is `anomalies`: it reports requirement `pending_closure` /
`rejected_closure`, component requirement edges marked `partial` / `none`, and
contradictions where an architecture edge says `full` but implementation/evidence
traceability does not support it.

### F4 — materialization state is now attached to each component requirement edge

**Decision:** accepted.  
**Resolution:** fixed.

Every canonical component `Implements`, `Implements / supports`, or
`Supports implementation of` edge now carries exactly one of:

- `full`;
- `partial`;
- `none`.

The state belongs to the component contribution, not to the normative requirement itself.
It changes only when the materialization state or architecture obligation changes; ordinary
refactoring inside one state does not require editing architecture.

Known current gaps are now explicit rather than hidden behind one component-wide marker:

- A.011 / `VPNG-U004-R5` — `partial`;
- A.011 / `VPNG-U004-R5.R1` — `partial`: supported operator/control wiring is absent;
- A.011 / `VPNG-U004-R5.R4` — `partial`: one-shot reconciliation and safe leave exist,
  but finite-cadence periodic reconciliation does not;
- A.008 / `VPNG-D001-R3.R1.R1` — `none`: release version is not yet exposed in the
  supported current-state presentation, allowed until actual release preparation by R3.C1.

The old A.011 component-wide `<partial>` marker was removed. `<partial>` retains only its
architecture meaning for a component projection across Spaces.

### F5 — component lookup and trace guards now enforce the new structure

**Decision:** accepted.  
**Resolution:** fixed.

Canonical component headings are `## [A.011] ProtectiveModeManager`; ordinary mentions
remain `A.011`, while normal Markdown links such as `[A.011](...)` remain legal.

The same change also fixes the previously accepted consistency findings:

- C.010 now resides in Annex C;
- the §2.9 Annex-C example names C.001/C.002/C.003 correctly;
- all seven previously dropped component-local implementation edges are present in the full
  manifest;
- shared host-routing lower units are traced to both E.002 and E.004 where reused;
- the explicitly aggressive `release1_host_boundary.py` trace is no longer assigned to
  peaceful E.002;
- stale `postponed aggressive` production docstring wording is removed.

The strengthened traceability test now checks canonical headings, Annex/ID agreement,
materialization status presence, explanation of every non-full edge, and containment of every
component-local Implementation edge in the exhaustive manifest.

### F6 — full architecture language migration is deliberately separate

**Decision:** accepted.  
**Resolution:** deferred.

The existing `architecture-ng.md` still contains substantial inherited Russian/English
mixed prose predating this CDC. New and directly edited methodology text was cleaned where
practical, but a whole-document language migration would be a broad editorial diff unrelated
to the semantic release/fulfillment change.

**Re-entry gate:** a dedicated future CDC must perform the architecture language cleanup and
add stricter update-time language hygiene without changing architecture semantics.

## Evidence

Mechanical validation against reviewed head reported:

- canonical component specs: **26**;
- duplicate component IDs: **0**;
- Annex/ID mismatches: **0**;
- requirement edges without `full|partial|none`: **0**;
- non-full edges: exactly A.008/R3.R1.R1 plus A.011/R5, R5.R1 and R5.R4;
- component-local Python Implementation edges: **26**;
- local edges absent from the exhaustive manifest: **0**;
- production Python units: **112**;
- normal manifest units: **111**;
- explicit architecture debt units: **1**;
- uncovered production units: **0**.

GitHub Actions lineage guard run `45150331073` completed **SUCCESS** on the reviewed head.

The repository's full Python workflow is not configured to run on this working-branch push.
A local clone attempt could not run because the execution environment has no external DNS.
No product behavior was changed in this review block; executable source edits are docstring-only.
The new invariant test itself therefore remains to receive its first normal executable run
when the full workflow is next invoked.

## Status disposition

Move to `closed`:

- `VPNG-D001-R3`;
- `VPNG-D001-R3.R1`;
- `VPNG-D001-R3.R1.R1`;
- `VPNG-D001-R3.R2`;
- `VPNG-D001-R3.R3`;
- `VPNG-D001-R3.C1`.
