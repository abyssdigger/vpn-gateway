# VPN-GATE NG2 — AvailabilityProbeManager

**Status:** normative NG2 design  
**Date:** 2026-11-15  
**Scope:** active-probe network-plane readiness and execution demand

## 1. Responsibility

`AvailabilityProbeManager` owns only the active-probe network plane:

- latest normalized `AvailabilityProbeSetRequest`;
- probe-specific `NetworkRules`;
- physical rules/readiness observation and repair;
- current `ProbeObservationGeneration`;
- publication of the current `ProbeExecutionPlan | None`.

It does **not** own:

- availability hysteresis;
- `availability_problems`;
- ping counters or tick latches;
- Profile priority;
- payload route membership;
- payload route materialization.

Those routing concerns belong to `PayloadTrafficManager`.

## 2. Probe request

Normalized probe input:

```text
probe_id
mechanism
concrete InterfaceIdentity
IPv4 target
enabled
interval_seconds
AvailabilityHysteresisPolicy
    failure_ticks
    recovery_good_news
```

`enabled=false` preserves logical configuration but creates no physical probe demand.

Physical ProbeRules are deduplicated by:

```text
(mechanism, InterfaceIdentity, target)
```

Neither cadence nor hysteresis is part of physical NetworkRules semantics. Cadence is
execution demand; hysteresis is projected separately into the payload-facing
AvailabilityPriorityChannel.

## 3. Physical generation

Probe results are authoritative only while the physical rules plane is freshly:

```text
KNOWN + MATCHED
```

The Manager owns one monotonically increasing `ProbeObservationGeneration`.

A new generation is opened after fresh READY. It is invalidated when:

- physical desired ProbeRules change;
- rules lose READY;
- all probes become disabled;
- shutdown starts.

Same-name/new-ifindex is a physical change because `InterfaceIdentity` includes ifindex.

The generation token exists only so old ping workers cannot report success into a newer
physical plane. It is not availability policy and is never used for route ordering.

## 4. Execution demand

For a current READY generation:

```text
AvailabilityProbeSetRequest
        +
ProbeObservationGeneration
        |
        v
ProbeExecutionPlanCalculator
        |
        v
ProbeExecutionPlan
    physical planes[]
    logical channels[]
```

Physical plane cadence is the fastest interval requested by its enabled logical consumers.

A logical execution channel carries physical send identity/cadence plus a
probe-independent `AvailabilityPriorityChannel` descriptor for good-news/tick output.
There is no logical evidence epoch.

`None` means execution must quiesce.

On physical invalidation, `None` is published before any later replacement generation.
Equivalent plans are suppressed.

## 5. Logical-only changes

A change that does not alter physical ProbeRules, for example only:

- `failure_ticks`;
- `recovery_good_news`;
- a logical consumer added to an already-existing physical plane;

does not create a new physical generation.

It can still publish a changed execution plan so the Agent sees current logical channels.
A hysteresis-only change updates the priority descriptor but does not restart physical or
tick cadence; an `interval_seconds` change changes cadence without changing physical
ProbeRules generation.

Availability hysteresis reset/preservation rules are handled by
`PayloadTrafficManager`, not here.

## 6. Execution-plan publication failures

Execution-plan publication is process-local and synchronous.

If publication of a changed plan raises:

- the exception remains visible to the Manager caller;
- the failed plan is not recorded as successfully published;
- an equivalent later request/audit may retry the same publication.

During shutdown, quiesce-plan publication is attempted before probe-rule cleanup. If that
publication raises, probe-owned NetworkRules cleanup is still attempted in `finally`;
the publisher exception remains visible after cleanup.

A failed quiesce is not recorded as delivered. If the previously published execution plan
is still non-None, a later shutdown/invalidation retries publication of `None` even
though the physical generation has already been cleared.

During steady-state generation invalidation, publication failure may stop the current
Manager operation before a replacement generation is opened. This is deliberate: the
Manager must not silently advance physical generation while the execution Agent may still
hold the preceding plan.

## 7. Audit and shutdown

Audit:

1. renew observed ProbeRules state;
2. if already READY, retain current physical generation;
3. otherwise invalidate the generation;
4. repair desired ProbeRules;
5. open a fresh generation only after READY is re-established;
6. publish changed execution demand.

Shutdown invalidates the generation, quiesces execution and cleans the Manager-owned
NetworkRules state.

## 8. Removed machinery

The Manager no longer contains or publishes:

- `AvailabilityProbeStateInfo`;
- `AvailabilityWindowState`;
- logical window state;
- good-news handlers;
- boundary handlers;
- `evidence_epoch`;
- `elapsed_intervals`;
- routing verdicts.

This is intentional: availability probing is an optional priority modifier, not the
backbone of runtime state.
