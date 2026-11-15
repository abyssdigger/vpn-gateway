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
                    AvailabilityProbeManager / collector
                         current channel state
                                  |
                                  | synchronous current snapshot
                                  v
                         route materializer
                                  |
                           transactional reorder
                                  |
                                return
```

The collector owns availability state and degradation/recovery policy. The route
materializer owns route-priority convergence. Probe execution never changes payload route
membership.

There is no asynchronous queue between collector and materializer. While materialization
runs, producers may accumulate new input facts; the collector processes them after the
synchronous materializer call returns.

The design relies on the operational scale already chosen for NG2: route-priority
materialization is millisecond-scale while probe cadence is second-scale. The model does
not attempt to reconstruct wall-clock history accumulated while materialization is in
progress.

## 2. Availability channel

A logical availability channel is identified by the current logical probe and its current
concrete physical plane:

```text
probe_id
mechanism
InterfaceIdentity(ifname, ifindex)
target
```

A concrete `InterfaceIdentity` remains significant. Same-name/new-ifindex is a different
physical channel generation.

Several logical channels may share one physical send plane. One valid physical reply may
therefore contribute one good-news fact to each current logical consumer of that plane.

Individual replies are otherwise colorless:

- no attempt id;
- no semantic send sequence;
- no reply timestamp in availability policy;
- no distinction between replies other than the channel to which they currently apply.

## 3. Normalized policy

Each enabled logical channel has:

```text
interval_seconds
failure_ticks
recovery_good_news
```

All three values are positive.

`failure_ticks` is the number of tick observations without any good news required to
move a GOOD channel to BAD.

`recovery_good_news` is the number of consecutive valid good-news replies required to
move a BAD channel to GOOD.

"Consecutive" here does not mean one reply per timer interval. Delayed replies remain
valid good news when they arrive. Several delayed replies may therefore complete recovery
in one collector pass.

A tick without any good news since the preceding tick breaks an incomplete BAD-channel
recovery sequence.

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

- while GOOD, only zero versus non-zero matters;
- while BAD, at most `recovery_good_news` replies can complete recovery.

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
status: GOOD | BAD
failure_misses
recovery_progress
good_news_since_tick
```

An implementation may encode `failure_misses` and `recovery_progress` using one signed
counter, but the semantic model above is normative and avoids off-by-one dependence on a
particular encoding.

Only one side of the state is active:

- GOOD uses `failure_misses`;
- BAD uses `recovery_progress`.

`good_news_since_tick` is a one-bit latch recording whether at least one valid reply has
been accepted since the preceding processed tick.

## 6. One collector pass

The collector is single-threaded with respect to channel-state calculation and synchronous
materialization. Producers only update the bounded input aggregates and wake the collector.

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

## 7. GOOD-channel rule

A GOOD channel can become BAD only while processing a tick.

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
        status = BAD
        recovery_progress = 0

good_news_since_tick = false
consume pending_good_news
consume tick_pending
```

The number of accumulated replies while GOOD is irrelevant beyond zero/non-zero.

Therefore:

```text
GOOD -> BAD
```

is exclusively a tick-driven transition.

## 8. BAD-channel rule

A BAD channel can become GOOD only while processing good news.

Every accepted reply contributes independently:

```text
if pending_good_news > 0:
    good_news_since_tick = true
    recovery_progress += pending_good_news
    recovery_progress = min(recovery_progress, recovery_good_news)

    if recovery_progress >= recovery_good_news:
        status = GOOD
        failure_misses = 0
```

Thus, with `recovery_good_news = 3`, three delayed replies arriving in one collector pass
are sufficient for immediate recovery. The collector does not wait for two additional
timer intervals merely to spread those replies across artificial observation windows.

If the channel entered the pass BAD and a tick is also pending:

```text
if no good news has been seen since the preceding tick
   and pending_good_news == 0:
    recovery_progress = 0

