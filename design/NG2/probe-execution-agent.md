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

Its outputs are:

```text
ProbeGoodNewsInfo
ProbeWindowBoundaryInfo
ProbeExecutionDiagnosticInfo
```

The first two feed availability evidence. Diagnostics are operational state only.

## 2. Ownership split

`AvailabilityProbeManager` owns:

- logical probe requests;
- ProbeRules lifecycle;
- READY `ProbeObservationGeneration`;
- evidence windows and hysteresis;
- `REACHABLE / UNREACHABLE / UNKNOWN` publication.

`ProbeExecutionAgent` owns:

- current execution plan lifecycle;
- monotonic cadence;
- physical send launch;
- generation-scoped worker acceptance;
- serialization of good-news/window publication;
- local execution diagnostics.

The Agent does **not** own:

- `failure_intervals`;
- routing verdicts;
- payload route membership;
- binding membership;
- per-attempt semantic identity.

## 3. Request lifecycle

A non-`None` plan means:

> execute this complete generation-bound probe demand.

`None` means:

> quiesce all current probe execution demand.

On physical ProbeRules generation loss,
`AvailabilityProbeManager` publishes `None` before starting a later lower-domain
transition. A later fresh READY generation publishes a replacement plan.

Logical-only changes may replace a plan without changing
`ProbeObservationGeneration`.

Each logical window also carries an opaque positive `evidence_epoch` owned by
`AvailabilityProbeManager`. The epoch changes whenever that logical probe definition
changes, including a `failure_intervals`-only change that does not alter physical cadence.

Unchanged plane cadence keeps its existing phase. A logical window keeps its phase only
when both interval and `evidence_epoch` are unchanged. A changed/new evidence epoch begins
a fresh logical interval without leaking `failure_intervals` into the Agent.

## 4. Cadence

Plan activation:

```text
start logical windows
send once immediately on every physical plane
```

At a later coincident deadline:

```text
1. publish due window boundary
2. launch the send for the next window
```

The Agent uses anchored monotonic deadlines.

If execution wakes late:

- elapsed logical windows are batched into one
  `ProbeWindowBoundaryInfo(elapsed_intervals=N)`;
- exactly one current physical send is launched;
- historical missed sends are not replayed as a burst;
- both deadline advances are O(1).

Thus a suspend/resume cannot create an unbounded event or process catch-up storm.

## 5. Physical send boundary

The production Agent depends on:

```text
ProbeSendDriver.execute_send(...)
    -> ProbeSendResult(
           good_news: bool,
           local_error: str | None
       )
```

No `NO_REPLY` type crosses this boundary.

The current Linux compatibility implementation wraps the already target-validated
single-shot `LinuxIcmpProbeDriver`:

```text
REPLY    -> good_news=true
NO_REPLY -> good_news=false, local_error=None
ERROR    -> good_news=false, local_error=<diagnostic>
```

This is intentionally an Adapter around historical diagnostic machinery. The production
Agent does not consume `ProbeAttemptResult`.

The long-lived entity is the Agent. Individual `ping -c 1` workers remain bounded
technical sends. This reuses the already proven capability-free Linux mechanism instead of
introducing an unvalidated raw/ping-socket implementation merely to make the worker
process itself persistent.

## 6. Send concurrency

At most one send may be in flight for one physical plane/generation.

If the next send deadline arrives before the previous send completes:

- no second process/thread is launched for that plane;
- local diagnostic state becomes `ERROR` with an overrun reason;
- observation windows continue normally;
- routing receives no immediate negative event.

This bounds execution resources even when technical send latency exceeds configured
cadence.

Different physical planes may execute concurrently.

## 7. Evidence publication

A successful technical reply emits:

```text
ProbeGoodNewsInfo(
    mechanism,
    InterfaceIdentity,
    target,
    ProbeObservationGeneration
)
```

A successful local execution without reply emits no availability event.

A local execution error emits no availability event.

Good-news and window-boundary publication share one Agent-local serialization lock. This
provides a definite source order inside one execution generation. Future
`EventEnvelope.revision` ordering must preserve that order across asynchronous delivery.

A result from an obsolete generation or from a plane no longer in the current plan is
discarded.

## 8. Window batching

`ProbeWindowBoundaryInfo` carries:

```text
probe_id
generation
elapsed_intervals >= 1
```

`AvailabilityProbeManager` first verifies both physical `generation` and logical
`evidence_epoch`, then `AvailabilityWindowState.close_intervals()` applies the same
integral semantics in O(1). A boundary already emitted for an older logical definition is
therefore stale even when the physical READY generation did not change.

If good news existed in the first elapsed window and several further windows elapsed
during suspension, the first boundary consumes that good news and the remaining windows
count as misses. No attempt correlation is introduced.

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
