# NG2 cycle checkpoint — Linux probe execution Agent

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-linux-probe-transport-40m`

## Cycle clock

- `CYCLE_INTERVAL`: 40 minutes
- cycle base: `e24a3640fe6b406a16dbc475dda9a7c50711d909`
- `CYCLE_START_COMMIT`: `f6aa29820714195abbafa2458cbedf9200a9d930`
- `T0`: `2026-11-15T01:33:53Z`
- final reviewed commit before checkpoint:
  `e92ac1b9ebae3c386d1d2128cdfbdb5c1ae1039b`
  at `2026-11-15T01:49:09Z`

The coherent review unit completed before the selected cycle interval. No independent next
review unit was started merely to consume the remaining interval.

## Completed review unit

Implemented production execution below the non-attempt availability contract.

### Event lifecycle

`AvailabilityProbeManager` now publishes latest-value:

```text
ProbeExecutionPlan | None
```

RequestEvents.

A physical READY-generation loss publishes `None` before subsequent lower-domain
transition. A later fresh generation publishes a replacement plan.

Logical policy changes can replace the plan without changing the physical
`ProbeObservationGeneration`.

### ProbeExecutionAgent

Added long-lived `LinuxProbeExecutionAgent`.

It owns:

- monotonic cadence;
- immediate first send;
- boundary-before-next-send ordering;
- generation-scoped worker acceptance;
- one in-flight send maximum per physical plane/generation;
- good-news/window publication source ordering;
- local execution diagnostic lifecycle.

It owns no availability verdict policy.

### Production send boundary

The Agent depends on:

```text
ProbeSendDriver.execute_send()
    -> ProbeSendResult(good_news, local_error)
```

The historical diagnostic `REPLY/NO_REPLY/ERROR` contract is hidden below
`LinuxDiagnosticPingSendAdapter`.

In particular:

```text
NO_REPLY -> no production event
ERROR    -> local diagnostic only
REPLY    -> ProbeGoodNewsInfo
```

The Linux mechanism remains the already target-validated capability-free
`LinuxIcmpProbeDriver`; no new raw/ping-socket kernel behavior was introduced.

The technical ping timeout is now an explicit required runtime value, not a hidden
availability-policy default.

### Suspend/resume behavior

Delayed execution is bounded:

- elapsed logical windows collapse into one
  `ProbeWindowBoundaryInfo(elapsed_intervals=N)`;
- the Manager applies the integral in O(1);
- missed physical sends are not replayed;
- one current send is launched;
- deadline advancement is O(1).

### Independent logical evidence epoch

Whole-slice review found that a `failure_intervals`-only change resets Manager evidence
without changing physical generation or interval.

Added Manager-owned opaque:

```text
LogicalProbeWindow.evidence_epoch
```

The scheduler restarts logical window phase when this epoch changes.

A second race was then closed: an already-emitted boundary from the old logical definition
could otherwise arrive after the reset while the physical generation still matched.

`ProbeWindowBoundaryInfo` therefore also carries `evidence_epoch`, and the Manager
requires both physical generation and logical evidence epoch to match.

Good-news intentionally remains bound only to the physical plane/generation because
positive evidence is classified by reply arrival rather than semantic attempt identity.

### Diagnostics

Added generation-scoped current diagnostic projection:

```text
READY
ERROR
INACTIVE
```

Repeated identical diagnostics are suppressed.

Plan/generation removal emits INACTIVE, and lock ordering prevents an obsolete worker from
publishing READY/ERROR after that invalidation.

## Autonomous review

Review:

`design/reviews/NG2-2026-11-15-linux-probe-execution-review.md`

Verdict: **PASS**.

Accepted and fixed findings include:

1. attempt-shaped Driver result leaking into production Agent;
2. missing RequestEvent lifecycle for execution demand;
3. suspend/resume catch-up storms;
4. unbounded overlapping physical sends;
5. unsynchronized good-news/window source ordering;
6. incomplete diagnostic invalidation lifecycle;
7. stale-worker diagnostic race;
8. threshold-only policy reset retaining an old logical window phase;
9. stale old logical boundary crossing a same-generation reset;
10. hidden default technical timeout;
11. minor public-contract validation gaps.

A new raw/ping-socket transport was rejected as unjustified complexity because the existing
Linux mechanism already supplies the required proven behavior.

## Tests and evidence

Temporary draft PR #16 was opened only to expose pull-request-triggered CI and was closed
without merge after the result was recorded.

Final observable `NG2 Python` workflow evidence:

- run: 515;
- compile: PASS;
- rootless unit suite: **338 tests PASS**;
- privileged Linux integration: PASS;
- selective probe-process isolation: PASS;
- EXP-025: PASS;
- EXP-026: PASS;
- EXP-027: PASS;
- nft ICMP selector syntax: PASS;
- Linux instance lifecycle: PASS;
- Linux Adapter: PASS;
- Linux LOCAL_PROCESS: PASS;
- Linux dataplane: PASS.

No new target-specific kernel claim was introduced, so no new target experiment is required
for this unit.

## Human decisions

None required.

## Remaining gates

Still open:

1. Event Delivery Environment / `EventEnvelope` epoch+revision ordering;
2. daemon/runtime assembly that instantiates `LinuxProbeExecutionAgent` and connects real
   event transport;
3. Profile/status consumption of local execution diagnostics;
4. serialization/schema lifecycle;
5. target validation only if a future send mechanism materially changes from the already
   validated capability-free ping implementation.

## Next review unit

Implement EventEnvelope ordering and the minimum runtime event-delivery assembly needed to
connect the already executable Managers/Agent without relying on synchronous test
publishers.

The first priority is to prove stale sequential delivery rejection; only then should the
real daemon assembly depend on that event path.
