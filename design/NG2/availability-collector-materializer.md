# VPN-GATE NG2 — availability collector and synchronous route materialization

**Status:** normative NG2 design  
**Date:** 2026-11-15  
**Scope:** active-probe evidence aggregation and route-priority materialization

This document supersedes the observation-window / negative-integral model previously
described in `availability-probe-manager.md`, `availability-routing-model.md` and
`probe-execution-agent.md`. Historical review/checkpoint documents remain evidence of
the design path.

## 1. Design goal

The availability path is intentionally small:

```text
physical ping workers                         timer
        |                                       |
        +--> colorless good news                +--> tick
                    \                           /
                     v                         v
                    bounded availability input
                                  |
                                  v
                       PayloadTrafficManager
                     availability collector state
                                  |
                                  | synchronous current snapshot
                                  v
                    route-priority materializer
                                  |
                           transactional reorder
                                  |
                                return
```

The collector state is owned by `PayloadTrafficManager`, because availability in NG2 is
routing-priority policy. The route-priority materializer is the sole transactional route
Executor already owned by that Manager. Probe execution never changes payload route
membership.

`AvailabilityProbeManager` continues to own physical ProbeRules/readiness and execution
demand, but no longer owns routing hysteresis. This avoids a synchronous call from one
Manager into another Manager's private Machinery.

There is no asynchronous queue between collector and materializer: both are inside the
same Manager execution flow. Producer-facing input is different: ping workers/timers update bounded aggregates under a
short lock. If the sole executor is already busy, ingress returns immediately. If it is
free, the ingress caller may become the collector executor and synchronously drain the
current aggregate snapshot. No dedicated collector thread or event queue is required.

The collector releases the input lock before route calculation/materialization. While a
materialization runs, other producers only accumulate new bounded facts; the current
executor processes them after the synchronous materializer call returns.

The design relies on the operational scale already chosen for NG2: route-priority
materialization is millisecond-scale while probe cadence is second-scale. The model does
not attempt to reconstruct wall-clock history accumulated while materialization is in
progress.

## 2. Availability-priority channel

Payload-facing availability uses a probe-independent descriptor:

```text
AvailabilityPriorityChannel
    channel_id
    InterfaceIdentity path
    enabled
    AvailabilityHysteresisPolicy
        failure_ticks
        recovery_good_news
```

It intentionally contains no:

- target address;
- probe mechanism;
- probe cadence;
- physical generation;
- attempt id;
- timestamp.

Physical probe execution may derive this descriptor from a richer logical probe request,
but PayloadTrafficManager never needs those physical details.

The full immutable descriptor is carried on good-news/tick input so a late callback from an
obsolete logical definition can be rejected without adding a logical epoch.

## 3. Hysteresis policy

Each enabled availability-priority channel has:

```text
failure_ticks
recovery_good_news
```

Both values are positive.

Probe cadence is separate and owned by ProbeExecutionAgent.

`failure_ticks` is the number of processed tick observations without any good news
required to set `availability_problems = true`.

`recovery_good_news` is the number of consecutive valid good-news replies required to
clear `availability_problems`.

"Consecutive" does not mean one reply per timer interval. Delayed replies remain valid
good news when they arrive. Several delayed replies may therefore complete recovery in one
collector pass.

A tick without any good news since the preceding tick breaks an incomplete recovery
sequence.

## 4. Input aggregation

The producer-facing input state is deliberately not an event journal.

For each current logical channel:

```text
pending_good_news: 0 .. recovery_good_news
tick_pending: bool
```

### 4.1. Good news

A valid reply increments `pending_good_news` with saturation:

```text
pending_good_news =
    min(pending_good_news + 1, recovery_good_news)
```

No larger value is semantically useful:

- while `availability_problems = false`, only zero versus non-zero matters;
- while `availability_problems = true`, at most `recovery_good_news` replies can complete recovery.

### 4.2. Tick

A timer firing sets:

```text
tick_pending = true
```

A second timer firing while it is already true has no additional semantic effect.

Ticks therefore do not form a queue and do not carry an elapsed-count value. If the
collector was unable to process several real timer expirations, NG2 intentionally
collapses them into the single fact that a tick happened.

There is no `elapsed_intervals` catch-up.

## 5. Collector-owned channel state

