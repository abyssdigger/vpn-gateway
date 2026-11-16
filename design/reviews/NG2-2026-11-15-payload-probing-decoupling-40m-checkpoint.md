# NG2 cycle checkpoint — payload/probing decoupling

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-payload-probing-decoupling-40m`

## Cycle clock

- `CYCLE_INTERVAL`: 40 minutes
- cycle base: `ccfb625cbe7d60274991c920bd960f91f4cbec5a`
- `CYCLE_START_COMMIT`: `3c9136c66494279cd7ad9d9e4d5c1ab4ecaf3a36`
- `T0`: `2026-11-15T09:35:39Z`
- tested code head:
  `c861c26295790ce923163b37cae0be7a0f0b4155`
  at `2026-11-15T09:42:50Z`
- final reviewed/documented commit before checkpoint:
  `20b8bf558ccbb0dee8706651fc6cb2400e12fbb2`
  at `2026-11-15T09:47:26Z`
- reviewed-unit elapsed time before checkpoint: **11m47s**

The requested ordered unit completed before the selected interval. No independent runtime
assembly unit was started merely to consume the remaining time.

## Ordered work completed

### 1. Payload cleanup

Removed the remaining payload/probing coupling:

- structural `PayloadTrafficStateRequest` has no availability-derived fields;
- removed availability prefix from `PayloadProfileRequest`;
- PayloadTrafficManager no longer imports `probe_rules` or `probe_transport`;
- added probe-independent `AvailabilityPriorityConfig` /
  `AvailabilityPriorityChannel`;
- `AvailabilityGoodNews` / `AvailabilityTick` carry only the current priority-channel
  descriptor;
- split probe cadence from payload hysteresis;
- renamed `ProfileProbeAssignment` to `ProfileAvailabilityAssignment`;
- inactive availability produces no lower routing prefix hint;
- lower `no_problem_prefix_length` renamed to neutral
  `preferred_prefix_length`;
- hysteresis-only changes no longer restart tick cadence.

### 2. Quantitative assessment before tests

Against cycle base, at tested code head:

```text
production Python: +348 / -377 => net -29 lines
tests:             +252 / -261 => net  -9 lines
production files changed: 9
test/integration files changed: 13
new production modules: 0
removed production modules: 0
```

PayloadTrafficManager:

```text
625 -> 565 lines  (-60)
methods: 21 -> 21
probe-domain import lines: 2 -> 0
old physical-probe type references: 33 -> 0
```

PayloadRules:

```text
422 -> 409 lines
```

Pre-test metrics are recorded in:

`design/reviews/NG2-2026-11-15-payload-probing-decoupling-pretest-metrics.md`

### 3. Automated testing

Temporary draft PR #19 exposed PR-only CI.

Workflow `NG2 Python` run **617** on tested code head
`c861c26295790ce923163b37cae0be7a0f0b4155`:

- compile: PASS;
- **279 unit tests PASS**;
- selective probe-process isolation: PASS;
- EXP-025: PASS;
- EXP-026: PASS;
- EXP-027: PASS;
- nft ICMP selector: PASS;
- Linux instance lifecycle: PASS;
- Linux Adapter: PASS;
- Linux LOCAL_PROCESS: PASS;
- Linux dataplane: PASS.

No new external/target experiment was required.

### 4. Payload-management documentation after green tests

Only after the positive code gate, documentation was revised:

- `payload-traffic-manager.md` rewritten around structural payload + separate optional
  availability priority;
- `runtime-event-model.md` now has independent physical probe demand,
  AvailabilityPriorityConfig and structural PayloadTrafficStateRequest;
- availability routing and lower Adapter use neutral preferred-prefix terminology;
- collector docs use `AvailabilityHysteresisPolicy` and probe-independent
  `AvailabilityPriorityChannel`;
- probe Manager/Agent docs reflect cadence/hysteresis split and generic good-news/tick
  output;
- README and CHANGELOG updated.

Final active-doc terminology scan found no stale occurrences of:

- `no_problem_prefix_length`;
- `confirmed_live_prefix_length`;
- `AvailabilityChannelPolicy`;
- `ProfileProbeAssignment`;
- `ProbeGoodNewsInfo`;
- `ProbeTickInfo`;
- `availability_probe_states`.

## Autonomous review

`design/reviews/NG2-2026-11-15-payload-probing-decoupling-review.md`

Verdict: **PASS**.

No unresolved payload/probing cleanup finding remains.

## Remaining work / next review unit

Runtime assembly only:

1. build/project `AvailabilityProbeSetRequest`;
2. independently build/project `AvailabilityPriorityConfig`;
3. publish structural `PayloadTrafficStateRequest`;
4. wire ProbeExecutionAgent -> PayloadTrafficManager good-news/tick ingress;
5. project probe diagnostics into status;
6. add ordinary audit/retry scheduling.

Do not reintroduce availability into PayloadTrafficStateRequest or add an availability
event/evidence bus.
