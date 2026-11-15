# NG2 cycle checkpoint — payload/probing tail review

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-payload-probing-tail-review-40m`

## Cycle clock

- `CYCLE_INTERVAL`: 40 minutes
- cycle base: `e281330a424aaa830a01b5d432f2ab5ed6d00f40`
- `CYCLE_START_COMMIT`: `9f03cf48e0bc8f3dd372641ba63588de3376c04a`
- `T0`: `2026-11-15T09:06:21Z`
- final reviewed commit before checkpoint:
  `40fe9f702f6219922ca5161dc57cce7c672ac3a9`
  at `2026-11-15T09:07:57Z`
- reviewed-unit elapsed time: **1m36s**

This was intentionally a review-only unit. Per user direction, no production cleanup or
runtime assembly was started before reporting the payload/probing tails.

## Review

`design/reviews/NG2-2026-11-15-payload-probing-tail-review.md`

Verdict: **FINDINGS — cleanup required before runtime assembly**.

## Main findings

1. `PayloadProfileRequest.no_problem_prefix_length` is a transient availability-derived
   boundary leaking into the structural payload Request contract.
2. `PayloadTrafficManager` still imports/stores the complete probe-domain model:
   `AvailabilityProbeSetRequest`, `AvailabilityProbeRequest`,
   `LogicalProbeChannel`, `ProbeGoodNewsInfo`, `ProbeTickInfo`, including
   target/mechanism information that payload priority does not need.
3. `AvailabilityChannelPolicy.interval_seconds` leaks probe cadence into payload
   hysteresis, even though the collector uses only failure/recovery thresholds.
4. `ProfileProbeAssignment` is still named/keyed as a probe object rather than an
   availability-channel association.
5. An availability boundary is emitted even when a Profile has no active availability
   configuration; optional probing is therefore not yet a true semantic no-op.
6. Active architecture docs still describe availability assignment/policy as part of
   `PayloadTrafficStateRequest`, contradicting the desired separation and current
   separate configuration path.
7. `CurrentRuntimeSnapshot.availability_probe_states` is a dead artifact from the
   removed AvailabilityProbeStateInfo control path.
8. `PayloadTrafficStateInfo` / `PayloadRulesState` themselves are clean and should not
   gain probe verdicts.
9. Retaining last verified effective route order is justified materializer state, not
   probe evidence history.
10. Generic lower `RoutingDomainSpec.no_problem_prefix_length` is still
    availability-flavored naming; the lower domain may need an optional technical boundary
    but should eventually use neutral routing terminology.

## Recommended next cleanup unit

Before runtime assembly:

1. remove availability-derived boundary from `PayloadTrafficStateRequest`;
2. introduce a small probe-independent availability-priority input contract;
3. split hysteresis thresholds from probe cadence;
4. rename ProfileProbeAssignment to an availability-channel assignment;
5. make unavailable/disabled availability input produce no lower routing-boundary hint;
6. remove stale runtime/docs snapshot/request references;
7. optionally neutralize lower routing-boundary naming;
8. rerun payload and full Linux route-priority regression.

## Tests

No production code changed in this review-only unit, so no CI result is claimed and no new
kernel experiment is required.

## Human decisions

None required to understand the findings. Cleanup should be discussed/accepted before
implementation because F1/F2 reshape public internal-domain contracts.