The collector owns, per channel:

```text
availability_problems: bool
failure_misses
recovery_progress
good_news_since_tick
```

An implementation may encode `failure_misses` and `recovery_progress` using one signed
counter, but the semantic model above is normative and avoids off-by-one dependence on a
particular encoding.

Only one side of the hysteresis state is active:

- `availability_problems = false` uses `failure_misses`;
- `availability_problems = true` uses `recovery_progress`.

Initial state is always `availability_problems = false`. Disabled probing also means
`availability_problems = false` by definition. Availability is an optional negative
priority modifier; absence of evidence never creates a problem state.

`good_news_since_tick` is a one-bit latch recording whether at least one valid reply has
been accepted since the preceding processed tick.

## 6. One collector pass

The `PayloadTrafficManager` collector loop is single-threaded with respect to
channel-state calculation and synchronous route-priority materialization. Producers only
update bounded input aggregates under a short mutex and wake the collector; the mutex is
never held across route calculation, kernel I/O or verification.

For each pass, the collector obtains the current accumulated facts. Events within that
pass are treated as simultaneous observations. Their source ordering is intentionally not
reconstructed.

The transition calculation is based on the channel status at entry to the pass. A
transition caused by one input kind is not immediately subjected to the opposite
transition rule from another input kind in the same pass.

This realizes two invariants:

```text
a tick never improves a channel
good news never worsens a channel
```

## 7. No-problem channel rule

A channel without availability problems can acquire them only while processing a tick.

Good-news arrivals before the next tick merely latch:

```text
good_news_since_tick = true
```

When `tick_pending` is processed:

```text
if good_news_since_tick or pending_good_news > 0:
    failure_misses = 0
else:
    failure_misses += 1
    if failure_misses >= failure_ticks:
        availability_problems = true
        recovery_progress = 0

good_news_since_tick = false
consume pending_good_news
consume tick_pending
```

The number of accumulated replies while `availability_problems = false` is irrelevant beyond zero/non-zero.

Therefore:

```text
false -> true
```

is exclusively a tick-driven transition.

## 8. Problem-channel rule

A channel with availability problems can clear them only while processing good news.

Every accepted reply contributes independently:

```text
if pending_good_news > 0:
    good_news_since_tick = true
    recovery_progress += pending_good_news
    recovery_progress = min(recovery_progress, recovery_good_news)

    if recovery_progress >= recovery_good_news:
        availability_problems = false
        failure_misses = 0
```

Thus, with `recovery_good_news = 3`, three delayed replies arriving in one collector pass
are sufficient for immediate recovery. The collector does not wait for two additional
timer intervals merely to spread those replies across artificial observation windows.

If the channel entered the pass problem and a tick is also pending:

```text
if no good news has been seen since the preceding tick
   and pending_good_news == 0:
    recovery_progress = 0

clear good_news_since_tick
consume tick_pending
```

If current good news completes recovery in the same pass, the simultaneous tick does not
then apply no-problem channel degradation logic to the newly cleared problem state.

Therefore:

```text
true -> false
```

is exclusively a good-news-driven transition.

## 9. Delayed-reply example

Policy:

```text
recovery_good_news = 3
```

The channel has `availability_problems = true`. Four probes are sent on successive physical cadences. The first three
timer periods produce no reply at the collector. During the fourth period three delayed
valid replies arrive.

The input aggregate can become:

```text
pending_good_news = 3
tick_pending = true   # if the fourth tick is already pending
```

The problem-channel rule consumes the three replies:

```text
recovery_progress: 0 -> 3
availability_problems: true -> false
```

The replies proved that three probes succeeded; transport delay did not turn them into
loss. No attempt correlation or reply timestamp is required.

## 10. Physical generation guard

The collector model itself has no logical evidence epoch and no event revision.
`AvailabilityProbeStateInfo` and the old routing-control chain through
`RuntimeStateManager` have been removed. Availability diagnostics, if later needed, must
be projected from current collector/Agent state without reintroducing that control path.

The existing physical `ProbeObservationGeneration` has a narrower purpose: a bounded
worker launched for an obsolete ProbeRules/interface generation must not contribute a
reply after that physical generation has been invalidated.

This guard is below availability hysteresis. It must not be used to version timer windows,
recovery policy, collector/materializer communication or route order.

