# NG3 review — active-main lineage split closure and future-main handoff

**Date:** 2026-11-17  
**Cycle:** `ng3-housekeeping-cycle-20261117-main-lineage-close-35m`  
**Baseline:** main snapshot 75, `b28f3e647d51b3c9f97190eb2daedaf253a68a88`

> **Corrective note — 2026-11-17:** the handoff below originally proposed applying only the
> `30 -> 31` delta to an empty tree. Validation of snapshot 32 proved that model invalid:
> snapshot 32 modifies generation-independent files already present before NG3. The accepted
> reconstruction basis is now the **full snapshot-31 tree after deterministic removal of
> inherited RC/NG1/NG2 generation payload**, followed by exact replay of later NG3-era commit
> deltas. See `NG3-2026-11-17-futuremain-root-model-correction-review.md`. The original
> empty-tree statement below is superseded and retained only as historical review context.

## Scope

This review closes the current repository-lineage housekeeping cycle on the existing
authoritative `main`.

It does not change product semantics, requirements, runtime behavior or the current main
ancestry.

The cycle records two already-proven facts:

1. active `main` has a clean NG3-only working tree and separated legacy CI; and
2. any later ancestry rewrite must be reconstructed on a separate branch from the exact
   preserved NG3 commit sequence, with `main` left untouched until review is complete.

## Closed active-main state

Main snapshot 75:

```text
commit b28f3e647d51b3c9f97190eb2daedaf253a68a88
tree   1297e5d42b7bb3816bfc6478b3ffc20549cf42e9
```

Legacy lines are separately preserved and tested:

```text
legacy-main-rc
legacy-main-ng1-2
legacy-main-ng3
```

The exact snapshot-75 main runs passed:

- Actual main lineage guard `44145601289`;
- NG3 Python `44145601265`.

Lineage guard evidence:

```text
ACTUAL_MAIN_LEGACY_ARTIFACTS=0
ACTUAL_MAIN_UNQUALIFIED_LEGACY_PATH_REFS=0
```

A direct tree audit found zero forbidden legacy paths.

## Future-main reconstruction basis

The preserved former-main history shows the NG3 numbered snapshot sequence beginning at
snapshot 31/44:

```text
30/44 d50652b7d2e8f671c18823ffcb588103257baa0d  pre-NG3 parent
31/44 edeac340fab70bfe8df3a5f2a034fdf3ca7af8be  first NG3 snapshot
...
44/44 d969290c75fe6d8a76d0dd7bf70ac99afc1c16e0
      211aefdc03a529162bb28385def6d21cc19db5aa  standalone AGENTS process commit
45    70f5d94f53954ecbba76c933adca587c0f8bd69f
...
74    a4183fc8a88fce1ba4d9942f8be201d286dd9322
```

The original `30 -> 31` delta was checked. It adds only four NG3 artifacts:

```text
design/NG3/architecture.md
design/NG3/requirements.md
design/reviews/NG3-2026-11-15-design-cycle-40m-checkpoint.md
design/reviews/NG3-2026-11-15-initial-requirements-architecture-review.md
```

Therefore snapshot 31 can naturally become a parentless reconstructed root by applying that
exact delta to an empty tree.

## Reconstruction invariant

The future candidate branch is not produced by copying the latest clean tree into one orphan
commit.

Instead, the historical NG3 commit sequence is replayed structurally:

```text
new #31 root
 -> new #32
 -> ...
 -> new #44
 -> new AGENTS process commit
 -> new #45
 -> ...
 -> new #74
 -> later current-line housekeeping snapshots
```

For every reconstructed commit:

```text
delta(reconstructed parent -> reconstructed commit)
==
delta(original parent -> original commit)
```

The comparison includes:

- path set;
- add/modify/delete/rename status;
- file mode;
- resulting file bytes for every changed path.

A mismatch is a hard stop condition. It is not fixed by editing the reconstructed commit to
make the sequence look plausible.

Meaningful inter-snapshot commits are retained. The standalone AGENTS commit between 44 and
45 is specifically required: omitting it would change the own delta of snapshot 45.

The full legacy trees are **not** expected to equal reconstructed trees because legacy trees
contain inherited RC/NG1/NG2 payload. Commit-delta equivalence is the identity criterion for
the NG3 line.

## Branch safety rule

The candidate branch may be named `futuremain`.

During reconstruction:

- current `main` remains authoritative and must not move;
- `legacy-main-*` refs remain immutable evidence inputs;
- no force-update of `main` is part of the reconstruction cycle;
- cutover, if ever accepted, is a later independent decision after a complete reconstruction
  manifest and CI review.

## Requirement-state check

No requirement change occurs in this housekeeping unit.

Mechanical check:

```text
normative R/C nodes: 159
closed:              159
pending_closure:       0
rejected_closure:      0
open:                  0
missing architecture references: 0
```

## Verdict

**ACCEPT.**

The active-main lineage split is a completed logical cycle. Snapshot 75 remains the safe
authoritative working line. The next independent cycle may construct `futuremain` from the
preserved NG3 sequence under strict per-commit delta equivalence, without modifying `main`.
