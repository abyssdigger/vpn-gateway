# NG2 cycle checkpoint — non-attempt probe execution contract

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-probe-execution-contract-40m`

## Cycle clock

- `CYCLE_INTERVAL`: 40 minutes
- cycle base: `07713a9c146b98cbb25bdf084b2cda8167f4cd85`
- `CYCLE_START_COMMIT`: `ac9940946d16dde7c66a974cb6c01855fa19c285`
- `T0`: `2026-11-14T22:32:42Z`
- latest reviewed commit before checkpoint:
  `a415badf4c7c96676ea9c6f4b04a999cc46c572d`
  at `2026-11-14T22:35:48Z`

The coherent review unit completed before the nominal cycle boundary. No independent
Linux transport implementation unit was started merely to consume the remaining interval.

## Completed review unit

Defined the production-facing execution contract below availability policy without
restoring attempt semantics.

### Execution demand

Added `ProbeExecutionPlanCalculator`:

```text
AvailabilityProbeSetRequest
    +
current READY ProbeObservationGeneration
        |
        v
ProbeExecutionPlan
    physical planes
        mechanism
        concrete InterfaceIdentity
        target
        send interval
    logical windows
        probe_id
        observation interval
```

Physical planes are deduplicated by
`(mechanism, InterfaceIdentity, target)`. If several enabled logical consumers share one
plane, physical cadence is the smallest requested interval. Observation windows remain
logical-probe specific.

### Execution facts

The production ingress contract contains only:

```text
ProbeGoodNewsInfo
ProbeWindowBoundaryInfo
```

There is no production `NO_REPLY` event and no attempt identity.

### Timing phase rule

Plan activation:

1. starts logical windows;
2. immediately sends once on every physical plane.

For a later coincident deadline:

1. due windows close first;
2. the next send follows and belongs to the next window.

This prevents a synthetic first-window miss without inventing attempt correlation.

### Concurrency hardening

A real execution source introduces independent callbacks. `AvailabilityProbeManager` now
serializes request/audit/good-news/window processing and generation/plan observation with
one re-entrant state lock.

A threaded regression proves that stale good-news arriving while a physical generation
transition is blocked cannot race into the new evidence state.

## Autonomous review

Review artifact:

`design/reviews/NG2-2026-11-15-probe-execution-contract-review.md`

Findings fixed:

1. duplicate physical-plane identity validation was initially too weak;
2. AvailabilityProbeManager lacked concurrency serialization for execution callbacks;
3. first-send / first-boundary phase ordering was ambiguous.

Confirmed invariants:

- no availability-driven route membership change;
- no production `NO_REPLY`;
- no attempt scheduler;
- logical consumers sharing a plane do not share hysteresis state;
- Linux/process details remain below the semantic contract.

Deferred behind existing named gates:

- concrete long-lived sender/receiver mechanism;
- persistent local execution-error diagnostics;
- EventEnvelope revision ordering for asynchronous late delivery.

Review verdict: **PASS for the semantic execution-contract unit**.

## Tests/evidence

Committed deterministic tests cover:

- shared-plane minimum send cadence;
- separate concrete paths;
- disabled execution demand;
- generation-bound event typing;
- duplicate physical identity rejection;
- READY-only execution plan;
- good-news/window event integration;
- concurrent stale-event rejection during generation transition.

The repository workflow runs compile/unit and privileged Linux integration on pushes that
touch `design/NG2/code/python/**`.

**Evidence limitation:** the available GitHub connector exposes pull-request workflow runs
but not push-triggered runs, so this checkpoint does not claim an observed CI PASS for
these new commits. No kernel behavior is newly claimed by this unit.

## Human decisions

None required.

The physical transport implementation remains intentionally unconstrained until the next
review unit compares the cheapest viable mechanism against the existing LOCAL_PROCESS /
diagnostic ping evidence.

## Next review unit

Concrete long-lived Linux sender/receiver machinery implementing `ProbeExecutionPlan`:

- generation-scoped lifecycle;
- immediate-first-send and boundary-before-next-send phase ordering;
- valid-reply publication only;
- local execution-error diagnostics separated from routing evidence;
- target/privileged validation only for mechanism properties not already proven.
