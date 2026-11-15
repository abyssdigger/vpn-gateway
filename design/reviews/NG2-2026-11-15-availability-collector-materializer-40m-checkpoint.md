# NG2 cycle checkpoint — availability collector/materializer architecture

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-availability-collector-materializer-40m`

## Cycle clock

- `CYCLE_INTERVAL`: 40 minutes
- cycle base: `a5e5d8ea90d4c96b023c767783af9af1b086dbaf`
- `CYCLE_START_COMMIT`: `fc34711ae3e9a66f39b1ce70ddb7ec851c7f6ca6`
- `T0`: `2026-11-15T03:49:23Z`
- final reviewed commit before checkpoint:
  `ee334776482663186fe5a46c4acb938805d0badb`
  at `2026-11-15T03:55:06Z`
- reviewed-unit elapsed time: **5m43s**

The architecture review unit completed well before the selected interval. Per
`CONTINUOUS-DEVELOPMENT.md`, no independent code-migration unit was started merely to
consume the remaining interval.

## Completed

Added normative:

`design/NG2/availability-collector-materializer.md`

The target model is now:

```text
ping workers/timer
      |
bounded aggregates
pending_good_news[channel] 0..recovery_good_news
tick_pending[channel] bool
      |
      v
PayloadTrafficManager availability collector
      |
current GOOD/BAD states
      |
      v
synchronous sole route-priority materializer
```

Key semantics:

- individual pings are colorless;
- ping multiplicity is significant while BAD and only zero/non-zero significant while GOOD;
- the ping counter saturates at `recovery_good_news`;
- tick is a boolean pending fact, never a queue/count;
- repeated undrained ticks collapse to one;
- GOOD -> BAD is tick-only;
- BAD -> GOOD is good-news-only;
- delayed replies can complete recovery in one collector pass;
- tick + pings in one pass are simultaneous observations;
- a transition caused by one input kind is not immediately subjected to the opposite rule
  in that same pass;
- collector -> materializer is synchronous;
- producers never block on materialization; they only update bounded aggregates;
- events arriving during materialization are processed after return as current facts;
- availability never changes payload route membership.

## Ownership changes

Routing hysteresis/current channel state moved into `PayloadTrafficManager`.

`AvailabilityProbeManager` now targets only:

- ProbeRules/readiness;
- current physical generation;
- execution demand.

`ProbeExecutionAgent` targets only:

- physical send cadence;
- logical tick cadence;
- bounded workers;
- stale physical-generation rejection;
- local diagnostics.

The physical `ProbeObservationGeneration` remains as a narrow stale-worker guard.
Logical `evidence_epoch`, logical window boundaries and `elapsed_intervals` are removed
from the target architecture.

## Documents updated

- `design/NG2/availability-collector-materializer.md`
- `design/NG2/availability-probe-manager.md`
- `design/NG2/availability-routing-model.md`
- `design/NG2/probe-execution-agent.md`
- `design/NG2/runtime-event-model.md`
- `design/NG2/payload-traffic-manager.md`

Review:

`design/reviews/NG2-2026-11-15-availability-collector-materializer-review.md`

Core architecture verdict: **PASS**.

## Tests / experiments

No code was changed in this review unit, so no CI result is claimed.

No new kernel/userspace behavior is introduced. Existing ping-generation and
route-transition evidence remains applicable; no new experiment is required for this
architecture unit.

## Python migration inspection

The current implementation is intentionally left unchanged for the next coherent code
unit. The inspected removal/reownership surface includes:

- `availability_routing.py`;
- `probe_rules.py`;
- `probe_transport.py`;
- `linux_probe_execution.py`;
- `availability_probe_manager.py`;
- `runtime_state_manager.py`;
- `payload_traffic_intent.py`;
- affected unit tests.

The next implementation must delete the superseded window/evidence pipeline rather than
wrap it with EventEnvelope machinery.

## Human decisions required

Two externally observable policy choices remain.

### H1 — initial channel state

Recommended:

```text
BAD / NOT_CONFIRMED
recovery_progress = 0
```

Diagnostic presentation may remain UNKNOWN until evidence exists.

Alternative: initial GOOD.

### H2 — policy-only change for an existing channel

Recommended:

- preserve current GOOD/BAD;
- reset active hysteresis progress;
- clear the per-channel pending tick/good-news aggregates.

Alternative: reinitialize to BAD/NOT_CONFIRMED.

## Next review unit

After H1/H2 are agreed, migrate Python to the bounded aggregate collector:

1. introduce normalized `failure_ticks + recovery_good_news`;
2. implement saturating good-news counters and boolean ticks;
3. move availability state into PayloadTrafficManager;
4. simplify ProbeExecutionAgent to sends + ticks;
5. remove logical windows/evidence epochs/batched boundaries;
6. remove RuntimeStateManager availability-priority mediation;
7. update deterministic unit tests;
8. run autonomous expert review and CI.
