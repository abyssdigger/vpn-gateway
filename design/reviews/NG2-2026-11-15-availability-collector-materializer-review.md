# NG2 review — aggregate availability collector / synchronous route materializer

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-availability-collector-materializer-40m`  
**Scope:** architecture review unit only; Python migration inspected but not implemented

## Reviewed invariants

The review checked the new model against:

- component ownership boundaries;
- probe physical-generation safety;
- route-membership invariant;
- single transactional route executor;
- simultaneous tick/good-news semantics;
- delayed reply recovery;
- bounded producer state;
- existing PayloadTrafficManager serialization;
- Rust-aligned minimal state/data flow.

## Findings

### F1 — collector ownership initially crossed a Manager/Machinery boundary

**Finding:** the first draft placed the stateful availability collector in
`AvailabilityProbeManager` and then synchronously called the route materializer owned by
`PayloadTrafficManager`. That would make one Manager depend directly on another
Manager's private Machinery and would conflict with the component model.

**Disposition:** accepted and fixed.

Routing hysteresis/current channel state now belongs inside `PayloadTrafficManager`.
`AvailabilityProbeManager` retains physical ProbeRules/readiness and execution-demand
ownership. Producer-facing good-news/tick input is a bounded short-lock port; collector
state and route materialization are one Manager flow.

### F2 — materializer baseline was too optimistic after partial failure

**Finding:** "compare with last successfully materialized snapshot" was insufficiently
precise if a kernel transaction fails after some route moves.

**Disposition:** accepted and fixed.

The baseline is now the last **verified** materialized projection. A failed/partial
transaction does not advance it; before a subsequent plan the materializer re-observes
authoritative route state.

### F3 — active documents still described the superseded window pipeline

**Finding:** the initial supersession note was not enough. Active documents still
described:

```text
AvailabilityProbeStateInfo
 -> RuntimeStateManager
 -> ProfileAvailabilityEvidence
 -> PayloadTrafficIntentCalculator
 -> effective ordered_paths
```

and logical windows / `elapsed_intervals`.

**Disposition:** accepted and fixed in the architecture set.

The routing model, runtime event model, probe Manager design, probe Agent design and
PayloadTrafficManager ownership now point to the bounded aggregate collector model.
Historical checkpoint/review documents are intentionally not rewritten.

### F4 — EventEnvelope would solve a problem the new availability path removes

**Finding:** the previous next unit proposed epoch/revision ordering primarily to protect
late asynchronous availability state delivery. The new path deliberately does not carry
that asynchronous state stream.

**Disposition:** accepted and fixed architecturally.

Collector -> route materializer is synchronous inside PayloadTrafficManager.
Producer -> collector is bounded aggregation, not an event journal. EventEnvelope may
still be useful for genuinely asynchronous streams elsewhere, but it is no longer a
prerequisite for availability-driven route reordering.

### F5 — physical generation guard remains justified

**Finding:** removing every generation/epoch-like token would re-open a real stale-worker
race: an old bounded ping process can finish after ProbeRules/interface replacement.

**Disposition:** retained with narrowed scope.

`ProbeObservationGeneration` remains only as a physical worker-lifetime guard. It does
not version hysteresis, ticks, collector state, materializer state or route order.

### F6 — Python migration surface is broad but mechanical

**Finding:** current Python still encodes the superseded model in multiple layers.

Observed migration surface includes:

- `availability_routing.py`: `AvailabilityWindowState`;
- `probe_rules.py`: `AvailabilityWindowPolicy(failure_intervals)`;
- `probe_transport.py`: `LogicalProbeWindow`, `evidence_epoch`,
  `ProbeWindowBoundaryInfo.elapsed_intervals`;
- `linux_probe_execution.py`: logical-window schedule/boundary publication;
- `availability_probe_manager.py`: Manager-owned window state, evidence epochs and
  routing-state publication;
- `runtime_state_manager.py` / `payload_traffic_intent.py`: the old
  AvailabilityProbeStateInfo -> effective-order pipeline;
- corresponding unit tests.

**Disposition:** accepted; implementation intentionally deferred to the next code review
unit. This architecture unit must not partially wrap the old pipeline with new abstractions.

The correct migration direction is deletion/reownership, not adaptation around the old
window model.

## Human semantic gates

Two user-visible policy semantics were not specified by the agreed state-machine
discussion and should not be guessed in code.

### H1 — initial channel state

Recommended default:

```text
routing status = BAD / NOT_CONFIRMED
recovery_progress = 0
```

Diagnostics may present this as UNKNOWN until observation exists.

This preserves payload membership/order when nothing is confirmed, while requiring the
normal `recovery_good_news` criterion before a path becomes preferred.

Alternative: start GOOD and require failure ticks to demote. That materially changes
startup routing preference.

### H2 — logical policy-only change

Recommended default:

- preserve current GOOD/BAD status;
- reset the active hysteresis accumulator:
  - GOOD: `failure_misses = 0`;
  - BAD: `recovery_progress = 0`;
- clear `good_news_since_tick` and pending tick/good-news aggregates for that channel.

This avoids a policy edit itself changing route priority while ensuring old partial
hysteresis is not interpreted under new thresholds.

Alternative: reinitialize the channel to BAD/NOT_CONFIRMED. That can cause an immediate
priority transition on configuration change.

Both choices are externally observable and therefore require human agreement.

## Final verdict

**Core architecture: PASS.**

The agreed aggregate model is internally coherent after F1-F5 and is substantially simpler
than the window/epoch design.

**Code migration: gated only by H1 and H2.**

No experiment is required for this architecture unit: it introduces no new kernel claim.
The already proven physical ping and route-transition mechanics remain unchanged.
