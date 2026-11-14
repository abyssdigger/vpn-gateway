# NG2 — live-boundary EMPTY-slot cycle checkpoint

**Date:** 2026-11-14  
**Cycle interval:** default project interval  
**T0:** 2026-11-14T19:18:18Z  
**First mutation:** `e4e135a276b9`  
**Final branch:** `code-cycle-20261114-live-boundary-empty-slot`  
**Latest tested executable:** `414637f9412ff361137922242b0130aec71073c9`  
**Final documentation head before checkpoint:** `11b015ce3ca5636c37c89c749bb97034d3dde231`

## Post-checkpoint correction

A later audit found that this checkpoint's phrase “single-flight payload transaction”
described an over-broad implementation: one global `PayloadTrafficManager` lock. The
agreed boundary is narrower and stronger semantically: **one Direct route-order Executor
per Profile**. The correction is implemented and reviewed on
`code-cycle-20261114-empty-slot-executor-audit`.

The EMPTY-slot algorithm and kernel evidence recorded below are unchanged.

## Completed

- replaced top-down route replacement with persistent EMPTY-slot moves;
- retained complete eligible route membership during every transition;
- made live-prefix boundary explicit as `priority_prefix_length`;
- implemented one generic route-slot permutation planner;
- verified recovery, demotion, far-right recovery and recovery through an existing dead tail;
- originally added over-broad global payload serialization; superseded by the
  post-checkpoint per-Profile Executor correction above;
- reserved metric capacity for the EMPTY working slot;
- aligned EXP-027, architecture docs, runtime model and changelog;
- corrected the earlier per-flow pinning caveat.

## Final route transition invariant

Steady state for an availability-managed Profile with `N` eligible paths:

```text
N routes
N + 1 ordinary metric slots
one EMPTY slot at the live/non-confirmed boundary
```

Each elementary move:

```text
add moving path into EMPTY
delete its old copy
```

During the add phase all `N` paths remain present and exactly one path has two routes.
After delete, the old slot is the new EMPTY.

## Transaction invariant

For route priority, one Profile has one Direct Executor. While that Executor is inside its
lower-domain apply/materialize/verify/commit operation, a newer route-order target for the
same Profile waits. Shared lower-domain serialization may additionally constrain physical
commits, but is not the caller-visible Profile transaction.

## Next natural unit

Wire production generation-bound good-news and interval-boundary evidence into
`AvailabilityWindowState`, then feed the resulting confirmed-live prefix into
`PayloadTrafficIntentCalculator`.

Do not reintroduce semantic attempt IDs or reply-to-send correlation.
