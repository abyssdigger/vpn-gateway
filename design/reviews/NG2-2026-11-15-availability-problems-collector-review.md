# NG2 review — availability_problems collector core

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-availability-problems-collector-40m`  
**Scope:** normative terminology plus pure collector/order core

## Scope reviewed

- `AvailabilityChannelPolicy`;
- bounded `AvailabilityPendingInput`;
- `AvailabilityChannelState`;
- `calculate_availability_path_order()`;
- interaction with the agreed collector/materializer architecture;
- startup/disabled-probing semantics;
- simultaneous tick/good-news behavior;
- delayed-reply recovery;
- route membership and configured-priority invariants.

## Findings

### F1 — GOOD/BAD was semantic leakage from explanatory slang

**Disposition:** accepted and fixed.

The routing state is now only:

```text
availability_problems: bool
```

Initial state is `false`. Disabled probing means `false` by definition.

Availability is therefore an optional negative priority modifier rather than a source of
the base runtime ranking.

### F2 — old "confirmed live" terminology implied startup delay

**Disposition:** accepted and fixed in the normative architecture.

Paths without availability problems form the preferred prefix in configured priority.
Problem paths retain their current relative order. With no problems, effective order is
exactly configured order. If every path has problems, probing has no better path to
promote and relative order is retained.

The metric-gap projection remains a lower materialization concern.

### F3 — bounded good-news count and good-news latch are both necessary

**Disposition:** retained.

They represent different timescales:

- `pending_good_news` counts replies accumulated since the last collector pass and is
  reset by that pass;
- `good_news_since_tick` remembers that at least one accepted reply occurred since the
  preceding processed tick, even if collector passes happened in between.

Collapsing them would either lose delayed-reply multiplicity or lose the no-miss fact
across collector passes.

### F4 — tick multiplicity must not leak back through scheduler delay

**Disposition:** satisfied by the core.

`AvailabilityPendingInput.note_tick()` only sets a boolean. Repeated undrained timer
firings cannot become an elapsed-interval count.

### F5 — policy-only change must not itself reorder routes

**Disposition:** fixed in the normative contract and represented by
`reset_policy_progress()`.

The current `availability_problems` flag is preserved, while hysteresis progress is
cleared. The integration layer must also clear that channel's pending input aggregate.

### F6 — disable must remove availability influence immediately

**Disposition:** fixed in the core.

`AvailabilityChannelState.disable()` clears `availability_problems` and progress.
The integration layer must also clear pending input. Payload membership is unaffected.

## Test coverage added

Deterministic tests cover:

- saturating good-news count;
- boolean/collapsed tick;
- initial no-problem state;
- negative hysteresis threshold;
- good-news reset before a tick;
- several delayed replies completing recovery in one pass;
- recovery progress across ticks containing good news;
- reset on a tick without good news;
- simultaneous recovery + tick not immediately re-degrading;
- policy-progress reset preserving the routing flag;
- disabled probing clearing the routing flag;
- configured order when no problem exists;
- promotion around a problem path;
- current relative order of problem paths;
- all-problem current-order retention;
- restored configured priority when problems clear.

## Boundary review

The new module is intentionally pure and does not yet replace the old executable pipeline.
That is a separate coherent unit because it changes ownership and threading across
`AvailabilityProbeManager`, `ProbeExecutionAgent`, `RuntimeStateManager` and
`PayloadTrafficManager`.

The next unit must delete/reown the old window/evidence path rather than adapt it around
this core.

## Verdict

**PASS** for the collector semantic core.

No new kernel/userspace behavior is claimed, so no new privileged experiment is required.
CI remains required for Python regression evidence.
