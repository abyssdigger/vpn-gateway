# VPN-GATE NG2 — ProbeExecutionAgent

**Status:** normative NG2 design  
**Date:** 2026-11-15  
**Scope:** physical probe sends, logical ticks and local execution diagnostics

## 1. Role

`ProbeExecutionAgent` is an Agent Engine below `AvailabilityProbeManager`.

Input:

```text
ProbeExecutionPlan | None
```

Outputs:

```text
AvailabilityGoodNews
AvailabilityTick
ProbeExecutionDiagnosticInfo
```

The Agent owns cadence/process execution only. It owns no availability hysteresis and no
payload routing policy.

## 2. Physical sends

Each deduplicated physical plane has:

```text
mechanism
InterfaceIdentity
target
send interval
```

Activation or physical cadence change schedules one immediate send.

At most one send is in flight per physical plane/generation. If the next send deadline
arrives while the previous worker is still running, no second worker is launched and the
condition is reported only as local execution diagnostic state.

Delayed scheduler wake-up launches at most one current send. Historical sends are not
burst-replayed.

## 3. Logical ticks

Each enabled logical channel has one tick cadence equal to its configured
`interval_seconds`.

A due logical tick publishes:

```text
AvailabilityTick(current AvailabilityPriorityChannel)
```

If execution wakes after several nominal intervals, exactly one current tick is published
and the deadline advances directly into the future.

There is no elapsed interval count and no boundary replay.

## 4. Good news

The technical send boundary is:

```text
ProbeSendDriver.execute_send(...)
    -> ProbeSendResult(
           good_news: bool,
           local_error: str | None
       )
```

Current Linux compatibility mapping:

```text
REPLY    -> good_news=true
NO_REPLY -> good_news=false
ERROR    -> local_error=<diagnostic>
```

`NO_REPLY` is not a production event.

A successful physical reply is fanned out to the **current** logical consumers of that
physical plane:

```text
AvailabilityGoodNews(current AvailabilityPriorityChannel)
```

Individual replies carry no attempt id, sequence or timestamp.

## 5. Stale result rejection

A bounded worker result is discarded unless, at completion time:

- a plan is still active;
- the physical generation matches;
- the physical plane remains in the current plan.

The probe-independent `AvailabilityPriorityChannel` descriptor carried by good-news/tick
input gives PayloadTrafficManager a cheap guard against a callback from an obsolete
logical definition. Target, mechanism and cadence do not cross that boundary.

No logical epoch is required.

## 6. Diagnostics

Local execution diagnostic states remain:

```text
READY
ERROR
INACTIVE
```

They are keyed by physical generation + plane.

Repeated identical diagnostics are suppressed. Plan removal or generation replacement
invalidates current diagnostics with `INACTIVE`.

Diagnostic state never directly changes route priority.

## 7. Process-local publication failures

The Agent treats publisher exceptions as failures of an adjacent process-local consumer,
not as probe verdicts.

Rules:

- a failing `AvailabilityTick` callback is logged and does not prevent due physical sends;
- one failing `AvailabilityGoodNews` callback does not block fanout to other current
  logical consumers of the same physical plane;
- READY/ERROR diagnostic publication failure is logged and does not suppress good news;
- a failed READY/ERROR publication is removed from duplicate-suppression state so the same
  diagnostic may be retried when observed again;
- failed INACTIVE diagnostic publication is logged but is not persisted in a reliable
  delivery queue.

No callback failure creates availability state, retry epochs or an EventEnvelope backlog.

Known callback failures are isolated at their exact publication boundary. Unexpected
internal Agent exceptions are **not** swallowed by a broad scheduler-loop catch; they
remain visible as implementation failures.

## 8. Scheduler thread lifecycle

`start()` is idempotent while the scheduler thread is running.

If construction/start of the scheduler thread raises synchronously, the Agent restores
its non-running bookkeeping before re-raising. A later ordinary `start()` may retry.

If the scheduler thread exits because of an unexpected internal exception, that exception
remains visible through normal Python thread exception reporting. The thread's `finally`
path clears the current running/thread identity, so a later explicit `start()` may create
a replacement scheduler thread.

This bookkeeping recovery does not convert unexpected internal exceptions into local
probe diagnostics and does not add automatic restart policy; outer runtime/service policy
may decide whether a restart is appropriate.

## 9. Shutdown

`stop()`:

- clears current plan;
- emits required `INACTIVE` diagnostics;
- terminates the scheduler thread;
- is idempotent.

Already-running bounded workers may complete, but stale generation/plan checks prevent
their results from becoming current good news.

## 10. Removed machinery

The Agent no longer has:

- `LogicalProbeWindow`;
- `ProbeWindowBoundaryInfo`;
- `evidence_epoch`;
- `elapsed_intervals`;
- good-news/window ordering locks;
- boundary-before-send policy semantics;
- catch-up window processing.

Its availability-facing behavior is now exactly: **send pings, report successful replies,
emit ticks**.
