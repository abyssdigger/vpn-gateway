# NG2 cycle checkpoint — free-slot route-priority transactions

**Date:** 2026-11-14  
**Branch:** `code-cycle-20261114-empty-slot-routing-v2`

## Cycle clock

- `CYCLE_INTERVAL`: 40 minutes
- `CYCLE_START_COMMIT`: `514c4354b65626756378af195b40b9ca7aa3352b`
- `T0`: `2026-11-14T19:38:39Z`
- latest executable/test-bearing reviewed head:
  `fa3d6615082e08d5100f37c3c1fa28d889698744`

The coherent review unit completed before the interval boundary, so no new review unit was
started merely to consume the remaining checkpoint window.

## Completed review unit

Implemented and reviewed the NG2 availability-driven route-priority transition model:

- no eligible path is intentionally removed during a priority transition;
- one elementary move is `add duplicate at free metric -> delete old copy`;
- the old metric becomes the next free position automatically;
- the free metric is not configuration, a route, a binding or persistent allocator state;
- mixed live/non-confirmed state derives the free position from transient
  `confirmed_live_prefix_length`;
- `None` means no active availability-derived boundary; `0` means active boundary with
  no confirmed-live path;
- all-live has no steady-state gap and uses the next unused ordinary metric as first
  transition scratch;
- all-non-confirmed routes begin at the second ordinary metric;
- verified physical no-op commits semantic-only live-prefix changes without an unnecessary
  forwarding barrier;
- route-priority materialization remains the narrow fast path; broader changes retain the
  structural fail-closed rebuild;
- per-Profile/routing-domain route-priority transactions are specified as serialized:
  superseding availability state can replace pending/latest desired but cannot interleave an
  active immutable move plan.

## Evidence

PASS on the final executable code baseline:

- NG2 unit suite: 248 tests;
- exhaustive four-path/free-slot planner permutations;
- privileged NG2 Linux integration;
- EXP-027 ordinary-prefix and default-route cases;
- Adapter A3 pure route reorder without nft/ip_forward mutation;
- Adapter A4 availability demotion/recovery with implicit live/dead gap;
- nft syntax integration;
- Linux instance integration;
- NG1 Python validation.

EXP-027 passed:

```text
ABGD.VEJ -> ABVGD.EJ
ABVGD.EJ -> ABGD.VEJ
ABGDEJ.V -> ABVGDEJ
ABVGDEJ -> ABGDEJ.V
```

The autonomous review is recorded in
`design/reviews/NG2-2026-11-14-free-slot-route-priority-review.md`.

## Review findings closed in this unit

Accepted and fixed:

1. fixed-slot `replace` could temporarily remove an eligible path;
2. persisted/configured gap modelling was unnecessary;
3. `ordered_paths` alone could not encode the transient live/non-confirmed boundary;
4. semantic-only `None -> N` caused needless structural rebuild;
5. route-slot projection arithmetic was duplicated;
6. hand-picked planner cases were insufficient;
7. live-prefix drift needed explicit SAFE priority-divergence semantics;
8. stale structural-only Adapter documentation and old EXP-027 wording.

## Explicit remaining gate

The lower Executor invocation is synchronous, therefore one invocation already has an
immutable plan.

The next runtime availability-wiring review unit must implement the corresponding
queue/coalescing rule above it:

```text
one active route-priority transaction per Profile/routing-domain
newer availability state -> pending/latest desired only
final verification of active plan
then start next plan from verified result
```

This is required before executable Event Delivery / RuntimeStateManager can issue repeated
availability-driven payload updates.

No Linux-driver lock, generic scheduler or speculative async framework was introduced in
this review unit.

## Human decisions

None currently required.
