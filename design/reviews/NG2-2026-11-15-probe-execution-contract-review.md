# NG2 autonomous review — non-attempt probe execution contract

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-probe-execution-contract-40m`  
**Scope:** generation-bound execution demand and delivery boundary between active probe execution and `AvailabilityProbeManager`

## Scope

Reviewed the new execution contract for:

- accidental restoration of semantic attempts or `NO_REPLY`;
- physical-plane deduplication vs logical-window policy;
- generation safety;
- startup/boundary timing ambiguity;
- concurrent delivery during rules-generation changes;
- component-model leakage into Linux/process details;
- premature commitment to a process/socket implementation.

## Findings

### F1 — physical identity validation was weaker than physical-plane identity

**Status:** accepted and fixed.

The initial `ProbeExecutionPlan` duplicate check compared whole
`PhysicalProbePlane` values. Two entries for the same
`(mechanism, InterfaceIdentity, target)` with different intervals therefore would not
have been rejected.

The plan now validates uniqueness by physical identity tuple and separately validates the
types of all plane/window entries. A regression test covers two different intervals for
the same physical plane.

### F2 — execution callbacks introduced a real concurrency boundary

**Status:** accepted and fixed.

Before this unit `AvailabilityProbeManager` had no state lock. A real sender/receiver can
deliver good-news/window events concurrently with request/audit processing. In particular,
an old-generation reply could race a physical rules transition around
`_active_generation` and `_window_states`.

The Manager now serializes its current semantic state with one re-entrant lock covering:

- request handling;
- audit;
- good-news delivery;
- window-boundary delivery;
- generation/plan observation;
- shutdown.

The lock intentionally spans the rules transition: once a physical generation starts
changing, an old execution event waits and is then rejected against the resulting current
generation. A threaded regression blocks the second Adapter apply, injects stale good-news
concurrently, and proves that it cannot publish REACHABLE into the new epoch.

### F3 — initial send vs first window boundary was ambiguous

**Status:** accepted and fixed in the contract.

If a plan merely supplied intervals, an implementation could legally schedule the first
send and first boundary for the same deadline and close an empty first window.

The normative phase rule is now:

```text
activation:
    start windows
    send once immediately on every physical plane

later coincident deadline:
    close due windows
    then send for the next window
```

This does not introduce attempt identity. Replies remain classified by arrival.

### F4 — shared logical probes must not share hysteresis state

**Status:** confirmed.

Physical transport is deduplicated by:

```text
(mechanism, InterfaceIdentity, target)
```

and uses the minimum requested interval of its enabled logical consumers. Logical
observation windows remain separate by `probe_id`. Therefore a faster consumer may cause
more physical sends, but it cannot alter another consumer's `failure_intervals` or
window counter.

### F5 — production `NO_REPLY` must remain absent

**Status:** confirmed.

The execution-to-Manager production inputs are only:

- `ProbeGoodNewsInfo`;
- `ProbeWindowBoundaryInfo`.

A window boundary carries no statement about a send result. Absence of good-news acquires
negative routing meaning only inside the Manager's existing window integral.

The diagnostic `LinuxIcmpProbeDriver -> ProbeAttemptResult(REPLY/NO_REPLY/ERROR)`
contract remains outside this production boundary.

### F6 — concrete transport topology is still an evidence-bearing lower unit

**Status:** accepted and deferred behind the next implementation unit.

This review deliberately does not choose between a long-lived ping process, ping socket,
or another Linux execution mechanism. Such a choice affects process/socket lifecycle,
reply validation, local-error diagnostics and potentially target-specific kernel behavior.

The current contract is sufficient to implement and compare those mechanisms without
changing availability routing semantics.

Re-entry condition: start the concrete sender/receiver machinery unit and validate any
mechanism property not already covered by the existing diagnostic ping/LOCAL_PROCESS
evidence.

### F7 — ordering of reply and boundary facts must survive asynchronous delivery

**Status:** accepted and deferred behind the existing EventEnvelope gate.

The execution source must serialize good-news and boundary publications for one execution
generation. The already-planned EventEnvelope epoch/revision layer must preserve/reject
revisions so a late old event cannot be applied after a newer one.

No separate ordering mechanism was added to this review unit because that would duplicate
the explicit Event Delivery Environment work item.

## Complexity/component-model review

No new Manager, scheduler, retry loop, recovery threshold or transport-specific semantic
type was introduced.

The split remains:

```text
AvailabilityProbeManager
    owns rules readiness generation + evidence windows

ProbeExecutionPlanCalculator
    pure projection of current execution demand

future lower execution machinery
    consumes physical cadence
    emits valid reply / window-boundary facts
```

Linux uid/gid, ping executable, socket options, process handles and transport errors do not
leak into `ProbeExecutionPlan`.

## Test coverage added

Added deterministic coverage for:

- shared physical plane -> minimum physical send interval;
- distinct concrete paths remain distinct planes;
- disabled probes create no execution demand;
- typed generation-bound execution events;
- duplicate physical identity rejection independent of interval;
- Manager execution-plan exposure only under a READY generation;
- execution event path reusing existing good-news/window semantics;
- concurrent stale good-news during a blocked physical generation transition.

The repository push workflow is configured to run compile/unit and privileged Linux
integration on Python-path changes. This connector does not expose push-triggered workflow
runs, so this review does not claim an observed CI result for the new commits.

## Verdict

**PASS for the semantic execution-contract review unit.**

No unresolved semantic or concurrency finding blocks the next unit. The next unit is the
concrete long-lived Linux sender/receiver machinery implementing `ProbeExecutionPlan`,
with local execution diagnostics and mechanism-specific evidence as needed.
