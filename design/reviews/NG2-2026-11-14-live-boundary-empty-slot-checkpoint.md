# NG2 — live-boundary EMPTY-slot cycle checkpoint

**Date:** 2026-11-14  
**Cycle interval:** default project interval  
**T0:** 2026-11-14T19:18:18Z  
**First mutation:** `e4e135a276b9`  
**Final branch:** `code-cycle-20261114-live-boundary-empty-slot`  
**Latest tested executable:** `414637f9412ff361137922242b0130aec71073c9`  
**Final documentation head before checkpoint:** `11b015ce3ca5636c37c89c749bb97034d3dde231`

## Completed

- replaced top-down route replacement with persistent EMPTY-slot moves;
- retained complete eligible route membership during every transition;
- made live-prefix boundary explicit as `priority_prefix_length`;
- implemented one generic route-slot permutation planner;
- verified recovery, demotion, far-right recovery and recovery through an existing dead tail;
- added single-flight payload transaction serialization;
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

Only one payload mutation transaction may be inside lower-domain
materialize/verify/commit at a time in the current Manager. A newer availability request
does not interleave with a transition already in progress.

## Next natural unit

Wire production generation-bound good-news and interval-boundary evidence into
`AvailabilityWindowState`, then feed the resulting confirmed-live prefix into
`PayloadTrafficIntentCalculator`.

Do not reintroduce semantic attempt IDs or reply-to-send correlation.
