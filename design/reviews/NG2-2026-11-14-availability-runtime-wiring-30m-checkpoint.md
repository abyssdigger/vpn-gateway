# NG2 cycle checkpoint — availability runtime wiring

**Date:** 2026-11-14  
**Branch:** `code-cycle-20261114-availability-runtime-wiring`

## Cycle clock

- `CYCLE_INTERVAL`: 30 minutes
- previous baseline: `02c932c9993c58ba8508809a37eada661f0be1f7`
- first implementation commit: `f6b2d2aea7f7031fead49ddda381a5991f64f510`
- `T0`: `2026-11-14T20:34:40Z`
- latest executable/test-bearing head:
  `dc0bd94f1446a05e64f56561f10183375e82649e`
- review head before this checkpoint:
  `172cd878d823dcc0c5a8dd1619be97443550fea9`

The coherent implementation/review unit completed before the nominal cycle boundary. No
new independent implementation unit was started merely to consume the remaining window.

## Completed implementation unit

The runtime semantic path is now executable through:

```text
valid generation-bound probe reply
    |
    v
AvailabilityProbeManager
    |  good-news + observation-window integral
    v
AvailabilityProbeStateInfo
    |
    v
RuntimeStateManager
    |
    +--> ProbeProfileEvidenceCalculator
    |
    +--> PayloadTrafficIntentCalculator
    |
    v
PayloadTrafficStateRequest
    |
    v
PayloadTrafficManager
    |  one serialized reconcile executor
    v
NetworkRulesAdapter
    |
    v
verified route-priority / structural Executor
```

### Availability evidence

Implemented:

- generation-bound physical-plane good-news;
- fan-out to all enabled logical consumers sharing the plane;
- immediate REACHABLE on positive evidence;
- negative integral only at logical window boundaries;
- UNREACHABLE only after `failure_intervals`;
- stale-generation good-news/window boundaries ignored;
- logical-policy changes reset only the affected evidence window;
- physical rules-generation changes reset all evidence windows;
- disabled consumers do not receive evidence.

No attempt id, semantic `NO_REPLY`, retry cadence or recovery threshold was restored.

### Probe -> Profile routing evidence

Added runtime-derived `ProfileProbeAssignment(profile_name, probe_ids)`.

It is not physical ProbeRules state and not Linux policy.

Runtime validates:

- Profile exists;
- probe exists;
- probe concrete path belongs to the current eligible Profile path set.

One logical probe may feed multiple Profiles.

### Effective payload intent

Added externally-stateless `PayloadTrafficIntentCalculator`.

Explicit inputs include:

- configured payload snapshot;
- previous configured snapshot;
- current effective snapshot;
- Profile confirmed-live evidence.

Rebase occurs only when path membership/configured priority changes or current effective
membership is no longer representable.

Unrelated Profile policy changes do not erase bubble-order history.

Semantics remain:

```text
availability inactive -> configured order, live-prefix=None
availability active, zero live -> preserve current order, live-prefix=0
positive evidence -> stable bubble promotion
single unconfirmed path -> path remains routed
```

### RuntimeStateManager

Added the first executable NG2 RuntimeStateManager slice.

It owns latest semantic snapshots, not Linux state.

Concurrent/re-entrant handler execution is serialized by a re-entrant state lock so two
overlapping calculations cannot publish contradictory effective snapshots.

This does not replace EventEnvelope epoch/revision ordering for sequential late delivery of
an old event.

### Payload transaction serialization

PayloadTrafficManager now owns exactly one reconcile executor.

While transaction A is running:

```text
B arrives -> pending B
C arrives -> pending C
A completes
C runs
```

Properties:

- current Adapter call is immutable;
- intermediate pending snapshots coalesce latest-value;
- concurrent threads cannot start a second materializer;
- re-entrant delivery does not deadlock;
- the mutex is not held across Adapter I/O;
- audits share the same executor;
- unexpected lower exception releases executor ownership.

End-to-end regression proves good-news arriving during an active payload apply becomes the
next desired transaction instead of interleaving the active one.

## Review corrections made during the cycle

The autonomous review found and fixed:

1. an initially over-broad rebase condition that reacted to any Profile object change
   instead of only path membership/configured priority;
2. reliance on accidental single-threaded delivery in PayloadTrafficManager;
3. lack of concurrent latest-value serialization in RuntimeStateManager;
4. missing early validation of probe/Profile path association;
5. insufficient validation of explicit Calculator inputs;
6. executor ownership could have been stranded by an unexpected lower exception.

No separate AvailabilityRoutingManager, scheduler or hidden stateful Calculator was added.

## Evidence

Latest executable head `dc0bd94f1446a05e64f56561f10183375e82649e`:

- NG2 unit suite: **290 tests PASS**;
- privileged NG2 Linux integration: PASS;
- EXP-027: PASS;
- Linux Adapter availability transition A4: PASS;
- Linux Adapter integration: PASS;
- NG1 Python validation: PASS.

Focused tests additionally cover:

- shared physical-plane fan-out;
- good-news reset and failure-window hysteresis;
- stale readiness generation rejection;
- disabled consumer exclusion;
- probe/Profile evidence projection;
- inactive vs zero-live availability;
- path membership/configured-priority rebase;
- preservation of bubble history across unrelated Profile policy changes;
- re-entrant and real concurrent request coalescing;
- unexpected executor failure recovery;
- end-to-end good-news during an active payload transaction.

Review:

`design/reviews/NG2-2026-11-14-availability-runtime-wiring-review.md`

Verdict: **PASS** for this review unit.

## Remaining gates

Not completed in this unit:

1. production probe sender/receiver transport;
2. ownership of interval triggers/cadence without semantic attempt scheduling;
3. persistent local execution-error diagnostics;
4. Event Delivery Environment epoch/revision filtering for late old events;
5. target validation if final transport materially differs from the already proven
   diagnostic ping mechanics.

The existing blocking `LinuxIcmpProbeDriver` remains diagnostic/evidence machinery and was
deliberately not promoted to the production semantic boundary.

## Human decisions

None currently required.