A logical-policy-only change preserves `availability_problems`, resets hysteresis progress,
and clears pending per-channel aggregates. It does not require an `evidence_epoch`.

## 11. Synchronous materializer boundary

The collector remembers current channel statuses. Counter/latch changes that do not change
`availability_problems` do not require materialization.

When the routing-relevant current snapshot changes, the collector calls the
`PayloadTrafficManager` route-priority materializer synchronously:

```text
materialize(current_snapshot)
```

The call does not return until the current route transaction has either:

- reached and verified the requested materialized state; or
- failed with an explicit convergence result.

The materializer owns the last **verified** materialized route-priority snapshot and
compares before acting. A failed/partially observed transaction never advances that
baseline; the next pass re-observes authoritative route state before planning further
moves:

```text
if desired == last_materialized:
    return

plan = diff(last_materialized, desired)
execute transaction
verify
last_materialized = desired
return
```

Only one materialization transaction for the relevant Profile/routing scope may execute at
a time.

For availability-driven reorder work there is therefore no:

- materializer-ready event;
- collector-to-materializer route-plan queue;
- second/concurrent route transaction;
- cancellation of a running route transaction;
- availability supersession inside a transaction.

Other payload-domain changes may still arrive through the existing
`PayloadTrafficManager` request path. They share the same sole transactional executor;
availability processing does not create a second executor or a second queue of kernel
moves.

New availability good-news/tick facts that arrive while materialization runs accumulate
only in the bounded collector input state. On return, the collector performs another pass over the latest
facts and, if the routing-relevant snapshot changed again, invokes materialization again.

## 12. Route semantics

Availability changes only priority.

It never:

- adds an eligible payload path;
- removes an eligible payload path;
- changes binding membership;
- changes filter/NAT membership merely because a channel is problem.

The existing effective-order and metric-hole model remains normative:

- paths with `availability_problems = false` precede paths with problems;
- configured priority is authoritative within each class;
- startup/disabled probing leaves configured order untouched;
- the free metric slot is emergent, not configured;
- when no availability-driven reorder has occurred, no availability gap is materialized;
- the route sorter is the sole transactional executor for priority rearrangement.

## 13. Execution-agent consequence

`ProbeExecutionAgent` still owns physical send cadence, bounded send workers, stale
physical-worker rejection and local execution diagnostics.

It no longer owns logical observation windows.

Its availability-facing outputs reduce to:

```text
AvailabilityGoodNews(current AvailabilityPriorityChannel)
AvailabilityTick(current AvailabilityPriorityChannel)
```

The tick is level-like input to the collector: repeated undrained ticks collapse to one
pending fact.

There is no production:

```text
ProbeWindowBoundaryInfo
elapsed_intervals
LogicalProbeWindow.evidence_epoch
window catch-up
boundary-before-next-send semantic ordering
```

A local `NO_REPLY` remains absence of good news, not an event. Local execution ERROR
remains diagnostic only.

## 14. Ordering and EventEnvelope consequence

This path does not require EventEnvelope ordering between collector and materializer
because they are one synchronous Manager flow.

Producer-to-collector delivery is not an Event journal either. It is a non-blocking input
port that updates bounded aggregates. Ordering is intentionally weaker than an event
journal: good-news multiplicity and the existence of a pending tick are aggregate facts.

A future general Event Delivery Environment may still use envelopes for other asynchronous
latest-value streams. It must not be introduced into this availability path merely to
reconstruct an order that the collector semantics explicitly discard.

## 15. Current implementation

The Python implementation now follows this model directly:

- `availability_collector.py` owns the small policy/state primitives and path-order
  calculation;
- `AvailabilityProbeManager` owns only ProbeRules/readiness plus physical generation and
  execution demand;
- `ProbeExecutionAgent` owns physical sends, logical ticks and local diagnostics;
- `PayloadTrafficManager` owns bounded availability inputs, channel state and the sole
  serialized route materializer.

Removed production artifacts:

- `availability_routing.py`;
- `payload_traffic_intent.py`;
- the availability-specific executable `runtime_state_manager.py` slice;
- logical windows, `evidence_epoch`, `elapsed_intervals` and boundary events.

The only retained generation token is `ProbeObservationGeneration`, scoped strictly to
physical stale-worker rejection.