clear good_news_since_tick
consume tick_pending
```

If current good news completes recovery in the same pass, the simultaneous tick does not
then apply GOOD-channel degradation logic to the newly GOOD state.

Therefore:

```text
BAD -> GOOD
```

is exclusively a good-news-driven transition.

## 9. Delayed-reply example

Policy:

```text
recovery_good_news = 3
```

The channel is BAD. Four probes are sent on successive physical cadences. The first three
timer periods produce no reply at the collector. During the fourth period three delayed
valid replies arrive.

The input aggregate can become:

```text
pending_good_news = 3
tick_pending = true   # if the fourth tick is already pending
```

The BAD rule consumes the three replies:

```text
recovery_progress: 0 -> 3
status: BAD -> GOOD
```

The replies proved that three probes succeeded; transport delay did not turn them into
loss. No attempt correlation or reply timestamp is required.

## 10. Physical generation guard

The collector model itself has no logical evidence epoch and no event revision.

The existing physical `ProbeObservationGeneration` has a narrower purpose: a bounded
worker launched for an obsolete ProbeRules/interface generation must not contribute a
reply after that physical generation has been invalidated.

This guard is below availability hysteresis. It must not be used to version timer windows,
recovery policy, collector/materializer communication or route order.

A logical-policy-only change resets the affected collector channel state directly. It does
not require an `evidence_epoch`.

## 11. Synchronous materializer boundary

The collector remembers current channel statuses. Counter/latch changes that do not change
a routing-relevant status do not require materialization.

When the routing-relevant current snapshot changes, the collector calls the route
materializer synchronously:

```text
materialize(current_snapshot)
```

The call does not return until the current route transaction has either:

- reached and verified the requested materialized state; or
- failed with an explicit convergence result.

The materializer owns the last successfully materialized snapshot and compares before
acting:

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

There is therefore no:

- materializer-ready event;
- pending route-plan queue;
- concurrent route transaction;
- cancellation of a running route transaction;
- route-plan supersession inside a transaction.

New probe/tick facts that arrive while materialization runs accumulate only in the bounded
collector input state. On return, the collector performs another pass over the latest
facts and, if the routing-relevant snapshot changed again, invokes materialization again.

## 12. Route semantics

Availability changes only priority.

It never:

- adds an eligible payload path;
- removes an eligible payload path;
- changes binding membership;
- changes filter/NAT membership merely because a channel is BAD.

The existing effective-order and metric-hole model remains normative:

- GOOD paths form the preferred prefix in configured priority;
- other paths retain relative effective order;
- the free metric slot is emergent, not configured;
- all GOOD => no steady gap;
- all BAD/non-confirmed => first ordinary metric slot is free;
- the route sorter is the sole transactional executor for priority rearrangement.

## 13. Execution-agent consequence

`ProbeExecutionAgent` still owns physical send cadence, bounded send workers, stale
physical-worker rejection and local execution diagnostics.

It no longer owns logical observation windows.

Its availability-facing outputs reduce to:

```text
good_news(current physical channel)
tick(current logical channel)
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
because the boundary is deliberately synchronous.

Producer-to-collector ordering is also intentionally weaker than an event journal:
good-news multiplicity and the existence of a pending tick are aggregated facts.

A future general Event Delivery Environment may still use envelopes for other asynchronous
latest-value streams. It must not be introduced into this availability path merely to
reconstruct an order that the collector semantics explicitly discard.

## 15. Implementation migration

Current code still contains the superseded window model. The implementation migration
must remove, rather than wrap:

- `AvailabilityWindowState` missed-window integral;
- `LogicalProbeWindow`;
- logical `evidence_epoch`;
- `ProbeWindowBoundaryInfo.elapsed_intervals`;
- batched window catch-up;
- source-order locking whose only purpose is ordering good-news against window boundaries.

The migration should introduce the bounded collector aggregates and direct synchronous
materializer handoff as the next coherent code review unit.

Physical-generation safety, bounded send-worker execution, diagnostic lifecycle and the
already proven Linux ping mechanism remain valid unless separately contradicted.
