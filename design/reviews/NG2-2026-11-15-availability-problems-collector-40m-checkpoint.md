# NG2 cycle checkpoint — availability_problems collector core

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-availability-problems-collector-40m`

## Cycle clock

- `CYCLE_INTERVAL`: 40 minutes
- cycle base: `8afc0ee25691bbbc6e8f50ac3a3e5eeeed376e0a`
- `CYCLE_START_COMMIT`: `b117ae0b256f40b6b5e84dbb510bf26922869325`
- `T0`: `2026-11-15T04:51:40Z`
- final reviewed commit before checkpoint:
  `f608b335530b342203a6708a322724df6ad997d0`
  at `2026-11-15T04:54:21Z`
- reviewed-unit elapsed time: **2m41s**

The coherent semantic-core unit completed before the selected interval. No independent
cross-Manager wiring unit was started merely to consume the remaining interval.

## Completed

Availability routing state is now defined as one optional negative modifier:

```text
availability_problems: bool
```

Semantics:

- initial state: `false`;
- probing disabled: `false` by definition;
- configured/base ranking remains authoritative by default;
- only negative hysteresis sets the flag;
- recovery good news clears it;
- availability never changes payload route membership.

Added pure executable core:

- `rou/availability_collector.py`
  - `AvailabilityChannelPolicy`;
  - `AvailabilityPendingInput`;
  - `AvailabilityChannelState`;
  - `calculate_availability_path_order()`.
- `rou/tests/test_availability_collector.py`.

Input aggregation:

```text
pending_good_news: 0..recovery_good_news   # saturating
tick_pending: bool                         # repeated ticks collapse
```

State machine:

- no-problem -> problem only while processing a tick;
- problem -> no-problem only while processing good news;
- delayed replies are counted independently and may complete recovery in one pass;
- a tick without good news breaks incomplete recovery;
- simultaneous recovery + tick cannot immediately reintroduce the problem;
- policy-progress reset preserves `availability_problems`;
- disable clears the flag.

Path order:

- no-problem paths form the configured-priority prefix;
- problem paths preserve current relative order;
- no problems => exactly configured order;
- all problems => current relative order unchanged.

## Architecture terminology

Active documents were updated away from GOOD/BAD/CONFIRMED_LIVE language toward
`availability_problems`.

The previous EventEnvelope/window/epoch model remains superseded for this path.

## Autonomous review

Review:

`design/reviews/NG2-2026-11-15-availability-problems-collector-review.md`

Verdict: **PASS** for the semantic core.

No accepted finding remains in this unit.

## Tests and evidence

Temporary draft PR #17 was opened only to expose PR-triggered CI and closed without merge.

Observable code-bearing CI head:

`845fb8478da9dfb88d3669172e8a88a529505754`

`NG2 Python` run **518**:

- compile: PASS;
- unit: **354 tests PASS** (`Ran 354 tests in 0.501s`, `OK`);
- privileged `linux-integration`: PASS;
- selective probe-process isolation: PASS;
- EXP-025: PASS;
- EXP-026: PASS;
- EXP-027: PASS;
- nft ICMP selector syntax: PASS;
- Linux instance lifecycle: PASS;
- Linux Adapter: PASS;
- Linux LOCAL_PROCESS: PASS;
- Linux dataplane: PASS.

Commits after the tested code-bearing head are documentation/review-only.

No new kernel/userspace claim was introduced, so no new target experiment is required.

## Human decisions

None open for this unit.

The earlier startup question is resolved:

```text
availability_problems = false
```

both initially and when probing is disabled.

Policy-only change preserves the flag and resets hysteresis progress/pending aggregates.

## Remaining migration

Current production Python still contains the superseded window/evidence pipeline. The next
coherent review unit is the ownership/wiring migration:

1. move channel state + bounded input ownership into `PayloadTrafficManager`;
2. replace logical windows with logical tick cadence in `ProbeExecutionAgent`;
3. remove `evidence_epoch`, `elapsed_intervals`, boundary publication and source-order lock;
4. remove routing-control `AvailabilityProbeStateInfo -> RuntimeStateManager ->
   PayloadTrafficIntentCalculator` mediation;
5. derive effective order inside `PayloadTrafficManager`;
6. route availability-driven changes through its existing sole transactional executor;
7. update deterministic tests and CI.

