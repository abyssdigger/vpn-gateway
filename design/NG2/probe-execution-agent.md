# VPN-GATE NG2 — ProbeExecutionAgent

> **2026-11-15 normative update:** logical observation windows are removed from the target
> architecture. `design/NG2/availability-collector-materializer.md` supersedes the
> `LogicalProbeWindow`, `evidence_epoch`, boundary batching and `elapsed_intervals`
> portions below. Physical send cadence, stale physical-generation rejection, bounded
> workers and local diagnostics remain normative.

**Status:** active NG2 design  
**Date:** 2026-11-15  
**Scope:** production execution of generation-bound active probe demand  
**Upstream contract:** `design/NG2/availability-probe-manager.md`

## 1. Role

`ProbeExecutionAgent` is an Engine of the Agent family.

It observes remote reachability by actively sending probes, but it does not own routing
policy and does not decide whether a payload path is eligible, reachable or removable.

Its inputs are latest-value `ProbeExecutionPlan | None` RequestEvents from
`AvailabilityProbeManager`.

Its availability-facing outputs are colorless good-news observations and logical ticks.
It also publishes local execution diagnostics. Good-news/tick inputs are aggregated by the
PayloadTrafficManager collector; they are not replayable event-journal records.

## 2. Ownership split

`AvailabilityProbeManager` owns:

- logical probe requests;
- ProbeRules lifecycle;
- READY `ProbeObservationGeneration`;
- physical ProbeRules/readiness generation;
- current execution demand.

`ProbeExecutionAgent` owns:

- current execution plan lifecycle;
- monotonic physical-send and logical-tick cadence;
- physical send launch;
- generation-scoped worker acceptance;
- local execution diagnostics.

The Agent does **not** own:

- `failure_intervals`;
- routing verdicts;
- payload route membership;
- binding membership;
- per-attempt semantic identity.

## 3. Request lifecycle

A non-`None` plan means: execute this complete current physical/logical probe demand.

`None` means: quiesce it.

A physical ProbeRules generation loss quiesces current demand before a later lower-domain
transition. A later fresh READY generation installs replacement demand.

Logical policy changes do not require an `evidence_epoch`. Routing hysteresis state is
outside this Agent.

## 4. Cadence

The Agent schedules two technical activities:

```text
physical send deadline -> launch at most one current send
logical tick deadline   -> set current channel tick_pending = true
```

A late wake-up does not replay historical activity:

- missed physical sends are not burst-replayed;
- repeated undrained logical ticks collapse to one pending fact in the collector input;
- the next deadlines advance to the future in O(1).

There is no elapsed-window catch-up.

## 5. Physical send boundary

The production Agent depends on:

```text
ProbeSendDriver.execute_send(...)
    -> ProbeSendResult(good_news: bool, local_error: str | None)
```

No `NO_REPLY` type crosses this boundary.

The current Linux compatibility implementation wraps the already target-validated
single-shot `LinuxIcmpProbeDriver`:

```text
REPLY    -> good_news=true
NO_REPLY -> good_news=false, local_error=None
ERROR    -> good_news=false, local_error=<diagnostic>
```

Individual `ping -c 1` workers remain bounded technical sends.

## 6. Send concurrency

At most one send may be in flight for one physical plane/generation.

If the next send deadline arrives before the previous send completes, no second worker is
launched for that plane and local diagnostic state records the overrun. Different physical
planes may execute concurrently.

## 7. Availability input publication

A successful reply contributes one colorless good-news unit to every current logical
consumer of that physical plane.

The receiving bounded input saturates at that channel's configured
`recovery_good_news`. No attempt identity, timestamp or semantic send sequence is
published.

A logical cadence firing only sets that channel's `tick_pending` flag. A second firing
while the flag is already set adds nothing.

The Agent does not need to order good news against ticks. The collector deliberately treats
the accumulated good-news count and pending-tick fact in one pass as simultaneous
observations.

A result from an obsolete physical generation or from a plane no longer in the current
plan is discarded.

## 8. Removed window machinery

The target Agent has no:

```text
LogicalProbeWindow.evidence_epoch
ProbeWindowBoundaryInfo.elapsed_intervals
boundary catch-up
boundary-before-next-send semantic ordering
good-news/window source-order lock
```

Physical generation remains only as a stale-worker safety guard.

## 9. Local diagnostics

`ProbeExecutionDiagnosticInfo` is generation- and plane-scoped.

States:

```text
READY
ERROR
INACTIVE
```

`ERROR` is local execution health only. It never directly changes routing evidence.

Repeated identical current diagnostics are suppressed.

When a plane/generation leaves the current plan, its latest diagnostic is followed by
`INACTIVE`. Diagnostic publication is serialized against plan invalidation so a stale
worker cannot publish `READY` or `ERROR` after the corresponding `INACTIVE`.

## 10. Shutdown

`stop()`:

- clears current execution demand;
- emits required diagnostic `INACTIVE` transitions;
- wakes and terminates the scheduler thread;
- is idempotent;
- does not accept late worker results as current evidence.

Already running bounded technical workers may finish after logical quiesce, but their
results are generation/plan checked and discarded. The Linux ping Driver receives an
**explicit required technical timeout** from runtime assembly; there is no hidden default
that could be mistaken for availability verdict policy.

## 11. Safety invariants

1. Probe execution never adds or removes payload routes.
2. `NO_REPLY` never becomes a production availability event.
3. Local execution `ERROR` never becomes an immediate routing verdict.
4. Old-generation worker results never become current evidence.
5. One physical plane cannot create unbounded overlapping workers.
6. Boundary-before-next-send ordering is preserved at coincident deadlines.
7. Suspended execution does not replay historical sends.
8. Execution diagnostics are explicitly invalidated when their plane/generation becomes
   inactive.

## 12. Remaining gates

This unit does not close:

- Event Delivery Environment / `EventEnvelope` revision filtering for delayed delivery;
- daemon/runtime assembly that instantiates the Agent and connects actual event transport;
- Profile status consumption of local execution diagnostics;
- target validation only if the Linux send mechanism later changes materially away from
  the already validated capability-free `/usr/bin/ping` path.

No new kernel behavior is claimed by the current implementation.
