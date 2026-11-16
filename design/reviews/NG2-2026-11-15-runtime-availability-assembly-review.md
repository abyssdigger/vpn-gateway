# NG2 review — minimal availability runtime assembly

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-runtime-assembly-40m`  
**Scope:** normalized availability projection and direct Manager/Agent wiring

## Verdict

**PASS after one accepted architecture fix.**

The review unit connects the already-tested probe and payload domains without restoring a
shared availability evidence/state layer.

## Implemented

New module:

`design/NG2/code/python/rou/runtime_assembly.py`

It contains:

- `RuntimeAvailabilityChannel`;
- `RuntimeAvailabilityConfig`;
- `AvailabilityProbeSetCalculator`;
- `AvailabilityPriorityConfigCalculator`;
- `ProbeExecutionPlanPort`;
- `AvailabilityGoodNewsPort`;
- `AvailabilityTickPort`;
- `AvailabilityConfigFanout`.

The normalized runtime slice is upstream of both domains:

```text
RuntimeAvailabilityConfig
    +--> AvailabilityProbeSetCalculator
    |       -> AvailabilityProbeSetRequest
    |
    +--> AvailabilityPriorityConfigCalculator
            -> AvailabilityPriorityConfig
```

No payload contract is derived from physical probe state/results.

## F1 — priority projection was initially derived from ProbeSetRequest

**Classification:** accepted and fixed.

The first implementation projected:

```text
AvailabilityProbeSetRequest
    -> AvailabilityPriorityConfig
```

That preserved payload-domain isolation but made the runtime projection itself serially
dependent on the physical-probe contract, contradicting the agreed independent projection
model.

Fixed by introducing the small normalized upstream `RuntimeAvailabilityConfig`. Both
domain requests are now pure sibling projections from the same explicit input.

## F2 — fanout order must make new Agent outputs immediately acceptable

**Classification:** accepted and fixed by explicit contract/test.

One normalized config fanout performs:

```text
1. calculate both projections without side effects
2. PayloadTrafficManager.configure_availability(priority)
3. AvailabilityProbeManager.handle_request(probes)
```

The payload descriptor is installed before the probe Manager may publish a new execution
plan. Therefore newly emitted good-news/tick descriptors can match immediately.

This is **ordered fanout, not a transaction**.

If the second Manager fails unexpectedly after step 2:

- a newly enabled payload channel begins with `availability_problems=false`;
- descriptors changed by path/hysteresis reject old callbacks;
- disabled availability is a no-op;
- if only physical target/mechanism changed, the old probe demand remains the actual
  current demand until the probe Manager accepts the new request, so its observations are
  not falsely attributed to an already-running new physical plane.

No rollback protocol or cross-Manager transaction is justified.

## F3 — event ports must not recreate an EventEnvelope dependency

**Classification:** accepted and satisfied.

The ports are synchronous typed forwarding boundaries only:

```text
AvailabilityProbeManager
    -> ProbeExecutionPlanPort
    -> ProbeExecutionAgent.update_plan()

ProbeExecutionAgent
    -> AvailabilityGoodNewsPort
    -> PayloadTrafficManager.handle_availability_good_news()

ProbeExecutionAgent
    -> AvailabilityTickPort
    -> PayloadTrafficManager.handle_availability_tick()
```

No revision, epoch, queue, retry journal or asynchronous event bus is added.

The physical `ProbeObservationGeneration` remains inside the probe execution path.

## F4 — runtime normalized slice must not become a second state machine

**Classification:** accepted and satisfied.

`RuntimeAvailabilityConfig` is immutable input data only. It owns no:

- current availability status;
- counters/latches;
- worker generation;
- route order;
- materialized state;
- history.

Its only purpose is to carry the common normalized configuration needed for two pure
domain projections.

## F5 — structural payload projection is not part of this code unit yet

**Classification:** accepted; next review unit, not a defect in this unit.

There is still no executable general RuntimeStateManager/config/binding model in the
Python reference. Creating one merely to claim a complete three-way runtime projection
would exceed the smallest coherent unit and invent upstream policy not yet modeled.

This unit therefore completes the availability-specific assembly only. Structural
`PayloadTrafficStateRequest` remains an independent existing Manager input.

The next runtime review unit should address the smallest justified structural runtime
projection/assembly without coupling it back to availability.

## Tests/evidence

Final code head for this review unit:

`8ea8b07793bdae84487fde9488c0924a587896fa`

GitHub Actions `NG2 Python` run **634**:

- compile: PASS;
- **286 rootless unit tests PASS**;
- selective probe-process isolation: PASS;
- EXP-025 stale probe conntrack generation: PASS;
- EXP-026 probe-class conntrack cleanup: PASS;
- EXP-027 route-priority transition: PASS;
- nft ICMP selector: PASS;
- Linux instance lifecycle: PASS;
- Linux Adapter: PASS;
- Linux LOCAL_PROCESS: PASS;
- Linux dataplane: PASS.

No new kernel behavior is claimed, so no new external experiment is required.

## Resulting boundary

```text
normalized availability config
    |
    +--> physical probe request --> AvailabilityProbeManager
    |                                  |
    |                              execution plan
    |                                  |
    |                                  v
    |                          ProbeExecutionAgent
    |                            |           |
    |                         good news     tick
    |                            |           |
    +--> payload priority config |           |
              |                  |           |
              +------------------v-----------v
                         PayloadTrafficManager
```

No unresolved finding remains in this review unit.
