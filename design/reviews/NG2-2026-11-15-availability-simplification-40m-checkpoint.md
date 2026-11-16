# NG2 cycle checkpoint — availability simplification

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-availability-simplification-40m`

## Cycle clock

- `CYCLE_INTERVAL`: 40 minutes
- cycle base: `4fe5af43b8891505bfbaae0f27b8a0c70b4471c6`
- `CYCLE_START_COMMIT`: `039a1c0f34e7d8842e8608f1a2af672052f0ecc4`
- `T0`: `2026-11-15T08:44:38Z`
- final reviewed/documented commit before checkpoint:
  `9df9b17f7fbb79c285f893ceba88c31bcefc4e73`
  at `2026-11-15T09:00:28Z`
- elapsed reviewed unit: **15m50s**

The coherent availability simplification unit completed before the selected interval. No
independent next review unit was started merely to consume the remainder.

## Completed

The superseded availability window/evidence pipeline was removed rather than adapted.

Current routing state per logical probe channel is only:

```text
availability_problems: bool
```

Initial and disabled-probing state is `false`.

Inputs are bounded:

```text
pending_good_news: 0..recovery_good_news
tick_pending: bool
```

Several delayed replies may complete recovery in one collector pass. Multiple undrained
ticks collapse to one fact.

## Ownership after migration

`AvailabilityProbeManager` owns only:

- ProbeRules/readiness;
- physical `ProbeObservationGeneration`;
- `ProbeExecutionPlan | None` publication.

`ProbeExecutionAgent` owns only:

- deduplicated physical send cadence;
- logical tick cadence;
- bounded send workers;
- local READY/ERROR/INACTIVE diagnostics.

`PayloadTrafficManager` owns:

- bounded good-news/tick ingress;
- current per-channel availability state;
- Profile/path problem aggregation;
- effective path order;
- `no_problem_prefix_length`;
- the same sole serialized route materializer used by the rest of payload policy.

## Removed production artifacts

- `availability_routing.py`;
- `payload_traffic_intent.py`;
- old availability-specific `runtime_state_manager.py` executable slice.

Also removed obsolete flow/test modules:

- `test_availability_routing.py`;
- `test_availability_runtime_flow.py`;
- `test_payload_traffic_intent.py`;
- `test_probe_execution_flow.py`;
- `test_runtime_state_manager.py`.

`availability_probe_state.py` now contains only the physical generation guard.

## Removed concepts

The executable availability path no longer has:

- `AvailabilityProbeStateInfo` routing mediation;
- `AvailabilityWindowState`;
- `LogicalProbeWindow`;
- `ProbeWindowBoundaryInfo`;
- `evidence_epoch`;
- `elapsed_intervals`;
- logical boundary catch-up;
- boundary/good-news source ordering;
- availability-specific EventEnvelope requirement.

The old `confirmed_live_prefix_length` name was replaced by
`no_problem_prefix_length`.

## Review findings fixed

Autonomous review:

`design/reviews/NG2-2026-11-15-availability-simplification-review.md`

Verdict: **PASS**.

Accepted/fixed findings included:

1. routing evidence still owned by AvailabilityProbeManager;
2. logical windows still present in ProbeExecutionAgent;
3. obsolete RuntimeStateManager / intent-calculator mediation;
4. stale logical callback rejection without reintroducing epochs;
5. repeated identical effective intent causing unnecessary materialization;
6. multi-probe path aggregation being too aggressive;
7. old confirmed-live terminology leaking into materialization;
8. unnecessary collector thread/queue complexity.

No unresolved finding remains.

## Code-size result

Compared with cycle base `4fe5af43...` and final tested code baseline
`857ea319...`:

```text
production Python: +671 / -1310  => net -639 lines
tests:             +614 / -2535  => net -1921 lines
```

This is a real reduction rather than relocation of the same availability machinery.

## Tests and evidence

Temporary draft PR #18 was used only as a PR-triggered CI gate.

Final code-bearing workflow:

- `NG2 Python` run **579**
- code head: `857ea3192bfe9f63e8567bf3f598b1b00f30c5d7`
- compile: PASS
- rootless unit suite: **278 tests PASS**
- privileged Linux integration: PASS
- selective probe-process isolation: PASS
- EXP-025: PASS
- EXP-026: PASS
- EXP-027: PASS
- nft ICMP selector syntax: PASS
- Linux instance lifecycle: PASS
- Linux Adapter: PASS
- Linux LOCAL_PROCESS: PASS
- Linux dataplane: PASS.

Later commits in this cycle are documentation/review-only.

No new kernel/userspace claim was introduced, so no new target experiment was required.

## Human decisions

None open.

## Remaining work

The availability state machine itself no longer has an implementation gate.

Remaining work is runtime assembly rather than more availability machinery:

1. structural config/request calculation and fanout;
2. send current probe/assignment configuration to AvailabilityProbeManager and
   PayloadTrafficManager;
3. wire ProbeExecutionAgent good-news/tick outputs to PayloadTrafficManager ingress;
4. project local probe execution diagnostics into final status;
5. general Event Delivery ordering only for other genuinely asynchronous streams.

## Next review unit

Minimal runtime assembly around the now-simplified Managers/Agent, without restoring an
availability event bus or evidence layer.
