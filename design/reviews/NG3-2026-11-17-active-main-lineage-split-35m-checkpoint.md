# NG3 35m checkpoint — close active-main lineage cycle

**Date:** 2026-11-17  
**Branch:** `ng3-housekeeping-cycle-20261117-main-lineage-close-35m`  
**Baseline main:** snapshot 75, `b28f3e647d51b3c9f97190eb2daedaf253a68a88`

## Closed logical unit

The repository-lineage split on current `main` is complete.

The accepted current working state is:

```text
main snapshot 75
commit b28f3e647d51b3c9f97190eb2daedaf253a68a88
tree   1297e5d42b7bb3816bfc6478b3ffc20549cf42e9
```

It has:

- no physical RC/NG1/NG2 generation trees;
- no legacy generation workflows;
- NG3-only current CI;
- an active-main hygiene gate;
- explicit branch-qualified historical references;
- full NG3 regression PASS.

This cycle adds only the durable lineage/reconstruction decision and its review/checkpoint.
It does not alter NG3 product semantics.

## Preserved historical refs

```text
legacy-main-rc
legacy-main-ng1-2
legacy-main-ng3
```

The future ancestry candidate will treat these as evidence inputs, not merge sources.

## Handoff to the next cycle

The next logical cycle may create `futuremain`, but must leave current `main` unchanged.

Canonical reconstruction starts from the preserved first NG3 snapshot:

```text
snapshot 31/44
edeac340fab70bfe8df3a5f2a034fdf3ca7af8be
```

Its original parent is:

```text
snapshot 30/44
d50652b7d2e8f671c18823ffcb588103257baa0d
```

The exact `30 -> 31` delta is applied to an empty tree, making reconstructed snapshot 31 the
parentless root.

Subsequent numbered snapshots and meaningful inter-snapshot commits are reconstructed in
original order. Each reconstructed commit must have an exact delta match to its original
commit. First mismatch stops the reconstruction.

The standalone process commit:

```text
211aefdc03a529162bb28385def6d21cc19db5aa
Process: add English AGENTS.md for stage-independent, review-first CD and mainline snapshots
```

between snapshots 44 and 45 is part of the required sequence.

## Requirement inventory

```text
159 / 159 closed
pending_closure  0
rejected_closure 0
open             0
missing architecture refs 0
```

## Current main evidence

Snapshot-75 exact-main workflows:

```text
Actual main lineage guard 44145601289 PASS
NG3 Python                44145601265 PASS
```

No future-main construction is included in this checkpoint.

No cutover or history rewrite of `main` is authorized by this checkpoint.
