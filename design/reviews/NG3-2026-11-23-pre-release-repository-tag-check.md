# NG3 2026-11-23 — pre-release repository tag and historical-ref check

**Scope:** repository-level pre-release check of Git tags, snapshot-source identity, and historical
appendix/source refs before preparation of Release-1 / version `0.1.0`.

**Reviewed repository state:** `main` at
`35c837cd5e896dd439032ffa39f654abe74e6f6d`.

## Verdict

**PASS — the repository tag/history state contains no defect that requires recovery of product
semantics, architecture, implementation, or release-relevant evidence into current NG3.**

This is repository-history hygiene evidence. It does not replace the version-specific
release-fulfillment review required by `PROJECT-CONVENTIONS.md` §10 for the actual `0.1.0`
candidate.

## Snapshot-source verification

The audit baseline contained **217 Git tags**, including **185 `*snapshot*-source` tags**.
All snapshot-source tags were annotated.

Every snapshot-source tag was checked against the corresponding publication lineage. Each tag
either resolves to the explicit `Source tip:` recorded by its snapshot wrapper or, where that
metadata was absent, identifies a commit whose tree exactly matches the published snapshot state.

No checked source tag was found to point at a snapshot/republication wrapper when a different
real source commit had been established.

### Snapshot 131

Snapshot 131 remains the one intentional source-tag gap.

The published wrapper is
`27f7b9c673559d5a756d774b31621e53f71a7f57`, but no independently established source commit
was found for that publication. Therefore no `ng3-snapshot-131-source` tag is present. Keeping
that source identity unset is preferable to inventing an unsupported historical fact.

### Specific recovered lines

The restored NG1/NG2 source tags exact-tree match their corresponding canonical publications.

The RC2 recovered source tags also match their canonical publications:

- `rc2-snapshot-python-split-source`:
  `3c29e077…` -> canonical `1df594f7…`;
- `rc2-snapshot-archive-reviews-source`:
  `fc9c580a…` -> canonical `6b3ea5cc…`.

The named NG3 source tags after numbered snapshot 163 exact-tree match their published
`Snapshot ...` commits.

Snapshot 76 and snapshot 77 are consistent with their wrapper metadata: snapshot 76 records
source tip `de30358a…`, and snapshot 77 records source tip `762d7255…`.

## Historical appendix/source review

Historical appendix, `used-in`, superseded, and evidence refs were reviewed for unique content
that current NG3 might otherwise have lost.

No such content requires restoration into current product semantics or implementation.

Relevant historical material remains useful as evidence or experimental substrate where it
already lives. In particular:

- the EXP-015 MTU/MSS appendix contains substantial prepared experimental work but remains
  explicitly unproven and cannot justify production MTU/MSS policy;
- the historical availability false-negative line contains earlier hysteresis, sample identity,
  evidence-store, lifecycle, and quarantine approaches; the applicable semantics have either
  been re-materialized in the current model or deliberately superseded by current availability
  requirements;
- the NG2 EMPTY-slot/Executor work is represented in current make-before-break, transaction,
  observation, availability-priority, and committed-base semantics;
- the NG2 probing-route invariant is represented by current requirements and architecture:
  probing does not change payload route membership;
- historical NG3 host-return, configured-path-key, decomposition, NAT-observer, SNAT, and
  host-routing lines all have explicit current successors or explicit rejection/replacement
  decisions.

`minimal-working-alpha` is a projectholder-created historical marker. Its placement was
intentional, but no rationale or semantic definition was recorded for the tag. It must therefore
not be interpreted as the canonical “first functioning alpha” milestone; that milestone is
independently represented by the documented NG3 snapshot history.

## Pre-release disposition

Repository-history hygiene does not block Release-1 / `0.1.0` preparation.

The release candidate must still satisfy the current release methodology independently:
canonical `VERSION`, runtime/current-status version exposure, candidate-specific fulfillment
review, deployment/bundle validation, and a separate projectholder release decision.
