# NG2 cycle — availability_problems collector migration

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-availability-problems-collector-40m`  
**CYCLE_INTERVAL:** 40 minutes  
**Cycle base:** `8afc0ee25691bbbc6e8f50ac3a3e5eeeed376e0a`

## Agreed semantics

Availability probing is an optional priority modifier, not a runtime backbone.

Per channel routing state is only:

```text
availability_problems: bool
```

Rules:

- probing disabled => `availability_problems = false`;
- initial state => `false`;
- configured/base ranking is authoritative by default;
- negative hysteresis may set the flag to `true`;
- recovery good-news hysteresis may clear it to `false`;
- availability never changes payload route membership;
- paths with `availability_problems=false` outrank paths with `true`, while configured order remains authoritative within the same class.

Implementation target:

- bounded saturating `pending_good_news`;
- boolean `tick_pending`;
- routing hysteresis/current availability state inside `PayloadTrafficManager`;
- synchronous sole route-priority materializer;
- no logical evidence epochs, elapsed-window replay, or EventEnvelope dependency on this path.
